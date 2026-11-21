import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AsRunEvento(Base):
    """O que foi ao ar (F11, item 1): uma linha por bloco entregue pelo /proxima.

    Nasce "enviado" quando o backend entrega o bloco. Vira "confirmado" quando o player reporta que tocou
    (fim natural do audio) e "falhou" quando o player reporta erro. Sem confirmacao, o bloco nao conta como
    "foi ao ar". FK sem cascata: as exclusoes de programa e de radialista (app/config/router.py) apagam antes.
    """

    __tablename__ = "as_run_eventos"
    __table_args__ = (Index("ix_as_run_eventos_programa_criado", "programa_id", "criado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)
    # Ordem de entrega dentro do programa (1, 2, ...): o relatorio le na ordem em que foi ao ar.
    ordem: Mapped[int] = mapped_column(Integer)
    # "fala" | "vinheta" | "patrocinador" | "musica" | "identificacao" (tipo do bloco, ver LiveProgramResponse.tipo).
    tipo: Mapped[str] = mapped_column(String)
    # Texto falado (ou vazio em vinheta/musica). Pode ter nome de ouvinte: nunca vai para log.
    texto: Mapped[str] = mapped_column(String, default="")
    vinheta_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patrocinador_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pedido_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "enviado" | "confirmado" | "falhou"
    status: Mapped[str] = mapped_column(String, default="enviado")
    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    confirmado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
