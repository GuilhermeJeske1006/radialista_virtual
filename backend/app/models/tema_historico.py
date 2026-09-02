import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TemaHistorico(Base):
    """Registro persistente de tema/assunto de comentario ou noticia ja abordado no ao vivo
    (sobrevive entre transmissoes e entre programas, ao contrario do historico de sessao no
    Redis, que expira em algumas horas e so' cobre o programa atual -- ver _historico_temas em
    app.live.router). Consultado por radio_config (join com Programa) pra nenhum programa da
    mesma radio repetir um assunto que outro programa (ou o proprio, em transmissao anterior)
    ja abordou recentemente -- ver _temas_recentes_da_radio.
    """

    __tablename__ = "tema_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)

    tema: Mapped[str] = mapped_column(String)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True
    )
