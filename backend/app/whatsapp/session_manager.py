"""Funcoes de apoio para provisionar um usuario no WuzAPI (uma vez por radio).

Fluxo (Fase 1/2, manual):
    from app.whatsapp.session_manager import criar_usuario, conectar_sessao, obter_qrcode
    resp = criar_usuario(admin_token="...", nome="radio-teste", token="...", webhook_url="http://.../webhook/whatsapp")
    conectar_sessao(resp["data"]["token"])
    obter_qrcode(resp["data"]["token"])  # escaneie o QR (base64 PNG) com o WhatsApp da radio -- expira rapido
"""

import httpx

from app.config.settings import settings


def criar_usuario(admin_token: str, nome: str, token: str, webhook_url: str) -> dict:
    url = f"{settings.wuzapi_base_url}/admin/users"
    headers = {"Authorization": admin_token}
    payload = {"name": nome, "token": token, "webhook": webhook_url, "events": "Message"}

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def conectar_sessao(user_token: str) -> dict:
    url = f"{settings.wuzapi_base_url}/session/connect"
    headers = {"token": user_token}
    payload = {"Subscribe": ["Message"], "Immediate": True}

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def obter_qrcode(user_token: str) -> dict:
    url = f"{settings.wuzapi_base_url}/session/qr"
    headers = {"token": user_token}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def obter_status_sessao(user_token: str) -> dict:
    url = f"{settings.wuzapi_base_url}/session/status"
    headers = {"token": user_token}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
