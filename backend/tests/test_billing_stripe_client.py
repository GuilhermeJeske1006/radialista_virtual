from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app.billing import stripe_client as sc
from app.config.settings import settings


@pytest.fixture
def stripe_api(monkeypatch):
    c = MagicMock()
    monkeypatch.setattr(sc, 'cliente', lambda: c)
    monkeypatch.setattr(settings, 'stripe_price_id_flex', 'price_flex')
    c.v1.prices.retrieve.return_value = SimpleNamespace(currency='brl',unit_amount=6990,
        recurring=SimpleNamespace(interval='month',interval_count=1))
    c.v1.customers.create.return_value = SimpleNamespace(id='cus_new')
    c.v1.subscriptions.create.return_value = SimpleNamespace(id='sub_new')
    return c


def test_customer_idempotente(db_session, account, stripe_api):
    assert sc._obter_ou_criar_customer(account, db_session) == 'cus_new'
    assert sc._obter_ou_criar_customer(account, db_session) == 'cus_new'
    assert stripe_api.v1.customers.create.call_count == 1
    assert stripe_api.v1.customers.create.call_args.kwargs['options']['idempotency_key'] == f'customer:{account.id}'


def test_checkout_primeira_mensalidade(db_session, account, stripe_api):
    sub = sc.criar_sessao_checkout(account, 'flex', db_session)
    assert account.stripe_subscription_id == sub.id
    params = stripe_api.v1.subscriptions.create.call_args.args[0]
    assert params['items'] == [{'price':'price_flex'}]
    assert params['metadata']['account_id'] == str(account.id)
    assert params['metadata']['plano'] == 'flex'
    assert params['payment_behavior'] == 'default_incomplete'
    assert 'payment_method_types' not in params['payment_settings']
    assert params['expand'] == ['latest_invoice.confirmation_secret']


def test_checkout_reusa_assinatura_incompleta(db_session, account, stripe_api):
    account.stripe_subscription_id = 'sub_pending'
    stripe_api.v1.subscriptions.retrieve.return_value = SimpleNamespace(id='sub_pending',status='incomplete')
    assert sc.criar_sessao_checkout(account,'flex',db_session).id == 'sub_pending'
    stripe_api.v1.subscriptions.create.assert_not_called()


@pytest.mark.parametrize('amount,currency', [(699,'brl'),(6990,'usd')])
def test_preco_configurado_incorreto_bloqueia(db_session, account, stripe_api, amount,currency):
    stripe_api.v1.prices.retrieve.return_value.unit_amount = amount
    stripe_api.v1.prices.retrieve.return_value.currency = currency
    with pytest.raises(HTTPException): sc.criar_sessao_checkout(account,'flex',db_session)
    stripe_api.v1.subscriptions.create.assert_not_called()


def test_cartao_salvo_ausente(db_session, account, stripe_api):
    stripe_api.v1.payment_methods.list.return_value.data = []
    with pytest.raises(sc.CartaoSalvoNaoEncontrado): sc.criar_sessao_checkout(account,'flex',db_session,True)


def test_cartao_salvo_e_portal(db_session, account, stripe_api):
    stripe_api.v1.payment_methods.list.return_value.data = [SimpleNamespace(id='pm_1',card=SimpleNamespace(brand='visa',last4='4242',exp_month=12,exp_year=2030))]
    sc.criar_sessao_checkout(account,'flex',db_session,True)
    assert stripe_api.v1.subscriptions.create.call_args.args[0]['default_payment_method'] == 'pm_1'
    assert sc.obter_cartao_mais_recente(account)['final'] == '4242'
    sc.criar_portal_sessao(account)
    assert stripe_api.v1.billing_portal.sessions.create.call_args.args[0]['customer'] == account.stripe_customer_id
