from app.billing import stripe_client
from app.models.account import Account
from app.planos import PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG


def _account(**kwargs):
    padrao = dict(email="a@a.com", senha_hash="x")
    padrao.update(kwargs)
    return Account(id=1, **padrao)


def test_criar_sessao_checkout_usa_client_reference_id(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout(_account())
    assert capturado["client_reference_id"] == "1"
    assert capturado["mode"] == "subscription"
    assert capturado["metadata"] == {"tipo": "assinatura"}


def test_criar_sessao_checkout_usa_customer_existente_sem_email(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout(_account(stripe_customer_id="cus_existente"))
    assert capturado["customer"] == "cus_existente"
    assert capturado["customer_email"] is None


def test_criar_sessao_checkout_agente_extra_cobra_preco_certo(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout_agente_extra(_account())
    unit_amount = capturado["line_items"][0]["price_data"]["unit_amount"]
    assert unit_amount == PRECO_AGENTE_ADICIONAL * 100
    assert capturado["metadata"] == {"tipo": "agente_extra"}


def test_criar_sessao_checkout_excedente_mensagens_multiplica_por_blocos(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout_excedente_mensagens(_account(), blocos=3)
    item = capturado["line_items"][0]
    assert item["quantity"] == 3
    assert item["price_data"]["unit_amount"] == PRECO_EXCEDENTE_1000_MSG * 100
    assert capturado["metadata"]["blocos"] == "3"


def test_criar_portal_sessao_usa_customer_id(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.billing_portal.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_portal_sessao(_account(stripe_customer_id="cus_1"))
    assert capturado["customer"] == "cus_1"
