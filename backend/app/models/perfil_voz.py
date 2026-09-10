"""Metadados do provedor e escolhas de interpretação isoladas por conta."""
import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MetadadosVoz(Base):
    __tablename__ = "metadados_vozes"
    voz_id: Mapped[str] = mapped_column(String, primary_key=True)
    categoria: Mapped[str] = mapped_column(String, default="desconhecida")
    idioma: Mapped[str | None] = mapped_column(String, nullable=True)
    sotaque: Mapped[str | None] = mapped_column(String, nullable=True)
    requer_verificacao: Mapped[bool] = mapped_column(Boolean, default=False)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))


class ConfiguracaoVoz(Base):
    __tablename__ = "configuracoes_vozes"
    __table_args__ = (UniqueConstraint("account_id", "voz_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    voz_id: Mapped[str] = mapped_column(String)
    modelo: Mapped[str | None] = mapped_column(String, nullable=True)
    perfil: Mapped[str] = mapped_column(String, default="atual")
    formato: Mapped[str] = mapped_column(String, default="mp3_44100_128")
    pronuncias: Mapped[dict] = mapped_column(JSON, default=dict)
