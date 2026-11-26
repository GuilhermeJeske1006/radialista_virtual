import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class GravacaoPrograma(Base):
    __tablename__ = "gravacoes_programa"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)
    audio_path: Mapped[str] = mapped_column(String)
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    escopo: Mapped[str] = mapped_column(String, default="completo")
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc))
    expira_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
