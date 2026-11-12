"""Clima da cidade da rádio pelo Open-Meteo (pública, sem chave).

Desde a F5 a leitura tem horário e fonte (`obter_leitura_clima` -> `LeituraClima`): o ao vivo a recebe como dado
verificável (app.dados.fontes.de_clima), com validade contada da observação. A cada sucesso a leitura também fica
guardada como "última leitura" (TTL em ConfigDados); com a API fora, essa última volta marcada, e o bloco de dados a
diz com o horário ou a omite (contingência "fonte não atualizou", pesquisa §10). `obter_clima_atual` é o invólucro
de antes para o WhatsApp: o mesmo texto ("23°C, céu limpo") e None em falha, sem usar a última leitura.
"""

import dataclasses
import datetime
import json
import logging

import httpx

from app.config.redis_client import redis_sessao as redis_client  # estado de sessão e cache: falha aberta (F3)
from app.dados.verificavel import CONFIG_DADOS

logger = logging.getLogger("radialista.weather")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo e' publica e sem API key -- coordenadas de uma cidade praticamente
# nunca mudam, cache bem mais longo que o do clima em si.
_CACHE_TTL_GEOCODING_SEGUNDOS = 30 * 24 * 60 * 60
# Cache da consulta e retenção da última leitura: ConfigDados (clima_cache_ttl_s, clima_ultima_leitura_ttl_s).
FONTE_CLIMA = "Open-Meteo"

# Codigos WMO (https://open-meteo.com/en/docs) traduzidos pro que interessa
# pro locutor citar no ar -- nao precisa do catalogo inteiro, so' o suficiente
# pra soar natural.
_DESCRICAO_CODIGO_WMO = {
    0: "céu limpo",
    1: "predomínio de sol",
    2: "parcialmente nublado",
    3: "nublado",
    45: "neblina",
    48: "neblina com geada",
    51: "garoa fraca",
    53: "garoa",
    55: "garoa forte",
    61: "chuva fraca",
    63: "chuva",
    65: "chuva forte",
    66: "chuva congelante",
    67: "chuva congelante forte",
    71: "neve fraca",
    73: "neve",
    75: "neve forte",
    77: "granizo fino",
    80: "pancadas de chuva fracas",
    81: "pancadas de chuva",
    82: "pancadas de chuva fortes",
    85: "pancadas de neve fracas",
    86: "pancadas de neve fortes",
    95: "trovoada",
    96: "trovoada com granizo",
    99: "trovoada com granizo forte",
}


def _geocodificar(cidade: str) -> tuple[float, float] | None:
    chave = f"weather:geo:{cidade.lower()}"
    cache = redis_client.get(chave)
    if cache is not None:
        dados = json.loads(cache)
        return (dados["lat"], dados["lon"]) if dados else None

    try:
        resposta = httpx.get(
            GEOCODING_URL,
            params={"name": cidade, "count": 1, "language": "pt", "format": "json"},
            timeout=5.0,
        )
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao geocodificar cidade: %r", cidade, exc_info=True)
        return None

    resultados = resposta.json().get("results") or []
    if not resultados:
        redis_client.set(chave, json.dumps(None), ex=_CACHE_TTL_GEOCODING_SEGUNDOS)
        return None

    coordenadas = (resultados[0]["latitude"], resultados[0]["longitude"])
    redis_client.set(
        chave,
        json.dumps({"lat": coordenadas[0], "lon": coordenadas[1]}),
        ex=_CACHE_TTL_GEOCODING_SEGUNDOS,
    )
    return coordenadas


@dataclasses.dataclass(frozen=True)
class LeituraClima:
    cidade: str
    temperatura_c: float
    codigo: int
    descricao: str
    observado_em: datetime.datetime    # current.time da API (hora local) - utc_offset_seconds, em UTC
    consultado_em: datetime.datetime
    fonte: str = FONTE_CLIMA
    ultima_leitura: bool = False       # veio da última leitura guardada (API fora)

    def para_json(self) -> str:
        return json.dumps({"cidade": self.cidade, "temperatura_c": self.temperatura_c, "codigo": self.codigo,
                           "descricao": self.descricao, "observado_em": self.observado_em.isoformat(),
                           "consultado_em": self.consultado_em.isoformat(), "fonte": self.fonte},
                          ensure_ascii=False)

    @classmethod
    def de_json(cls, bruto: str, ultima_leitura: bool = False) -> "LeituraClima | None":
        try:
            dados = json.loads(bruto)
            return cls(cidade=dados["cidade"], temperatura_c=float(dados["temperatura_c"]),
                       codigo=int(dados["codigo"]), descricao=dados["descricao"],
                       observado_em=datetime.datetime.fromisoformat(dados["observado_em"]),
                       consultado_em=datetime.datetime.fromisoformat(dados["consultado_em"]),
                       fonte=dados.get("fonte") or FONTE_CLIMA, ultima_leitura=ultima_leitura)
        except (ValueError, KeyError, TypeError):
            return None


def _chave_leitura(cidade: str) -> str:
    return f"weather:leitura:v2:{cidade.lower()}"


def _chave_ultima(cidade: str) -> str:
    return f"weather:ultima:{cidade.lower()}"


def _observado_em(atual: dict, offset_s, consultado_em: datetime.datetime) -> datetime.datetime:
    """`current.time` vem na hora local da cidade (timezone=auto), sem fuso; `utc_offset_seconds` o leva a UTC."""
    try:
        local = datetime.datetime.fromisoformat(str(atual["time"]))
        return (local - datetime.timedelta(seconds=int(offset_s or 0))).replace(tzinfo=datetime.timezone.utc)
    except (KeyError, ValueError, TypeError):
        return consultado_em


def _ultima_leitura(cidade: str) -> "LeituraClima | None":
    bruto = redis_client.get(_chave_ultima(cidade))
    return LeituraClima.de_json(bruto, ultima_leitura=True) if bruto else None


def obter_leitura_clima(cidade: str | None) -> LeituraClima | None:
    """Leitura atual com horário da observação e fonte, ou a última guardada se a API falhar (marcada com
    `ultima_leitura`), ou None (cidade vazia, cidade inexistente, nada guardado). Nunca levanta."""
    cidade = (cidade or "").strip()
    if not cidade:
        return None
    cache = redis_client.get(_chave_leitura(cidade))
    if cache:
        leitura = LeituraClima.de_json(cache)
        if leitura is not None:
            return leitura

    coordenadas = _geocodificar(cidade)
    if coordenadas is None:
        return _ultima_leitura(cidade)
    lat, lon = coordenadas
    try:
        resposta = httpx.get(
            FORECAST_URL,
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code", "timezone": "auto"},
            timeout=5.0,
        )
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao consultar previsao do tempo: %r", cidade, exc_info=True)
        return _ultima_leitura(cidade)

    corpo = resposta.json()
    atual = corpo.get("current") or {}
    temperatura, codigo = atual.get("temperature_2m"), atual.get("weather_code")
    if temperatura is None or codigo is None:
        return _ultima_leitura(cidade)
    consultado_em = datetime.datetime.now(datetime.timezone.utc)
    leitura = LeituraClima(cidade=cidade, temperatura_c=float(temperatura), codigo=int(codigo),
                           descricao=_DESCRICAO_CODIGO_WMO.get(codigo, "tempo variável"),
                           observado_em=_observado_em(atual, corpo.get("utc_offset_seconds"), consultado_em),
                           consultado_em=consultado_em)
    bruto = leitura.para_json()
    redis_client.set(_chave_leitura(cidade), bruto, ex=CONFIG_DADOS.clima_cache_ttl_s)
    redis_client.set(_chave_ultima(cidade), bruto, ex=CONFIG_DADOS.clima_ultima_leitura_ttl_s)
    return leitura


def obter_clima_atual(cidade: str) -> str | None:
    """Descricao curta em portugues do clima atual da cidade (ex.: '23°C, céu limpo'),
    ou None se a cidade nao foi configurada ou a consulta falhar -- falha aqui nunca
    deve derrubar a geracao do prompt, so' faz o locutor ficar sem citar o clima.
    Invólucro de obter_leitura_clima (F5): a última leitura guardada não vale aqui (o WhatsApp não tem como dizer
    o horário dela)."""
    leitura = obter_leitura_clima(cidade)
    if leitura is None or leitura.ultima_leitura:
        return None
    return f"{round(leitura.temperatura_c)}°C, {leitura.descricao}"
