import json

import httpx
import pytest

from app.config.redis_client import redis_client
from app.config.settings import settings
from app.live.spotify import _chave_cache_categoria, buscar_faixas_por_categoria


def _artista(nome, popularidade):
    return {"id": nome, "name": nome, "popularity": popularidade}


def _faixa(nome_artista, titulo):
    return {"name": titulo, "artists": [{"name": nome_artista}]}


@pytest.fixture(autouse=True)
def _credenciais_fake(monkeypatch):
    monkeypatch.setattr(settings, "spotify_client_id", "fake-id")
    monkeypatch.setattr(settings, "spotify_client_secret", "fake-secret")
    monkeypatch.setattr("app.live.spotify._obter_token", lambda: "fake-token")


def test_sem_credenciais_devolve_lista_vazia(monkeypatch):
    monkeypatch.setattr(settings, "spotify_client_id", "")
    monkeypatch.setattr(settings, "spotify_client_secret", "")
    monkeypatch.setattr("app.live.spotify._obter_token", lambda: None)
    assert buscar_faixas_por_categoria("sertanejo") == []


def test_falha_de_rede_devolve_lista_vazia(monkeypatch):
    def _get_com_falha(*args, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr("app.live.spotify.httpx.get", _get_com_falha)
    assert buscar_faixas_por_categoria("sertanejo") == []


def test_busca_e_agrega_faixas_dos_artistas(monkeypatch):
    monkeypatch.setattr(
        "app.live.spotify._buscar_artistas_do_genero",
        lambda token, genero: [_artista("a1", 90), _artista("a2", 50)],
    )

    def _faixas(token, nome_artista):
        if nome_artista == "a1":
            return [("Artista Um", "Musica A"), ("Artista Um", "Musica B")]
        return [("Artista Dois", "Musica C")]

    monkeypatch.setattr("app.live.spotify._faixas_do_artista", _faixas)

    faixas = buscar_faixas_por_categoria("sertanejo")
    assert set(faixas) == {
        ("Artista Um", "Musica A"),
        ("Artista Um", "Musica B"),
        ("Artista Dois", "Musica C"),
    }

    # Resultado ficou cacheado no Redis -- 2a chamada nao deveria precisar bater na Spotify de
    # novo (mas aqui so' confirmamos que o cache foi escrito com o mesmo conteudo).
    em_cache = redis_client.get(_chave_cache_categoria("sertanejo"))
    assert em_cache is not None
    assert set(tuple(item) for item in json.loads(em_cache)) == set(faixas)


def test_usa_cache_sem_bater_na_api_de_novo(monkeypatch):
    chamadas = {"n": 0}

    def _buscar_artistas(token, genero):
        chamadas["n"] += 1
        return [_artista("a1", 90)]

    monkeypatch.setattr("app.live.spotify._buscar_artistas_do_genero", _buscar_artistas)
    monkeypatch.setattr(
        "app.live.spotify._faixas_do_artista",
        lambda token, nome_artista: [(f"Artista {i}", f"Musica {i}") for i in range(10)],
    )

    primeira = buscar_faixas_por_categoria("sertanejo")
    segunda = buscar_faixas_por_categoria("sertanejo")

    assert chamadas["n"] == 1
    assert set(primeira) == set(segunda)


def test_exclui_titulos_ja_tocados(monkeypatch):
    monkeypatch.setattr(
        "app.live.spotify._buscar_artistas_do_genero", lambda token, genero: [_artista("a1", 90)]
    )
    monkeypatch.setattr(
        "app.live.spotify._faixas_do_artista",
        lambda token, nome_artista: [(f"Artista {i}", f"Musica {i}") for i in range(10)],
    )

    todas = buscar_faixas_por_categoria("sertanejo")
    tocada = {"musica 3"}  # ja normalizado (minusculo), ver _titulo_normalizado
    restantes = buscar_faixas_por_categoria("sertanejo", excluir_titulos=tocada)

    assert len(restantes) == len(todas) - 1
    assert ("Artista 3", "Musica 3") not in restantes


def test_buscar_artistas_descarta_canal_marca_de_compilacao(monkeypatch):
    """Testado ao vivo contra a API de verdade: busca livre por 'sertanejo' devolve tanto
    artista real (Henrique & Juliano) quanto canal/marca de compilacao (Sertanejo Play,
    Fazendinha Sessions, CountryBeat) -- so' o artista real deve sobrar (ver
    _parece_marca_ou_compilacao)."""
    from app.live.spotify import _buscar_artistas_do_genero

    def _fake_get(url, params=None, headers=None, timeout=None):
        class _Resposta:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "artists": {
                        "items": [
                            _artista("Sertanejo Play", 0),
                            _artista("Fazendinha Sessions", 0),
                            _artista("CountryBeat", 0),
                            _artista("Henrique & Juliano", 0),
                        ]
                    }
                }

        return _Resposta()

    monkeypatch.setattr("app.live.spotify.httpx.get", _fake_get)

    artistas = _buscar_artistas_do_genero("fake-token", "sertanejo")
    assert [a["name"] for a in artistas] == ["Henrique & Juliano"]


def test_faixas_do_artista_descarta_medley_e_sessao(monkeypatch):
    """Testado ao vivo contra a API de verdade: gravadora/canal (ex.: 'MJ Records') as vezes
    cataloga 'musica A / musica B' como se fosse 1 faixa so' -- descartado antes de virar
    query pro YouTube (ver _PADRAO_FAIXA_COMPOSTA)."""
    from app.live.spotify import _faixas_do_artista

    def _fake_get(url, params=None, headers=None, timeout=None):
        class _Resposta:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "tracks": {
                        "items": [
                            _faixa("MJ Records", "Insegurança / Fim de Noite - Ao Vivo"),
                            _faixa("Fazendinha Sessions", "Fazendinha Sessions #6: Fulano, Beltrano"),
                            _faixa("Henrique & Juliano", "Última Saudade - Ao Vivo"),
                        ]
                    }
                }

        return _Resposta()

    monkeypatch.setattr("app.live.spotify.httpx.get", _fake_get)

    faixas = _faixas_do_artista("fake-token", "qualquer")
    assert faixas == [("Henrique & Juliano", "Última Saudade - Ao Vivo")]


def test_lista_pequena_demais_forca_nova_consulta(monkeypatch):
    """Cache com so' 3 faixas, todas ja tocadas exceto 1: abaixo de _MIN_FAIXAS_DISPONIVEIS (5),
    entao busca de novo na Spotify em vez de devolver a lista curta."""
    chamadas = {"n": 0}

    def _buscar_artistas(token, genero):
        chamadas["n"] += 1
        return [_artista("a1", 90)]

    monkeypatch.setattr("app.live.spotify._buscar_artistas_do_genero", _buscar_artistas)
    monkeypatch.setattr(
        "app.live.spotify._faixas_do_artista",
        lambda token, nome_artista: [("Artista X", "Musica 1"), ("Artista X", "Musica 2"), ("Artista X", "Musica 3")],
    )

    buscar_faixas_por_categoria("sertanejo")
    assert chamadas["n"] == 1

    buscar_faixas_por_categoria("sertanejo", excluir_titulos={"musica 1", "musica 2"})
    assert chamadas["n"] == 2
