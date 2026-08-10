import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.billing.limites import (
    limite_agentes_efetivo,
    limite_mensagens_efetivo,
    mensagens_extras_do_mes,
    mensagens_respondidas_no_mes,
    mes_referencia_atual,
)
from app.billing.stripe_client import (
    criar_sessao_checkout,
    criar_sessao_checkout_agente_extra,
    criar_sessao_checkout_excedente_mensagens,
)
from app.config.settings import settings
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip
from app.models.account import Account
from app.models.compra_excedente import CompraExcedente
from app.models.radio_config import RadioConfig

logger = logging.getLogger("radialista.billing")
router = APIRouter(prefix="/billing", tags=["billing"])


class ExcedenteMensagensRequest(BaseModel):
    blocos: int = Field(default=1, ge=1, le=50)


def _exigir_plano_ativo(account: Account) -> None:
    if account.plano_status != "ativo":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Assine um plano antes de comprar itens avulsos.",
        )


@router.post("/checkout")
def checkout(account: Account = Depends(get_current_account)):
    sessao = criar_sessao_checkout(account)
    return {"url": sessao.url}


@router.post("/agentes-extras/checkout")
def checkout_agente_extra(account: Account = Depends(get_current_account)):
    _exigir_plano_ativo(account)
    sessao = criar_sessao_checkout_agente_extra(account)
    return {"url": sessao.url}


@router.post("/excedente-mensagens/checkout")
def checkout_excedente_mensagens(
    dados: ExcedenteMensagensRequest, account: Account = Depends(get_current_account)
):
    _exigir_plano_ativo(account)
    sessao = criar_sessao_checkout_excedente_mensagens(account, dados.blocos)
    return {"url": sessao.url}


@router.get("/status")
def status_plano(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    agentes_usados = db.query(RadioConfig).filter_by(account_id=account.id).count()
    mensagens_usadas = mensagens_respondidas_no_mes(db, account.id)

    return {
        "plano_status": account.plano_status,
        "plano": account.plano,
        "agentes_usados": agentes_usados,
        "agentes_limite": limite_agentes_efetivo(account),
        "agentes_extras": account.agentes_extras,
        "mensagens_usadas": mensagens_usadas,
        "mensagens_limite": limite_mensagens_efetivo(db, account),
        "mensagens_extras": mensagens_extras_do_mes(db, account.id),
    }


@router.post(
    "/webhook",
    dependencies=[Depends(limitar_por_ip("billing_webhook", limite=120, janela_segundos=60))],
)
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    assinatura = request.headers.get("stripe-signature", "")

    try:
        evento = stripe.Webhook.construct_event(payload, assinatura, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload invalido") from exc

    tipo = evento["type"]
    dados = evento["data"]["object"]

    if tipo == "checkout.session.completed":
        account = db.get(Account, int(dados["client_reference_id"]))
        if account is not None:
            tipo_compra = dados.get("metadata", {}).get("tipo", "assinatura")

            if tipo_compra == "assinatura":
                account.plano_status = "ativo"
                account.stripe_customer_id = dados.get("customer")
                account.stripe_subscription_id = dados.get("subscription")
                _definir_ativo(db, account, True)
            elif tipo_compra == "agente_extra":
                account.agentes_extras += 1
                account.stripe_customer_id = dados.get("customer") or account.stripe_customer_id
            elif tipo_compra == "excedente_mensagens":
                blocos = int(dados.get("metadata", {}).get("blocos", "1"))
                db.add(
                    CompraExcedente(
                        account_id=account.id,
                        quantidade=blocos * 1000,
                        mes_referencia=mes_referencia_atual(),
                    )
                )
                account.stripe_customer_id = dados.get("customer") or account.stripe_customer_id

            db.commit()

    elif tipo in ("customer.subscription.deleted", "customer.subscription.updated"):
        if tipo == "customer.subscription.updated" and dados.get("status") not in ("canceled", "unpaid"):
            return {"status": "ignorado"}

        account = db.query(Account).filter_by(stripe_customer_id=dados.get("customer")).first()
        if account is not None:
            account.plano_status = "cancelado"
            _definir_ativo(db, account, False)
            db.commit()

    return {"status": "ok"}


def _definir_ativo(db: Session, account: Account, ativo: bool) -> None:
    db.query(RadioConfig).filter_by(account_id=account.id).update({"ativo": ativo})
