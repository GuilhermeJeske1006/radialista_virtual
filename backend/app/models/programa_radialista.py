import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ProgramaRadialista(Base):
    """Vinculo de um radialista extra (co-apresentador) a um programa, com papel e
    comportamento proprios. Programa.radio_config_id continua sendo o "dono" -- essa
    tabela so guarda linhas pra participantes explicitamente adicionados pelo usuario
    (incluindo, opcionalmente, uma linha pra customizar papel/comportamento do proprio
    dono). Programa sem nenhuma linha aqui se comporta como hoje (locutor unico).
    """

    __tablename__ = "programa_radialistas"
    __table_args__ = (UniqueConstraint("programa_id", "radio_config_id", name="uq_programa_radialista"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)
    radio_config_id: Mapped[int] = mapped_column(ForeignKey("radio_configs.id"), index=True)

    papel: Mapped[str] = mapped_column(String, default="Apresentador principal")
    comportamento: Mapped[str] = mapped_column(String, default="")
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
