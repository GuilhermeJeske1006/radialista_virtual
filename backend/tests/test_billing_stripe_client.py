from types import SimpleNamespace

from app.billing import stripe_client
from app.models.account import Account
from app.planos import PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG


def _account(**kwargs):
    return Account(id=1, **kwargs)


def test_obter_ou_criar_customer_reusa_existente(db_session):
    account = _account(stripe_customer_id="cus_existente")
    assert stripe_client._obter_ou_criar_customer(account, db_session) == "cus_existente"


def test_obter_ou_criar_customer_cria_e_persiste(monkeypatch, db_session):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.Customer,
        "create",
        lambda **kwargs: capturado.update(kwargs) or SimpleNamespace(id="cus_novo"),
    )
    account = _account()
    customer_id = stripe_client._obter_ou_criar_customer(account, db_session)
    assert customer_id == "cus_novo"
    assert account.stripe_customer_id == "cus_novo"
    assert capturado["metadata"] == {"account_id": "1"}


def test_criar_sessao_checkout_usa_account_id_no_metadata(monkeypatch, db_session):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.Subscription,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout(_account(stripe_customer_id="cus_1"), "starter", db_session)
    assert capturado["customer"] == "cus_1"
    assert capturado["payment_behavior"] == "default_incomplete"
    assert capturado["metadata"] == {"tipo": "assinatura", "plano": "starter", "account_id": "1"}


def test_criar_sessao_checkout_usa_price_do_plano_escolhido(monkeypatch, db_session):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.Subscription,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    monkeypatch.setitem(stripe_client.PRICE_ID_POR_PLANO, "growth", "price_growth_fake")
    stripe_client.criar_sessao_checkout(_account(stripe_customer_id="cus_1"), "growth", db_session)
    assert capturado["items"] == [{"price": "price_growth_fake"}]
    assert capturado["metadata"]["plano"] == "growth"


def test_criar_sessao_checkout_cria_customer_quando_nao_existe(monkeypatch, db_session):
    monkeypatch.setattr(stripe_client.stripe.Customer, "create", lambda **kwargs: SimpleNamespace(id="cus_criado"))
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.Subscription,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    account = _account()
    stripe_client.criar_sessao_checkout(account, "starter", db_session)
    assert capturado["customer"] == "cus_criado"
    assert account.stripe_customer_id == "cus_criado"


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


def test_criar_sessao_checkout_agente_extra_cobra_preco_certo(monkeypatch, db_session):
    monkeypatch.setattr(stripe_client.stripe.Product, "retrieve", lambda produto_id: SimpleNamespace(id=produto_id))
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.Subscription,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout_agente_extra(_account(stripe_customer_id="cus_1"), db_session)
    unit_amount = capturado["items"][0]["price_data"]["unit_amount"]
    assert unit_amount == PRECO_AGENTE_ADICIONAL * 100
    assert capturado["items"][0]["price_data"]["product"] == stripe_client._PRODUTO_AGENTE_EXTRA_ID
    assert capturado["metadata"] == {"tipo": "agente_extra", "account_id": "1"}


def test_obter_ou_criar_produto_agente_extra_cria_se_nao_existir(monkeypatch):
    def _retrieve_falha(produto_id):
        raise stripe_client.stripe.error.InvalidRequestError("No such product", "id")

    capturado = {}
    monkeypatch.setattr(stripe_client.stripe.Product, "retrieve", _retrieve_falha)
    monkeypatch.setattr(
        stripe_client.stripe.Product,
        "create",
        lambda **kwargs: capturado.update(kwargs) or SimpleNamespace(id=kwargs["id"]),
    )
    produto_id = stripe_client._obter_ou_criar_produto_agente_extra()
    assert produto_id == stripe_client._PRODUTO_AGENTE_EXTRA_ID
    assert capturado["id"] == stripe_client._PRODUTO_AGENTE_EXTRA_ID


def test_criar_sessao_checkout_excedente_mensagens_multiplica_por_blocos(monkeypatch, db_session):
    capturado = {}
    monkeypatch.setattr(
        stripe_client.stripe.PaymentIntent,
        "create",
        lambda **kwargs: capturado.update(kwargs) or object(),
    )
    stripe_client.criar_sessao_checkout_excedente_mensagens(_account(stripe_customer_id="cus_1"), 3, db_session)
    assert capturado["amount"] == PRECO_EXCEDENTE_1000_MSG * 100 * 3
    assert capturado["payment_method_types"] == ["card"]
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
