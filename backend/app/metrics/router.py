import datetime
import math

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.account import Account
from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig
from app.whatsapp.sender import buscar_avatar

router = APIRouter(prefix="/metrics", tags=["metrics"])


class InteractionLogResponse(BaseModel):
    id: int
    telefone: str
    mensagem_usuario: str
    resposta: str | None
    status: str
    criado_em: datetime.datetime

    model_config = {"from_attributes": True}


class InteractionLogContaResponse(InteractionLogResponse):
    radialista_nome: str
    nome: str | None = None
    origem: str


class ConversaResponse(BaseModel):
    telefone: str
    nome: str | None
    radialista_nome: str
    ultima_mensagem: str
    ultimo_status: str
    ultima_em: datetime.datetime
    total_mensagens: int


class AvatarResponse(BaseModel):
    url: str | None


class ConversasPaginadasResponse(BaseModel):
    conversas: list[ConversaResponse]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class MensagensPaginadasResponse(BaseModel):
    mensagens: list[InteractionLogContaResponse]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


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


@router.get("/conversations", response_model=ConversasPaginadasResponse)
def listar_conversas(
    pagina: int = 1,
    tamanho_pagina: int = 20,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Uma "conversa" = todas as mensagens de um mesmo telefone, de qualquer
    radialista da conta (todos compartilham o mesmo numero de WhatsApp).
    Paginado por conversa, mais recente primeiro -- igual a lista de chats do WhatsApp."""
    pagina = max(1, pagina)
    tamanho_pagina = max(1, min(tamanho_pagina, 100))

    resumo_por_telefone = (
        db.query(
            InteractionLog.telefone.label("telefone"),
            func.max(InteractionLog.criado_em).label("ultima_em"),
            func.count(InteractionLog.id).label("total_mensagens"),
        )
        .join(RadioConfig, InteractionLog.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account.id)
        .group_by(InteractionLog.telefone)
        .subquery()
    )

    total = db.query(func.count()).select_from(resumo_por_telefone).scalar()

    pagina_de_resumos = (
        db.query(resumo_por_telefone)
        .order_by(resumo_por_telefone.c.ultima_em.desc())
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
        .all()
    )
    telefones_da_pagina = [linha.telefone for linha in pagina_de_resumos]

    ultima_mensagem_por_telefone = {}
    if telefones_da_pagina:
        ultimas = (
            db.query(InteractionLog, RadioConfig.nome_locutor)
            .join(RadioConfig, InteractionLog.radio_config_id == RadioConfig.id)
            .filter(RadioConfig.account_id == account.id, InteractionLog.telefone.in_(telefones_da_pagina))
            .order_by(InteractionLog.telefone, InteractionLog.criado_em.desc())
            .distinct(InteractionLog.telefone)
            .all()
        )
        ultima_mensagem_por_telefone = {log.telefone: (log, nome) for log, nome in ultimas}

    # O nome (PushName) so' vem preenchido em mensagens do ouvinte -- pega o mais
    # recente entre essas, mesmo que a ultima mensagem da conversa tenha sido da radio.
    nomes_por_telefone: dict[str, str] = {}
    if telefones_da_pagina:
        linhas_nome = (
            db.query(InteractionLog.telefone, InteractionLog.nome)
            .join(RadioConfig, InteractionLog.radio_config_id == RadioConfig.id)
            .filter(
                RadioConfig.account_id == account.id,
                InteractionLog.telefone.in_(telefones_da_pagina),
                InteractionLog.nome.isnot(None),
            )
            .order_by(InteractionLog.telefone, InteractionLog.criado_em.desc())
            .distinct(InteractionLog.telefone)
            .all()
        )
        nomes_por_telefone = dict(linhas_nome)

    conversas = [
        ConversaResponse(
            telefone=linha.telefone,
            nome=nomes_por_telefone.get(linha.telefone),
            radialista_nome=ultima_mensagem_por_telefone[linha.telefone][1],
            ultima_mensagem=ultima_mensagem_por_telefone[linha.telefone][0].mensagem_usuario,
            ultimo_status=ultima_mensagem_por_telefone[linha.telefone][0].status,
            ultima_em=linha.ultima_em,
            total_mensagens=linha.total_mensagens,
        )
        for linha in pagina_de_resumos
    ]

    return ConversasPaginadasResponse(
        conversas=conversas,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=max(1, math.ceil(total / tamanho_pagina)),
    )


@router.get("/conversations/{telefone}/messages", response_model=MensagensPaginadasResponse)
def mensagens_da_conversa(
    telefone: str,
    pagina: int = 1,
    tamanho_pagina: int = 20,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Mensagens de uma conversa, paginadas do jeito que o WhatsApp carrega o
    historico: pagina 1 = mensagens mais recentes, paginas seguintes = mais antigas.
    Cada pagina volta em ordem cronologica (mais antiga primeiro) pra render direto."""
    pagina = max(1, pagina)
    tamanho_pagina = max(1, min(tamanho_pagina, 100))

    base = (
        db.query(InteractionLog, RadioConfig.nome_locutor)
        .join(RadioConfig, InteractionLog.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account.id, InteractionLog.telefone == telefone)
    )

    total = base.count()

    linhas = (
        base.order_by(InteractionLog.criado_em.desc())
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
        .all()
    )

    mensagens = [
        InteractionLogContaResponse(
            id=log.id,
            telefone=log.telefone,
            nome=log.nome,
            mensagem_usuario=log.mensagem_usuario,
            resposta=log.resposta,
            status=log.status,
            criado_em=log.criado_em,
            radialista_nome=nome_radialista,
            origem=log.origem,
        )
        for log, nome_radialista in reversed(linhas)
    ]

    return MensagensPaginadasResponse(
        mensagens=mensagens,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=max(1, math.ceil(total / tamanho_pagina)),
    )


@router.get("/conversations/{telefone}/avatar", response_model=AvatarResponse)
def avatar_da_conversa(
    telefone: str,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Tenta buscar a foto de perfil do contato no WuzAPI. Best-effort -- se a
    conta nao tiver WhatsApp conectado ou o contato nao tiver foto, devolve url=None."""
    if not account.wuzapi_token:
        return AvatarResponse(url=None)

    return AvatarResponse(url=buscar_avatar(telefone, account.wuzapi_token))
