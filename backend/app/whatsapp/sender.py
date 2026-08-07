import base64

import httpx

from app.config.settings import settings


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
