import logging

import stripe

from app.config.settings import settings
from app.models.account import Account
from app.planos import PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG

logger = logging.getLogger("radialista.stripe")

stripe.api_key = settings.stripe_secret_key


def criar_sessao_checkout(account: Account) -> "stripe.checkout.Session":
    logger.info("Criando sessao de checkout (assinatura): account_id=%s", account.id)
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        client_reference_id=str(account.id),
        customer_email=account.email if not account.stripe_customer_id else None,
        customer=account.stripe_customer_id or None,
        success_url=f"{settings.frontend_url}/billing?success=true",
        cancel_url=f"{settings.frontend_url}/billing?canceled=true",
        metadata={"tipo": "assinatura"},
    )


def criar_sessao_checkout_agente_extra(account: Account) -> "stripe.checkout.Session":
    logger.info("Criando sessao de checkout (agente extra): account_id=%s", account.id)
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": "Agente adicional"},
                    "unit_amount": PRECO_AGENTE_ADICIONAL * 100,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(account.id),
        customer_email=account.email if not account.stripe_customer_id else None,
        customer=account.stripe_customer_id or None,
        success_url=f"{settings.frontend_url}/radialista?agente_extra=true",
        cancel_url=f"{settings.frontend_url}/radialista?agente_extra=cancelado",
        metadata={"tipo": "agente_extra"},
    )


def criar_sessao_checkout_excedente_mensagens(account: Account, blocos: int) -> "stripe.checkout.Session":
    logger.info("Criando sessao de checkout (excedente): account_id=%s blocos=%s", account.id, blocos)
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": "Excedente de mensagens (bloco de 1.000)"},
                    "unit_amount": PRECO_EXCEDENTE_1000_MSG * 100,
                },
                "quantity": blocos,
            }
        ],
        client_reference_id=str(account.id),
        customer_email=account.email if not account.stripe_customer_id else None,
        customer=account.stripe_customer_id or None,
        success_url=f"{settings.frontend_url}/billing?excedente=true",
        cancel_url=f"{settings.frontend_url}/billing?excedente=cancelado",
        metadata={"tipo": "excedente_mensagens", "blocos": str(blocos)},
    )


def criar_portal_sessao(account: Account) -> "stripe.billing_portal.Session":
    logger.info("Criando sessao do portal de billing: account_id=%s", account.id)
    return stripe.billing_portal.Session.create(
        customer=account.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
