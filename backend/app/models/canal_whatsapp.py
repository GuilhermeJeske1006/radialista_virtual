"""Estado durável do canal. Nenhuma destas tabelas substitui o histórico legado."""
import datetime
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


def agora():
    return datetime.datetime.now(datetime.timezone.utc)


class EntradaWhatsapp(Base):
    __tablename__ = "whatsapp_entradas"
    __table_args__ = (Index("ix_whatsapp_entrada_trabalho", "estado", "disponivel_em"),
                      Index("ix_whatsapp_entrada_conversa", "account_id", "telefone", "estado"))
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String, unique=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"))
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), nullable=True)
    telefone: Mapped[str] = mapped_column(String, index=True)
    nome: Mapped[str] = mapped_column(String, default="")
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True)
    citada_id: Mapped[str | None] = mapped_column(String, nullable=True)
    from_me: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo: Mapped[str] = mapped_column(String, default="texto")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="pendente", index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str] = mapped_column(String, default="")
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)
    disponivel_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)


class PreferenciasCanal(Base):
    __tablename__ = "whatsapp_preferencias"
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    notificar_resultado: Mapped[bool] = mapped_column(Boolean, default=False)


class StatusWhatsapp(Base):
    __tablename__ = "whatsapp_status"
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    dados: Mapped[dict] = mapped_column(JSON, default=dict)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class EnvioWhatsapp(Base):
    __tablename__ = "whatsapp_envios"
    __table_args__ = (Index("ix_whatsapp_envio_trabalho", "estado", "tentativas"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String, unique=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    log_id: Mapped[int] = mapped_column(ForeignKey("interaction_logs.id"), unique=True)
    telefone: Mapped[str] = mapped_column(String, index=True)
    texto: Mapped[str] = mapped_column(Text)
    automatico: Mapped[bool] = mapped_column(Boolean, default=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    estado: Mapped[str] = mapped_column(String, default="pendente", index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class EventoCanal(Base):
    __tablename__ = "whatsapp_eventos"
    __table_args__ = (UniqueConstraint("account_id", "sequencia"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    sequencia: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String)
    dados: Mapped[dict] = mapped_column(JSON, default=dict)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class LeituraConversa(Base):
    __tablename__ = "whatsapp_leituras"
    __table_args__ = (UniqueConstraint("usuario_id", "conversa_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas_ouvintes.id"))
    ultimo_log_id: Mapped[int] = mapped_column(Integer, default=0)


class ConexaoEventos(Base):
    __tablename__ = "whatsapp_conexoes_eventos"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    expira_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotaConversa(Base):
    __tablename__ = "whatsapp_notas"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas_ouvintes.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    texto: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class ResponsavelConversa(Base):
    __tablename__ = "whatsapp_responsaveis"
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas_ouvintes.id"), primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)


class MemoriaConversa(Base):
    __tablename__ = "whatsapp_memorias"
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas_ouvintes.id"), primary_key=True)
    resumo: Mapped[str] = mapped_column(Text, default="")
    fontes: Mapped[list] = mapped_column(JSON, default=list)
    ultimo_log_id: Mapped[int] = mapped_column(Integer, default=0)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class BlocoReproduzido(Base):
    __tablename__ = "blocos_reproduzidos"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), index=True, nullable=True)
    ocorrencia: Mapped[str] = mapped_column(String)
    token: Mapped[str] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String)
    fala: Mapped[str] = mapped_column(Text, default="")
    assunto_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assunto: Mapped[dict] = mapped_column(JSON, default=dict)
    musica: Mapped[dict] = mapped_column(JSON, default=dict)
    estado: Mapped[str] = mapped_column(String, default="preparado")
    player_id: Mapped[str | None] = mapped_column(String, nullable=True)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class EstadoTransmissao(Base):
    __tablename__ = "estados_transmissao"
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), primary_key=True)
    ocorrencia: Mapped[str] = mapped_column(String)
    player_id: Mapped[str] = mapped_column(String)
    heartbeat_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)
    bloco_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DiscussaoPrograma(Base):
    __tablename__ = "discussoes_programa"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), index=True, nullable=True)
    ocorrencia: Mapped[str] = mapped_column(String)
    bloco_id: Mapped[int] = mapped_column(ForeignKey("blocos_reproduzidos.id"), unique=True)
    assunto_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pergunta: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String, default="aberta")
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class ContribuicaoOuvinte(Base):
    __tablename__ = "contribuicoes_ouvintes"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas_ouvintes.id"))
    log_id: Mapped[int] = mapped_column(ForeignKey("interaction_logs.id"), unique=True)
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), index=True, nullable=True)
    ocorrencia: Mapped[str] = mapped_column(String)
    discussao_id: Mapped[int | None] = mapped_column(ForeignKey("discussoes_programa.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String, default="aguardando_revisao")
    texto_autorizado: Mapped[str] = mapped_column(Text, default="")
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    assunto_id: Mapped[int | None] = mapped_column(ForeignKey("assuntos.id"), nullable=True)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=agora)


class DecisaoPauta(Base):
    __tablename__ = "decisoes_pauta"
    __table_args__ = (UniqueConstraint("programa_id", "assunto_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"))
    assunto_id: Mapped[int] = mapped_column(ForeignKey("assuntos.id"))
    estado: Mapped[str] = mapped_column(String)  # fixado | descartado
