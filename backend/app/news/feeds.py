"""Leitura de feeds RSS/Atom das fontes cadastradas (ver app.models.fonte_noticia).

Roda so' dentro do worker assincrono (ver app.news.worker), nunca no caminho de fala do ao
vivo -- um feed lento ou fora do ar nao pode travar a locucao (ver Fase 1 do plano de
jornalismo, "apuracao e' assincrona, fala e' sincrona").
"""

import calendar
import dataclasses
import datetime
import html
import logging
import re

import feedparser
import httpx

from app.models.fonte_noticia import FonteNoticia

logger = logging.getLogger("radialista.news.feeds")

_TIMEOUT_SEGUNDOS = 8.0
_USER_AGENT = "LocufyNewsWorker/1.0 (+https://locufy.com)"

_TAG_HTML_RE = re.compile(r"<[^>]+>")
_ESPACOS_RE = re.compile(r"\s+")


def _sem_html(texto: str) -> str:
    """Muitos feeds (ex.: G1) mandam o resumo com marcacao HTML (<img>, <br>, entidade &amp;
    etc.) -- sem limpar isso aqui, a tag vaza pro prompt do LLM (ver app.news.pauta.montar_lauda,
    que usa Noticia.resumo cru) e pode ate' ser lida ao vivo pelo locutor."""
    sem_tags = _TAG_HTML_RE.sub(" ", texto)
    return _ESPACOS_RE.sub(" ", html.unescape(sem_tags)).strip()


@dataclasses.dataclass
class ItemFeed:
    titulo: str
    resumo: str
    url: str
    publicado_em: datetime.datetime


def _data_publicacao(entrada: dict) -> datetime.datetime:
    """feedparser ja' devolve published_parsed/updated_parsed como struct_time em UTC quando
    consegue interpretar a data do feed -- sem isso (feed mal formado, campo ausente), usa o
    momento da coleta: melhor superestimar o frescor de uma materia real do que descartar ela
    por falta de data explicita."""
    estrutura = entrada.get("published_parsed") or entrada.get("updated_parsed")
    if estrutura:
        try:
            return datetime.datetime.fromtimestamp(calendar.timegm(estrutura), tz=datetime.timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    return datetime.datetime.now(datetime.timezone.utc)


def ler_feed(fonte: FonteNoticia) -> list[ItemFeed]:
    """Baixa e interpreta um feed RSS/Atom. Tolerante a qualquer falha (rede, timeout, XML
    quebrado, feed inexistente): devolve lista vazia em vez de propagar excecao, porque uma
    fonte com problema nunca pode derrubar a coleta das demais (ver
    test_worker_com_feed_quebrado_nao_derruba_coleta)."""
    if not fonte.url_feed:
        return []

    cabecalhos = {"User-Agent": _USER_AGENT}
    if fonte.etag:
        cabecalhos["If-None-Match"] = fonte.etag
    if fonte.last_modified:
        cabecalhos["If-Modified-Since"] = fonte.last_modified

    try:
        resposta = httpx.get(fonte.url_feed, headers=cabecalhos, timeout=_TIMEOUT_SEGUNDOS, follow_redirects=True)
    except httpx.HTTPError:
        logger.warning("Falha ao baixar feed: fonte_id=%s url=%s", fonte.id, fonte.url_feed, exc_info=True)
        return []

    if resposta.status_code == 304:
        return []
    if resposta.status_code >= 400:
        logger.warning(
            "Feed respondeu com erro: fonte_id=%s url=%s status=%s", fonte.id, fonte.url_feed, resposta.status_code
        )
        return []

    fonte.etag = resposta.headers.get("etag", "") or ""
    fonte.last_modified = resposta.headers.get("last-modified", "") or ""

    try:
        interpretado = feedparser.parse(resposta.content)
    except Exception:
        logger.warning("Falha ao interpretar feed: fonte_id=%s url=%s", fonte.id, fonte.url_feed, exc_info=True)
        return []

    itens = []
    for entrada in getattr(interpretado, "entries", []) or []:
        titulo = (entrada.get("title") or "").strip()
        url = (entrada.get("link") or "").strip()
        if not titulo or not url:
            continue
        resumo = _sem_html(entrada.get("summary") or entrada.get("description") or "")
        itens.append(ItemFeed(titulo=titulo, resumo=resumo, url=url, publicado_em=_data_publicacao(entrada)))
    return itens
