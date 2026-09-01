import datetime
import math
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.admin_sistema.dependencies import get_current_super_admin
from app.billing.limites import mensagens_respondidas_no_mes
from app.db.database import get_db
from app.models.account import Account
from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig
from app.models.super_admin import SuperAdmin
from app.models.usuario import Usuario
from app.planos import PLANOS, PRECO_AGENTE_ADICIONAL, PRECO_POR_PLANO

router = APIRouter(prefix="/admin", tags=["admin"])

_PLANO_STATUS_VALIDOS = {"trial", "ativo", "inadimplente", "cancelado"}


class OverviewResponse(BaseModel):
    total_empresas: int
    por_status: dict[str, int]
    por_plano: dict[str, int]
    novas_empresas_30_dias: int
    total_usuarios_ativos: int
    mensagens_30_dias: int
    mrr_planos: int
    mrr_agentes_extras: int


class EmpresaResponse(BaseModel):
    id: int
    nome_radio: str
    email_admin: str | None
    plano: str
    plano_status: str
    criado_em: datetime.datetime
    usuarios_ativos: int
    agentes: int


class EmpresasPaginadasResponse(BaseModel):
    empresas: list[EmpresaResponse]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class UsuarioDaEmpresaResponse(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    ativo: bool


class EmpresaDetalheResponse(EmpresaResponse):
    slogan: str
    frequencia: str
    cidade: str
    tipo_radio: str
    mensagens_mes: int
    usuarios: list[UsuarioDaEmpresaResponse]


class AtualizarEmpresaRequest(BaseModel):
    plano: str | None = None
    plano_status: str | None = None


@router.get("/overview", response_model=OverviewResponse)
def overview(db: Session = Depends(get_db), _admin: SuperAdmin = Depends(get_current_super_admin)):
    agora = datetime.datetime.now(datetime.timezone.utc)

    total_empresas = db.query(Account).count()
    por_status = dict(db.query(Account.plano_status, func.count(Account.id)).group_by(Account.plano_status).all())

    contas_ativas = db.query(Account).filter(Account.plano_status == "ativo").all()
    por_plano = dict(Counter(conta.plano for conta in contas_ativas))

    novas_empresas_30_dias = db.query(Account).filter(Account.criado_em >= agora - datetime.timedelta(days=30)).count()
    total_usuarios_ativos = db.query(Usuario).filter_by(ativo=True).count()
    mensagens_30_dias = (
        db.query(InteractionLog)
        .filter(InteractionLog.origem == "ouvinte", InteractionLog.criado_em >= agora - datetime.timedelta(days=30))
        .count()
    )

    return OverviewResponse(
        total_empresas=total_empresas,
        por_status=por_status,
        por_plano=por_plano,
        novas_empresas_30_dias=novas_empresas_30_dias,
        total_usuarios_ativos=total_usuarios_ativos,
        mensagens_30_dias=mensagens_30_dias,
        mrr_planos=sum(PRECO_POR_PLANO.get(conta.plano, 0) for conta in contas_ativas),
        mrr_agentes_extras=sum(conta.agentes_extras * PRECO_AGENTE_ADICIONAL for conta in contas_ativas),
    )


@router.get("/empresas", response_model=EmpresasPaginadasResponse)
def listar_empresas(
    pagina: int = 1,
    tamanho_pagina: int = 20,
    busca: str | None = None,
    status_filtro: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _admin: SuperAdmin = Depends(get_current_super_admin),
):
    pagina = max(1, pagina)
    tamanho_pagina = max(1, min(tamanho_pagina, 100))

    query = db.query(Account)
    if busca:
        query = query.filter(Account.nome_radio.ilike(f"%{busca}%"))
    if status_filtro:
        query = query.filter(Account.plano_status == status_filtro)

    total = query.count()
    contas = (
        query.order_by(Account.criado_em.desc())
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
        .all()
    )

    ids = [conta.id for conta in contas]
    usuarios_por_conta: dict[int, int] = {}
    agentes_por_conta: dict[int, int] = {}
    if ids:
        usuarios_por_conta = dict(
            db.query(Usuario.account_id, func.count(Usuario.id))
            .filter(Usuario.account_id.in_(ids), Usuario.ativo.is_(True))
            .group_by(Usuario.account_id)
            .all()
        )
        agentes_por_conta = dict(
            db.query(RadioConfig.account_id, func.count(RadioConfig.id))
            .filter(RadioConfig.account_id.in_(ids))
            .group_by(RadioConfig.account_id)
            .all()
        )

    empresas = [
        EmpresaResponse(
            id=conta.id,
            nome_radio=conta.nome_radio,
            email_admin=conta.email,
            plano=conta.plano,
            plano_status=conta.plano_status,
            criado_em=conta.criado_em,
            usuarios_ativos=usuarios_por_conta.get(conta.id, 0),
            agentes=agentes_por_conta.get(conta.id, 0),
        )
        for conta in contas
    ]

    return EmpresasPaginadasResponse(
        empresas=empresas,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=max(1, math.ceil(total / tamanho_pagina)),
    )


def _buscar_empresa(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada")
    return account


def _detalhe_response(db: Session, account: Account) -> EmpresaDetalheResponse:
    usuarios = db.query(Usuario).filter_by(account_id=account.id).order_by(Usuario.criado_em.asc()).all()
    agentes = db.query(RadioConfig).filter_by(account_id=account.id).count()

    return EmpresaDetalheResponse(
        id=account.id,
        nome_radio=account.nome_radio,
        email_admin=account.email,
        plano=account.plano,
        plano_status=account.plano_status,
        criado_em=account.criado_em,
        usuarios_ativos=sum(1 for usuario in usuarios if usuario.ativo),
        agentes=agentes,
        slogan=account.slogan,
        frequencia=account.frequencia,
        cidade=account.cidade,
        tipo_radio=account.tipo_radio,
        mensagens_mes=mensagens_respondidas_no_mes(db, account.id),
        usuarios=[
            UsuarioDaEmpresaResponse(id=u.id, nome=u.nome, email=u.email, role=u.role, ativo=u.ativo)
            for u in usuarios
        ],
    )


@router.get("/empresas/{account_id}", response_model=EmpresaDetalheResponse)
def detalhe_empresa(
    account_id: int,
    db: Session = Depends(get_db),
    _admin: SuperAdmin = Depends(get_current_super_admin),
):
    return _detalhe_response(db, _buscar_empresa(db, account_id))


@router.patch("/empresas/{account_id}", response_model=EmpresaDetalheResponse)
def atualizar_empresa(
    account_id: int,
    dados: AtualizarEmpresaRequest,
    db: Session = Depends(get_db),
    _admin: SuperAdmin = Depends(get_current_super_admin),
):
    account = _buscar_empresa(db, account_id)

    if dados.plano is not None:
        if dados.plano not in PLANOS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plano invalido")
        account.plano = dados.plano

    if dados.plano_status is not None:
        if dados.plano_status not in _PLANO_STATUS_VALIDOS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status invalido")
        account.plano_status = dados.plano_status
        # Espelha o efeito colateral que o webhook do Stripe ja aplica (app/billing/router.py::
        # _definir_ativo) quando o status muda via pagamento -- aqui e' o mesmo efeito, so'
        # disparado manualmente pelo staff em vez de vir do Stripe.
        if dados.plano_status == "ativo":
            db.query(RadioConfig).filter_by(account_id=account.id).update({"ativo": True})
        elif dados.plano_status in ("cancelado", "inadimplente"):
            db.query(RadioConfig).filter_by(account_id=account.id).update({"ativo": False})

    db.commit()
    db.refresh(account)
    return _detalhe_response(db, account)
