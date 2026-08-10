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


def configurar_entrega_midia(user_token: str) -> dict:
    """Configura o WuzAPI pra mandar midia recebida (audio, imagem, etc) ja decriptada
    em base64 dentro do proprio payload do webhook -- sem isso o webhook so' recebe
    metadados criptografados, inuteis pra transcricao (ver app/whatsapp/webhook.py e
    app/stt/client.py). Idempotente: seguro chamar de novo em toda conexao."""
    url = f"{settings.wuzapi_base_url}/session/s3/config"
    headers = {"token": user_token}
    payload = {"enabled": False, "media_delivery": "base64"}

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def configurar_hmac(user_token: str, hmac_key: str) -> dict:
    """Configura a chave HMAC que o WuzAPI usa pra assinar (header x-hmac-signature,
    HMAC-SHA256 do corpo cru) todo webhook desse usuario. E' a unica forma de autenticar
    de verdade quem chama /webhook/whatsapp -- o payload so' carrega o "userID" (id
    sequencial do WuzAPI, nao secreto), entao sem assinatura qualquer um podia forjar
    mensagens em nome de outra conta (ver app/whatsapp/webhook.py::_verificar_assinatura)."""
    url = f"{settings.wuzapi_base_url}/session/hmac/config"
    headers = {"token": user_token}
    payload = {"hmac_key": hmac_key}

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


def desconectar_sessao(user_token: str) -> dict:
    """Desloga do WhatsApp (invalida a sessao no WuzAPI) -- reconectar depois exige
    escanear um novo QR Code. Diferente de so' derrubar o websocket: aqui o numero
    fica desvinculado ate o usuario conectar de novo."""
    url = f"{settings.wuzapi_base_url}/session/logout"
    headers = {"token": user_token}

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=headers)
        response.raise_for_status()
        return response.json()


def obter_status_sessao(user_token: str) -> dict:
    url = f"{settings.wuzapi_base_url}/session/status"
    headers = {"token": user_token}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
