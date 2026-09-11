import datetime

import pytest

from app.models.fonte_noticia import FonteNoticia
from app.models.noticia import Noticia
from app.news.curadoria import ResultadoCuradoria
from app.news.feeds import ItemFeed
from app.news.worker import coletar_conta, coletar_fonte


@pytest.fixture()
def fonte(db_session, account):
    fonte = FonteNoticia(account_id=account.id, nome="Portal Exemplo", url_feed="https://portal.example.com/rss", tipo="imprensa", ativa=True)
    db_session.add(fonte)
    db_session.commit()
    db_session.refresh(fonte)
    return fonte


def _resultado(**kwargs):
    base = dict(categoria="transito", score=80.0)
    base.update(kwargs)
    return ResultadoCuradoria(**base)


def test_coletar_fonte_grava_noticia_nova(db_session, account, fonte, monkeypatch):
    item = ItemFeed(titulo="Rua interditada", resumo="Obra na rede de agua", url="https://portal.example.com/n1", publicado_em=datetime.datetime.now(datetime.timezone.utc))
    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item])
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: _resultado())

    total = coletar_fonte(db_session, account, fonte)

    assert total == 1
    noticias = db_session.query(Noticia).filter_by(account_id=account.id).all()
    assert len(noticias) == 1
    assert noticias[0].titulo == "Rua interditada"
    assert noticias[0].categoria == "transito"


def test_coletar_fonte_nao_duplica_mesma_url(db_session, account, fonte, monkeypatch):
    item = ItemFeed(titulo="Rua interditada", resumo="", url="https://portal.example.com/n1", publicado_em=datetime.datetime.now(datetime.timezone.utc))
    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item])
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: _resultado())

    coletar_fonte(db_session, account, fonte)
    total_segunda_rodada = coletar_fonte(db_session, account, fonte)

    assert total_segunda_rodada == 0
    assert db_session.query(Noticia).filter_by(account_id=account.id).count() == 1


def test_coletar_fonte_descarta_item_bloqueado_na_curadoria(db_session, account, fonte, monkeypatch):
    item = ItemFeed(titulo="Materia sensivel", resumo="", url="https://portal.example.com/n2", publicado_em=datetime.datetime.now(datetime.timezone.utc))
    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item])
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: None)

    total = coletar_fonte(db_session, account, fonte)

    assert total == 0
    assert db_session.query(Noticia).filter_by(account_id=account.id).count() == 0


def test_coletar_conta_ignora_fonte_sem_url_feed(db_session, account, monkeypatch):
    fonte_sem_feed = FonteNoticia(account_id=account.id, nome="Sem feed ainda", url_feed="", ativa=True)
    db_session.add(fonte_sem_feed)
    db_session.commit()

    chamou_ler_feed = []
    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: chamou_ler_feed.append(f) or [])

    assert coletar_conta(db_session, account) == 0
    assert chamou_ler_feed == []


def test_coletar_fonte_nao_duplica_titulo_parecido_vindo_de_url_diferente(db_session, account, fonte, monkeypatch):
    outra_fonte = FonteNoticia(account_id=account.id, nome="Outro Portal", url_feed="https://outro.example.com/rss", ativa=True)
    db_session.add(outra_fonte)
    db_session.commit()

    item_original = ItemFeed(
        titulo="Rua São Paulo interditada apos obra na rede de agua", resumo="",
        url="https://portal.example.com/n1", publicado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    item_quase_igual = ItemFeed(
        titulo="Rua São Paulo interditada apos obra na rede de agua em Blumenau", resumo="",
        url="https://outro.example.com/mesma-materia", publicado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: _resultado())

    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item_original])
    coletar_fonte(db_session, account, fonte)

    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item_quase_igual])
    total_segunda_fonte = coletar_fonte(db_session, account, outra_fonte)

    assert total_segunda_fonte == 0
    assert db_session.query(Noticia).filter_by(account_id=account.id).count() == 1


def test_coletar_fonte_marca_noticia_original_como_retificada(db_session, account, fonte, monkeypatch):
    item_original = ItemFeed(
        titulo="Rua São Paulo interditada apos obra na rede de agua", resumo="Trecho fechado",
        url="https://portal.example.com/n1", publicado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    item_retificacao = ItemFeed(
        titulo="Correção: rua São Paulo interditada apos obra na rede de agua", resumo="Trecho reaberto mais cedo do que informado",
        url="https://portal.example.com/n1-correcao", publicado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: _resultado())

    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item_original])
    coletar_fonte(db_session, account, fonte)

    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item_retificacao])
    total_retificacao = coletar_fonte(db_session, account, fonte)

    assert total_retificacao == 0
    noticia = db_session.query(Noticia).filter_by(account_id=account.id).one()
    assert noticia.retificada is True
    assert noticia.texto_retificacao == "Trecho reaberto mais cedo do que informado"


def test_coletar_fonte_retificacao_sem_materia_original_nao_vira_noticia_nova(db_session, account, fonte, monkeypatch):
    item_retificacao = ItemFeed(
        titulo="Correção: numero de casas atingidas pela enchente", resumo="",
        url="https://portal.example.com/correcao-solta", publicado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [item_retificacao])
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: _resultado())

    total = coletar_fonte(db_session, account, fonte)

    assert total == 0
    assert db_session.query(Noticia).filter_by(account_id=account.id).count() == 0


def test_coletar_conta_com_fonte_quebrada_nao_derruba_as_demais(db_session, account, fonte, monkeypatch):
    outra_fonte = FonteNoticia(account_id=account.id, nome="Outro Portal", url_feed="https://outro.example.com/rss", ativa=True)
    db_session.add(outra_fonte)
    db_session.commit()

    item_ok = ItemFeed(titulo="Materia valida", resumo="", url="https://outro.example.com/n1", publicado_em=datetime.datetime.now(datetime.timezone.utc))

    def _ler_feed(f):
        if f.id == fonte.id:
            raise RuntimeError("feed quebrado")
        return [item_ok]

    monkeypatch.setattr("app.news.worker.ler_feed", _ler_feed)
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: _resultado())

    total = coletar_conta(db_session, account)

    assert total == 1
    assert db_session.query(Noticia).filter_by(account_id=account.id).count() == 1
