import stripe
from fastapi import HTTPException
from app.config.settings import settings


def cliente():
    return stripe.StripeClient(settings.stripe_secret_key, stripe_version='2026-08-26.dahlia')


def plano_por_price_id(price_id):
    return 'flex' if price_id and price_id == settings.stripe_price_id_flex else None


class CartaoSalvoNaoEncontrado(Exception):
    pass


def _obter_ou_criar_customer(account, db):
    if not account.stripe_customer_id:
        c = cliente().v1.customers.create({'email': account.email, 'metadata': {'account_id': str(account.id)}},
            options={'idempotency_key': f'customer:{account.id}'})
        account.stripe_customer_id = c.id
        db.commit()
    return account.stripe_customer_id


def criar_sessao_checkout(account, plano_id, db, usar_cartao_salvo=False):
    if plano_id != 'flex' or not settings.stripe_price_id_flex:
        raise HTTPException(503, 'Preço Locufy Flex ainda não configurado')
    c = cliente()
    price = c.v1.prices.retrieve(settings.stripe_price_id_flex)
    if price.currency != 'brl' or price.unit_amount != 6990 or price.recurring.interval != 'month' or price.recurring.interval_count != 1:
        raise HTTPException(503, 'Preço Stripe incompatível com Locufy Flex')
    customer = _obter_ou_criar_customer(account, db)
    if account.stripe_subscription_id:
        subscription = c.v1.subscriptions.retrieve(account.stripe_subscription_id,
            {'expand': ['latest_invoice.confirmation_secret']})
        if subscription.status in ('incomplete', 'active', 'past_due', 'unpaid'):
            return subscription
    params = {'customer': customer, 'items': [{'price': settings.stripe_price_id_flex}],
        'payment_behavior': 'default_incomplete',
        'payment_settings': {'save_default_payment_method': 'on_subscription'},
        'expand': ['latest_invoice.confirmation_secret'],
        'metadata': {'tipo': 'assinatura', 'plano': 'flex', 'account_id': str(account.id)}}
    if usar_cartao_salvo:
        cards = c.v1.payment_methods.list({'customer': customer, 'type': 'card', 'limit': 1})
        if not cards.data:
            raise CartaoSalvoNaoEncontrado()
        params['default_payment_method'] = cards.data[0].id
    sub = c.v1.subscriptions.create(params, options={'idempotency_key': f'flex:{account.id}:{account.stripe_subscription_id or "primeira"}'})
    account.stripe_subscription_id = sub.id
    db.commit()
    return sub


def obter_cartao_mais_recente(account):
    if not account.stripe_customer_id:
        return None
    cards = cliente().v1.payment_methods.list({'customer': account.stripe_customer_id, 'type': 'card', 'limit': 1})
    if not cards.data:
        return None
    card = cards.data[0].card
    return {'bandeira': card.brand, 'final': card.last4, 'mes_expiracao': card.exp_month, 'ano_expiracao': card.exp_year}


def criar_portal_sessao(account):
    return cliente().v1.billing_portal.sessions.create({'customer': account.stripe_customer_id,
        'return_url': f'{settings.frontend_url}/billing'})


def dados_stripe(obj):
    # SDK 15 deixou de implementar o protocolo Mapping nos recursos.
    return obj.to_dict() if isinstance(obj, stripe.StripeObject) else obj
