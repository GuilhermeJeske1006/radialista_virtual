import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CategoriaVinheta(Base):
    """Categoria de vinhetagem da conta (ex.: "Abertura", "Vinhetas", "Comerciais").
    Agrupa itens de BibliotecaAudioItem e Patrocinador -- ver app/categorias_vinheta/router.py.
    """

    __tablename__ = "categorias_vinheta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome: Mapped[str] = mapped_column(String)

    # "biblioteca" (audio pro cartwall, BibliotecaAudioItem) ou "propaganda" (Patrocinador) --
    # define que tipo de inserção pode entrar nessa categoria, ver app/categorias_vinheta/router.py.
    tipo: Mapped[str] = mapped_column(String, default="biblioteca")

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
