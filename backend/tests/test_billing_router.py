import json
from types import SimpleNamespace

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
    monkeypatch.setattr(
        "app.billing.router.criar_sessao_checkout",
        lambda acc: SimpleNamespace(url="https://checkout.stripe.com/session123"),
    )
    resposta = client.post("/billing/checkout", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["url"] == "https://checkout.stripe.com/session123"


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
                "metadata": {"tipo": "assinatura"},
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
    assert radio_config.ativo is True


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
