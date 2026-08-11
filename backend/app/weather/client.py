import json
import logging

import httpx

from app.config.redis_client import redis_client

logger = logging.getLogger("radialista.weather")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo e' publica e sem API key -- coordenadas de uma cidade praticamente
# nunca mudam, cache bem mais longo que o do clima em si.
_CACHE_TTL_GEOCODING_SEGUNDOS = 30 * 24 * 60 * 60
_CACHE_TTL_CLIMA_SEGUNDOS = 30 * 60

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


def obter_clima_atual(cidade: str) -> str | None:
    """Descricao curta em portugues do clima atual da cidade (ex.: '23°C, céu limpo'),
    ou None se a cidade nao foi configurada ou a consulta falhar -- falha aqui nunca
    deve derrubar a geracao do prompt, so' faz o locutor ficar sem citar o clima."""
    cidade = (cidade or "").strip()
    if not cidade:
        return None

    chave_cache = f"weather:atual:{cidade.lower()}"
    cache = redis_client.get(chave_cache)
    if cache is not None:
        return cache or None

    coordenadas = _geocodificar(cidade)
    if coordenadas is None:
        return None
    lat, lon = coordenadas

    try:
        resposta = httpx.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=5.0,
        )
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao consultar previsao do tempo: %r", cidade, exc_info=True)
        return None

    atual = resposta.json().get("current") or {}
    temperatura = atual.get("temperature_2m")
    codigo = atual.get("weather_code")
    if temperatura is None or codigo is None:
        return None

    descricao_codigo = _DESCRICAO_CODIGO_WMO.get(codigo, "tempo variável")
    descricao = f"{round(temperatura)}°C, {descricao_codigo}"
    redis_client.set(chave_cache, descricao, ex=_CACHE_TTL_CLIMA_SEGUNDOS)
    return descricao
