"""Ledger comercial. Valores em microrreais; tarifas publicadas são imutáveis."""
from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


def agora():
    return datetime.now(timezone.utc)


class TarifaIA(Base):
    __tablename__ = 'tarifas_ia'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    provedor: Mapped[str] = mapped_column(String(80))
    modelo: Mapped[str] = mapped_column(String(100), index=True)
    versao: Mapped[str] = mapped_column(String(80))
    # {entrada: {preco: "5", divisor: "1000000"}, ...}
    unidades: Mapped[dict] = mapped_column(JSON)
    moeda: Mapped[str] = mapped_column(String(3), default='USD')
    cambio: Mapped[str] = mapped_column(String(40))
    acrescimo: Mapped[str] = mapped_column(String(40), default='100')
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    descricao: Mapped[str] = mapped_column(String, default='')
    limitacoes: Mapped[str] = mapped_column(String, default='')
    exemplos: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint('tipo', 'modelo', 'versao'),)


class ContaConsumo(Base):
    __tablename__ = 'contas_consumo'
    account_id: Mapped[int] = mapped_column(primary_key=True)
    limite: Mapped[int] = mapped_column(BigInteger, default=0)
    exposicao: Mapped[int] = mapped_column(BigInteger, default=0)
    modelos: Mapped[dict] = mapped_column(JSON, default=dict)
    ciclo_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ciclo_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsoIA(Base):
    __tablename__ = 'usos_ia'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[int] = mapped_column(index=True)
    chave: Mapped[str] = mapped_column(String(200))
    operacao: Mapped[str] = mapped_column(String(100))
    funcionalidade: Mapped[str] = mapped_column(String(80))
    canal: Mapped[str] = mapped_column(String(80))
    contexto: Mapped[dict] = mapped_column(JSON, default=dict)
    tipo: Mapped[str] = mapped_column(String(30))
    modelo: Mapped[str] = mapped_column(String(100))
    tarifa: Mapped[dict] = mapped_column(JSON)
    unidades: Mapped[dict] = mapped_column(JSON, default=dict)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default='reservado', index=True)
    reservado: Mapped[int] = mapped_column(BigInteger)
    custo_bruto: Mapped[int] = mapped_column(BigInteger, default=0)
    reserva_interna: Mapped[int] = mapped_column(BigInteger, default=0)
    preco: Mapped[int] = mapped_column(BigInteger, default=0)
    provedor_request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fatura_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    original_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # encerrar_contexto consulta por operação ao fim de cada request autenticada.
    __table_args__ = (UniqueConstraint('account_id', 'chave'), Index('ix_usos_ia_conta_operacao', 'account_id', 'operacao'))


class FaturaConsumo(Base):
    __tablename__ = 'faturas_consumo'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    account_id: Mapped[int] = mapped_column(index=True)
    assinatura: Mapped[str] = mapped_column(String(100))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30), default='conferindo')
    linhas: Mapped[list] = mapped_column(JSON, default=list)
    consumo: Mapped[int] = mapped_column(BigInteger, default=0)
    total_centavos: Mapped[int] = mapped_column(BigInteger, default=0)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    __table_args__ = (UniqueConstraint('account_id', 'assinatura', 'inicio', 'fim'),)


class EventoCobranca(Base):
    __tablename__ = 'eventos_cobranca'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
