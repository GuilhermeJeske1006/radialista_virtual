from uuid import uuid4
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from app.billing.fechamento import registrar_pagamento
from app.funnel.service import FunnelEvent, record_event
from app.models.consumo_flex import FaturaConsumo
ORIGIN = {"Origin": "https://locufybr.com"}
def payload(**overrides):
    return {"id": str(uuid4()), "evento": "register_click", "local": "hero", "plano": "starter", "campanha": {"utm_source": "newsletter"}, **overrides}
def test_public_event_persists_once(client, db_session):
    event = payload()
    for _ in range(2):
        assert client.post('/funnel/events', json=event, headers=ORIGIN).status_code == 204
    rows = db_session.query(FunnelEvent).all()
    assert len(rows) == 1
    assert rows[0].account_id is None
    assert rows[0].campanha == {"utm_source": "newsletter"}
def test_rejects_spoofed_payment_personal_data_and_unknown_origin(client):
    assert client.post('/funnel/events', json=payload(evento='subscription_confirmed'), headers=ORIGIN).status_code == 422
    assert client.post('/funnel/events', json=payload(email='private@example.com'), headers=ORIGIN).status_code == 422
    assert client.post('/funnel/events', json=payload(campanha={'utm_source':'private@example.com'}), headers=ORIGIN).status_code == 422
    assert client.post('/funnel/events', json=payload(), headers={'Origin':'https://untrusted.example'}).status_code == 403
    assert client.post('/funnel/events', content='x'*2049, headers=ORIGIN).status_code == 413
def test_respects_privacy_signal(client, db_session):
    for signal in ['DNT','Sec-GPC']:
        assert client.post('/funnel/events', json=payload(), headers={**ORIGIN,signal:'1'}).status_code == 204
    assert db_session.query(FunnelEvent).count() == 0
def test_summary_requires_admin(client):
    assert client.get('/admin/funnel').status_code == 401
def test_success_inherits_attribution_and_deduplicates(db_session, account):
    record_event(db_session, 'account_created', event_id=f'account:{account.id}', account_id=account.id, campanha={'utm_source':'newsletter'})
    for _ in range(2):
        record_event(db_session, 'subscription_confirmed', event_id='subscription:sub_test', account_id=account.id, plano='starter', valor_centavos=39900)
    db_session.commit()
    assert db_session.query(FunnelEvent).count() == 2
    paid=db_session.get(FunnelEvent,'subscription:sub_test')
    assert paid.campanha == {'utm_source':'newsletter'}
    assert paid.valor_centavos == 39900
def test_optional_metric_failure_does_not_rollback_business_data(db_session, account):
    account.nome_radio='Nome preservado'
    record_event(db_session, None, event_id='invalid')
    db_session.commit()
    db_session.refresh(account)
    assert account.nome_radio == 'Nome preservado'
def test_accepts_checkout_step(client, db_session):
    assert client.post('/funnel/events', json=payload(evento='register_checkout_step', local='register', plano='flex'), headers=ORIGIN).status_code == 204
    assert db_session.query(FunnelEvent).one().evento == 'register_checkout_step'
def invoice(ident, reason, **extra):
    return {'id': ident, 'status': 'paid', 'billing_reason': reason, 'period_start': 1000, 'period_end': 2000, 'total': 7500, **extra}
def test_first_paid_subscription_invoice_records_revenue_once(db_session, account):
    account.stripe_subscription_id = 'sub_1'
    record_event(db_session, 'account_created', event_id=f'account:{account.id}', account_id=account.id, campanha={'utm_source':'newsletter'})
    registrar_pagamento(db_session, account, invoice('in_renovacao', 'subscription_cycle', period_start=2000, period_end=3000))
    for _ in range(2):
        registrar_pagamento(db_session, account, invoice('in_adesao', 'subscription_create', amount_paid=6990))
    db_session.commit()
    paid = db_session.query(FunnelEvent).filter_by(evento='subscription_confirmed').all()
    assert [(p.id, p.account_id, p.plano, p.valor_centavos, p.campanha) for p in paid] == [('subscription:sub_1', account.id, 'flex', 6990, {'utm_source':'newsletter'})]
def test_payment_survives_metric_failure(db_session, account):
    def falha(*_): raise SQLAlchemyError('indisponível')
    account.stripe_subscription_id = 'sub_1'
    event.listen(FunnelEvent, 'before_insert', falha)
    try:
        registrar_pagamento(db_session, account, invoice('in_adesao', 'subscription_create'))
        db_session.commit()
    finally:
        event.remove(FunnelEvent, 'before_insert', falha)
    db_session.refresh(account)
    assert account.plano_status == 'ativo'
    assert db_session.get(FaturaConsumo, 'in_adesao').estado == 'paga'
    assert db_session.query(FunnelEvent).count() == 0
