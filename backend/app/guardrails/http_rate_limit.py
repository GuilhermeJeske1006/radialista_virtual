import datetime
import logging

from fastapi import HTTPException, Request, status

from app.config.redis_client import redis_client as _redis

logger = logging.getLogger("radialista.rate_limit")


def _chave_bucket(chave: str, janela_segundos: int) -> str:
    bucket = int(datetime.datetime.now(datetime.timezone.utc).timestamp() // janela_segundos)
    return f"rl_http:{chave}:{bucket}"


def limite_excedido(chave: str, limite: int, janela_segundos: int = 60) -> bool:
    """Fixed window rate limit contado no Redis, mesmo padrao do rate limiter de mensagens
    do WhatsApp em app/guardrails/rate_limiter.py. True se a chave ja estourou o limite.

    Incrementa a contagem a cada chamada -- pra rota onde so a TENTATIVA (nao o sucesso) deve
    contar pro limite (ex.: rate limit por IP de rota publica). Quando o custo real (ex.: uma
    chamada de LLM) so deve contar se a operacao teve sucesso, use `limite_atingido` +
    `registrar_consumo` em vez desta funcao (ver app.config.router._validar_limite_geracao_ia).
    """
    chave_redis = _chave_bucket(chave, janela_segundos)
    contagem = _redis.incr(chave_redis)
    if contagem == 1:
        _redis.expire(chave_redis, janela_segundos)
    return contagem > limite


def limite_atingido(chave: str, limite: int, janela_segundos: int = 60) -> bool:
    """Como limite_excedido, mas so LE a contagem atual -- nao incrementa. Use antes de uma
    operacao cujo custo real so deve ser registrado se ela tiver sucesso (ver registrar_consumo).
    """
    contagem = _redis.get(_chave_bucket(chave, janela_segundos))
    return int(contagem or 0) >= limite


def registrar_consumo(chave: str, janela_segundos: int = 60) -> None:
    """Incrementa a contagem da janela atual -- chame so depois que a operacao cujo custo real
    se quer limitar (ex.: uma geracao via LLM que teve sucesso) de fato aconteceu (ver
    limite_atingido)."""
    chave_redis = _chave_bucket(chave, janela_segundos)
    contagem = _redis.incr(chave_redis)
    if contagem == 1:
        _redis.expire(chave_redis, janela_segundos)


def limitar_por_ip(chave: str, limite: int, janela_segundos: int = 60):
    """Dependencia FastAPI que limita requisicoes por IP a uma rota publica."""

    def dependencia(request: Request) -> None:
        ip = request.client.host if request.client else "desconhecido"
        if limite_excedido(f"{chave}:{ip}", limite, janela_segundos):
            logger.warning("Rate limit HTTP excedido: chave=%s ip=%s", chave, ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisicoes. Tente novamente em instantes.",
            )

    return dependencia
