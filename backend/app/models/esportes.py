"""Piloto editorial: tabelas próprias, sem alterar o fluxo dos programas ao vivo."""
from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PerfilEsportivo(Base):
    __tablename__ = "perfis_esportivos"
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id", ondelete="CASCADE"), primary_key=True)
    dados: Mapped[dict] = mapped_column(JSON)


class FonteEsportiva(Base):
    __tablename__ = "fontes_esportivas"
    __table_args__ = (UniqueConstraint("account_id", "dominio"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    dominio: Mapped[str] = mapped_column(String)
    dados: Mapped[dict] = mapped_column(JSON)
    historico: Mapped[list] = mapped_column(JSON, default=list)
    revisao: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": revisao}


class EdicaoEsportiva(Base):
    __tablename__ = "edicoes_esportivas"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id", ondelete="CASCADE"), index=True)
    dados: Mapped[dict] = mapped_column(JSON)
    audios: Mapped[dict] = mapped_column(JSON, default=dict)
    aprovacao_roteiro: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    aprovacao_audio: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    historico: Mapped[list] = mapped_column(JSON, default=list)
    revisao: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": revisao}
