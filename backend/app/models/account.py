import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String)
    nome: Mapped[str] = mapped_column(String, default="")

    # Dados da emissora (unicos por conta -- todos os radialistas da conta falam pela mesma radio).
    nome_radio: Mapped[str] = mapped_column(String, default="")
    slogan: Mapped[str] = mapped_column(String, default="")
    frequencia: Mapped[str] = mapped_column(String, default="")
    telefone: Mapped[str] = mapped_column(String, default="")
    endereco: Mapped[str] = mapped_column(String, default="")

    # trial | ativo | inadimplente | cancelado
    plano_status: Mapped[str] = mapped_column(String, default="trial")

    # starter | growth | professional | business -- ver app/planos.py pros limites de cada um.
    plano: Mapped[str] = mapped_column(String, default="starter")

    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
