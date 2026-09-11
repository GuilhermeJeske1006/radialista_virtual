import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Noticia(Base):
    """Item de pauta apurado pelo worker assincrono (ver app.news.worker) a partir de RSS de
    fontes cadastradas (ver FonteNoticia) -- e' a materia-prima real que falta pro bloco de
    noticia do ao vivo hoje (ver app.news.pauta.proxima_noticia), em vez de so' uma regra
    editorial sem fato nenhum por tras.

    `detalhes` guarda os campos de "lauda" extraidos na curadoria (ver app.news.curadoria):
    quando, onde, numeros, pessoas, impacto, servico, proximo_passo, ainda_nao_divulgado --
    o mesmo formato que vira o bloco "PAUTA DESTE BLOCO" injetado no prompt (ver
    app.news.pauta.montar_lauda). Nem todo campo vem preenchido: RSS costuma trazer so
    titulo/resumo, o resto e' o que a curadoria conseguiu extrair dali.
    """

    __tablename__ = "noticias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    fonte_id: Mapped[int | None] = mapped_column(ForeignKey("fontes_noticia.id"), nullable=True, index=True)

    # Duplicados da fonte no momento da coleta -- sobrevivem mesmo se a fonte for editada/excluida
    # depois, pra manter a atribuicao original da materia intacta (ver Fase 7, rastreabilidade).
    fonte_nome: Mapped[str] = mapped_column(String)
    fonte_tipo: Mapped[str] = mapped_column(String, default="imprensa")

    titulo: Mapped[str] = mapped_column(String)
    resumo: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String)
    # sha256(url) -- indice unico de dedupe: a mesma materia costuma chegar por mais de um feed.
    url_hash: Mapped[str] = mapped_column(String, unique=True, index=True)

    publicado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    coletado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True
    )

    # seguranca | transito | clima_defesa_civil | saude | economia | servico_publico |
    # agenda_cultura | geral -- taxonomia fixa atribuida na curadoria (ver
    # app.news.curadoria._CATEGORIAS_NOTICIA), cruzada com Programa.tipos_noticias (texto livre)
    # na hora de montar a pauta (ver app.news.pauta._categoria_permitida).
    categoria: Mapped[str] = mapped_column(String, default="geral", index=True)
    cidade: Mapped[str] = mapped_column(String, default="")

    # Score de noticiabilidade (0-100) atribuido na curadoria: proximidade da cidade, impacto,
    # atualidade e peso da fonte -- usado por proxima_noticia pra ordenar candidatos.
    score: Mapped[float] = mapped_column(Float, default=0.0)

    # False quando a curadoria descarta (topico proibido, termo sempre bloqueado) -- mantida na
    # tabela por auditoria, mas nunca mais concorre a virar pauta.
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # True quando o worker detecta que a propria fonte retificou esta materia depois (ver
    # app.news.worker._detectar_retificacao) -- dispara correcao explicita no proximo bloco de
    # noticia deste programa (ver Fase 7 do plano de jornalismo, app.news.pauta.correcao_pendente).
    retificada: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    texto_retificacao: Mapped[str] = mapped_column(String, default="")

    detalhes: Mapped[dict] = mapped_column(JSON, default=dict)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
