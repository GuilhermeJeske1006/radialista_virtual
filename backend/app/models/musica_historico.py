import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MusicaHistorico(Base):
    """Registro persistente de musica tocada no ao vivo (sobrevive entre transmissoes,
    ao contrario do historico de sessao no Redis, que expira em algumas horas -- ver
    _historico_musicas em app.live.router). Guarda tanto musica escolhida automaticamente
    (origem "auto") quanto pedido real do ouvinte via WhatsApp (origem "pedido_ouvinte"),
    pra dar sinal de longo prazo de que genero/artista o publico mais pede (ver
    _pedidos_publico_mais_frequentes em app.live.router).
    """

    __tablename__ = "musica_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)

    # Preenchido so' quando a musica veio do catalogo persistente (ver app.live.song_service --
    # sugestao da LLM no formato "Artista - Musica"); nulo pras demais origens (musica_permitida
    # texto livre, pedido_ouvinte, genero de bloco customizado), que ainda nao passam pelo
    # catalogo. Nao remove video_id/titulo/canal acima: continuam sendo a fonte usada por
    # _pedidos_publico_mais_frequentes e pelo historico/auditoria existentes.
    song_id: Mapped[int | None] = mapped_column(ForeignKey("musicas.id"), nullable=True, index=True)

    video_id: Mapped[str] = mapped_column(String)
    titulo: Mapped[str] = mapped_column(String)
    canal: Mapped[str] = mapped_column(String)

    query: Mapped[str] = mapped_column(String)
    # Query normalizada (sem acento, minuscula) pra agrupar pedidos equivalentes escritos
    # de formas diferentes (ex.: "Chitaozinho e Xororo" e "chitãozinho e xororó").
    query_normalizada: Mapped[str] = mapped_column(String, index=True)

    # auto (escolhida pelo sistema a partir da config do programa) | pedido_ouvinte (via WhatsApp)
    origem: Mapped[str] = mapped_column(String, index=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True
    )
