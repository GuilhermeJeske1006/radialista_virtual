import json
from types import SimpleNamespace

from app.models.compra_excedente import CompraExcedente
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


def test_checkout_devolve_client_secret_da_sessao(client, account, auth_headers, monkeypatch):
    capturado = {}

    def _fake_criar_sessao(acc, plano_id, db):
        capturado["plano_id"] = plano_id
        pi = SimpleNamespace(client_secret="cs_test_secret123")
        return SimpleNamespace(latest_invoice=SimpleNamespace(payment_intent=pi))

    monkeypatch.setattr("app.billing.router.criar_sessao_checkout", _fake_criar_sessao)
    resposta = client.post(
        "/billing/checkout", json={"plano_id": "growth"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["client_secret"] == "cs_test_secret123"
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
        lambda acc, db: SimpleNamespace(
            latest_invoice=SimpleNamespace(payment_intent=SimpleNamespace(client_secret="cs_test_extra123"))
        ),
    )
    resposta = client.post("/billing/agentes-extras/checkout", headers=auth_headers(account.id))
    assert resposta.status_code == 200


def test_checkout_excedente_mensagens_valida_blocos(client, account_factory, auth_headers):
    account = account_factory(email="ativo@a.com", plano_status="ativo")
    resposta = client.post(
        "/billing/excedente-mensagens/checkout", json={"blocos": 0}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 422


def _linha_invoice(metadata: dict, subscription_id: str) -> dict:
    # A API version dessa conta Stripe nao tem mais "subscription"/"subscription_details" no
    # nivel raiz da invoice -- o metadata da subscription e a referencia pra ela vem no line
    # item (sempre 1 por invoice nos nossos fluxos, um price por assinatura).
    return {
        "data": [
            {
                "metadata": metadata,
                "parent": {"subscription_item_details": {"subscription": subscription_id}},
            }
        ]
    }


def test_webhook_invoice_paid_assinatura_ativa_conta(client, account, db_session, monkeypatch):
    radio_config = RadioConfig(account_id=account.id, ativo=False)
    db_session.add(radio_config)
    db_session.commit()

    evento = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "billing_reason": "subscription_create",
                "customer": "cus_123",
                "lines": _linha_invoice(
                    {"tipo": "assinatura", "plano": "growth", "account_id": str(account.id)}, "sub_123"
                ),
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
    assert account.stripe_subscription_id == "sub_123"
    assert radio_config.ativo is True

    notificacao = db_session.query(Notificacao).filter_by(tipo="billing").first()
    assert notificacao is not None
    assert notificacao.titulo == "Assinatura ativada"


def test_webhook_invoice_paid_ignora_renovacao_mensal(client, account, db_session, monkeypatch):
    # billing_reason=="subscription_cycle" e' renovacao, nao ativacao inicial -- nao pode
    # reprocessar a ativacao (nem incrementar agentes_extras) todo mes.
    evento = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "billing_reason": "subscription_cycle",
                "customer": "cus_123",
                "lines": _linha_invoice({"tipo": "agente_extra", "account_id": str(account.id)}, "sub_123"),
            }
        },
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200
    db_session.refresh(account)
    assert account.agentes_extras == 0


def test_webhook_assinatura_invalida_retorna_400(client, monkeypatch):
    def _levanta(*args, **kwargs):
        raise ValueError("assinatura invalida")

    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", _levanta)
    resposta = client.post("/billing/webhook", content="{}", headers={"stripe-signature": "fake"})
    assert resposta.status_code == 400


def test_webhook_agente_extra_incrementa_contador(client, account, db_session, monkeypatch):
    evento = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "billing_reason": "subscription_create",
                "customer": "cus_123",
                "lines": _linha_invoice({"tipo": "agente_extra", "account_id": str(account.id)}, "sub_extra_1"),
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


def test_webhook_payment_intent_succeeded_credita_excedente(client, account, db_session, monkeypatch):
    evento = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "customer": "cus_123",
                "metadata": {"tipo": "excedente_mensagens", "blocos": "3", "account_id": str(account.id)},
            }
        },
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200

    compra = db_session.query(CompraExcedente).filter_by(account_id=account.id).first()
    assert compra is not None
    assert compra.quantidade == 3000


def test_webhook_payment_intent_succeeded_ignora_pagamento_de_invoice(client, account, db_session, monkeypatch):
    # PaymentIntent de uma invoice de assinatura tambem dispara payment_intent.succeeded --
    # so' o metadata.tipo=="excedente_mensagens" (setado por nos' na compra avulsa) autoriza credito.
    evento = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"customer": "cus_123", "metadata": {}}},
    }
    monkeypatch.setattr("app.billing.router.stripe.Webhook.construct_event", lambda *a, **k: evento)

    resposta = client.post(
        "/billing/webhook", content=json.dumps(evento), headers={"stripe-signature": "fake"}
    )
    assert resposta.status_code == 200
    assert db_session.query(CompraExcedente).filter_by(account_id=account.id).first() is None


def test_webhook_subscription_updated_sincroniza_plano_pelo_price(
    client, account_factory, db_session, monkeypatch
):
    account = account_factory(
        email="sync-plano@a.com",
        plano_status="ativo",
        plano="starter",
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_principal",
    )

    evento = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_principal",
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
    account.stripe_subscription_id = "sub_principal"
    radio_config = RadioConfig(account_id=account.id, ativo=True)
    db_session.add(radio_config)
    db_session.commit()

    evento = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_principal", "customer": "cus_123"}},
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


def test_webhook_subscription_deleted_ignora_subscription_de_agente_extra(client, account, db_session, monkeypatch):
    # Cada agente extra comprado gera sua PROPRIA subscription no Stripe (fora da assinatura
    # principal do plano) -- cancelar uma dessas nao pode derrubar a conta inteira.
    account.plano_status = "ativo"
    account.stripe_customer_id = "cus_123"
    account.stripe_subscription_id = "sub_principal"
    radio_config = RadioConfig(account_id=account.id, ativo=True)
    db_session.add(radio_config)
    db_session.commit()

    evento = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_agente_extra", "customer": "cus_123"}},
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
