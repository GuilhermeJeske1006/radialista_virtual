import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.account import Account
from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig

router = APIRouter(prefix="/metrics", tags=["metrics"])


class InteractionLogResponse(BaseModel):
    id: int
    telefone: str
    mensagem_usuario: str
    resposta: str | None
    status: str
    criado_em: datetime.datetime

    model_config = {"from_attributes": True}


def _buscar_radialista(db: Session, account: Account, radialista_id: int) -> RadioConfig:
    config = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radialista nao encontrado")
    return config


@router.get("/summary")
def resumo(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    config = _buscar_radialista(db, account, radialista_id)

    base = db.query(InteractionLog).filter_by(radio_config_id=config.id)

    total = base.count()

    por_status = dict(
        db.query(InteractionLog.status, func.count(InteractionLog.id))
        .filter(InteractionLog.radio_config_id == config.id)
        .group_by(InteractionLog.status)
        .all()
    )

    agora = datetime.datetime.now(datetime.timezone.utc)
    ultimos_7_dias = base.filter(InteractionLog.criado_em >= agora - datetime.timedelta(days=7)).count()
    ultimos_30_dias = base.filter(InteractionLog.criado_em >= agora - datetime.timedelta(days=30)).count()

    return {
        "total": total,
        "por_status": por_status,
        "ultimos_7_dias": ultimos_7_dias,
        "ultimos_30_dias": ultimos_30_dias,
    }


@router.get("/interactions", response_model=list[InteractionLogResponse])
def interacoes_recentes(
    radialista_id: int,
    limit: int = 30,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    config = _buscar_radialista(db, account, radialista_id)

    limit = max(1, min(limit, 100))

    return (
        db.query(InteractionLog)
        .filter_by(radio_config_id=config.id)
        .order_by(InteractionLog.criado_em.desc())
        .limit(limit)
        .all()
    )
