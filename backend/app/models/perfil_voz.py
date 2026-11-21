"""Metadados do provedor e escolhas de interpretação isoladas por conta."""
import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
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


class RitmoVoz(Base):
    """Ritmo observado (palavras por minuto) por voz, modelo, perfil e categoria de bloco, medido no
    áudio final da fala (F2, app.live.ritmo_voz). Global por voz, não por conta: o ritmo é da voz e da
    configuração de síntese, e voz clonada já tem id próprio. Só agregados numéricos, nenhum texto.
    Ritmo = palavras / segundos x 60 (segundos sem as pausas explícitas)."""
    __tablename__ = "ritmos_voz"
    __table_args__ = (UniqueConstraint("voz_id", "modelo", "perfil", "categoria"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    voz_id: Mapped[str] = mapped_column(String, index=True)
    modelo: Mapped[str] = mapped_column(String)
    perfil: Mapped[str] = mapped_column(String, default="atual")
    categoria: Mapped[str] = mapped_column(String, default="padrao")
    amostras: Mapped[int] = mapped_column(Integer, default=0)
    palavras: Mapped[float] = mapped_column(Float, default=0.0)
    segundos: Mapped[float] = mapped_column(Float, default=0.0)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
