import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), index=True)

    # Guardamos o hash (sha256) do token, nunca o valor em texto puro -- mesmo
    # padrao de senha_hash em Usuario, so que aqui e so pra permitir lookup por igualdade.
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)

    expira_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
