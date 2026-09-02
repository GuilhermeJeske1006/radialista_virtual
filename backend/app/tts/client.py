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
#
# stability abaixo de ~0.3 deixa o v3 instavel demais e sai artefato nas terminacoes de frase/palavra
# (a propria ElevenLabs recomenda nao descer disso) -- piso levantado pra 0.34/0.37 depois de reclamacao
# de locucao "com cara de IA" nas terminacoes, mais evidente nos blocos energicos que usavam 0.28/0.32.
_VOICE_SETTINGS_POR_TIPO = {
    "abertura": {"stability": 0.34, "style": 0.55, "speed": 1.05},
    "musica": {"stability": 0.34, "style": 0.55, "speed": 1.05},
    "chamada_ouvinte": {"stability": 0.37, "style": 0.5, "speed": 1.03},
    "comentario": {"stability": 0.45, "style": 0.3, "speed": 0.95},
    "noticia": {"stability": 0.5, "style": 0.25, "speed": 0.93},
    "patrocinador": {"stability": 0.4, "style": 0.35, "speed": 1.0},
}

# ajuste fino por cima do tipo de bloco, a partir do tom real da fala gerada (ver
# app.llm.client.classificar_tom_fala) -- o mesmo tipo de bloco pode sair mais ou menos
# intenso dependendo do que o locutor realmente falou naquela vez.
#
# delta de stability do tom "energico" reduzido (-0.07 -> -0.04): empilhado com o piso ja baixo
# dos blocos energicos, derrubava a stability efetiva perto de 0.3 de novo.
_AJUSTE_TOM = {
    "energico": {"stability": -0.04, "style": 0.1, "speed": 0.04},
    "calmo": {"stability": 0.07, "style": -0.1, "speed": -0.04},
    "neutro": {},
}

# audio tag [excited] do eleven_v3 (so mandado no tom "energico") direciona uma entrega ofegante --
# muita respiracao audivel entre as frases, mais que o [calm] do tom oposto. Tirado ate ter como
# validar por audicao um tag mais neutro; energia do bloco continua vindo so de stability/style/speed.
_TAG_POR_TOM = {
    "calmo": "[calm]",
}

# similarity_boost/use_speaker_boost nao sao suportados pelo eleven_v3.
_CHAVES_INDISPONIVEIS_V3 = {"similarity_boost", "use_speaker_boost"}

# Voz clonada (Instant Voice Cloning, ver clonar_voz) precisa de similarity_boost alto pra soar
# parecida com quem gravou a amostra -- eleven_v3 nao suporta esse parametro (ver
# _CHAVES_INDISPONIVEIS_V3 acima), entao pra voz clonada a sintese cai pro multilingual_v2 (que
# suporta), mesmo com elevenlabs_model=eleven_v3 configurado pro catalogo. Sem isso a voz clonada
# sai com o similarity_boost padrao da ElevenLabs em vez do trinado pra fidelidade, ficando
# perceptivelmente diferente da voz original.
_MODEL_FALLBACK_CLONE = "eleven_multilingual_v2"
_SIMILARITY_BOOST_CLONE = 0.95


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


def _construir_voice_settings(tipo_bloco: str | None, tom: str | None, modelo: str, eh_clonada: bool) -> dict:
    categoria = _categoria_tipo_bloco(tipo_bloco) if tipo_bloco else ""
    voice_settings = {**_VOICE_SETTINGS_PADRAO, **_VOICE_SETTINGS_POR_TIPO.get(categoria, {})}
    for chave, delta in _AJUSTE_TOM.get(tom or "", {}).items():
        voice_settings[chave] = voice_settings[chave] + delta

    voice_settings["stability"] = max(0.0, min(1.0, voice_settings["stability"]))
    voice_settings["style"] = max(0.0, min(1.0, voice_settings["style"]))
    voice_settings["speed"] = max(0.7, min(1.2, voice_settings["speed"]))

    if eh_clonada:
        voice_settings["similarity_boost"] = _SIMILARITY_BOOST_CLONE
        voice_settings["use_speaker_boost"] = True

    if modelo != "eleven_v3":
        return voice_settings
    return {k: v for k, v in voice_settings.items() if k not in _CHAVES_INDISPONIVEIS_V3}


def sintetizar_audio(
    texto: str,
    voice_id: str | None = None,
    tipo_bloco: str | None = None,
    tom: str | None = None,
    eh_clonada: bool = False,
) -> bytes:
    """Gera audio (mp3) a partir de texto via ElevenLabs. Lanca httpx.HTTPStatusError em falha.

    eh_clonada indica se voice_id e' uma voz clonada da conta (app.models.voz_clonada.VozClonada,
    ver app.tts.voices.voz_valida_para_conta) em vez de uma voz do catalogo fixo -- afeta o modelo
    e o similarity_boost usados (ver _MODEL_FALLBACK_CLONE acima).
    """
    url = _ELEVENLABS_URL.format(voice_id=voice_id or settings.elevenlabs_voice_id)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    modelo = settings.elevenlabs_model
    if eh_clonada and modelo == "eleven_v3":
        modelo = _MODEL_FALLBACK_CLONE
    voice_settings = _construir_voice_settings(tipo_bloco, tom, modelo, eh_clonada)

    texto_tts = texto
    if modelo == "eleven_v3":
        tag = _TAG_POR_TOM.get(tom or "")
        if tag:
            texto_tts = f"{tag} {texto}"

    payload = {
        "text": texto_tts,
        "model_id": modelo,
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


def obter_preview_url(voice_id: str) -> str | None:
    """Busca a preview_url (amostra curta pronta, hospedada pela ElevenLabs) de uma voz.

    Devolve None se a API nao estiver configurada ou a chamada falhar -- o catalogo de
    vozes cai pra lista sem audio de amostra nesse caso, sem quebrar a pagina.
    """
    if not settings.elevenlabs_api_key:
        return None

    url = _ELEVENLABS_VOICE_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("preview_url")
    except httpx.HTTPError:
        logger.warning("Falha ao buscar preview_url da voz %s", voice_id)
        return None


def renomear_voz(voice_id: str, nome: str) -> None:
    """Atualiza o nome de uma voz clonada na ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = f"{_ELEVENLABS_VOICE_URL.format(voice_id=voice_id)}/edit"
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    data = {"name": nome}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, data=data)
        response.raise_for_status()


def excluir_voz_clonada(voice_id: str) -> None:
    """Remove uma voz clonada na ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = _ELEVENLABS_VOICE_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": settings.elevenlabs_api_key}

    with httpx.Client(timeout=30.0) as client:
        response = client.delete(url, headers=headers)
        response.raise_for_status()
