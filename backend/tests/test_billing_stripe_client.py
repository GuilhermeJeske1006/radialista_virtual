from app.billing import stripe_client
from app.models.account import Account
from app.planos import PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG


def _account(**kwargs):
    return Account(id=1, **kwargs)


def test_criar_sessao_checkout_usa_client_reference_id(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout(_account(), "starter")
    assert capturado["client_reference_id"] == "1"
    assert capturado["mode"] == "subscription"
    assert capturado["metadata"] == {"tipo": "assinatura", "plano": "starter"}


def test_criar_sessao_checkout_usa_price_do_plano_escolhido(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    monkeypatch.setitem(stripe_client.PRICE_ID_POR_PLANO, "growth", "price_growth_fake")
    stripe_client.criar_sessao_checkout(_account(), "growth")
    assert capturado["line_items"] == [{"price": "price_growth_fake", "quantity": 1}]
    assert capturado["metadata"] == {"tipo": "assinatura", "plano": "growth"}


def test_criar_sessao_checkout_usa_customer_existente_sem_email(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.checkout.Session,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout(_account(stripe_customer_id="cus_existente"), "starter")
    assert capturado["customer"] == "cus_existente"
    assert capturado["customer_email"] is None


def test_trocar_plano_assinatura_troca_item_da_assinatura_existente(monkeypatch):
    monkeypatch.setattr(
        stripe_client.stripe.Subscription,
        "retrieve",
        lambda sub_id: {"items": {"data": [{"id": "si_1"}]}},
    )
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.Subscription,
        "modify",
        lambda sub_id, **kwargs: capturado.update(kwargs) or capturado.setdefault("sub_id", sub_id),
    )
    monkeypatch.setitem(stripe_client.PRICE_ID_POR_PLANO, "professional", "price_professional_fake")
    stripe_client.trocar_plano_assinatura(_account(stripe_subscription_id="sub_1"), "professional")
    assert capturado["sub_id"] == "sub_1"
    assert capturado["items"] == [{"id": "si_1", "price": "price_professional_fake"}]


def test_plano_por_price_id_resolve_e_ignora_desconhecido(monkeypatch):
    monkeypatch.setitem(stripe_client.PRICE_ID_POR_PLANO, "growth", "price_growth_fake")
    monkeypatch.setitem(stripe_client.PLANO_POR_PRICE_ID, "price_growth_fake", "growth")
    assert stripe_client.plano_por_price_id("price_growth_fake") == "growth"
    assert stripe_client.plano_por_price_id("price_desconhecido") is None
    assert stripe_client.plano_por_price_id(None) is None


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
