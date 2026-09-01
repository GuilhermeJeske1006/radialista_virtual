import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Notificacao(Base):
    """Notificacao in-app de um usuario (nao da conta inteira -- cada pessoa marca a
    propria como lida). Gerada por app/notificacoes/service.py a partir de eventos reais
    (webhook do Stripe, convite aceito, WhatsApp desconectado -- ver alertar_desconexao.py).
    """

    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)

    # billing | whatsapp | equipe -- origem do evento, usado so pra exibicao (icone/filtro).
    tipo: Mapped[str] = mapped_column(String)

    titulo: Mapped[str] = mapped_column(String)
    mensagem: Mapped[str] = mapped_column(String)

    # Rota do painel pra onde o clique na notificacao leva. Nulo = notificacao informativa, sem destino.
    link: Mapped[str | None] = mapped_column(String, nullable=True)

    lida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
