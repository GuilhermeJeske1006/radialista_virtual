import datetime
import logging

from fastapi import HTTPException, Request, status
from redis import RedisError

from app.config.redis_client import disjuntor, redis_client as _redis

logger = logging.getLogger("radialista.rate_limit")

# Redis fora (decisão D5 da F3): as rotas públicas de autenticação falham FECHADAS (503) -- sem contagem, login e
# recuperação de senha ficariam sem limite contra força bruta. Todo o resto (ao vivo, contas, webhook) falha aberto.
ROTAS_FALHA_FECHADA = frozenset({"auth_login", "auth_register", "auth_esqueci_senha", "auth_redefinir_senha"})


def _sem_redis(chave: str, falha_fechada: bool, erro: Exception | None = None) -> bool:
    if erro is not None:
        disjuntor.falhou("rate_limit", erro)
    logger.warning("rate_limit_sem_redis chave=%s politica=%s", chave.split(":", 1)[0],
                   "fechada" if falha_fechada else "aberta")
    if falha_fechada:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Serviço temporariamente indisponível. Tente novamente em instantes.")
    return False


def _chave_bucket(chave: str, janela_segundos: int) -> str:
    bucket = int(datetime.datetime.now(datetime.timezone.utc).timestamp() // janela_segundos)
    return f"rl_http:{chave}:{bucket}"


def limite_excedido(chave: str, limite: int, janela_segundos: int = 60, *, falha_fechada: bool = False) -> bool:
    """Fixed window rate limit contado no Redis, mesmo padrao do rate limiter de mensagens
    do WhatsApp em app/guardrails/rate_limiter.py. True se a chave ja estourou o limite.

    Incrementa a contagem a cada chamada -- pra rota onde so a TENTATIVA (nao o sucesso) deve
    contar pro limite (ex.: rate limit por IP de rota publica). Quando o custo real (ex.: uma
    chamada de LLM) so deve contar se a operacao teve sucesso, use `limite_atingido` +
    `registrar_consumo` em vez desta funcao (ver app.config.router._validar_limite_geracao_ia).

    Redis fora (ou disjuntor aberto, ver app.config.redis_client): `falha_fechada` levanta 503; senao, nao limita.
    """
    if disjuntor.aberto():
        return _sem_redis(chave, falha_fechada)
    chave_redis = _chave_bucket(chave, janela_segundos)
    try:
        contagem = _redis.incr(chave_redis)
        if contagem == 1:
            _redis.expire(chave_redis, janela_segundos)
    except RedisError as erro:
        return _sem_redis(chave, falha_fechada, erro)
    return contagem > limite


def limite_atingido(chave: str, limite: int, janela_segundos: int = 60) -> bool:
    """Como limite_excedido, mas so LE a contagem atual -- nao incrementa. Use antes de uma
    operacao cujo custo real so deve ser registrado se ela tiver sucesso (ver registrar_consumo).
    """
    if disjuntor.aberto():
        return False
    try:
        contagem = _redis.get(_chave_bucket(chave, janela_segundos))
    except RedisError as erro:
        return _sem_redis(chave, False, erro)
    return int(contagem or 0) >= limite


def registrar_consumo(chave: str, janela_segundos: int = 60) -> None:
    """Incrementa a contagem da janela atual -- chame so depois que a operacao cujo custo real
    se quer limitar (ex.: uma geracao via LLM que teve sucesso) de fato aconteceu (ver
    limite_atingido)."""
    if disjuntor.aberto():
        return
    chave_redis = _chave_bucket(chave, janela_segundos)
    try:
        contagem = _redis.incr(chave_redis)
        if contagem == 1:
            _redis.expire(chave_redis, janela_segundos)
    except RedisError as erro:
        _sem_redis(chave, False, erro)


def limitar_por_ip(chave: str, limite: int, janela_segundos: int = 60):
    """Dependencia FastAPI que limita requisicoes por IP a uma rota publica."""

    def dependencia(request: Request) -> None:
        ip = request.client.host if request.client else "desconhecido"
        if limite_excedido(f"{chave}:{ip}", limite, janela_segundos, falha_fechada=chave in ROTAS_FALHA_FECHADA):
            logger.warning("Rate limit HTTP excedido: chave=%s ip=%s", chave, ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisicoes. Tente novamente em instantes.",
            )

    return dependencia
