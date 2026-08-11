import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ConviteUsuario(Base):
    __tablename__ = "convites_usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), index=True)
    email: Mapped[str] = mapped_column(String, index=True)

    # admin | membro -- role que o usuario recebe ao aceitar o convite.
    role: Mapped[str] = mapped_column(String, default="membro")

    # Guardamos o hash (sha256) do token, nunca o valor em texto puro -- mesmo
    # padrao de PasswordResetToken.token_hash, so pra permitir lookup por igualdade.
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)

    convidado_por_usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"))

    expira_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    aceito_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revogado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
