import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Assunto(Base):
    """Um gancho de conversa derivado de uma fonte bruta (noticia, musica, efemeride, pedido de
    ouvinte, ou gerado como reserva estrategica) -- ver plano-assuntos.md, Fase A/B. Materia-prima
    do bloco de comentario do ao vivo, no lugar da lista crua de tags em Programa.assuntos_ao_vivo.

    Um mesmo item bruto (ex.: uma Noticia) explode em varios Assunto (2 a 5 ganchos), cada um com
    seu proprio recorte -- ver app.topics.derivador. O casamento de cada gancho com cada programa
    (score, ponte editorial, eixos que ele rende) fica em AssuntoPrograma, nao aqui: este registro
    e' o fato/gancho em si, independente de programa.
    """

    __tablename__ = "assuntos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)

    # noticia | musica | efemeride | ouvinte | reserva -- ver app.topics.fontes.
    origem: Mapped[str] = mapped_column(String, index=True)
    # id da linha de origem (Noticia.id, MusicaHistorico.id, Musica.id...) quando aplicavel --
    # usado so' pra dedupe (nao derivar o mesmo item bruto duas vezes), nunca por FK de verdade
    # porque a origem varia de tabela conforme `origem` acima.
    origem_ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    titulo: Mapped[str] = mapped_column(String)
    # O gancho de conversa em si -- a ideia, nao a fala pronta (ver ADR item 1: isto e' nota de
    # pauta, quem decide como vira fala e' o eixo, escolhido em app.topics.pauta_conversa).
    gancho: Mapped[str] = mapped_column(String)
    # Fatos reais extraidos SO' do texto de origem (nunca inventados) -- mesma disciplina de
    # app.news.curadoria.curar_item. Lista curta, cada item uma frase/dado citavel.
    fatos: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Pergunta pronta pro locutor jogar pro ouvinte, quando o eixo escolhido for "pergunta" --
    # ver app.topics.eixos.INSTRUCAO_EIXO. Vazio quando o gancho nao rende pergunta natural.
    pergunta_ouvinte: Mapped[str] = mapped_column(String, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Ate' quando este gancho e' valido pra virar pauta -- None = nunca expira (reserva
    # estrategica e almanaque). Noticia expira em 24-48h, efemeride no dia, sazonal em semanas
    # (ver Fase A do plano-assuntos.md).
    validade_ate: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Peso editorial de base (0-10), antes do score especifico por programa em AssuntoPrograma --
    # ex.: reserva estrategica nasce com peso baixo, so' concorre quando o resto ja' esgotou.
    peso_base: Mapped[float] = mapped_column(Float, default=5.0)
    url_origem: Mapped[str] = mapped_column(String, default="")

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True
    )
