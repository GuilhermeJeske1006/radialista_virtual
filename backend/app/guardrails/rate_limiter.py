import datetime

import redis

from app.config.settings import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)


def dentro_do_limite(wuzapi_token: str, telefone: str, limite_por_hora: int) -> bool:
    hora_atual = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H")
    chave = f"rl:{wuzapi_token}:{telefone}:{hora_atual}"

    contagem = _redis.incr(chave)
    if contagem == 1:
        _redis.expire(chave, 3600)

    return contagem <= limite_por_hora
