"""Cache exato de áudio, compartilhado entre buffered/streaming.

Nunca cacheia streams interrompidos. Chave inclui identidade da credencial,
conta, voz, texto, modelo, formato, prosódia e pronúncias. TTL e tamanho limitados.
"""
import base64
from contextlib import contextmanager
from functools import wraps
import hashlib
import inspect
import json
import logging
import time
from uuid import uuid4

from fastapi import HTTPException
from redis.exceptions import RedisError, WatchError

from app.billing.contexto_ia import atual
from app.config.redis_client import redis_client
from app.config.settings import settings
from app.billing.contexto_ia import modelo_efetivo

logger = logging.getLogger("radialista.tts.cache")
MAX_BYTES = 2 * 1024 * 1024


def _chave(signature, args, kwargs):
    bound = signature.bind(*args, **kwargs)
    bound.apply_defaults()
    dados = dict(bound.arguments)
    for nome in ("timeout_segundos", "max_tentativas", "reutilizar_audio"):
        dados.pop(nome, None)
    dados["modelo"] = dados.get("modelo") or modelo_efetivo("tts", settings.elevenlabs_model)
    dados["voice_id"] = dados.get("voice_id") or settings.elevenlabs_voice_id
    # v3 não recebe contexto anterior. Não deixar ele destruir o cache de
    # patrocinadores/vinhetas que são idênticos na requisição ao provedor.
    if dados["modelo"] == "eleven_v3":
        dados["texto_anterior"] = None
    conta = atual.get()
    dados["conta"] = conta.id if conta else None
    dados["credencial"] = hashlib.sha256(settings.elevenlabs_api_key.encode()).hexdigest()
    digest = hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"tts:audio:v1:{digest}"


def _ler(chave):
    try:
        valor = redis_client.get(chave)
        if valor:
            dados = base64.b64decode(valor, validate=True)
            if dados and len(dados) <= MAX_BYTES:
                logger.info("tts_cache_hit")
                return dados
    except (RedisError, ValueError):
        logger.warning("Cache TTS indisponível ou inválido")
    return None


def _gravar(chave, audio):
    if not audio or len(audio) > MAX_BYTES:
        return
    try:
        redis_client.set(chave, base64.b64encode(audio).decode(), ex=max(1, settings.ia_cache_ttl_segundos))
    except RedisError:
        logger.warning("Falha ao guardar cache TTS")


@contextmanager
def _exclusivo(chave):
    lock = chave + ":lock"
    token = str(uuid4())
    adquirido = False
    try:
        try:
            limite = time.monotonic() + 25
            while not redis_client.set(lock, token, nx=True, ex=120):
                if time.monotonic() >= limite:
                    raise HTTPException(429, "Este áudio já está sendo preparado. Aguarde para tentar novamente.")
                time.sleep(0.05)
            adquirido = True
        except RedisError:
            logger.warning("Dedupe TTS indisponível; orçamento continua validando gasto")
        yield
    finally:
        if adquirido:
            try:
                with redis_client.pipeline() as pipe:
                    pipe.watch(lock)
                    if pipe.get(lock) == token:
                        pipe.multi()
                        pipe.delete(lock)
                        pipe.execute()
            except (RedisError, WatchError):
                pass  # O TTL remove somente este lock, nunca o de outro worker.


def cache_audio(func):
    signature = inspect.signature(func)

    def habilitado(args, kwargs):
        return settings.ia_cache_habilitado and signature.bind(*args, **kwargs).arguments.get("reutilizar_audio", True)

    if inspect.isgeneratorfunction(func):
        @wraps(func)
        def stream(*args, **kwargs):
            if not habilitado(args, kwargs):
                yield from func(*args, **kwargs)
                return
            chave = _chave(signature, args, kwargs)
            hit = _ler(chave)
            if hit is not None:
                yield hit
                return
            with _exclusivo(chave):
                hit = _ler(chave)
                if hit is not None:
                    yield hit
                    return
                partes, tamanho = [], 0
                gerador = func(*args, **kwargs)
                try:
                    for parte in gerador:
                        tamanho += len(parte)
                        if tamanho <= MAX_BYTES:
                            partes.append(parte)
                        else:
                            partes.clear()
                        yield parte
                    if tamanho <= MAX_BYTES:
                        _gravar(chave, b"".join(partes))
                finally:
                    gerador.close()
        return stream

    @wraps(func)
    def buffered(*args, **kwargs):
        if not habilitado(args, kwargs):
            return func(*args, **kwargs)
        chave = _chave(signature, args, kwargs)
        hit = _ler(chave)
        if hit is not None:
            return hit
        with _exclusivo(chave):
            hit = _ler(chave)
            if hit is not None:
                return hit
            audio = func(*args, **kwargs)
            _gravar(chave, audio)
            return audio
    return buffered
