import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String)
    nome: Mapped[str] = mapped_column(String, default="")

    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), index=True)
    account = relationship("Account", back_populates="usuarios")

    # admin | membro -- admin gerencia equipe/config/billing, membro so opera o dia a dia.
    role: Mapped[str] = mapped_column(String, default="membro")

    # Desativado em vez de deletado quando removido da equipe, pra preservar
    # historico (interaction_log, etc) que possa referenciar o usuario no futuro.
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
