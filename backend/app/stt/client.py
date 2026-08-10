import base64

import httpx

from app.config.settings import settings

_ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def stt_habilitado() -> bool:
    return bool(settings.elevenlabs_api_key)


def transcrever_audio(audio_base64: str, mime_type: str = "audio/ogg") -> str:
    """Transcreve audio (base64, ja decriptado pelo WuzAPI) via ElevenLabs Speech-to-Text.

    Lanca httpx.HTTPStatusError em falha -- quem chama decide o fallback (webhook
    trata como transcricao vazia e so registra o log, sem travar o resto do fluxo).
    """
    audio_bytes = base64.b64decode(audio_base64)
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    files = {"file": ("audio.ogg", audio_bytes, mime_type)}
    data = {"model_id": "scribe_v1"}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(_ELEVENLABS_STT_URL, headers=headers, files=files, data=data)
        response.raise_for_status()
        return str(response.json().get("text") or "").strip()
