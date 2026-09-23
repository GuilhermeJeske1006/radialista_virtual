import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TrilhaVinheta(Base):
    """Trilha instrumental que vai por baixo da voz das vinhetas de um programa (ver
    app/vinhetas/trilha.py). Uma por programa, compartilhada pelas 3 vinhetas dele -- mesma
    identidade sonora e uma unica chamada a Music API."""

    __tablename__ = "trilhas_vinheta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    # Nulo = trilha da radio (nao de um programa especifico).
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), nullable=True, index=True)

    # "ia" (ElevenLabs Music) | "banco" (app/vinhetas/assets/trilhas) | "upload" (enviada pelo usuario).
    origem: Mapped[str] = mapped_column(String)

    # Estilo do banco local (ex.: "sertanejo") ou resumo do pedido feito a IA.
    estilo: Mapped[str | None] = mapped_column(String, nullable=True)

    # Prompt mandado a Music API (so' origem="ia").
    prompt: Mapped[str | None] = mapped_column(String, nullable=True)

    # Caminho relativo no storage (ver app.storage).
    audio_path: Mapped[str] = mapped_column(String)

    duracao_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
