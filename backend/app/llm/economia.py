"""Cache de prefixo sem remover instruções e contabilidade por chamada."""
import hashlib
import json
import logging

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.billing.consumo_ia import concluir, reservar, falhar
from app.billing.contexto_ia import atual
from app.config.redis_client import redis_client
from app.config.settings import settings

logger = logging.getLogger("radialista.llm.custos")


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


def criar_mensagem(client, **kwargs):
    from app.billing.contexto_ia import modelo_efetivo
    model = kwargs["model"]
    if model != settings.llm_classification_model:
        model = kwargs["model"] = modelo_efetivo('llm', model)
        if 'haiku' in model:
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
        kwargs["system"] = [{"type": "text", "text": kwargs["system"], "cache_control": {"type": "ephemeral"}}]
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
        resposta = client.messages.create(**kwargs)
    except Exception:
        falhar(reserva)
        raise
    usage = getattr(resposta, "usage", None)
    if usage is not None:
        ins = getattr(usage, "input_tokens", 0) or 0
        outs = getattr(usage, "output_tokens", 0) or 0
        writes = getattr(usage, "cache_creation_input_tokens", 0) or 0
        reads = getattr(usage, "cache_read_input_tokens", 0) or 0
        tools = getattr(usage, "server_tool_use", None)
        buscas = (getattr(tools, "web_search_requests", 0) or 0) if tools else 0
        custo = (entrada * (ins + 1.25 * writes + 0.1 * reads) + saida * outs) / 1_000_000 + buscas * 0.01
        concluir(reserva, custo, {"entrada": ins, "saida": outs, "cache_write": writes, "cache_read": reads, "buscas": buscas}, entregue=False if getattr(resposta, "stop_reason", None) == "refusal" else None, request_id=getattr(resposta, "id", None))
        logger.info("llm_consumo modelo=%s entrada=%s saida=%s cache_write=%s cache_read=%s usd=%.6f",
                    model, ins, outs, writes, reads, custo)
    else:
        falhar(reserva)
    return resposta
