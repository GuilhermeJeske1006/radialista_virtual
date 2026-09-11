import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FonteNoticia(Base):
    """Fonte de apuracao de noticia (feed RSS/Atom de orgao oficial, imprensa ou assessoria)
    cadastrada por conta -- promove o texto livre `Programa.fontes_noticias` a entidade real,
    consumivel pelo worker de coleta (ver app.news.worker). Uma fonte sem url_feed (ex.: seed
    gerada a partir da cidade da conta antes do usuario preencher o feed de verdade, ver
    app.news.seeds_fontes) fica inativa e e' ignorada pelo worker ate ganhar uma URL real --
    nunca inventamos o endereco do feed.
    """

    __tablename__ = "fontes_noticia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    nome: Mapped[str] = mapped_column(String)
    url_feed: Mapped[str] = mapped_column(String, default="")

    # oficial (prefeitura, defesa civil, corpo de bombeiros) | imprensa (portal/jornal) | assessoria
    tipo: Mapped[str] = mapped_column(String, default="imprensa")

    # Multiplicador de score na curadoria (ver app.news.curadoria) -- fonte oficial pesa mais
    # que assessoria por padrao, mas a conta pode ajustar.
    peso: Mapped[float] = mapped_column(Float, default=1.0)

    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    # Cabecalhos de cache condicional (RFC 7232) devolvidos pelo servidor do feed na ultima
    # coleta com sucesso -- evita reprocessar o feed inteiro quando ele nao mudou (ver
    # app.news.feeds.ler_feed). Vazio ate a primeira coleta.
    etag: Mapped[str] = mapped_column(String, default="")
    last_modified: Mapped[str] = mapped_column(String, default="")

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
