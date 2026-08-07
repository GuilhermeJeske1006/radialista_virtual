import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"), index=True)

    telefone: Mapped[str] = mapped_column(String, index=True)
    mensagem_usuario: Mapped[str] = mapped_column(Text)
    resposta: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ok | bloqueado_horario | bloqueado_rate_limit | bloqueado_conteudo
    status: Mapped[str] = mapped_column(String)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
