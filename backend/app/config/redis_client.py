"""Cliente Redis do backend, com timeouts e um disjuntor para o estado de sessão do ao vivo (F3, item 6 da
docs/auditoria.md).

- `redis_client`: o cliente cru, agora com `socket_connect_timeout`, `socket_timeout` e `health_check_interval`
  (settings.redis_*). Quem precisa saber que o Redis falhou (travas e deduplicação do WhatsApp, rate limit) usa
  este e trata o erro.
- `redis_sessao`: o mesmo cliente atrás do disjuntor. Cada comando passa por `seguro`: um `RedisError` (timeout,
  conexão recusada) devolve um padrão neutro (nada guardado, lista vazia, rotação na primeira opção), grava um log
  por janela e abre o disjuntor por `settings.redis_pausa_apos_falha_s`; com ele aberto, nenhum comando toca o
  socket. Só para estado de sessão e cache, em que "não lembrar" é aceitável: com o Redis "buraco negro", dezenas
  de chamadas por /proxima × timeout ainda travariam a rota sem o disjuntor.
"""

import copy
import logging
import threading
import time
from typing import Any, Callable, TypeVar

import redis

from app.config.settings import settings

logger = logging.getLogger("radialista.redis")

T = TypeVar("T")


def criar_cliente(url: str) -> redis.Redis:
    return redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_s,
        socket_timeout=settings.redis_socket_timeout_s,
        health_check_interval=settings.redis_health_check_s,
    )


redis_client = criar_cliente(settings.redis_url)


class Disjuntor:
    """Aberto depois de uma falha, por `pausa_s` segundos: as operações devolvem o padrão sem tocar o Redis.
    Depois da pausa, a próxima operação tenta de novo (meio aberto); se falhar, abre outra vez."""

    def __init__(self, pausa_s: Callable[[], float] = lambda: settings.redis_pausa_apos_falha_s,
                 relogio: Callable[[], float] = time.monotonic):
        self._pausa_s = pausa_s
        self._relogio = relogio
        self._aberto_ate = 0.0
        self._trava = threading.Lock()

    def aberto(self) -> bool:
        return self._relogio() < self._aberto_ate

    def falhou(self, nome: str, erro: Exception) -> None:
        with self._trava:
            ja_aberto = self.aberto()
            self._aberto_ate = self._relogio() + self._pausa_s()
        if not ja_aberto:
            # Um log por janela: com o disjuntor aberto as operações nem chegam aqui.
            logger.warning("redis_indisponivel operacao=%s erro=%s pausa_s=%s", nome, type(erro).__name__,
                           self._pausa_s())

    def fechar(self) -> None:
        self._aberto_ate = 0.0


disjuntor = Disjuntor()


def redis_disponivel() -> bool:
    return not disjuntor.aberto()


def seguro(operacao: Callable[[], T], padrao: T, nome: str) -> T:
    """Roda `operacao` no Redis; com o disjuntor aberto ou num `RedisError`, devolve `padrao`."""
    if disjuntor.aberto():
        return padrao
    try:
        return operacao()
    except redis.RedisError as erro:
        disjuntor.falhou(nome, erro)
        return padrao


# Padrão neutro de cada comando quando o Redis está fora (estado de sessão e cache do ao vivo).
PADROES_SESSAO: dict[str, Any] = {
    "get": None, "set": None, "delete": 0, "exists": 0, "expire": False, "ttl": -2,
    "incr": 1, "hget": None, "hset": 0, "hgetall": {}, "hincrby": 0,
    "smembers": set(), "sadd": 0, "srem": 0, "sismember": False,
    "lrange": [], "lpush": 0, "rpush": 0, "ltrim": True, "lrem": 0, "llen": 0,
}


class ClienteSeguro:
    """Proxy do cliente Redis em que os comandos de `padroes` passam por `seguro`. O cliente é lido na hora da
    chamada (um teste que troca um método do cliente cru continua valendo); o resto passa direto."""

    def __init__(self, cliente: Callable[[], Any], padroes: dict[str, Any]):
        self._cliente = cliente
        self._padroes = padroes

    def __getattr__(self, nome: str):
        if nome not in self._padroes:
            return getattr(self._cliente(), nome)
        padrao = self._padroes[nome]

        def comando(*args, **kwargs):
            return seguro(lambda: getattr(self._cliente(), nome)(*args, **kwargs), copy.copy(padrao), nome)

        comando.__name__ = nome
        return comando


redis_sessao = ClienteSeguro(lambda: redis_client, PADROES_SESSAO)
