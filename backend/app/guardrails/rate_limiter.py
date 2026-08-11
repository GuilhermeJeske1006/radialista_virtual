import datetime
import logging

from app.config.redis_client import redis_client as _redis

logger = logging.getLogger("radialista.rate_limit")


def dentro_do_limite(wuzapi_token: str, telefone: str, limite_por_hora: int) -> bool:
    hora_atual = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H")
    chave = f"rl:{wuzapi_token}:{telefone}:{hora_atual}"

    contagem = _redis.incr(chave)
    if contagem == 1:
        _redis.expire(chave, 3600)

    dentro = contagem <= limite_por_hora
    if not dentro:
        logger.warning("Rate limit de mensagens excedido: telefone=%s limite=%s", telefone, limite_por_hora)
    return dentro
