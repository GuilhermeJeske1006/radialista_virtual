from types import SimpleNamespace
from unittest.mock import MagicMock
import hashlib
import hmac
import json
import time
import pytest
import stripe
from sqlalchemy import text
from app.billing import router as billing
from app.billing.fechamento import periodo
from app.config.settings import settings
from app.funnel.service import FunnelEvent
from app.models.account import Account
from app.models.consumo_flex import ContaConsumo, EventoCobranca, FaturaConsumo


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
    db_session.refresh(a)
    assert a.plano_status=='inadimplente'
    stripe_api.v1.invoices.retrieve.return_value={**invoice,'status':'paid'}
    assert evento(client,'invoice.paid',invoice,'evt_2').status_code==200
    db_session.refresh(a)
    assert a.plano_status=='ativo'
    assert db_session.query(FaturaConsumo).count()==1


def test_evento_nao_confirmado_em_falha_pode_ser_reentregue(client,db_session,account_factory,stripe_api):
    account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1')
    stripe_api.v1.invoices.retrieve.side_effect=RuntimeError('indisponível')
    with pytest.raises(RuntimeError):
        evento(client,'invoice.paid',{'id':'in_1','customer':'cus_1'})
    assert db_session.get(EventoCobranca,'evt_1') is None


def test_evento_outra_assinatura_nao_altera_conta(client,db_session,account_factory,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_principal',plano_status='ativo')
    assert evento(client,'customer.subscription.deleted',{'id':'sub_outra','customer':'cus_1'}).status_code==200
    db_session.refresh(a)
    assert a.plano_status=='ativo'
    stripe_api.v1.subscriptions.retrieve.assert_not_called()


@pytest.mark.parametrize('cartao',['pm_1',None])
def test_fatura_final_do_cancelamento_cobra_cartao_da_assinatura(client,account_factory,stripe_api,monkeypatch,cartao):
    # Cartão salvo só na assinatura: sem repassá-lo, a fatura avulsa ficaria em aberto sem cobrança.
    account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='ativo')
    monkeypatch.setattr(billing,'fechar',MagicMock())
    stripe_api.v1.subscriptions.retrieve.return_value={'id':'sub_1','customer':'cus_1','status':'canceled',
        'canceled_at':2000,'start_date':1000,'default_payment_method':cartao}
    stripe_api.v1.invoices.create.return_value={'id':'in_final','status':'draft'}
    assert evento(client,'customer.subscription.deleted',{'id':'sub_1','customer':'cus_1'}).status_code==200
    params=stripe_api.v1.invoices.create.call_args.args[0]
    assert params.get('default_payment_method')==cartao
    billing.fechar.assert_called_once()


def fatura_adesao(**extra):
    return {'id':'in_1','customer':'cus_1','parent':{'subscription_details':{'subscription':'sub_1'}},
        'status':'paid','billing_reason':'subscription_create','period_start':1000,'period_end':1000,'total':6990,'amount_paid':6990,
        'lines':{'data':[{'parent':{'type':'subscription_item_details'},'period':{'start':1000,'end':2000}}]},**extra}


def confirmar(client, auth_headers, a):
    return client.post('/billing/confirmar',headers=auth_headers(a.id))


def test_confirmar_ativa_trial_com_fatura_paga(client,db_session,account_factory,auth_headers,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='trial')
    stripe_api.v1.subscriptions.retrieve.return_value={'id':'sub_1','status':'active','latest_invoice':fatura_adesao()}
    r=confirmar(client,auth_headers,a)
    assert r.status_code==200 and r.json()=={'plano_status':'ativo'}
    assert stripe_api.v1.subscriptions.retrieve.call_args.args==('sub_1',{'expand':['latest_invoice']})
    db_session.refresh(a)
    assert a.plano_status=='ativo' and a.plano=='flex'
    assert db_session.get(FaturaConsumo,'in_1').estado=='paga'
    assert db_session.get(ContaConsumo,a.id).ciclo_fim.replace(tzinfo=None)==periodo(2000).replace(tzinfo=None)


@pytest.mark.parametrize('extra',[{'status':'open'},{'parent':{'subscription_details':{'subscription':'sub_outra'}}}])
def test_confirmar_nao_ativa_sem_fatura_paga_da_assinatura(client,db_session,account_factory,auth_headers,stripe_api,extra):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='trial')
    stripe_api.v1.subscriptions.retrieve.return_value={'id':'sub_1','status':'incomplete','latest_invoice':fatura_adesao(**extra)}
    r=confirmar(client,auth_headers,a)
    assert r.status_code==200 and r.json()=={'plano_status':'trial'}
    assert db_session.get(FaturaConsumo,'in_1') is None
    assert db_session.query(FunnelEvent).count()==0


def test_confirmar_ignora_renovacao_paga(client,db_session,account_factory,auth_headers,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='inadimplente')
    db_session.add(ContaConsumo(account_id=a.id,limite=0,exposicao=500,modelos={},ciclo_inicio=periodo(0),ciclo_fim=periodo(1000)))
    db_session.commit()
    renovacao=fatura_adesao(billing_reason='subscription_cycle')
    stripe_api.v1.subscriptions.retrieve.return_value={'id':'sub_1','status':'active','latest_invoice':renovacao}
    r=confirmar(client,auth_headers,a)
    assert r.status_code==200 and r.json()=={'plano_status':'inadimplente'}
    db_session.expire_all()
    conta=db_session.get(ContaConsumo,a.id)
    assert conta.exposicao==500 and conta.ciclo_fim.replace(tzinfo=None)==periodo(1000).replace(tzinfo=None)
    assert db_session.get(Account,a.id).plano_status=='inadimplente'
    assert db_session.get(FaturaConsumo,'in_1') is None


@pytest.mark.parametrize('dados',[{'stripe_subscription_id':'sub_1','plano_status':'ativo'},{'plano_status':'trial'}])
def test_confirmar_sem_consultar_stripe(client,account_factory,auth_headers,stripe_api,dados):
    a=account_factory(stripe_customer_id='cus_1',**dados)
    r=confirmar(client,auth_headers,a)
    assert r.status_code==200 and r.json()=={'plano_status':dados['plano_status']}
    stripe_api.v1.subscriptions.retrieve.assert_not_called()


def test_confirmar_erro_do_stripe_vira_502(client,account_factory,auth_headers,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='trial')
    stripe_api.v1.subscriptions.retrieve.side_effect=stripe.APIConnectionError('falha interna sk_test_segredo')
    r=confirmar(client,auth_headers,a)
    assert r.status_code==502 and 'sk_test' not in r.text


def test_confirmar_exige_admin(client,account,usuario_factory):
    from app.auth.security import criar_token
    membro=usuario_factory(account.id,'membro@example.com')
    assert client.post('/billing/confirmar',headers={'Authorization':f'Bearer {criar_token(membro.id)}'}).status_code==403


@pytest.mark.parametrize('webhook_primeiro',[False,True])
def test_confirmar_e_webhook_descontam_exposicao_uma_vez(client,db_session,account_factory,auth_headers,stripe_api,webhook_primeiro):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='trial')
    # Consumo fictício na adesão deixa visível um desconto em dobro.
    db_session.add_all([ContaConsumo(account_id=a.id,limite=0,exposicao=500,modelos={}),
        FaturaConsumo(id='in_1',account_id=a.id,assinatura='sub_1',inicio=periodo(1000),fim=periodo(1000),consumo=200,estado='emitida')])
    db_session.commit()
    invoice=fatura_adesao()
    stripe_api.v1.invoices.retrieve.return_value=invoice
    stripe_api.v1.subscriptions.retrieve.return_value={'id':'sub_1','status':'active','latest_invoice':invoice}
    if webhook_primeiro:
        assert evento(client,'invoice.paid',invoice).status_code==200
    assert confirmar(client,auth_headers,a).json()=={'plano_status':'ativo'}
    if not webhook_primeiro:
        assert evento(client,'invoice.paid',invoice).json()['status']=='ok'
    db_session.expire_all()
    assert db_session.get(ContaConsumo,a.id).exposicao==300
    assert db_session.get(Account,a.id).plano_status=='ativo'
    eventos=[(e.id,e.evento,e.plano,e.account_id,e.valor_centavos) for e in db_session.query(FunnelEvent).all()]
    assert eventos==[('subscription:sub_1','subscription_confirmed','flex',a.id,6990)]


def conta_cancelada(db_session, account_factory, assinatura_atual):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id=assinatura_atual,plano_status='cancelado')
    # Fatura final da assinatura cancelada (sub_1), já paga.
    db_session.add(FaturaConsumo(id='in_final',account_id=a.id,assinatura='sub_1',inicio=periodo(1000),fim=periodo(1500),estado='paga'))
    db_session.commit()
    return a


@pytest.mark.parametrize('via',['webhook','confirmar'])
def test_reassinatura_paga_reativa_conta_cancelada(client,db_session,account_factory,auth_headers,stripe_api,via):
    a=conta_cancelada(db_session,account_factory,'sub_2')
    invoice=fatura_adesao(id='in_2',parent={'subscription_details':{'subscription':'sub_2'}},period_start=3000,period_end=3000)
    stripe_api.v1.invoices.retrieve.return_value=invoice
    stripe_api.v1.subscriptions.retrieve.return_value={'id':'sub_2','status':'active','latest_invoice':invoice}
    if via=='webhook':
        assert evento(client,'invoice.paid',invoice).status_code==200
    else:
        assert confirmar(client,auth_headers,a).json()=={'plano_status':'ativo'}
    db_session.expire_all()
    assert db_session.get(Account,a.id).plano_status=='ativo'
    assert db_session.get(FunnelEvent,'subscription:sub_2').valor_centavos==6990


def test_adesao_atrasada_da_assinatura_cancelada_nao_reativa(client,db_session,account_factory,stripe_api):
    a=conta_cancelada(db_session,account_factory,'sub_1')
    stripe_api.v1.invoices.retrieve.return_value=fatura_adesao()
    assert evento(client,'invoice.paid',fatura_adesao()).status_code==200
    db_session.expire_all()
    assert db_session.get(Account,a.id).plano_status=='cancelado'


@pytest.mark.parametrize('tipo',['invoice.payment_failed','invoice.payment_action_required'])
def test_adesao_recusada_mantem_trial_e_nova_assinatura_ativa(client,db_session,account_factory,stripe_api,tipo):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='trial')
    recusada=fatura_adesao(status='open')
    stripe_api.v1.invoices.retrieve.return_value=recusada
    assert evento(client,tipo,recusada).status_code==200
    db_session.refresh(a)
    assert a.plano_status=='trial' and db_session.get(FaturaConsumo,'in_1').estado=='emitida'
    # Assinatura incompleta expira; o checkout cria outra e a nova adesão é paga.
    a.stripe_subscription_id='sub_2'
    db_session.commit()
    nova=fatura_adesao(id='in_2',parent={'subscription_details':{'subscription':'sub_2'}},period_start=3000,period_end=3000)
    stripe_api.v1.invoices.retrieve.return_value=nova
    assert evento(client,'invoice.paid',nova,'evt_2').status_code==200
    db_session.refresh(a)
    assert a.plano_status=='ativo'


def test_reassinatura_recusada_mantem_cancelado(client,db_session,account_factory,stripe_api):
    a=conta_cancelada(db_session,account_factory,'sub_2')
    adesao=fatura_adesao(id='in_2',parent={'subscription_details':{'subscription':'sub_2'}},period_start=3000,period_end=3000)
    stripe_api.v1.invoices.retrieve.return_value={**adesao,'status':'open'}
    assert evento(client,'invoice.payment_failed',adesao).status_code==200
    db_session.expire_all()
    assert db_session.get(Account,a.id).plano_status=='cancelado' and db_session.get(FaturaConsumo,'in_2').estado=='emitida'
    stripe_api.v1.invoices.retrieve.return_value=adesao
    assert evento(client,'invoice.paid',adesao,'evt_2').status_code==200
    db_session.expire_all()
    assert db_session.get(Account,a.id).plano_status=='ativo'


def test_renovacao_recusada_continua_inadimplente(client,db_session,account_factory,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='ativo')
    recusada=fatura_adesao(status='open',billing_reason='subscription_cycle')
    stripe_api.v1.invoices.retrieve.return_value=recusada
    assert evento(client,'invoice.payment_failed',recusada).status_code==200
    db_session.refresh(a)
    assert a.plano_status=='inadimplente' and db_session.get(FaturaConsumo,'in_1').estado=='pendente'


def test_webhook_decide_com_conta_relida_apos_lock(client,db_session,account_factory,stripe_api):
    a=account_factory(stripe_customer_id='cus_1',stripe_subscription_id='sub_1',plano_status='trial')
    # Outra transação cancelou a conta; a instância em memória continua "trial".
    db_session.execute(text("UPDATE accounts SET plano_status='cancelado' WHERE id=:id"),{'id':a.id})
    renovacao=fatura_adesao(billing_reason='subscription_cycle')
    stripe_api.v1.invoices.retrieve.return_value=renovacao
    assert evento(client,'invoice.paid',renovacao).status_code==200
    db_session.expire_all()
    assert db_session.get(Account,a.id).plano_status=='cancelado'


def test_checkout_sem_cartao_salvo_409(client,account,auth_headers,monkeypatch):
    def sem_cartao(*a): raise billing.CartaoSalvoNaoEncontrado()
    monkeypatch.setattr(billing,'criar_sessao_checkout',sem_cartao)
    r=client.post('/billing/checkout',json={'usar_cartao_salvo':True},headers=auth_headers(account.id))
    assert r.status_code==409 and r.json()['detail']=='Nenhum cartão salvo. Informe um novo cartão.'
