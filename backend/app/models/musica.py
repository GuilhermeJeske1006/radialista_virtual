import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Musica(Base):
    """Identidade persistente de uma musica (titulo+artista), independente da query de texto
    usada pra encontra-la no YouTube -- catalogo separado do historico de reproducao
    (ver MusicaHistorico). Sem isso, a mesma faixa sugerida pela LLM em momentos diferentes
    (ver sugerir_musica_do_genero em app.llm.client) gerava uma busca nova no YouTube toda vez
    que o texto da sugestao variasse, mesmo ja tendo sido resolvida antes.

    youtube_video_id nulo = musica catalogada mas ainda sem faixa do YouTube resolvida (ver
    resolver_musica_catalogada em app.live.song_service). Uma vez resolvido, sobrevive a um
    flush/restart do Redis -- ao contrario do cache de busca em app.live.music, que e' so'
    Redis com TTL.
    """

    __tablename__ = "musicas"
    __table_args__ = (
        UniqueConstraint("titulo_normalizado", "artista_normalizado", name="uq_musicas_titulo_artista_normalizado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    titulo: Mapped[str] = mapped_column(String)
    artista: Mapped[str] = mapped_column(String)
    # Chave de lookup (sem acento, minusculo, pontuacao removida -- ver _normalizar em
    # app.live.song_service) pra "Jorge & Mateus" e "jorge e mateus" caírem na mesma Musica.
    titulo_normalizado: Mapped[str] = mapped_column(String, index=True)
    artista_normalizado: Mapped[str] = mapped_column(String, index=True)

    youtube_video_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    youtube_titulo: Mapped[str | None] = mapped_column(String, nullable=True)
    youtube_canal: Mapped[str | None] = mapped_column(String, nullable=True)
    # Segundo de inicio do corte (ver SEGUNDOS_PULAR_AO_VIVO em app.live.music) -- preservado
    # pra reconstruir a MusicaEncontrada sem precisar reclassificar "ao vivo" a partir do titulo.
    youtube_inicio_segundos: Mapped[int] = mapped_column(Integer, default=0)
    duracao_segundos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # {"descricao": str, "tags": list[str], "ano": str | None} -- ver _buscar_metadados_musica
    # em app.live.music. Nulo enquanto youtube_video_id tambem for nulo.
    youtube_metadados: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # "alta" (origem ja' e' catalogo validado -- Spotify ou curadoria do admin) | "baixa"
    # (pedido de ouvinte digitado a mao, pode ter erro de digitacao, ou sugestao de texto livre
    # da LLM, que pode "inventar" uma combinacao artista+musica que nao existe de verdade) --
    # ver _confianca_da_origem em app.live.song_service. Nulo enquanto youtube_video_id tambem
    # for nulo (ainda sem resolucao pra avaliar).
    confianca: Mapped[str | None] = mapped_column(String, nullable=True)
    # "pendente" (ainda sem youtube_video_id) | "resolvida" (video encontrado e persistido) |
    # "sem_correspondencia" (uma tentativa de resolucao rodou e o YouTube nao devolveu nada
    # valido) -- ver resolver_musica_catalogada em app.live.song_service. Uma Musica
    # "sem_correspondencia" continua sendo tentada de novo na proxima sugestao (nao ha' logica
    # de pular retry ainda), o status aqui e' so' pra visibilidade/curadoria futura.
    status: Mapped[str] = mapped_column(String, default="pendente")

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    atualizado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
