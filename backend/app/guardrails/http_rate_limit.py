import datetime

from fastapi import HTTPException, Request, status

from app.config.redis_client import redis_client as _redis


def limite_excedido(chave: str, limite: int, janela_segundos: int = 60) -> bool:
    """Fixed window rate limit contado no Redis, mesmo padrao do rate limiter de mensagens
    do WhatsApp em app/guardrails/rate_limiter.py. True se a chave ja estourou o limite.
    """
    bucket = int(datetime.datetime.now(datetime.timezone.utc).timestamp() // janela_segundos)
    chave_redis = f"rl_http:{chave}:{bucket}"

    contagem = _redis.incr(chave_redis)
    if contagem == 1:
        _redis.expire(chave_redis, janela_segundos)

    return contagem > limite


def limitar_por_ip(chave: str, limite: int, janela_segundos: int = 60):
    """Dependencia FastAPI que limita requisicoes por IP a uma rota publica."""

    def dependencia(request: Request) -> None:
        ip = request.client.host if request.client else "desconhecido"
        if limite_excedido(f"{chave}:{ip}", limite, janela_segundos):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisicoes. Tente novamente em instantes.",
            )

    return dependencia
