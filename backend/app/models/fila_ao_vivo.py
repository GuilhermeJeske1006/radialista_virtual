import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FilaAoVivo(Base):
    """Pedidos de ouvintes (via WhatsApp) esperando pra entrar no programa ao vivo.

    O bot nunca responde no WhatsApp: mensagens viram um item aqui (tipo "abraco" ou
    "musica") e sao consumidas pelo /live/programa/proxima quando o locutor le o
    recado ou toca a musica no ar.
    """

    __tablename__ = "fila_ao_vivo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"), index=True)

    telefone: Mapped[str] = mapped_column(String, index=True)
    nome: Mapped[str] = mapped_column(String, default="")

    # abraco | musica
    tipo: Mapped[str] = mapped_column(String, index=True)

    mensagem_usuario: Mapped[str] = mapped_column(Text)
    musica_query: Mapped[str | None] = mapped_column(String, nullable=True)

    atendido: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    atendido_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
