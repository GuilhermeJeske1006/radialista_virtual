import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.settings import settings
from app.db.database import get_db
from app.models.account import Account
from app.models.radio_config import RadioConfig
from app.whatsapp.session_manager import conectar_sessao, criar_usuario, obter_qrcode, obter_status_sessao

logger = logging.getLogger("radialista.onboarding")
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _buscar_radialista(db: Session, account: Account, radialista_id: int) -> RadioConfig:
    radialista = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
    if radialista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radialista nao encontrado")
    return radialista


@router.post("/{radialista_id}/wuzapi-user")
def criar_usuario_wuzapi(
    radialista_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)
):
    radialista = _buscar_radialista(db, account, radialista_id)
    if radialista.wuzapi_token:
        return {"status": "ja_existe", "wuzapi_token": radialista.wuzapi_token}

    novo_token = secrets.token_hex(16)
    try:
        criar_usuario(
            admin_token=settings.wuzapi_admin_token,
            nome=f"radio-{account.id}-{radialista.id}",
            token=novo_token,
            webhook_url=settings.wuzapi_webhook_url,
        )
    except httpx.HTTPStatusError as exc:
        logger.exception("Falha ao criar usuario no WuzAPI")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao criar usuario no WuzAPI") from exc

    radialista.wuzapi_token = novo_token
    db.commit()

    return {"status": "criado", "wuzapi_token": novo_token}


@router.post("/{radialista_id}/connect")
def conectar(radialista_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    radialista = _buscar_radialista(db, account, radialista_id)
    if not radialista.wuzapi_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crie o usuario WuzAPI antes de conectar")

    try:
        return conectar_sessao(radialista.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao conectar sessao no WuzAPI") from exc


@router.get("/{radialista_id}/qrcode")
def qrcode(radialista_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    radialista = _buscar_radialista(db, account, radialista_id)
    if not radialista.wuzapi_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crie o usuario WuzAPI antes de obter o QR Code")

    try:
        return obter_qrcode(radialista.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao obter QR Code do WuzAPI") from exc


@router.get("/{radialista_id}/status")
def status_sessao(radialista_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    radialista = _buscar_radialista(db, account, radialista_id)
    if not radialista.wuzapi_token:
        return {"connected": False}

    try:
        return obter_status_sessao(radialista.wuzapi_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao obter status da sessao") from exc
