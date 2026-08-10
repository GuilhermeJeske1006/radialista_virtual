import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.settings import settings
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip, limite_excedido
from app.models.account import Account
from app.models.voz_clonada import VozClonada
from app.planos import limites_do_plano
from app.tts.client import clonar_voz, excluir_voz_clonada
from app.tts.voices import listar_vozes

logger = logging.getLogger("radialista.tts")

router = APIRouter(prefix="/tts", tags=["tts"])

_TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024
_EXTENSOES_PERMITIDAS = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}


class VozClonadaResponse(BaseModel):
    id: int
    nome: str
    voz_id: str

    model_config = {"from_attributes": True}


@router.get("/voices", dependencies=[Depends(limitar_por_ip("tts_voices", limite=30, janela_segundos=60))])
def vozes():
    return listar_vozes()


@router.get("/vozes-clonadas", response_model=list[VozClonadaResponse])
def listar_vozes_clonadas(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return db.query(VozClonada).filter_by(account_id=account.id).order_by(VozClonada.id.asc()).all()


@router.post("/vozes-clonadas", response_model=VozClonadaResponse, status_code=status.HTTP_201_CREATED)
async def criar_voz_clonada(
    nome: str = Form(...),
    arquivo: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if not limites_do_plano(account.plano).clonagem_voz:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Clonagem de voz disponivel a partir do plano Growth. Faca upgrade em /billing.",
        )
    if limite_excedido(f"clonar_voz:{account.id}", limite=5, janela_segundos=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de clonagens por hora atingido. Tenta de novo daqui a pouco.",
        )

    if not nome.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome obrigatorio")
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS nao configurado")

    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in _EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de audio nao suportado. Use: {', '.join(_EXTENSOES_PERMITIDAS)}",
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de audio vazio")
    if len(conteudo) > _TAMANHO_MAXIMO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo de audio maior que 15MB")

    try:
        voice_id = clonar_voz(
            nome.strip(),
            conteudo,
            _EXTENSOES_PERMITIDAS[extensao],
            arquivo.filename or f"amostra{extensao}",
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("Falha ao clonar voz na ElevenLabs: %s", exc.response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel clonar a voz agora. Verifique se o audio tem qualidade suficiente e tente de novo.",
        ) from exc

    voz_clonada = VozClonada(account_id=account.id, nome=nome.strip(), voz_id=voice_id)
    db.add(voz_clonada)
    db.commit()
    db.refresh(voz_clonada)
    return voz_clonada


@router.delete("/vozes-clonadas/{voz_clonada_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_voz_clonada_endpoint(
    voz_clonada_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    voz_clonada = db.query(VozClonada).filter_by(id=voz_clonada_id, account_id=account.id).first()
    if voz_clonada is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz clonada nao encontrada")

    try:
        excluir_voz_clonada(voz_clonada.voz_id)
    except httpx.HTTPStatusError as exc:
        logger.warning("Falha ao excluir voz na ElevenLabs (%s): %s", voz_clonada.voz_id, exc.response.text)

    db.delete(voz_clonada)
    db.commit()
