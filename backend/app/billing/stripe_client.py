import logging

import stripe
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.account import Account
from app.planos import PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG

logger = logging.getLogger("radialista.stripe")

stripe.api_key = settings.stripe_secret_key

# Um price recorrente por plano -- mantido aqui (nao em app/planos.py) porque e' o unico
# lugar que fala com o Stripe; o resto do app so conhece o id do plano ("starter" etc).
PRICE_ID_POR_PLANO = {
    "starter": settings.stripe_price_id_starter,
    "growth": settings.stripe_price_id_growth,
    "professional": settings.stripe_price_id_professional,
}
PLANO_POR_PRICE_ID = {v: k for k, v in PRICE_ID_POR_PLANO.items() if v}


def plano_por_price_id(price_id: str | None) -> str | None:
    return PLANO_POR_PRICE_ID.get(price_id) if price_id else None


def _obter_ou_criar_customer(account: Account, db: Session) -> str:
    if account.stripe_customer_id:
        return account.stripe_customer_id
    customer = stripe.Customer.create(email=account.email, metadata={"account_id": str(account.id)})
    account.stripe_customer_id = customer.id
    db.commit()
    return customer.id


# Subscription.create (diferente de Checkout Session) nao aceita price_data.product_data
# pra criar produto na hora -- so' referencia um Product que ja existe. Id fixo (nao um
# id gerado pelo Stripe) pra poder so' tentar buscar antes de criar, sem precisar guardar
# esse id em lugar nenhum (nem settings, nem banco).
_PRODUTO_AGENTE_EXTRA_ID = "locufy-agente-adicional"


def _obter_ou_criar_produto_agente_extra() -> str:
    try:
        stripe.Product.retrieve(_PRODUTO_AGENTE_EXTRA_ID)
    except stripe.error.InvalidRequestError:
        stripe.Product.create(id=_PRODUTO_AGENTE_EXTRA_ID, name="Agente adicional")
    return _PRODUTO_AGENTE_EXTRA_ID


def criar_sessao_checkout(account: Account, plano_id: str, db: Session) -> "stripe.Subscription":
    # Subscription direto via API (payment_behavior=default_incomplete) em vez de Checkout
    # Session -- o client_secret do PaymentIntent da primeira invoice alimenta um
    # <PaymentElement> nosso, checkout transparente de verdade (nao o widget pronto do
    # Stripe). Fica "incomplete" ate o frontend confirmar o pagamento; so' vira "active"
    # (e a conta e' ativada) quando o webhook invoice.paid chegar.
    logger.info("Criando assinatura pendente: account_id=%s plano=%s", account.id, plano_id)
    customer_id = _obter_ou_criar_customer(account, db)
    return stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": PRICE_ID_POR_PLANO[plano_id]}],
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription", "payment_method_types": ["card"]},
        expand=["latest_invoice.payment_intent"],
        metadata={"tipo": "assinatura", "plano": plano_id, "account_id": str(account.id)},
    )


def trocar_plano_assinatura(account: Account, plano_id: str) -> None:
    logger.info("Trocando plano da assinatura: account_id=%s plano_novo=%s", account.id, plano_id)
    assinatura = stripe.Subscription.retrieve(account.stripe_subscription_id)
    item_id = assinatura["items"]["data"][0]["id"]
    stripe.Subscription.modify(
        account.stripe_subscription_id,
        items=[{"id": item_id, "price": PRICE_ID_POR_PLANO[plano_id]}],
        proration_behavior="create_prorations",
    )


def criar_sessao_checkout_agente_extra(account: Account, db: Session) -> "stripe.Subscription":
    logger.info("Criando assinatura pendente (agente extra): account_id=%s", account.id)
    customer_id = _obter_ou_criar_customer(account, db)
    return stripe.Subscription.create(
        customer=customer_id,
        items=[
            {
                "price_data": {
                    "currency": "brl",
                    "product": _obter_ou_criar_produto_agente_extra(),
                    "unit_amount": PRECO_AGENTE_ADICIONAL * 100,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }
        ],
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription", "payment_method_types": ["card"]},
        expand=["latest_invoice.payment_intent"],
        metadata={"tipo": "agente_extra", "account_id": str(account.id)},
    )


def criar_sessao_checkout_excedente_mensagens(account: Account, blocos: int, db: Session) -> "stripe.PaymentIntent":
    # Compra avulsa (nao recorrente) -- PaymentIntent direto, sem Subscription.
    logger.info("Criando payment intent (excedente): account_id=%s blocos=%s", account.id, blocos)
    customer_id = _obter_ou_criar_customer(account, db)
    return stripe.PaymentIntent.create(
        amount=PRECO_EXCEDENTE_1000_MSG * 100 * blocos,
        currency="brl",
        customer=customer_id,
        payment_method_types=["card"],
        metadata={"tipo": "excedente_mensagens", "blocos": str(blocos), "account_id": str(account.id)},
    )


def criar_portal_sessao(account: Account) -> "stripe.billing_portal.Session":
    logger.info("Criando sessao do portal de billing: account_id=%s", account.id)
    return stripe.billing_portal.Session.create(
        customer=account.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
