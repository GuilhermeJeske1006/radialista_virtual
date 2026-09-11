"""Worker assíncrono de apuração (ver Fase 1 do plano de jornalismo): lê os feeds das fontes
ativas de cada conta, descarta duplicata (por URL e por título parecido), manda o resto pra
curadoria e grava o que sobra como `Noticia` -- a matéria-prima que app.news.pauta consome no
ao vivo. Roda fora do ciclo de request/resposta (cron externo, ver `python -m app.news.worker`),
nunca no caminho de fala.
"""

import datetime
import hashlib
import logging
import re
import unicodedata

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.account import Account
from app.models.fonte_noticia import FonteNoticia
from app.models.noticia import Noticia
from app.news.curadoria import curar_item
from app.news.feeds import ler_feed

logger = logging.getLogger("radialista.news.worker")

# Mesma noticia costuma chegar por mais de uma fonte (ex.: prefeitura e portal regional cobrindo
# o mesmo fato) com URLs diferentes -- so' o hash de URL nao pega isso, entao tambem compara
# titulo por sobreposicao de palavras dentro dessa janela.
_JANELA_DEDUPE_TITULO_HORAS = 48
_LIMIAR_SIMILARIDADE_TITULO = 0.7
_PONTUACAO_RE = re.compile(r"[^\w\s]")

# Termos que sinalizam que um item de feed é a PRÓPRIA fonte corrigindo uma matéria anterior,
# não uma matéria nova (ver Fase 7 do plano de jornalismo: protocolo de correção no ar). Deixa de
# fora termo genérico demais como "atualização" -- só conta como sinal quando explicitamente fala
# de retificar/corrigir, pra não marcar matéria nova parecida como correção por engano. Aplicado
# sempre sobre texto já sem acento (ver _sem_acento), por isso só a forma ascii aqui.
_TERMOS_RETIFICACAO_RE = re.compile(r"\b(retifica\w*|corrig\w*|correcao\w*|errata\w*)\b")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _palavras(texto: str) -> set[str]:
    sem_pontuacao = _PONTUACAO_RE.sub(" ", _sem_acento(texto.lower()))
    return {p for p in sem_pontuacao.split() if p}


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()


def _titulo_ja_coletado(db: Session, account_id: int, titulo: str, desde: datetime.datetime) -> bool:
    palavras_novo = _palavras(titulo)
    if len(palavras_novo) < 3:
        return False
    recentes = (
        db.query(Noticia.titulo)
        .filter(Noticia.account_id == account_id, Noticia.coletado_em >= desde)
        .all()
    )
    for (titulo_existente,) in recentes:
        palavras_existente = _palavras(titulo_existente)
        if not palavras_existente:
            continue
        similaridade = len(palavras_novo & palavras_existente) / len(palavras_novo | palavras_existente)
        if similaridade >= _LIMIAR_SIMILARIDADE_TITULO:
            return True
    return False


def _e_retificacao(titulo: str) -> bool:
    return bool(_TERMOS_RETIFICACAO_RE.search(_sem_acento(titulo.lower())))


def _achar_noticia_para_retificar(db: Session, account_id: int, titulo: str, desde: datetime.datetime) -> Noticia | None:
    """Acha a matéria original que este item (já identificado como retificação, ver
    _e_retificacao) provavelmente está corrigindo -- mesma heurística de sobreposição de palavras
    de `_titulo_ja_coletado`, ignorando os termos de retificação no título novo (senão eles nunca
    batem com o título original, que não os tem)."""
    palavras_novo = _palavras(_TERMOS_RETIFICACAO_RE.sub(" ", _sem_acento(titulo.lower())))
    if len(palavras_novo) < 3:
        return None
    recentes = (
        db.query(Noticia)
        .filter(Noticia.account_id == account_id, Noticia.coletado_em >= desde, Noticia.retificada.is_(False))
        .all()
    )
    for existente in recentes:
        palavras_existente = _palavras(existente.titulo)
        if not palavras_existente:
            continue
        similaridade = len(palavras_novo & palavras_existente) / len(palavras_novo | palavras_existente)
        if similaridade >= _LIMIAR_SIMILARIDADE_TITULO:
            return existente
    return None


def coletar_fonte(db: Session, account: Account, fonte: FonteNoticia) -> int:
    """Coleta uma fonte e grava as notícias novas. Nunca propaga exceção de rede/parse (ver
    app.news.feeds.ler_feed, já tolerante) nem de curadoria (ver app.news.curadoria.curar_item) --
    o pior caso é essa fonte não render nada nesta rodada, o worker segue pras demais."""
    itens = ler_feed(fonte)
    db.commit()  # persiste etag/last_modified atualizados por ler_feed mesmo sem item novo

    novas = 0
    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_JANELA_DEDUPE_TITULO_HORAS)
    for item in itens:
        url_hash = _url_hash(item.url)
        if db.query(Noticia.id).filter_by(url_hash=url_hash).first():
            continue

        if _e_retificacao(item.titulo):
            original = _achar_noticia_para_retificar(db, account.id, item.titulo, desde)
            if original is not None:
                original.retificada = True
                original.texto_retificacao = item.resumo or item.titulo
                db.commit()
                continue
            # Retificação sem matéria original encontrada (já saiu da janela, ou nunca foi
            # coletada por essa conta) -- nao ha' o que corrigir, mas tambem nao vira noticia
            # nova por engano.
            continue

        if _titulo_ja_coletado(db, account.id, item.titulo, desde):
            continue

        resultado = curar_item(item, fonte_nome=fonte.nome, fonte_tipo=fonte.tipo, cidade=account.cidade, peso_fonte=fonte.peso)
        if resultado is None:
            continue

        db.add(
            Noticia(
                account_id=account.id,
                fonte_id=fonte.id,
                fonte_nome=fonte.nome,
                fonte_tipo=fonte.tipo,
                titulo=item.titulo,
                resumo=resultado.resumo or item.resumo,
                url=item.url,
                url_hash=url_hash,
                publicado_em=item.publicado_em,
                categoria=resultado.categoria,
                cidade=account.cidade or "",
                score=resultado.score,
                ativa=True,
                detalhes={
                    "quando": resultado.quando,
                    "onde": resultado.onde,
                    "numeros": resultado.numeros,
                    "pessoas": resultado.pessoas,
                    "impacto": resultado.impacto,
                    "servico": resultado.servico,
                    "proximo_passo": resultado.proximo_passo,
                    "ainda_nao_divulgado": resultado.ainda_nao_divulgado,
                },
            )
        )
        novas += 1
    db.commit()
    return novas


def coletar_conta(db: Session, account: Account) -> int:
    total = 0
    fontes = db.query(FonteNoticia).filter_by(account_id=account.id, ativa=True).all()
    for fonte in fontes:
        if not fonte.url_feed:
            continue
        try:
            total += coletar_fonte(db, account, fonte)
        except Exception:
            logger.warning("Falha ao coletar fonte: fonte_id=%s url=%s", fonte.id, fonte.url_feed, exc_info=True)
            db.rollback()
    return total


def executar() -> None:
    """Ponto de entrada de uma rodada de coleta -- pra todas as contas, pra todas as fontes
    ativas com feed cadastrado. Pensado pra ser chamado por um agendador externo (cron do
    compose, por exemplo, a cada 10 minutos) via `python -m app.news.worker`."""
    db = SessionLocal()
    try:
        for account in db.query(Account).all():
            try:
                novas = coletar_conta(db, account)
                if novas:
                    logger.info("news_worker_coleta account_id=%s novas=%s", account.id, novas)
            except Exception:
                logger.warning("Falha ao coletar conta no worker de notícias: account_id=%s", account.id, exc_info=True)
                db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executar()
