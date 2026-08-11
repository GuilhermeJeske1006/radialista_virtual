import base64
import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger("radialista.whatsapp_sender")


def enviar_mensagem(telefone: str, texto: str, wuzapi_token: str) -> None:
    url = f"{settings.wuzapi_base_url}/chat/send/text"
    headers = {"token": wuzapi_token}
    payload = {"Phone": telefone, "Body": texto}

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()


def enviar_audio(telefone: str, audio_mp3: bytes, wuzapi_token: str) -> None:
    url = f"{settings.wuzapi_base_url}/chat/send/audio"
    headers = {"token": wuzapi_token}
    audio_b64 = base64.b64encode(audio_mp3).decode("ascii")
    payload = {"Phone": telefone, "Audio": f"data:audio/mpeg;base64,{audio_b64}"}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()


def buscar_avatar(telefone: str, wuzapi_token: str) -> str | None:
    """Busca a foto de perfil do contato no WuzAPI. Best-effort: contato pode
    nao ter foto ou ter privacidade restrita, nesses casos devolve None."""
    url = f"{settings.wuzapi_base_url}/user/avatar"
    headers = {"token": wuzapi_token}
    payload = {"Phone": telefone, "Preview": True}

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json().get("URL") or None
    except httpx.HTTPError:
        logger.warning("Falha ao buscar avatar no WuzAPI: telefone=%s", telefone, exc_info=True)
        return None
