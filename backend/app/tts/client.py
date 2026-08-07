import httpx

from app.config.settings import settings

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def tts_habilitado(voice_id: str | None = None) -> bool:
    return bool(settings.elevenlabs_api_key and (voice_id or settings.elevenlabs_voice_id))


def sintetizar_audio(texto: str, voice_id: str | None = None) -> bytes:
    """Gera audio (mp3) a partir de texto via ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = _ELEVENLABS_URL.format(voice_id=voice_id or settings.elevenlabs_voice_id)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.35,
            "similarity_boost": 0.8,
            "style": 0.4,
            "use_speaker_boost": True,
        },
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.content
