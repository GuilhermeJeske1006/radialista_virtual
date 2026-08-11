import logging
import time
import unicodedata

import httpx

from app.config.settings import settings

logger = logging.getLogger("radialista.tts")

# ElevenLabs 429 (rate limit de conta, comum com varios blocos gerando TTS em
# sequencia rapida no ao vivo) e' quase sempre transitorio -- vale tentar de novo
# antes de desistir e o front cair pra voz generica do navegador.
_TTS_MAX_TENTATIVAS = 3
_TTS_BACKOFF_BASE_SEGUNDOS = 1.5

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices/add"
_ELEVENLABS_VOICE_URL = "https://api.elevenlabs.io/v1/voices/{voice_id}"

# radio e sempre em portugues -- fixa o idioma pro modelo nao tentar detectar sozinho por
# trecho (numero solto e onde a deteccao mais erra, cai pra leitura estilo ingles).
_LANGUAGE_CODE = "pt"

_VOICE_SETTINGS_PADRAO = {
    "stability": 0.35,
    "similarity_boost": 0.8,
    "style": 0.4,
    "use_speaker_boost": True,
    "speed": 1.0,
}

# ajustes de prosodia por tipo de bloco do programa ao vivo (ver _PROSODIA_BLOCO em app.live.router):
# blocos de abertura/musica/chamada pedem mais energia e ritmo mais rapido (menos estabilidade, mais estilo);
# comentario/noticia pedem ritmo mais calmo e estavel.
_VOICE_SETTINGS_POR_TIPO = {
    "abertura": {"stability": 0.28, "style": 0.55, "speed": 1.05},
    "musica": {"stability": 0.28, "style": 0.55, "speed": 1.05},
    "chamada_ouvinte": {"stability": 0.32, "style": 0.5, "speed": 1.03},
    "comentario": {"stability": 0.45, "style": 0.3, "speed": 0.95},
    "noticia": {"stability": 0.5, "style": 0.25, "speed": 0.93},
    "patrocinador": {"stability": 0.4, "style": 0.35, "speed": 1.0},
}

# ajuste fino por cima do tipo de bloco, a partir do tom real da fala gerada (ver
# app.llm.client.classificar_tom_fala) -- o mesmo tipo de bloco pode sair mais ou menos
# intenso dependendo do que o locutor realmente falou naquela vez.
_AJUSTE_TOM = {
    "energico": {"stability": -0.07, "style": 0.1, "speed": 0.04},
    "calmo": {"stability": 0.07, "style": -0.1, "speed": -0.04},
    "neutro": {},
}

# eleven_v3 entende audio tags no proprio texto pra dirigir emocao/entonacao. So faz sentido
# mandar quando o modelo ativo for v3 -- em v2 o tag seria lido literalmente como texto.
_TAG_POR_TOM = {
    "energico": "[excited]",
    "calmo": "[calm]",
}

# similarity_boost/use_speaker_boost nao sao suportados pelo eleven_v3.
_CHAVES_INDISPONIVEIS_V3 = {"similarity_boost", "use_speaker_boost"}


def tts_habilitado(voice_id: str | None = None) -> bool:
    return bool(settings.elevenlabs_api_key and (voice_id or settings.elevenlabs_voice_id))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _categoria_tipo_bloco(tipo_bloco: str) -> str:
    """Reconhece bloco customizado (ex.: 'Musica Vaneira') como variacao do tipo base 'musica'
    pra manter a prosodia certa, mesmo sem bater exatamente com o preset -- ver mesma logica em
    app.live.router._categoria_bloco.
    """
    normalizado = _sem_acento(tipo_bloco.strip().lower())
    for base in _VOICE_SETTINGS_POR_TIPO:
        if normalizado == base or normalizado.startswith(f"{base} ") or normalizado.startswith(f"{base}:"):
            return base
    return normalizado


def _construir_voice_settings(tipo_bloco: str | None, tom: str | None) -> dict:
    categoria = _categoria_tipo_bloco(tipo_bloco) if tipo_bloco else ""
    voice_settings = {**_VOICE_SETTINGS_PADRAO, **_VOICE_SETTINGS_POR_TIPO.get(categoria, {})}
    for chave, delta in _AJUSTE_TOM.get(tom or "", {}).items():
        voice_settings[chave] = voice_settings[chave] + delta

    voice_settings["stability"] = max(0.0, min(1.0, voice_settings["stability"]))
    voice_settings["style"] = max(0.0, min(1.0, voice_settings["style"]))
    voice_settings["speed"] = max(0.7, min(1.2, voice_settings["speed"]))

    if settings.elevenlabs_model != "eleven_v3":
        return voice_settings
    return {k: v for k, v in voice_settings.items() if k not in _CHAVES_INDISPONIVEIS_V3}


def sintetizar_audio(
    texto: str,
    voice_id: str | None = None,
    tipo_bloco: str | None = None,
    tom: str | None = None,
) -> bytes:
    """Gera audio (mp3) a partir de texto via ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = _ELEVENLABS_URL.format(voice_id=voice_id or settings.elevenlabs_voice_id)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    voice_settings = _construir_voice_settings(tipo_bloco, tom)

    texto_tts = texto
    if settings.elevenlabs_model == "eleven_v3":
        tag = _TAG_POR_TOM.get(tom or "")
        if tag:
            texto_tts = f"{tag} {texto}"

    payload = {
        "text": texto_tts,
        "model_id": settings.elevenlabs_model,
        "voice_settings": voice_settings,
        "language_code": _LANGUAGE_CODE,
    }

    with httpx.Client(timeout=30.0) as client:
        for tentativa in range(1, _TTS_MAX_TENTATIVAS + 1):
            response = client.post(url, headers=headers, json=payload)
            if response.status_code != 429 or tentativa == _TTS_MAX_TENTATIVAS:
                if response.status_code >= 400:
                    logger.warning("Falha ao sintetizar audio na ElevenLabs (%s)", response.status_code)
                response.raise_for_status()
                return response.content

            logger.warning("Rate limit da ElevenLabs (429) na tentativa %s/%s", tentativa, _TTS_MAX_TENTATIVAS)
            espera = float(response.headers.get("retry-after", 0)) or _TTS_BACKOFF_BASE_SEGUNDOS * tentativa
            time.sleep(espera)


def clonar_voz(nome: str, audio_bytes: bytes, content_type: str, nome_arquivo: str) -> str:
    """Clona uma voz na ElevenLabs (Instant Voice Cloning) a partir de uma amostra de audio.

    Devolve o voice_id criado. Lanca httpx.HTTPStatusError em falha (ex.: amostra curta demais,
    creditos de clonagem esgotados no plano ElevenLabs).
    """
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    files = {"files": (nome_arquivo, audio_bytes, content_type)}
    data = {"name": nome}

    with httpx.Client(timeout=60.0) as client:
        response = client.post(_ELEVENLABS_VOICES_URL, headers=headers, data=data, files=files)
        response.raise_for_status()
        return response.json()["voice_id"]


def excluir_voz_clonada(voice_id: str) -> None:
    """Remove uma voz clonada na ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = _ELEVENLABS_VOICE_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": settings.elevenlabs_api_key}

    with httpx.Client(timeout=30.0) as client:
        response = client.delete(url, headers=headers)
        response.raise_for_status()
