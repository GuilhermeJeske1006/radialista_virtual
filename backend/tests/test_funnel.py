from uuid import uuid4
from app.funnel.service import FunnelEvent, record_event
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
