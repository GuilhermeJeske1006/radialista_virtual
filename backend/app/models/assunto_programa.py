import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AssuntoPrograma(Base):
    """Casamento de um Assunto (gancho) com um Programa especifico -- ver app.topics.matcher e
    ADR do plano-assuntos.md (secao 1).

    `ponte` e' briefing editorial, NUNCA fala pronta: responde pra quem e' este programa e por
    que o gancho importa pra esse publico -- e' neutro de eixo de proposito (ver
    app.topics.eixos), porque o mesmo briefing serve tanto pra abordar o gancho como FATO quanto
    como PERGUNTA ou MEMORIA. Quem decide o eixo efetivo, olhando o historico de sessao, e'
    app.topics.pauta_conversa -- nunca este registro, que e' escrito uma vez, no match, offline.

    Nao guarda `usado_em`: consumo e' estado de sessao (ver ADR item 1), fica no historico Redis
    de app.topics.pauta_conversa, nao numa coluna aqui -- senao duas transmissoes do mesmo
    programa em dias diferentes colidiriam no mesmo registro.
    """

    __tablename__ = "assuntos_programa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    assunto_id: Mapped[int] = mapped_column(ForeignKey("assuntos.id"), index=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)

    # 0-10, calculado por app.topics.matcher (sobreposicao de tags + ajuste do haiku de
    # casamento, quando ele roda -- ver degradacao por teto diario no matcher).
    score: Mapped[float] = mapped_column(Float, default=0.0)
    ponte: Mapped[str] = mapped_column(String, default="")
    # Subconjunto de app.topics.eixos.EIXOS_ASSUNTO que este gancho rende bem NESTE programa --
    # cardapio, nao escolha final (ver ADR item 1). Vazio = qualquer eixo serve (fallback de
    # degradacao do matcher, ou reserva estrategica, que por ser atemporal rende todos).
    eixos_sugeridos: Mapped[list[str]] = mapped_column(JSON, default=list)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True
    )
