from types import SimpleNamespace
from unittest.mock import MagicMock
import hashlib
import hmac
import json
import time
import pytest
from app.billing import router as billing
from app.config.settings import settings
from app.models.consumo_flex import EventoCobranca, FaturaConsumo


@pytest.fixture
def stripe_api(monkeypatch):
    c = MagicMock()
    monkeypatch.setattr(billing, 'cliente', lambda: c)
    return c


def evento(client, tipo, dados, ident='evt_1'):
    body=json.dumps({'object':'event','id':ident,'type':tipo,'created':int(time.time()),'data':{'object':dados}}).encode()
    ts=str(int(time.time()))
    sig=hmac.new(settings.stripe_webhook_secret.encode(), ts.encode()+b'.'+body,hashlib.sha256).hexdigest()
    return client.post('/billing/webhook',content=body,headers={'stripe-signature':f't={ts},v1={sig}'})


def test_webhook_rejeita_assinatura_invalida(client):
    assert client.post('/billing/webhook',json={}).status_code == 400


@pytest.mark.parametrize('endpoint',['/billing/agentes-extras/checkout','/billing/excedente-mensagens/checkout','/billing/trocar-plano'])
def test_ofertas_antigas_encerradas(client, account, auth_headers,endpoint):
    assert client.post(endpoint,json={},headers=auth_headers(account.id)).status_code == 410


def test_checkout_flex(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(billing, 'criar_sessao_checkout',lambda *a: SimpleNamespace(latest_invoice={'confirmation_secret':{'client_secret':'pi_secret'}}))
    r=client.post('/billing/checkout',json={'plano_id':'flex'},headers=auth_headers(account.id))
    assert r.status_code == 200 and r.json()['client_secret'] == 'pi_secret'
    assert client.post('/billing/checkout',json={'plano_id':'growth'},headers=auth_headers(account.id)).status_code == 400


@pytest.mark.parametrize('reason',['subscription_create','subscription_cycle'])
def test_pagamento_ativa_primeira_e_renovacao(client, db_session, account_factory, stripe_api,reason):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='inadimplente')
    invoice={'id':'in_1','customer':'cus_1','parent':{'subscription_details':{'subscription':'sub_1'}},
        'status':'paid','period_start':1000,'period_end':2000,'total':6990,'billing_reason':reason}
    stripe_api.v1.invoices.retrieve.return_value=invoice
    assert evento(client,'invoice.paid',invoice).status_code == 200
    db_session.refresh(a)
    assert a.plano_status == 'ativo' and a.plano == 'flex'
    assert db_session.get(FaturaConsumo,'in_1').estado == 'paga'
    assert evento(client,'invoice.paid',invoice).json()['status']=='duplicado'
    assert db_session.query(EventoCobranca).count()==1


def test_falha_atrasada_nao_reabre_divida_paga(client, db_session, account_factory,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='ativo')
    paid={'id':'in_1','customer':'cus_1','subscription':'sub_1','status':'paid','period_start':1000,'period_end':2000,'total':6990}
    stripe_api.v1.invoices.retrieve.return_value=paid
    assert evento(client,'invoice.payment_failed',{**paid,'status':'open'}).status_code==200
    db_session.refresh(a)
    assert a.plano_status=='ativo'


def test_falha_retentativa_na_mesma_fatura(client, db_session,account_factory,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='ativo')
    invoice={'id':'in_1','customer':'cus_1','subscription':'sub_1','status':'open','period_start':1000,'period_end':2000,'total':6990}
    stripe_api.v1.invoices.retrieve.return_value=invoice
    assert evento(client,'invoice.payment_failed',invoice).status_code==200
    db_session.refresh(a); assert a.plano_status=='inadimplente'
    stripe_api.v1.invoices.retrieve.return_value={**invoice,'status':'paid'}
    assert evento(client,'invoice.paid',invoice,'evt_2').status_code==200
    db_session.refresh(a); assert a.plano_status=='ativo'
    assert db_session.query(FaturaConsumo).count()==1


def test_evento_nao_confirmado_em_falha_pode_ser_reentregue(client,db_session,account_factory,stripe_api):
    account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1')
    stripe_api.v1.invoices.retrieve.side_effect=RuntimeError('indisponível')
    with pytest.raises(RuntimeError): evento(client,'invoice.paid',{'id':'in_1','customer':'cus_1'})
    assert db_session.get(EventoCobranca,'evt_1') is None


def test_evento_outra_assinatura_nao_altera_conta(client,db_session,account_factory,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_principal',plano_status='ativo')
    assert evento(client,'customer.subscription.deleted',{'id':'sub_outra','customer':'cus_1'}).status_code==200
    db_session.refresh(a); assert a.plano_status=='ativo'
    stripe_api.v1.subscriptions.retrieve.assert_not_called()
