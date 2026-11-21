import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PromessaNoAr(Base):
    """Promessa feita no ar (F4, app.live.promessas): "daqui a pouco tem recado", "depois do intervalo...".

    Única fonte de verdade das promessas (decisão D3): sem Redis, porque o Redis da F3 falha aberto e esquecer
    uma promessa é vencê-la. Estados: aberta → cumprida | cancelada (contingência dita) | vencida. As exclusões
    de programa e de radialista (app/config/router.py) apagam estas linhas à mão: a FK não tem cascata.
    """

    __tablename__ = "promessas_no_ar"
    __table_args__ = (Index("ix_promessas_no_ar_programa_ocorrencia_estado", "programa_id", "ocorrencia", "estado"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)
    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"), index=True)
    # Ocorrencia.chave (app.live.relogio.ocorrencia_em, vale sem relógio); fora da grade: "manual:<data local>".
    ocorrencia: Mapped[str] = mapped_column(String, index=True)
    # Idempotência: um registro por (request_id, trecho).
    request_id: Mapped[str] = mapped_column(String, default="")
    tipo: Mapped[str] = mapped_column(String)
    classe: Mapped[str] = mapped_column(String, default="")
    marcador: Mapped[str] = mapped_column(String, default="")
    # Pode ter nome de ouvinte: nunca vai para log.
    trecho: Mapped[str] = mapped_column(Text, default="")
    evento_alvo: Mapped[str] = mapped_column(String)
    evento_tipo: Mapped[str] = mapped_column(String, default="")
    evento_rotulo: Mapped[str] = mapped_column(String, default="")
    prazo: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    prazo_posicao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="aberta", index=True)
    motivo: Mapped[str] = mapped_column(String, default="")
    contingencia: Mapped[str] = mapped_column(Text, default="")
    eventos: Mapped[list] = mapped_column(JSON, default=list)
    criada_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    resolvida_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
