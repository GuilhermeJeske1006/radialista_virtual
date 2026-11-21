"""Exclusão por conversa e liberação atômica, sem apagar locks de outra execução."""

from contextlib import contextmanager
import uuid
import hashlib
from fastapi import HTTPException
from redis.exceptions import WatchError
from app.config.redis_client import redis_client


@contextmanager
def bloquear_conversa(account_id, telefone, db=None):
    if db is not None and db.get_bind().dialect.name == "postgresql":
        from sqlalchemy import text
        numero = int.from_bytes(hashlib.sha256(f"{account_id}:{telefone}".encode()).digest()[:8], "big", signed=True)
        # Conexão dedicada: a trava sobrevive aos commits do atendimento. O servidor
        # libera ao encerrar a conexão/processo; não depende de cache/eviction Redis.
        with db.get_bind().connect() as conn:
            if not conn.execute(text("SELECT pg_try_advisory_lock(:n)"), {"n": numero}).scalar():
                raise HTTPException(503, "Conversa em processamento; tente novamente", headers={"Retry-After": "2"})
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:n)"), {"n": numero})
        return
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
