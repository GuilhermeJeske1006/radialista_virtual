"""Cache de categoria de bloco customizado com TTL e teto (F6, U10; item 9 de docs/auditoria.md, D18).

O hash global `cache:categoria_bloco_customizado` guarda a classificação por LLM de cada rótulo de bloco sem prefixo
conhecido. Antes não tinha `expire` nem teto: crescia sem limite com os rótulos de todas as contas.
"""

import pytest
import redis

from app.config import redis_client as modulo
from app.config.redis_client import redis_client
from app.config.settings import settings
from app.live.router import _CACHE_CATEGORIA_CUSTOMIZADA, _categoria_bloco


@pytest.fixture(autouse=True)
def _disjuntor_fechado():
    modulo.disjuntor.fechar()
    yield
    modulo.disjuntor.fechar()


@pytest.fixture
def classificacoes(monkeypatch):
    chamadas: list[str] = []
    monkeypatch.setattr("app.live.router.classificar_categoria_bloco",
                        lambda tipo: chamadas.append(tipo) or "musica")
    return chamadas


def test_u10_valores_em_settings():
    assert settings.cache_categoria_bloco_ttl_s == 30 * 24 * 60 * 60
    assert settings.cache_categoria_bloco_max == 5000
    assert modulo.PADROES_SESSAO["hlen"] == 0


def test_u10_ttl_depois_do_hset_e_renovado_a_cada_gravacao(classificacoes):
    assert _categoria_bloco("chamamé e xote") == "musica"
    ttl = redis_client.ttl(_CACHE_CATEGORIA_CUSTOMIZADA)
    assert 0 < ttl <= settings.cache_categoria_bloco_ttl_s
    redis_client.expire(_CACHE_CATEGORIA_CUSTOMIZADA, 60)
    assert _categoria_bloco("forró pé de serra") == "musica"
    assert redis_client.ttl(_CACHE_CATEGORIA_CUSTOMIZADA) > 60
    # Leitura do cache não chama o LLM de novo nem regrava.
    assert _categoria_bloco("chamamé e xote") == "musica"
    assert classificacoes == ["chamamé e xote", "forró pé de serra"]


def test_u10_teto_apaga_o_hash_e_regrava(classificacoes, monkeypatch):
    monkeypatch.setattr(settings, "cache_categoria_bloco_max", 2)
    for rotulo in ("bloco um", "bloco dois"):
        _categoria_bloco(rotulo)
    assert redis_client.hlen(_CACHE_CATEGORIA_CUSTOMIZADA) == 2
    _categoria_bloco("bloco três")
    assert redis_client.hgetall(_CACHE_CATEGORIA_CUSTOMIZADA) == {"bloco tres": "musica"}
    assert redis_client.ttl(_CACHE_CATEGORIA_CUSTOMIZADA) > 0


def test_u10_redis_fora_nao_levanta_e_classifica(classificacoes, monkeypatch):
    def quebrado(*_a, **_k):
        raise redis.ConnectionError("redis fora")

    for nome in ("hget", "hset", "hlen", "expire", "delete"):
        monkeypatch.setattr(modulo.redis_client, nome, quebrado)
    assert _categoria_bloco("moda de viola") == "musica"
    assert classificacoes == ["moda de viola"]
