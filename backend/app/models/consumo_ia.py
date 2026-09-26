"""Livro de consumo conservador em microrreais, independente da transação da rota."""
from sqlalchemy import BigInteger, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class OrcamentoIA(Base):
    __tablename__ = "orcamentos_ia"
    account_id: Mapped[int] = mapped_column(primary_key=True)
    mes: Mapped[str] = mapped_column(String(7), primary_key=True)
    comprometido: Mapped[int] = mapped_column(BigInteger, default=0)


class ConsumoIA(Base):
    __tablename__ = "consumos_ia"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[int] = mapped_column(index=True)
    mes: Mapped[str] = mapped_column(String(7), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    modelo: Mapped[str] = mapped_column(String(80))
    reservado: Mapped[int] = mapped_column(BigInteger)
    custo: Mapped[int] = mapped_column(BigInteger)
    # Reservas desconhecidas continuam comprometidas; nunca liberar por timeout.
    estado: Mapped[str] = mapped_column(String(20), default="reservado")
    unidades: Mapped[dict] = mapped_column(JSON, default=dict)
