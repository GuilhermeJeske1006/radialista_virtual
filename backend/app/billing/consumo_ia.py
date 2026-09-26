"""Ponto único de medição usado pelos adaptadores dos provedores."""
from fastapi import HTTPException
from app.billing.contexto_ia import atual
from app.billing.flex import autorizar, finalizar
from app.config.settings import settings
from app.db.database import SessionLocal


def reservar(tipo, modelo, usd=0, *, unidades_max=None):
    if not settings.ia_medicao_habilitada and not settings.ia_orcamento_bloquear:
        return None
    conta = atual.get()
    if conta and not conta.faturavel:
        return None
    if not conta or conta.id is None:
        raise HTTPException(503, 'Geração sem conta atribuída')
    if unidades_max is None:
        raise HTTPException(503, 'Adaptador sem medição de unidades')
    try:
        with SessionLocal() as db, db.begin():
            return autorizar(db, conta.id, tipo, modelo, unidades_max,
                operacao=conta.operacao, funcionalidade=conta.funcionalidade or tipo,
                chave=f"{conta.operacao}:{conta.proxima_etapa()}", canal=conta.canal, contexto={'programa_id': conta.programa_id})
    except HTTPException as exc:
        conta.recusas.append(exc)
        raise


def concluir(identificador, usd=0, unidades=None, *, entregue=None, request_id=None):
    if identificador is None:
        return
    with SessionLocal() as db, db.begin():
        finalizar(db, identificador, unidades or {}, entregue=entregue,
            request_id=request_id, reserva_fracao=settings.ia_reserva_fracao)


def falhar(identificador, unidades=None):
    concluir(identificador, unidades=unidades, entregue=False)


def microrreais(usd):
    """Somente estimativa interna; nunca usada como base da cobrança."""
    from decimal import Decimal, ROUND_CEILING
    return int((Decimal(str(usd)) * Decimal(str(settings.ia_cambio_brl_usd)) *
        (1 + Decimal(str(settings.ia_reserva_fracao))) * 1000000).quantize(Decimal(1), rounding=ROUND_CEILING))
