import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FalaEmRevisao(Base):
    """Fala que o roteamento (F12, app.live.roteamento_revisao) não deixou ir ao ar sozinha.

    Guarda o texto original (pode ter nome de ouvinte: nunca vai para log). Estados em app.live.revisao.
    FK sem cascata: as exclusões de programa e de radialista (app/config/router.py) apagam antes.
    """

    __tablename__ = "falas_em_revisao"
    __table_args__ = (Index("ix_falas_em_revisao_programa_estado", "programa_id", "estado"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)
    categoria: Mapped[str] = mapped_column(String, default="")
    texto: Mapped[str] = mapped_column(String, default="")
    rota: Mapped[str] = mapped_column(String)
    motivo: Mapped[str] = mapped_column(String, default="revisao")
    estado: Mapped[str] = mapped_column(String)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    prazo_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decidido_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
