import stripe

from app.config.settings import settings
from app.models.account import Account

stripe.api_key = settings.stripe_secret_key


def criar_sessao_checkout(account: Account) -> "stripe.checkout.Session":
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        client_reference_id=str(account.id),
        customer_email=account.email if not account.stripe_customer_id else None,
        customer=account.stripe_customer_id or None,
        success_url=f"{settings.frontend_url}/billing?success=true",
        cancel_url=f"{settings.frontend_url}/billing?canceled=true",
    )


def criar_portal_sessao(account: Account) -> "stripe.billing_portal.Session":
    return stripe.billing_portal.Session.create(
        customer=account.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
