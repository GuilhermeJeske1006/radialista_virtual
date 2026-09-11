import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NoticiaHistorico(Base):
    """Registro persistente de noticia (da tabela `noticias`) que foi ao ar num bloco de
    programa -- espelho de MusicaHistorico, mas pro lado editorial. Ao contrario de
    TemaHistorico (que proibe repetir o mesmo assunto), aqui a repeticao da MESMA noticia e' o
    esperado -- e' assim que radio de verdade funciona (ver Fase 6 do plano de jornalismo) --
    so que sempre com angulo novo (campo `angulo`, rotacionado por
    app.news.pauta.proxima_noticia) e abertura de fala diferente da vez anterior. Serve tambem
    de auditoria: qual noticia foi ao ar, com que angulo e que fala exata, pra rastreabilidade
    (Fase 7) e pro limite de repeticoes por transmissao.
    """

    __tablename__ = "noticia_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), index=True)
    noticia_id: Mapped[int] = mapped_column(ForeignKey("noticias.id"), index=True)

    # fato | impacto | servico | reacao | contexto (ver app.news.pauta._ANGULOS_NOTICIA)
    angulo: Mapped[str] = mapped_column(String)
    fala: Mapped[str] = mapped_column(String)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True
    )
