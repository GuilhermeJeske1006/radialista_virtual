import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class ConversaOuvinte(Base):
    __tablename__ = "conversas_ouvintes"
    __table_args__ = (UniqueConstraint("account_id", "telefone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    telefone: Mapped[str] = mapped_column(String)
    nome: Mapped[str] = mapped_column(String, default="")
    humano: Mapped[bool] = mapped_column(Boolean, default=False)
    historico: Mapped[list] = mapped_column(JSON, default=list)
    pendente: Mapped[dict] = mapped_column(JSON, default=dict)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
