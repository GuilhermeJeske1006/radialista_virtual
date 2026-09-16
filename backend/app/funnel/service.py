"""Métricas próprias do funil: eventos limitados, sem conteúdo de formulários."""
import datetime
import logging
import uuid

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.database import Base

logger = logging.getLogger("radialista.funnel")


class Campaign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Só códigos de campanha; e-mail, URLs, texto livre e dados pessoais não são aceitos.
    utm_source: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    utm_medium: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    utm_campaign: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    utm_content: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    utm_term: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")


class FunnelEvent(Base):
    __tablename__ = "funnel_events"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    evento: Mapped[str] = mapped_column(String(40), index=True)
    local: Mapped[str] = mapped_column(String(40), default="register")
    plano: Mapped[str] = mapped_column(String(20), default="")
    campanha: Mapped[dict] = mapped_column(JSON, default=dict)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    valor_centavos: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)


def record_event(db: Session, evento: str, *, event_id: str | None = None, account_id: int | None = None,
                 plano: str = "", campanha: dict | None = None, local: str = "register", valor_centavos: int = 0) -> None:
    """Savepoint: falha de medição nunca desfaz cadastro/pagamento. Chamador controla commit."""
    try:
        with db.begin_nested():
            key = event_id or str(uuid.uuid4())
            if db.get(FunnelEvent, key) is not None:
                return
            if campanha is None and account_id:
                source = db.get(FunnelEvent, f"account:{account_id}")
                campanha = source.campanha if source else {}
            db.add(FunnelEvent(id=key, evento=evento, local=local, plano=plano, campanha=campanha or {},
                               account_id=account_id, valor_centavos=valor_centavos))
            db.flush()
    except SQLAlchemyError:
        logger.warning("Não foi possível registrar evento do funil: %s", evento)
