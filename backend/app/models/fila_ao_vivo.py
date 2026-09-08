import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FilaAoVivo(Base):
    """Pedidos de ouvintes (via WhatsApp) esperando pra entrar no programa ao vivo.

    O novo atendimento separa o relato privado do conteúdo aprovado e só marca
    atendido após confirmação de reprodução. Registros legados preservam seu histórico.
    """

    __tablename__ = "fila_ao_vivo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"), index=True)

    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), nullable=True, index=True)
    transmissao: Mapped[str | None] = mapped_column(String, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="em_fila", index=True)
    eventos: Mapped[list] = mapped_column(JSON, default=list)
    texto_autorizado: Mapped[str] = mapped_column(Text, default="")
    motivo: Mapped[str] = mapped_column(String, default="")
    selecao_token: Mapped[str | None] = mapped_column(String, nullable=True)
    selecionado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telefone: Mapped[str] = mapped_column(String, index=True)
    nome: Mapped[str] = mapped_column(String, default="")

    # abraco | musica | sorteio
    tipo: Mapped[str] = mapped_column(String, index=True)

    # recado_comum | participacao_sorteio | reacao_engracada | pedido_musica | reclamacao | pergunta | outro
    natureza: Mapped[str] = mapped_column(String, default="outro")

    mensagem_usuario: Mapped[str] = mapped_column(Text)
    musica_query: Mapped[str | None] = mapped_column(String, nullable=True)

    atendido: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    atendido_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
