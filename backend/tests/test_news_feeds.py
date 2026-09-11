from types import SimpleNamespace

import httpx

from app.models.fonte_noticia import FonteNoticia
from app.news.feeds import ler_feed

_RSS_VALIDO = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Portal Exemplo</title>
<item>
  <title>Rua interditada apos obra na rede de agua</title>
  <link>https://portal.example.com/noticia-1</link>
  <description>Trecho de 300 metros fechado desde a manha.</description>
  <pubDate>Mon, 01 Sep 2025 10:00:00 GMT</pubDate>
</item>
</channel></rss>
"""


def _fonte(**kwargs) -> FonteNoticia:
    base = dict(id=1, account_id=1, nome="Portal Exemplo", url_feed="https://portal.example.com/rss", tipo="imprensa", peso=1.0, etag="", last_modified="")
    base.update(kwargs)
    return FonteNoticia(**base)


def test_ler_feed_sem_url_devolve_lista_vazia():
    assert ler_feed(_fonte(url_feed="")) == []


def test_ler_feed_com_erro_de_rede_nao_propaga_excecao(monkeypatch):
    def _levantar(*args, **kwargs):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr("app.news.feeds.httpx.get", _levantar)
    assert ler_feed(_fonte()) == []


def test_ler_feed_com_xml_quebrado_nao_propaga_excecao(monkeypatch):
    resposta = SimpleNamespace(status_code=200, content=b"isso nao e xml valido <<<", headers={})
    monkeypatch.setattr("app.news.feeds.httpx.get", lambda *a, **k: resposta)
    assert ler_feed(_fonte()) == []


def test_ler_feed_com_status_erro_devolve_lista_vazia(monkeypatch):
    resposta = SimpleNamespace(status_code=503, content=b"", headers={})
    monkeypatch.setattr("app.news.feeds.httpx.get", lambda *a, **k: resposta)
    assert ler_feed(_fonte()) == []


def test_ler_feed_com_304_devolve_lista_vazia(monkeypatch):
    resposta = SimpleNamespace(status_code=304, content=b"", headers={})
    monkeypatch.setattr("app.news.feeds.httpx.get", lambda *a, **k: resposta)
    assert ler_feed(_fonte(etag='"abc"')) == []


def test_ler_feed_valido_extrai_item_e_atualiza_cache_condicional(monkeypatch):
    resposta = SimpleNamespace(status_code=200, content=_RSS_VALIDO, headers={"etag": '"v1"', "last-modified": "Mon, 01 Sep 2025 10:00:00 GMT"})
    monkeypatch.setattr("app.news.feeds.httpx.get", lambda *a, **k: resposta)
    fonte = _fonte()
    itens = ler_feed(fonte)
    assert len(itens) == 1
    assert itens[0].titulo == "Rua interditada apos obra na rede de agua"
    assert itens[0].url == "https://portal.example.com/noticia-1"
    assert itens[0].publicado_em.year == 2025
    assert fonte.etag == '"v1"'
    assert fonte.last_modified == "Mon, 01 Sep 2025 10:00:00 GMT"
