"""API da 'Pauta do dia' (ver Fase H do plano-assuntos.md): da' ao cliente visibilidade e
controle editorial sobre os assuntos que o pipeline (ver app.topics.pipeline) casou pro
programa dele -- fixar sobe a prioridade, descartar tira da pauta. So' LE/escreve
AssuntoPrograma, nunca deriva nem casa nada aqui (isso e' sempre offline, ver app.topics.matcher).
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.router import _buscar_programa
from app.db.database import get_db
from app.models.account import Account
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma

router = APIRouter(prefix="/topics", tags=["topics"])

# Quanto "fixar" (ver Fase H) soma ao score -- alto o bastante pra vencer qualquer concorrente
# normal (score do matcher vai de 0 a 10, ver app.topics.matcher) sem precisar de uma coluna
# "fixado" separada (mais schema, mesmo resultado pratico: sempre no topo da escolha).
_BONUS_FIXAR = 100.0


class AssuntoPautaResponse(BaseModel):
    id: int  # id do AssuntoPrograma (casamento) -- usado pra fixar/descartar.
    assunto_id: int
    titulo: str
    gancho: str
    fatos: list[str]
    tags: list[str]
    origem: str
    score: float
    ponte: str
    eixos_sugeridos: list[str]
    validade_ate: datetime.datetime | None

    model_config = {"from_attributes": True}


def _buscar_assunto_programa(db: Session, account: Account, programa_id: int, assunto_programa_id: int) -> AssuntoPrograma:
    programa = _buscar_programa(db, account, programa_id)
    ap = db.query(AssuntoPrograma).filter_by(id=assunto_programa_id, programa_id=programa.id).first()
    if ap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assunto nao encontrado pra este programa")
    return ap


@router.get("/programas/{programa_id}/pauta", response_model=list[AssuntoPautaResponse])
def listar_pauta_do_dia(
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    agora = datetime.datetime.now(datetime.timezone.utc)
    linhas = (
        db.query(AssuntoPrograma, Assunto)
        .join(Assunto, Assunto.id == AssuntoPrograma.assunto_id)
        .filter(
            AssuntoPrograma.programa_id == programa.id,
            (Assunto.validade_ate.is_(None)) | (Assunto.validade_ate > agora),
        )
        .order_by(AssuntoPrograma.score.desc())
        .all()
    )
    return [
        AssuntoPautaResponse(
            id=ap.id, assunto_id=assunto.id, titulo=assunto.titulo, gancho=assunto.gancho,
            fatos=assunto.fatos or [], tags=assunto.tags or [], origem=assunto.origem,
            score=ap.score, ponte=ap.ponte, eixos_sugeridos=ap.eixos_sugeridos or [],
            validade_ate=assunto.validade_ate,
        )
        for ap, assunto in linhas
    ]


@router.post("/programas/{programa_id}/pauta/{assunto_programa_id}/fixar", response_model=AssuntoPautaResponse)
def fixar_assunto(
    programa_id: int,
    assunto_programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    ap = _buscar_assunto_programa(db, account, programa_id, assunto_programa_id)
    ap.score += _BONUS_FIXAR
    db.commit()
    db.refresh(ap)
    assunto = db.get(Assunto, ap.assunto_id)
    return AssuntoPautaResponse(
        id=ap.id, assunto_id=assunto.id, titulo=assunto.titulo, gancho=assunto.gancho,
        fatos=assunto.fatos or [], tags=assunto.tags or [], origem=assunto.origem,
        score=ap.score, ponte=ap.ponte, eixos_sugeridos=ap.eixos_sugeridos or [],
        validade_ate=assunto.validade_ate,
    )


@router.delete("/programas/{programa_id}/pauta/{assunto_programa_id}", status_code=status.HTTP_204_NO_CONTENT)
def descartar_assunto(
    programa_id: int,
    assunto_programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Remove so' o CASAMENTO com este programa (ver AssuntoPrograma) -- o gancho em si (Assunto)
    continua podendo servir outro programa da mesma conta, se tiver sido casado com ele tambem."""
    ap = _buscar_assunto_programa(db, account, programa_id, assunto_programa_id)
    db.delete(ap)
    db.commit()
