import json
from types import SimpleNamespace

from app.models.notificacao import Notificacao
from app.models.radio_config import RadioConfig


def test_status_plano(client, account, auth_headers, db_session):
    db_session.add(RadioConfig(account_id=account.id))
    db_session.commit()

    resposta = client.get("/billing/status", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["agentes_usados"] == 1
    assert corpo["plano"] == account.plano


def test_checkout_devolve_url_da_sessao(client, account, auth_headers, monkeypatch):
    capturado = {}

    def _fake_criar_sessao(acc, plano_id):
        capturado["plano_id"] = plano_id
        return SimpleNamespace(url="https://checkout.stripe.com/session123")

    monkeypatch.setattr("app.billing.router.criar_sessao_checkout", _fake_criar_sessao)
    resposta = client.post(
        "/billing/checkout", json={"plano_id": "growth"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["url"] == "https://checkout.stripe.com/session123"
    assert capturado["plano_id"] == "growth"


def test_checkout_rejeita_plano_invalido(client, account, auth_headers):
    resposta = client.post(
        "/billing/checkout", json={"plano_id": "inexistente"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_checkout_rejeita_se_ja_ativo(client, account_factory, auth_headers):
    account = account_factory(email="ativo-checkout@a.com", plano_status="ativo")
    resposta = client.post(
        "/billing/checkout", json={"plano_id": "growth"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_trocar_plano_exige_assinatura_ativa(client, account, auth_headers):
    resposta = client.post(
        "/billing/trocar-plano", json={"plano_id": "growth"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 402


def test_trocar_plano_rejeita_mesmo_plano(client, account_factory, auth_headers):
    account = account_factory(
        email="mesmo-plano@a.com", plano_status="ativo", plano="growth", stripe_subscription_id="sub_1"
    )
    resposta = client.post(
        "/billing/trocar-plano", json={"plano_id": "growth"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_trocar_plano_troca_e_atualiza_status(client, account_factory, auth_headers, db_session, monkeypatch):
    account = account_factory(
        email="troca-plano@a.com", plano_status="ativo", plano="starter", stripe_subscription_id="sub_1"
    )
    monkeypatch.setattr("app.billing.router.trocar_plano_assinatura", lambda acc, plano_id: None)

    resposta = client.post(
        "/billing/trocar-plano", json={"plano_id": "professional"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["plano"] == "professional"

    db_session.refresh(account)
    assert account.plano == "professional"


def test_portal_exige_customer_id(client, account, auth_headers):
    resposta = client.post("/billing/portal", headers=auth_headers(account.id))
    assert resposta.status_code == 402


def test_portal_devolve_url_da_sessao(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="portal@a.com", stripe_customer_id="cus_123")
    monkeypatch.setattr(
        "app.billing.router.criar_portal_sessao",
        lambda acc: SimpleNamespace(url="https://billing.stripe.com/portal123"),
    )
    resposta = client.post("/billing/portal", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["url"] == "https://billing.stripe.com/portal123"


def test_checkout_agente_extra_exige_plano_ativo(client, account, auth_headers):
    assert account.plano_status != "ativo"
    resposta = client.post("/billing/agentes-extras/checkout", headers=auth_headers(account.id))
    assert resposta.status_code == 402


def test_checkout_agente_extra_com_plano_ativo(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="ativo@a.com", plano_status="ativo")
    monkeypatch.setattr(
        "app.billing.router.criar_sessao_checkout_agente_extra",
        lambda acc: SimpleNamespace(url="https://checkout.stripe.com/extra"),
    )
    resposta = client.post("/billing/agentes-extras/checkout", headers=auth_headers(account.id))
    assert resposta.status_code == 200


def test_checkout_excedente_mensagens_valida_blocos(client, account_factory, auth_headers):
    account = account_factory(email="ativo@a.com", plano_status="ativo")
    resposta = client.post(
        "/billing/excedente-mensagens/checkout", json={"blocos": 0}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 422


def test_webhook_checkout_completed_assinatura_ativa_conta(client, account, db_session, monkeypatch):
    radio_config = RadioConfig(account_id=account.id, ativo=False)
    db_session.add(radio_config)
    db_session.commit()

    evento = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(account.id),
                "customer": "cus_123",
                "subscription": "sub_123",
                "metadata": {"tipo": "assinatura", "plano": "growth"},
            }
        },
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200

    db_session.refresh(account)
    db_session.refresh(radio_config)
    assert account.plano_status == "ativo"
    assert account.plano == "growth"
    assert radio_config.ativo is True

    notificacao = db_session.query(Notificacao).filter_by(tipo="billing").first()
    assert notificacao is not None
    assert notificacao.titulo == "Assinatura ativada"


def test_webhook_assinatura_invalida_retorna_400(client, monkeypatch):
    def _levanta(*args, **kwargs):
        raise ValueError("assinatura invalida")

    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", _levanta)
    resposta = client.post("/billing/webhook", content="{}", headers={"stripe-signature": "fake"})
    assert resposta.status_code == 400


def test_webhook_agente_extra_incrementa_contador(client, account, db_session, monkeypatch):
    evento = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(account.id),
                "customer": "cus_123",
                "metadata": {"tipo": "agente_extra"},
            }
        },
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200
    db_session.refresh(account)
    assert account.agentes_extras == 1


def test_webhook_subscription_updated_sincroniza_plano_pelo_price(
    client, account_factory, db_session, monkeypatch
):
    account = account_factory(email="sync-plano@a.com", plano_status="ativo", plano="starter", stripe_customer_id="cus_123")

    evento = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "customer": "cus_123",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_growth_fake"}}]},
            }
        },
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)
    monkeypatch.setattr(
        "app.billing.router.plano_por_price_id",
        lambda price_id: "growth" if price_id == "price_growth_fake" else None,
    )

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200
    db_session.refresh(account)
    assert account.plano == "growth"
    assert account.plano_status == "ativo"


def test_webhook_assinatura_cancelada_desativa_conta(client, account, db_session, monkeypatch):
    account.plano_status = "ativo"
    account.stripe_customer_id = "cus_123"
    radio_config = RadioConfig(account_id=account.id, ativo=True)
    db_session.add(radio_config)
    db_session.commit()

    evento = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_123"}},
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200
    db_session.refresh(account)
    db_session.refresh(radio_config)
    assert account.plano_status == "cancelado"
    assert radio_config.ativo is False

    notificacao = db_session.query(Notificacao).filter_by(tipo="billing").first()
    assert notificacao is not None
    assert notificacao.titulo == "Assinatura cancelada"
