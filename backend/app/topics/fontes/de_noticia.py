"""Deriva ganchos de conversa a partir de uma Noticia ja apurada (ver app.news.worker) --
fonte principal do banco de assuntos (ver Fase B do plano-assuntos.md). Roda no worker, depois
da coleta de noticia e antes do casamento por programa (ver app.topics.pipeline).
"""

import datetime
import logging

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.assunto import Assunto
from app.models.noticia import Noticia
from app.news.pauta import _JANELA_VALIDADE_HORAS
from app.topics.derivador import derivar_ganchos

logger = logging.getLogger("radialista.topics.fontes.de_noticia")


def _ja_derivada(db: Session, noticia_id: int) -> bool:
    return db.query(Assunto.id).filter_by(origem="noticia", origem_ref_id=noticia_id).first() is not None


def derivar_de_noticia(db: Session, noticia: Noticia, account: Account) -> list[Assunto]:
    """Deriva e persiste os ganchos desta noticia como Assunto -- no-op (lista vazia) se ja
    tiver sido derivada antes (ver _ja_derivada) ou se o derivador nao achar materia real."""
    if _ja_derivada(db, noticia.id):
        return []

    texto_fonte = f"Titulo: {noticia.titulo}\nResumo: {noticia.resumo}\nFonte: {noticia.fonte_nome}"
    ganchos = derivar_ganchos(texto_fonte, contexto=f"Cidade da radio: {account.cidade or 'nao informada'}")
    if not ganchos:
        return []

    janela_horas = _JANELA_VALIDADE_HORAS.get(noticia.categoria, 48)
    validade_ate = noticia.publicado_em + datetime.timedelta(hours=janela_horas)
    if validade_ate.tzinfo is None:
        validade_ate = validade_ate.replace(tzinfo=datetime.timezone.utc)

    assuntos = []
    for gancho in ganchos:
        assunto = Assunto(
            account_id=account.id,
            origem="noticia",
            origem_ref_id=noticia.id,
            titulo=gancho.titulo,
            gancho=gancho.gancho,
            fatos=gancho.fatos,
            tags=gancho.tags,
            pergunta_ouvinte=gancho.pergunta_ouvinte,
            validade_ate=validade_ate,
            peso_base=noticia.score / 10.0,
            url_origem=noticia.url,
        )
        db.add(assunto)
        assuntos.append(assunto)
    db.commit()
    return assuntos
