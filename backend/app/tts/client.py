import httpx

from app.config.settings import settings

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

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
}


def tts_habilitado(voice_id: str | None = None) -> bool:
    return bool(settings.elevenlabs_api_key and (voice_id or settings.elevenlabs_voice_id))


def sintetizar_audio(texto: str, voice_id: str | None = None, tipo_bloco: str | None = None) -> bytes:
    """Gera audio (mp3) a partir de texto via ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = _ELEVENLABS_URL.format(voice_id=voice_id or settings.elevenlabs_voice_id)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    voice_settings = {**_VOICE_SETTINGS_PADRAO, **_VOICE_SETTINGS_POR_TIPO.get(tipo_bloco or "", {})}
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": voice_settings,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.content
