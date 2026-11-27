"""Cache de prefixo sem remover instruções e contabilidade por chamada."""
import hashlib
import json
import logging

from anthropic import AuthenticationError, BadRequestError, PermissionDeniedError
from fastapi import HTTPException
from redis.exceptions import RedisError

from app.billing.consumo_ia import concluir, reservar, falhar
from app.billing.contexto_ia import atual
from app.config.redis_client import redis_client, redis_sessao
from app.config.settings import settings
from app.guardrails.provedores import executar
from app.llm.system_partes import blocos_para_cache

logger = logging.getLogger("radialista.llm.custos")


def _entrada_para_capacidade(dados):
    imagens = 0
    def sem_binarios(valor):
        nonlocal imagens
        if isinstance(valor, list):
            return [sem_binarios(v) for v in valor]
        if isinstance(valor, dict):
            if valor.get("type") == "image":
                imagens += 1
                return {"type": "image"}
            return {k: sem_binarios(v) for k, v in valor.items()}
        return valor
    texto = json.dumps(sem_binarios(dados), ensure_ascii=False, default=str).encode()
    # Base64 não corresponde aos tokens visuais cobrados. Reservar margem por
    # imagem e reconciliar o uso, sem alterar o payload enviado ao modelo.
    return len(texto) + imagens * settings.ia_imagem_reserva_tokens


def chave_classificacao(system, user, max_tokens):
    conta = atual.get()
    dados = [settings.llm_classification_model, system, user, max_tokens,
             conta.id if conta else None, hashlib.sha256(settings.anthropic_api_key.encode()).hexdigest()]
    return "llm:classificacao:v1:" + hashlib.sha256(json.dumps(dados, ensure_ascii=False).encode()).hexdigest()


def ler_classificacao(chave):
    if settings.ia_cache_habilitado:
        try:
            return redis_client.get(chave)
        except RedisError:
            logger.warning("Cache de classificação indisponível")
    return None


def guardar_classificacao(chave, texto):
    if settings.ia_cache_habilitado and texto:
        try:
            redis_client.set(chave, texto, ex=max(1, settings.ia_cache_ttl_segundos))
        except RedisError:
            logger.warning("Falha ao guardar classificação")


# Disjuntor de indisponibilidade do provedor por conta/credencial (saldo zerado, 401/403, limite de gasto).
# Sem ele, cada /proxima do painel (retentativas a cada 5-30 s) bate no provedor, que recusa de novo:
# em 27/11 foram ~390 chamadas inúteis em 1h30 enquanto o ar ficava só com vinhetas. Redis em falha
# aberta (redis_sessao): sem Redis o comportamento é o de antes.
_CHAVE_DISJUNTOR_LLM = "cb:llm_indisponivel"
_CHAVE_NIVEL_DISJUNTOR_LLM = "cb:llm_indisponivel:nivel"
_TTL_DISJUNTOR_LLM_S = (120, 300, 900)
MENSAGEM_SEM_CREDITO = "Serviço de IA indisponível por falta de créditos no provedor. Contate o suporte."


def llm_indisponivel() -> bool:
    """True com o disjuntor aberto: o provedor recusou por saldo/credencial há pouco."""
    try:
        return bool(redis_sessao.get(_CHAVE_DISJUNTOR_LLM))
    except Exception:  # noqa: BLE001 - o disjuntor nunca pode derrubar a geração: sem Redis, falha aberta
        return False


def _abrir_disjuntor_llm(motivo: str, modelo: str, request_id=None) -> None:
    try:
        _abrir_disjuntor_llm_redis(motivo, modelo, request_id)
    except Exception:  # noqa: BLE001
        logger.error("llm_saldo_insuficiente motivo=%s modelo=%s request_id=%s (disjuntor indisponível)",
                     motivo, modelo, request_id)


def _abrir_disjuntor_llm_redis(motivo: str, modelo: str, request_id=None) -> None:
    try:
        nivel = int(redis_sessao.get(_CHAVE_NIVEL_DISJUNTOR_LLM) or 0)
    except (TypeError, ValueError):
        nivel = 0
    ttl = _TTL_DISJUNTOR_LLM_S[min(nivel, len(_TTL_DISJUNTOR_LLM_S) - 1)]
    redis_sessao.set(_CHAVE_NIVEL_DISJUNTOR_LLM, nivel + 1, ex=3600)
    # nx: um único log de erro (e um único evento no Sentry) por abertura, não um por chamada.
    if redis_sessao.set(_CHAVE_DISJUNTOR_LLM, motivo, ex=ttl, nx=True):
        logger.error("llm_saldo_insuficiente motivo=%s modelo=%s request_id=%s pausa_s=%s",
                     motivo, modelo, request_id, ttl)


def _fechar_disjuntor_llm() -> None:
    try:
        if redis_sessao.get(_CHAVE_NIVEL_DISJUNTOR_LLM) is not None:
            redis_sessao.delete(_CHAVE_NIVEL_DISJUNTOR_LLM)
            logger.info("llm_disponivel_novamente")
    except Exception:  # noqa: BLE001
        pass


def _erro_de_credencial(exc: Exception):
    """Motivo do disjuntor para erros do provedor que não se resolvem retentando; None nos demais."""
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return "credencial"
    if isinstance(exc, BadRequestError):
        mensagem = (exc.message or "").lower()
        if "credit balance is too low" in mensagem:
            return "saldo"
        if "usage limit" in mensagem or "spend limit" in mensagem:
            return "limite_gasto"
    return None


def criar_mensagem(client, **kwargs):
    from app.billing.contexto_ia import modelo_efetivo
    if llm_indisponivel():
        # Falha rápida: sem reserva, sem chamada ao provedor, sem log por tentativa.
        raise HTTPException(503, MENSAGEM_SEM_CREDITO)
    model = kwargs["model"]
    if model != settings.llm_classification_model:
        model = kwargs["model"] = modelo_efetivo('llm', model)
        if model.startswith('claude-haiku-4'):  # Haiku 4.5 não aceita estes parâmetros
            kwargs.pop('thinking', None)
            kwargs.pop('output_config', None)
    tarifas = settings.ia_tarifas_llm.get(model)
    if tarifas is None:
        raise HTTPException(503, "Tarifa do modelo de IA não configurada")
    entrada, saida = tarifas
    if entrada < 0 or saida < 0:
        raise HTTPException(503, "Tarifa de IA inválida")
    # Mesmas instruções, ordem e texto. Cache write custa 1.25x; não reduzir
    # histórico ou fatos arbitrariamente para atingir uma meta de tokens.
    if settings.llm_prompt_cache and isinstance(kwargs.get("system"), str):
        # Prompt dividido em estável + variável (system_partes): só a parte estável fica no prefixo cacheado.
        kwargs["system"] = blocos_para_cache(kwargs["system"]) or [
            {"type": "text", "text": kwargs["system"], "cache_control": {"type": "ephemeral"}}]
    # Limite conservador de entrada em UTF-8 (>= tokens usuais). Ferramentas de
    # busca podem acrescentar contexto: reservar a janela inteira nesses casos.
    bruto = json.dumps({k: kwargs.get(k) for k in ("system", "messages", "tools")},
                       ensure_ascii=False, default=str).encode()
    tokens_max = len(bruto) + 2048
    buscas_max = sum(t.get("max_uses", 0) for t in kwargs.get("tools", []) if t.get("name") == "web_search")
    if buscas_max:
        tokens_max = max(tokens_max, 200_000)
    teto = (tokens_max * entrada * 1.25 + kwargs["max_tokens"] * saida) / 1_000_000 + buscas_max * 0.01
    reserva = reservar("llm", model, teto, unidades_max={
        "entrada": tokens_max, "saida": kwargs["max_tokens"],
        "cache_write": tokens_max, "cache_read": tokens_max, "buscas": buscas_max})
    try:
        # Reserva conservadora do texto conhecido. O uso real reconcilia os buckets;
        # ferramentas precisam de margem para contexto obtido durante a requisição.
        estimativa = _entrada_para_capacidade({k: kwargs.get(k) for k in ("system", "messages", "tools")})
        estimativa += settings.ia_busca_reserva_tokens if buscas_max else 0
        timeout = kwargs.pop("timeout", settings.ia_llm_timeout_s)
        resposta = executar("llm", model,
            lambda restante: client.messages.create(**kwargs, timeout=min(float(timeout), restante)),
            timeout_s=float(timeout), entrada=estimativa, saida=kwargs["max_tokens"])
    except Exception as exc:
        falhar(reserva)
        # A Anthropic responde 400 quando o saldo do provedor acaba. Sem tradução,
        # essa exceção chega ao painel como 500 e esconde a causa da fala local.
        motivo = _erro_de_credencial(exc)
        if motivo:
            _abrir_disjuntor_llm(motivo, model, getattr(exc, "request_id", None))
            raise HTTPException(503, MENSAGEM_SEM_CREDITO) from exc
        raise
    _fechar_disjuntor_llm()
    usage = getattr(resposta, "usage", None)
    if usage is not None:
        ins = getattr(usage, "input_tokens", 0) or 0
        outs = getattr(usage, "output_tokens", 0) or 0
        writes = getattr(usage, "cache_creation_input_tokens", 0) or 0
        reads = getattr(usage, "cache_read_input_tokens", 0) or 0
        tools = getattr(usage, "server_tool_use", None)
        buscas = (getattr(tools, "web_search_requests", 0) or 0) if tools else 0
        coef_leitura = settings.ia_coef_cache_leitura.get(model, 0.1)
        custo = (entrada * (ins + 1.25 * writes + coef_leitura * reads) + saida * outs) / 1_000_000 + buscas * 0.01
        concluir(reserva, custo, {"entrada": ins, "saida": outs, "cache_write": writes, "cache_read": reads, "buscas": buscas}, entregue=False if getattr(resposta, "stop_reason", None) == "refusal" else None, request_id=getattr(resposta, "id", None))
        logger.info("llm_consumo modelo=%s entrada=%s saida=%s cache_write=%s cache_read=%s usd=%.6f",
                    model, ins, outs, writes, reads, custo)
    else:
        falhar(reserva)
    return resposta
