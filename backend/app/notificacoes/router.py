import datetime
import math

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_usuario
from app.db.database import get_db
from app.models.notificacao import Notificacao
from app.models.usuario import Usuario

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


class NotificacaoResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    tipo: str
    titulo: str
    mensagem: str
    link: str | None
    lida: bool
    criado_em: datetime.datetime


class NotificacaoPaginadaResponse(BaseModel):
    notificacoes: list[NotificacaoResponse]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class ContagemNaoLidasResponse(BaseModel):
    total: int


@router.get("", response_model=NotificacaoPaginadaResponse)
def listar_notificacoes(
    pagina: int = 1,
    tamanho_pagina: int = 20,
    apenas_nao_lidas: bool = False,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    pagina = max(1, pagina)
    tamanho_pagina = max(1, min(tamanho_pagina, 100))

    base = db.query(Notificacao).filter(Notificacao.usuario_id == usuario.id)
    if apenas_nao_lidas:
        base = base.filter(Notificacao.lida.is_(False))

    total = base.count()
    notificacoes = (
        base.order_by(Notificacao.criado_em.desc())
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
        .all()
    )

    return NotificacaoPaginadaResponse(
        notificacoes=notificacoes,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=max(1, math.ceil(total / tamanho_pagina)),
    )


@router.get("/contagem-nao-lidas", response_model=ContagemNaoLidasResponse)
def contagem_nao_lidas(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)):
    total = (
        db.query(Notificacao)
        .filter(Notificacao.usuario_id == usuario.id, Notificacao.lida.is_(False))
        .count()
    )
    return ContagemNaoLidasResponse(total=total)


@router.post("/{notificacao_id}/marcar-lida", response_model=NotificacaoResponse)
def marcar_lida(
    notificacao_id: int,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    notificacao = db.query(Notificacao).filter_by(id=notificacao_id, usuario_id=usuario.id).first()
    if notificacao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificacao nao encontrada")

    notificacao.lida = True
    db.commit()
    db.refresh(notificacao)
    return notificacao


@router.post("/marcar-todas-lidas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_todas_lidas(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)):
    db.query(Notificacao).filter_by(usuario_id=usuario.id, lida=False).update({"lida": True})
    db.commit()
