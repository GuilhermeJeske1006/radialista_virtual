import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class RadioConfig(Base):
    """Um radialista (agente): identidade e voz.

    O numero de WhatsApp e' um so por conta (radio), compartilhado por todos os
    radialistas -- ver Account.wuzapi_token (app/models/account.py).

    Tom, topicos, mensagens, musicas, noticias e pesquisa ficam no Programa
    (app/models/programa.py) -- um mesmo locutor pode apresentar programas
    com conteudo e regras diferentes em horarios diferentes.
    """

    __tablename__ = "radio_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Uma conta pode ter varios radialistas (agentes), todos atendendo pelo mesmo numero de WhatsApp.
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome_locutor: Mapped[str] = mapped_column(String, default="Ze do Radio")

    # Personalidade/comportamento do locutor (texto livre), usado no prompt do LLM.
    personalidade: Mapped[str] = mapped_column(String, default="")

    # Id de uma das vozes do catalogo (app/tts/voices.py). Nulo = usa a voz padrao configurada no servidor.
    voz_id: Mapped[str | None] = mapped_column(String, nullable=True)

    timezone: Mapped[str] = mapped_column(String, default="America/Sao_Paulo")

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    resposta_automatica_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
