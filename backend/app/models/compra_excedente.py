import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CompraExcedente(Base):
    """Bloco de mensagens extras comprado avulso (fora do limite do plano).

    Ligado a um mes_referencia ("YYYY-MM") pra que o excedente valha so
    naquele mes, no mesmo espirito do reset mensal de LimitesPlano.mensagens_mes.
    """

    __tablename__ = "compras_excedente"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    quantidade: Mapped[int] = mapped_column(Integer)
    mes_referencia: Mapped[str] = mapped_column(String)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
