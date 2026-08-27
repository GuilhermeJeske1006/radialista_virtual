import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Account(Base):
    """Representa a radio (tenant). Login/pessoa vive em Usuario (varios por conta)."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    usuarios = relationship("Usuario", back_populates="account")

    @property
    def email(self) -> str | None:
        """Compat pra billing/stripe_client.py -- email do usuario admin da conta."""
        admin = next((u for u in self.usuarios if u.role == "admin" and u.ativo), None)
        return admin.email if admin else None

    # Dados da emissora (unicos por conta -- todos os radialistas da conta falam pela mesma radio).
    nome_radio: Mapped[str] = mapped_column(String, default="")
    slogan: Mapped[str] = mapped_column(String, default="")
    frequencia: Mapped[str] = mapped_column(String, default="")
    telefone: Mapped[str] = mapped_column(String, default="")
    endereco: Mapped[str] = mapped_column(String, default="")

    # Cidade usada pro locutor saber a previsao do tempo real (app/weather/client.py) --
    # separada de endereco porque endereco e' texto livre, sem geocoding confiavel.
    cidade: Mapped[str] = mapped_column(String, default="")

    # trial | ativo | inadimplente | cancelado
    plano_status: Mapped[str] = mapped_column(String, default="trial")

    # starter | growth | professional -- ver app/planos.py pros limites de cada um.
    plano: Mapped[str] = mapped_column(String, default="starter")

    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Agentes comprados avulso, alem do que o plano ja inclui (ver PRECO_AGENTE_ADICIONAL) --
    # somado ao limite base do plano em app/billing/limites.py:limite_agentes_efetivo.
    agentes_extras: Mapped[int] = mapped_column(Integer, default=0)

    # Cada conta (radio) tem um unico numero de WhatsApp, compartilhado por todos
    # os radialistas/agentes. Token usado pra autenticar chamadas ao WuzAPI (header "token").
    # Nulo ate a conta concluir o onboarding (criar usuario + conectar sessao no WuzAPI).
    wuzapi_token: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)

    # Id interno do usuario no WuzAPI (campo "userID" no payload do webhook --
    # o WuzAPI nao reenvia o "token" no corpo do webhook, so esse id).
    wuzapi_user_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)

    # Chave HMAC configurada no WuzAPI (app/whatsapp/session_manager.py::configurar_hmac) --
    # usada pra verificar a assinatura x-hmac-signature de todo webhook recebido em
    # /webhook/whatsapp, unica forma de confirmar que a chamada veio mesmo do WuzAPI
    # (e nao de alguem forjando o "userID", que e' sequencial e nao secreto).
    wuzapi_hmac_key: Mapped[str | None] = mapped_column(String, nullable=True)

    # True assim que o WhatsApp conecta pela primeira vez (onboarding concluido) --
    # usado so pra disparar o e-mail de boas-vindas uma unica vez (ver
    # app/onboarding/router.py::status_sessao), ja que o status e' pollado a cada 3s.
    onboarding_email_enviado: Mapped[bool] = mapped_column(Boolean, default=False)

    # True enquanto a sessao do WhatsApp esta caida E o alerta ja foi mandado pro admin
    # (ver app/onboarding/alertar_desconexao.py) -- evita reenviar e-mail a cada execucao
    # do job. Volta pra False assim que a sessao reconecta, pra proxima queda avisar de novo.
    wuzapi_desconectado_alerta_enviado: Mapped[bool] = mapped_column(Boolean, default=False)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
