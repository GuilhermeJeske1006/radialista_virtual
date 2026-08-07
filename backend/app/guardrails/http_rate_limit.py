import datetime

from fastapi import HTTPException, Request, status

from app.guardrails.rate_limiter import _redis


def limitar_por_ip(chave: str, limite: int, janela_segundos: int = 60):
    """Dependencia FastAPI que limita requisicoes por IP a uma rota publica.

    Janela fixa (fixed window) contada no Redis, mesmo padrao do rate limiter
    de mensagens do WhatsApp em app/guardrails/rate_limiter.py.
    """

    def dependencia(request: Request) -> None:
        ip = request.client.host if request.client else "desconhecido"
        bucket = int(datetime.datetime.now(datetime.timezone.utc).timestamp() // janela_segundos)
        chave_redis = f"rl_http:{chave}:{ip}:{bucket}"

        contagem = _redis.incr(chave_redis)
        if contagem == 1:
            _redis.expire(chave_redis, janela_segundos)

        if contagem > limite:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisicoes. Tente novamente em instantes.",
            )

    return dependencia
