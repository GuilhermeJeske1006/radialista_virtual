import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.auth.email import enviar_email_boas_vindas
from app.config.settings import settings
from app.db.database import get_db
from app.models.account import Account
from app.whatsapp.session_manager import (
    conectar_sessao,
    configurar_entrega_midia,
    configurar_hmac,
    criar_usuario,
    desconectar_sessao,
    obter_qrcode,
    obter_status_sessao,
)

logger = logging.getLogger("radialista.onboarding")
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/wuzapi-user")
def criar_usuario_wuzapi(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    if account.wuzapi_token:
        return {"status": "ja_existe", "wuzapi_token": account.wuzapi_token}

    novo_token = secrets.token_hex(16)
    try:
        resp = criar_usuario(
            admin_token=settings.wuzapi_admin_token,
            nome=f"radio-{account.id}",
            token=novo_token,
            webhook_url=settings.wuzapi_webhook_url,
        )
    except httpx.HTTPStatusError as exc:
        logger.exception("Falha ao criar usuario no WuzAPI")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao criar usuario no WuzAPI") from exc

    account.wuzapi_token = novo_token
    # O webhook do WuzAPI manda "userID" no corpo, nunca o "token" -- precisa
    # desse id pra casar a mensagem recebida com a conta certa.
    account.wuzapi_user_id = (resp.get("data") or {}).get("id")
    db.commit()

    try:
        configurar_entrega_midia(novo_token)
    except httpx.HTTPStatusError:
        # Best-effort: sem isso so' perde a transcricao de audio (webhook.py ignora
        # audio sem base64), nao trava o resto do onboarding.
        logger.exception("Falha ao configurar entrega de midia no WuzAPI")

    try:
        hmac_key = secrets.token_hex(32)
        configurar_hmac(novo_token, hmac_key)
        account.wuzapi_hmac_key = hmac_key
        db.commit()
    except httpx.HTTPStatusError:
        # Best-effort: sem isso o webhook aceita mensagens dessa conta sem verificar
        # assinatura (ver app/whatsapp/webhook.py::_verificar_assinatura) -- pior que
        # travar o onboarding inteiro por uma falha transitoria no WuzAPI.
        logger.exception("Falha ao configurar HMAC no WuzAPI")

    return {"status": "criado", "wuzapi_token": novo_token}


@router.post("/connect")
def conectar(account: Account = Depends(get_current_account)):
    if not account.wuzapi_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crie o usuario WuzAPI antes de conectar")

    try:
        # Self-heal pra contas criadas antes dessa configuracao existir -- idempotente.
        configurar_entrega_midia(account.wuzapi_token)
    except httpx.HTTPStatusError:
        logger.exception("Falha ao configurar entrega de midia no WuzAPI")

    try:
        return conectar_sessao(account.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao conectar sessao no WuzAPI") from exc


@router.get("/qrcode")
def qrcode(account: Account = Depends(get_current_account)):
    if not account.wuzapi_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crie o usuario WuzAPI antes de obter o QR Code")

    try:
        return obter_qrcode(account.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao obter QR Code do WuzAPI") from exc


@router.post("/logout")
def desconectar(account: Account = Depends(get_current_account)):
    if not account.wuzapi_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WhatsApp nao conectado")

    try:
        return desconectar_sessao(account.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao desconectar do WuzAPI") from exc


@router.get("/status")
def status_sessao(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    if not account.wuzapi_token:
        return {"connected": False}

    try:
        resultado = obter_status_sessao(account.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao obter status da sessao") from exc

    logado = (resultado.get("data") or {}).get("loggedIn", False)
    if logado and not account.onboarding_email_enviado:
        admin = next((u for u in account.usuarios if u.role == "admin" and u.ativo), None)
        if admin is not None:
            enviar_email_boas_vindas(admin.email, admin.nome)
        account.onboarding_email_enviado = True
        db.commit()

    return resultado
