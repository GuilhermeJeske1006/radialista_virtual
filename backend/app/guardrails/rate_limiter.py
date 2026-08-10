import datetime

from app.config.redis_client import redis_client as _redis


def dentro_do_limite(wuzapi_token: str, telefone: str, limite_por_hora: int) -> bool:
    hora_atual = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H")
    chave = f"rl:{wuzapi_token}:{telefone}:{hora_atual}"

    contagem = _redis.incr(chave)
    if contagem == 1:
        _redis.expire(chave, 3600)

    return contagem <= limite_por_hora
