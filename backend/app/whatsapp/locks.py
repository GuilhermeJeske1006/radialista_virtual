"""Exclusão por conversa e liberação atômica, sem apagar locks de outra execução."""

from contextlib import contextmanager
import uuid
from fastapi import HTTPException
from redis.exceptions import WatchError
from app.config.redis_client import redis_client


@contextmanager
def bloquear_conversa(account_id, telefone):
    chave = f"atendimento:lock:{account_id}:{telefone}"
    token = uuid.uuid4().hex
    if not redis_client.set(chave, token, nx=True, ex=300):
        raise HTTPException(
            503,
            "Conversa em processamento; tente novamente",
            headers={"Retry-After": "2"},
        )
    try:
        yield
    finally:
        with redis_client.pipeline() as pipe:
            try:
                pipe.watch(chave)
                if pipe.get(chave) == token:
                    pipe.multi()
                    pipe.delete(chave)
                    pipe.execute()
            except WatchError:
                pass
