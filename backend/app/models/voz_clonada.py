import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class VozClonada(Base):
    """Voz clonada na ElevenLabs (Instant Voice Cloning) a partir de audio enviado pelo
    usuario -- ver app/tts/client.py::clonar_voz. voz_id e' o id retornado pela ElevenLabs,
    usado do mesmo jeito que os ids do catalogo fixo (app/tts/voices.py) em RadioConfig.voz_id
    e Patrocinador.voz_id. Edicao/exclusao continua restrita a conta que criou (account_id),
    mas uma voz com compartilhada=True fica valida pra qualquer conta usar (ver
    app/tts/voices.py::voz_valida_para_conta).
    """

    __tablename__ = "vozes_clonadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome: Mapped[str] = mapped_column(String)
    voz_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    compartilhada: Mapped[bool] = mapped_column(Boolean, default=False)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
