"""Admissão global, fila limitada e retentativas dos provedores de IA.

WATCH/MULTI mantém fila, leases e token buckets atômicos entre servidores (também
em testes com fakeredis). Redis indisponível fecha a admissão: o ao vivo mantém a
música em vez de disparar uma quantidade ilimitada de chamadas pagas.
"""
import hashlib
import json
import logging
import math
import random
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from email.utils import parsedate_to_datetime
from uuid import uuid4

from fastapi import HTTPException
from redis.exceptions import RedisError, WatchError

from app.config.redis_client import redis_client
from app.config.settings import settings

logger = logging.getLogger("radialista.ia.capacidade")
_contexto = ContextVar("capacidade_ia", default=(1, None))
_METRICAS = ("solicitacoes", "sucessos", "erros", "rejeicoes", "retries", "429", "espera_ms", "duracao_ms",
             "entrada_tokens", "saida_tokens", "cache_read_tokens")
_HEADERS = ("maximum-concurrent-requests", "current-concurrent-requests",
            "anthropic-ratelimit-requests-limit", "anthropic-ratelimit-requests-remaining",
            "anthropic-ratelimit-input-tokens-limit", "anthropic-ratelimit-input-tokens-remaining",
            "anthropic-ratelimit-output-tokens-limit", "anthropic-ratelimit-output-tokens-remaining")


class CapacidadeIndisponivel(HTTPException):
    def __init__(self):
        super().__init__(503, "Geração temporariamente ocupada. A transmissão pode continuar com o conteúdo já preparado.",
                         headers={"Retry-After": "5"})


@contextmanager
def contexto_capacidade(prioridade=1, timeout_s=None):
    anterior = _contexto.get()[1]
    prazo = time.monotonic() + timeout_s if timeout_s is not None else anterior
    if anterior is not None and prazo is not None:
        prazo = min(prazo, anterior)
    token = _contexto.set((prioridade, prazo))
    try:
        yield
    finally:
        _contexto.reset(token)


def prazo_operacao(timeout_s):
    prazo = time.monotonic() + timeout_s
    limite = _contexto.get()[1]
    return min(prazo, limite) if limite is not None else prazo


def nome_pool(servico, modelo=""):
    # Conservador: todos os modelos TTS compartilham a mesma concorrência da conta.
    # As famílias 4.x do Claude têm buckets compartilhados no provedor.
    if servico != "llm":
        return servico
    modelo = re.sub(r"-\d{8}$", "", modelo)
    for familia in ("opus", "sonnet"):
        if modelo.startswith(f"claude-{familia}-4"):
            modelo = f"claude-{familia}-4.x"
    return f"llm:{modelo}"


def _limites(pool):
    limites = dict(settings.ia_limites_provedores.get(pool.split(":")[0], {}))
    limites.update(settings.ia_limites_por_pool.get(pool, {}))
    if limites.get("concorrencia", 0) < 1 or any(v < 0 for v in limites.values()):
        raise CapacidadeIndisponivel()
    return limites


def _chave(pool):
    credencial = settings.anthropic_api_key if pool.startswith("llm:") else settings.elevenlabs_api_key
    identidade = hashlib.sha256(credencial.encode()).hexdigest()[:24]
    return f"ia:capacidade:v1:{identidade}:{pool}"


def _agora():
    segundos, micros = redis_client.time()
    return segundos + micros / 1_000_000


def _alterar(chave, func):
    # Número limitado também quando outro worker altera o estado sem parar.
    for _ in range(32):
        try:
            with redis_client.pipeline() as pipe:
                pipe.watch(chave)
                estado = json.loads(pipe.get(chave) or "{}")
                resultado = func(estado)
                pipe.multi()
                ttl = max(3600, math.ceil(estado.get("pausa_ate", 0) - _agora()) + 1)
                pipe.set(chave, json.dumps(estado), ex=ttl)
                pipe.execute()
                return resultado
        except WatchError:
            continue
    raise CapacidadeIndisponivel()


def _metrica(chave, nome, valor=1):
    try:
        chave = f"{chave}:metricas:{int(_agora() // 60)}"
        with redis_client.pipeline() as pipe:
            pipe.hincrby(chave, nome, valor)
            pipe.expire(chave, 3600)
            pipe.execute()
    except RedisError:
        logger.warning("ia_metricas_indisponiveis")


def _atualizar(estado, limites, agora):
    decorrido = max(0, agora - estado.get("atualizado", agora))
    for campo in ("rpm", "entrada", "saida"):
        teto = limites.get(campo, 0)
        if teto:
            estado[campo] = min(teto, estado.get(campo, teto) + decorrido * teto / 60)
    estado["atualizado"] = agora
    for grupo in ("ativos", "fila"):
        estado[grupo] = {k: v for k, v in estado.get(grupo, {}).items() if v["expira"] > agora}


class Vaga:
    def __init__(self, chave, pool, identidade, entrada, saida):
        self.chave, self.pool, self.identidade = chave, pool, identidade
        self.entrada, self.saida = entrada, saida
        self.uso = None
        self.status = 200

    def registrar_uso(self, entrada, saida):
        self.uso = (entrada, saida)

    def observar(self, resposta):
        self.status = getattr(resposta, "status_code", 200)
        headers = getattr(resposta, "headers", {})
        observados = {}
        for nome in _HEADERS:
            try:
                if nome in headers:
                    observados[nome] = max(0, int(headers[nome]))
            except (ValueError, TypeError):
                pass
        if observados:
            try:
                _alterar(self.chave, lambda estado: estado.update(observado=observados))
            except (RedisError, CapacidadeIndisponivel):
                logger.warning("ia_headers_nao_registrados pool=%s", self.pool)


@contextmanager
def vaga(servico, modelo="", *, prazo, entrada=0, saida=0):
    pool = nome_pool(servico, modelo)
    chave, identidade = _chave(pool), uuid4().hex
    limites = _limites(pool)
    inicio = time.monotonic()
    fim_fila = min(prazo, inicio + settings.ia_fila_espera_s)
    adquirida = False
    falhou = False
    inicio_chamada = inicio
    ingresso = Vaga(chave, pool, identidade, entrada, saida)
    try:
        _metrica(chave, "solicitacoes")
        if any(limites.get(c, 0) and n > limites[c] for c, n in (("entrada", entrada), ("saida", saida))):
            raise CapacidadeIndisponivel()
        while True:
            agora = _agora()
            restante = prazo - time.monotonic()

            def admitir(estado):
                _atualizar(estado, limites, agora)
                fila = estado["fila"]
                if identidade not in fila:
                    if len(fila) >= settings.ia_fila_max:
                        return False
                    fila[identidade] = {"prioridade": _contexto.get()[0], "ordem": agora,
                                        "expira": agora + max(0, fim_fila - time.monotonic()) + 1}
                primeiro = min(fila, key=lambda k: (fila[k]["prioridade"], fila[k]["ordem"], k))
                consumo = {"rpm": 1, "entrada": entrada, "saida": saida}
                permitido = (restante > 0 and primeiro == identidade
                             and len(estado["ativos"]) < limites["concorrencia"]
                             and estado.get("pausa_ate", 0) <= agora
                             and all(not limites.get(c, 0) or estado[c] >= n for c, n in consumo.items()))
                if permitido:
                    del fila[identidade]
                    # Inclui a última leitura de socket que pode começar perto do deadline.
                    estado["ativos"][identidade] = {"expira": agora + restante * 2 + 10}
                    for c, n in consumo.items():
                        if limites.get(c, 0):
                            estado[c] -= n
                return permitido

            adquirida = _alterar(chave, admitir)
            if adquirida:
                inicio_chamada = time.monotonic()
                break
            if time.monotonic() >= fim_fila:
                logger.warning("ia_fila_prazo_excedido pool=%s", pool)
                raise CapacidadeIndisponivel()
            time.sleep(min(random.uniform(.08, .15), max(0, fim_fila - time.monotonic())))
        _metrica(chave, "espera_ms", round((time.monotonic() - inicio) * 1000))
        yield ingresso
    except RedisError as exc:
        falhou = True
        logger.warning("ia_admissao_sem_redis pool=%s erro=%s", pool, type(exc).__name__)
        raise CapacidadeIndisponivel() from exc
    except CapacidadeIndisponivel:
        falhou = True
        _metrica(chave, "rejeicoes")
        raise
    except BaseException:
        falhou = True
        raise
    finally:
        if adquirida:
            _metrica(chave, "duracao_ms", round((time.monotonic() - inicio_chamada) * 1000))
            _metrica(chave, "erros" if falhou or ingresso.status >= 400 else "sucessos")
        def liberar(estado):
            estado.get("fila", {}).pop(identidade, None)
            existia = estado.get("ativos", {}).pop(identidade, None)
            if existia and ingresso.uso is not None:
                _atualizar(estado, limites, _agora())
                for campo, previsto, real in zip(("entrada", "saida"), (entrada, saida), ingresso.uso):
                    if limites.get(campo, 0):
                        # Uso maior que a estimativa deixa dívida para o próximo refill.
                        estado[campo] = min(limites[campo], estado[campo] + previsto - real)
        try:
            _alterar(chave, liberar)
        except (RedisError, CapacidadeIndisponivel):
            logger.warning("ia_liberacao_lease_pendente pool=%s", pool)


def _retry_after(headers):
    valor = headers.get("retry-after")
    if valor is None and headers.get("retry-after-ms"):
        try:
            espera = float(headers["retry-after-ms"]) / 1000
            return max(0, espera) if math.isfinite(espera) else None
        except (TypeError, ValueError):
            return None
    if valor is None:
        return None
    try:
        espera = float(valor)
    except (ValueError, TypeError):
        try:
            espera = parsedate_to_datetime(valor).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, espera) if math.isfinite(espera) else None


def espera_retentativa(servico, modelo, resposta, tentativa, prazo, max_tentativas):
    """Publica cooldown mesmo sem tempo para tentar novamente. Nunca encurta Retry-After."""
    status = getattr(resposta, "status_code", None)
    if status not in (429, 503, 529):
        return False
    # Cota financeira não é uma sobrecarga transitória.
    try:
        corpo = resposta.json()
        erro = corpo.get("error", corpo.get("detail", {}))
        if isinstance(erro, dict) and (erro.get("details", {}) or {}).get("error_code") == "enforced_spend_limit_reached":
            return False
        if isinstance(erro, dict) and erro.get("status") in ("quota_exceeded", "payment_issue"):
            return False
    except (AttributeError, ValueError, TypeError):
        pass
    pool = nome_pool(servico, modelo)
    chave = _chave(pool)
    espera = _retry_after(getattr(resposta, "headers", {}))
    if espera is None:
        espera = random.uniform(.75, 1.25) * 1.5 * 2 ** (tentativa - 1)
    if status == 429:
        _metrica(chave, "429")
    try:
        agora = _agora()
        _alterar(chave, lambda estado: estado.update(pausa_ate=max(estado.get("pausa_ate", 0), agora + espera)))
    except RedisError as exc:
        raise CapacidadeIndisponivel() from exc
    if tentativa >= max_tentativas or espera >= prazo - time.monotonic():
        return False
    _metrica(chave, "retries")
    logger.warning("ia_retentativa pool=%s status=%s tentativa=%s espera_s=%.2f", pool, status, tentativa, espera)
    time.sleep(espera)
    return True


def executar(servico, modelo, operacao, *, timeout_s, max_tentativas=None, entrada=0, saida=0):
    """Retry só em rejeição explícita; timeout/conexão interrompida pode já ter sido cobrado."""
    prazo = prazo_operacao(timeout_s)
    max_tentativas = max_tentativas if max_tentativas is not None else settings.ia_retentativas
    for tentativa in range(1, max(1, max_tentativas) + 1):
        erro = None
        with vaga(servico, modelo, prazo=prazo, entrada=entrada, saida=saida) as ingresso:
            try:
                resposta = operacao(max(.001, prazo - time.monotonic()))
            except Exception as exc:
                resposta = getattr(exc, "response", None)
                if resposta is None:
                    raise
                erro = exc
            status = getattr(resposta, "status_code", 200)
            ingresso.observar(resposta)
            if status >= 400:
                ingresso.registrar_uso(0, 0)
            uso = getattr(resposta, "usage", None)
            if uso is not None:
                ingresso.registrar_uso((getattr(uso, "input_tokens", 0) or 0)
                                       + (getattr(uso, "cache_creation_input_tokens", 0) or 0),
                                       getattr(uso, "output_tokens", 0) or 0)
                _metrica(ingresso.chave, "entrada_tokens", ingresso.uso[0])
                _metrica(ingresso.chave, "saida_tokens", ingresso.uso[1])
                _metrica(ingresso.chave, "cache_read_tokens", getattr(uso, "cache_read_input_tokens", 0) or 0)
        if espera_retentativa(servico, modelo, resposta, tentativa, prazo, max_tentativas):
            continue
        if erro is not None:
            raise erro
        return resposta


def estado_provedores():
    """Somente para administração: sem credenciais, textos ou dados de outras contas."""
    pools = set(settings.ia_limites_provedores) - {"llm"}
    pools.update(nome_pool("llm", modelo) for modelo in settings.ia_tarifas_llm)
    pools.add(nome_pool("llm", settings.llm_classification_model))
    pools.update(settings.ia_limites_por_pool)
    resultado = []
    try:
        agora = _agora()
        for pool in sorted(pools):
            chave, limites = _chave(pool), _limites(pool)
            estado = json.loads(redis_client.get(chave) or "{}")
            _atualizar(estado, limites, agora)
            totais = dict.fromkeys(_METRICAS, 0)
            with redis_client.pipeline() as pipe:
                for minuto in range(int(agora // 60) - 14, int(agora // 60) + 1):
                    pipe.hgetall(f"{chave}:metricas:{minuto}")
                for metricas in pipe.execute():
                    for campo in totais:
                        totais[campo] += int(metricas.get(campo, 0))
            alertas = []
            if len(estado["ativos"]) >= limites["concorrencia"] * .7:
                alertas.append("concorrencia_acima_70_porcento")
            if totais["429"]:
                alertas.append("rate_limit_detectado")
            if totais["rejeicoes"]:
                alertas.append("geracoes_recusadas")
            resultado.append({"pool": pool, "limites": limites, "ativos": len(estado["ativos"]),
                              "fila": len(estado["fila"]), "pausa_s": max(0, estado.get("pausa_ate", 0) - agora),
                              "observado": estado.get("observado", {}), "alertas": alertas,
                              "disponivel": {c: estado.get(c) for c in ("rpm", "entrada", "saida") if limites.get(c)},
                              "ultimos_15_minutos": totais})
        return {"redis_disponivel": True, "provedores": resultado}
    except RedisError:
        return {"redis_disponivel": False, "provedores": []}
