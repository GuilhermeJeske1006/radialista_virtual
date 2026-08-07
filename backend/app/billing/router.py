import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.billing.stripe_client import criar_sessao_checkout
from app.config.settings import settings
from app.db.database import get_db
from app.models.account import Account
from app.models.radio_config import RadioConfig

logger = logging.getLogger("radialista.billing")
router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout")
def checkout(account: Account = Depends(get_current_account)):
    sessao = criar_sessao_checkout(account)
    return {"url": sessao.url}


@router.get("/status")
def status_plano(account: Account = Depends(get_current_account)):
    return {"plano_status": account.plano_status}


@router.post("/webhook")
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
            account.plano_status = "ativo"
            account.stripe_customer_id = dados.get("customer")
            account.stripe_subscription_id = dados.get("subscription")
            _definir_ativo(db, account, True)
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
    config = db.query(RadioConfig).filter_by(account_id=account.id).first()
    if config is not None:
        config.ativo = ativo
