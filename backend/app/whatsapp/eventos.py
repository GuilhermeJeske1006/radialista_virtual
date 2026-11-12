"""Eventos escritos na transação do efeito; cursor ordenado por conta, inclusive no commit."""
from sqlalchemy import func
from app.models.account import Account
from app.models.canal_whatsapp import EventoCanal


def registrar(db, account_id, tipo, **dados):
    # O bloqueio da conta serializa atribuição E commit. IDs globais de sequences
    # não garantem ordenação de commit entre duas transações concorrentes.
    db.query(Account.id).filter_by(id=account_id).with_for_update().one()
    db.flush()
    seq = (db.query(func.max(EventoCanal.sequencia)).filter_by(account_id=account_id).scalar() or 0) + 1
    evento = EventoCanal(account_id=account_id, sequencia=seq, tipo=tipo, dados=dados)
    db.add(evento)
    db.flush()
    return evento


def depois(db, account_id, cursor, limite=100):
    return [{"id": e.sequencia, "tipo": e.tipo, "schema": 1, "dados": e.dados,
             "em": e.criado_em.isoformat()} for e in db.query(EventoCanal).filter(
        EventoCanal.account_id == account_id, EventoCanal.sequencia > cursor,
    ).order_by(EventoCanal.sequencia).limit(limite).all()]
