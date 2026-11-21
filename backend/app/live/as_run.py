"""As-run persistente (F11, item 1): o que foi ao ar, com confirmacao do player.

`registrar_envio` grava uma linha por bloco que o /proxima entregou (status "enviado"). `confirmar_evento` aceita
o relato do player: "confirmado" (tocou ate o fim) ou "falhou". Sem confirmacao, o bloco nao conta como ao ar.
"""

import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.as_run_evento import AsRunEvento

STATUS_VALIDOS_PLAYER = ("confirmado", "falhou")
_TAMANHO_MAX_TEXTO = 500


def registrar_envio(db: Session, account_id: int, programa_id: int, tipo: str, texto: str = "",
                    vinheta_id: int | None = None, patrocinador_id: int | None = None,
                    video_id: str | None = None, pedido_id: int | None = None) -> int:
    ordem = (db.query(func.count(AsRunEvento.id)).filter_by(programa_id=programa_id).scalar() or 0) + 1
    evento = AsRunEvento(
        account_id=account_id, programa_id=programa_id, ordem=ordem, tipo=tipo,
        texto=(texto or "")[:_TAMANHO_MAX_TEXTO], vinheta_id=vinheta_id, patrocinador_id=patrocinador_id,
        video_id=video_id, pedido_id=pedido_id, status="enviado",
    )
    db.add(evento)
    db.commit()
    return evento.id


def confirmar_evento(db: Session, account_id: int, programa_id: int, evento_id: int, status: str) -> AsRunEvento | None:
    """Devolve o evento atualizado, ou None quando nao existe para esta conta e programa. Status fora de
    STATUS_VALIDOS_PLAYER levanta ValueError (o router converte em 400)."""
    if status not in STATUS_VALIDOS_PLAYER:
        raise ValueError(f"status invalido: {status}")
    evento = db.query(AsRunEvento).filter_by(id=evento_id, account_id=account_id, programa_id=programa_id).first()
    if evento is None:
        return None
    evento.status = status
    evento.confirmado_em = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    return evento
