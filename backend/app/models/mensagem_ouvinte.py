import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class MensagemOuvinte(Base):
    """Inbox persistente: bolhas agrupadas continuam identificáveis nas reentregas."""

    __tablename__ = "mensagens_ouvintes"
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String, unique=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"))
    programa_id: Mapped[int | None] = mapped_column(
        ForeignKey("programas.id"), nullable=True
    )
    telefone: Mapped[str] = mapped_column(String, index=True)
    texto: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String, default="pendente", index=True)
    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
