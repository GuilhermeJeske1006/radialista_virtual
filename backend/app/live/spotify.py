import json
import logging
import re
from base64 import b64encode

import httpx

from app.config.redis_client import redis_client
from app.config.settings import settings
from app.live.music import _sem_acento, _titulo_normalizado

logger = logging.getLogger("radialista.spotify")

# Sinal de que a faixa da Spotify e' na verdade um "pacote" (medley de 2+ musicas emendadas
# num so' credito, ou sessao com varios artistas) em vez de uma musica avulsa -- testado ao
# vivo contra a API de verdade: gravadora/canal (ex.: "MJ Records") as vezes cataloga um video
# de "musica A / musica B" como se fosse 1 faixa so', e o filtro de titulo do YouTube (ver
# TERMOS_COLETANEA em app.live.music) so' pega isso pela PALAVRA ("coletanea", "sequencia de"),
# nao pelo FORMATO do titulo -- aqui pega o formato antes de virar query pro YouTube.
_PADRAO_FAIXA_COMPOSTA = re.compile(r"/|\bsess(a|õ)o\b|\bsessions?\b", re.IGNORECASE)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"

# Lista de faixas por genero muda pouco (repertorio de um estilo musical e' estavel) --
# TTL longo pra' so' consultar a Spotify de novo raramente, nao a cada musica tocada.
_CACHE_TTL_CATEGORIA_SEGUNDOS = 14 * 24 * 60 * 60

# Abaixo disso, a lista cacheada (depois de tirar o que ja tocou recentemente) e' considerada
# "pequena demais" e forca nova consulta a' Spotify, mesmo com TTL ainda valido -- senao um
# genero de nicho, tocado com frequencia, repete sempre as mesmas poucas faixas restantes.
_MIN_FAIXAS_DISPONIVEIS = 5

# Busca varios artistas do genero em vez de 1 so', pra' lista final ter variedade.
#
# 10, nao mais: testado ao vivo contra a Spotify API de verdade, limit>10 em /v1/search devolve
# 400 "Invalid limit" pra' esta app (restricao de quota nao documentada publicamente -- doc
# oficial diz max 50, mas na pratica app novo/client-credentials fica preso em 10).
_MAX_ARTISTAS_POR_GENERO = 10

# "Artistas" que na verdade sao canal/marca de compilacao, nao um artista/dupla de verdade --
# testado ao vivo: pra busca livre por 'sertanejo', a Spotify devolve esse tipo de conta lado a
# lado com artista real ("Sertanejo Play", "Fazendinha Sessions", "CountryBeat" ao lado de
# "Henrique & Juliano", "Jorge & Mateus"). Faixa creditada a essas contas tende a ser
# compilacao/mix tambem -- gera query fraca (artista+titulo genericos demais) e o YouTube erra o
# casamento com mais frequencia. popularity/genres vem None nesta app (ver _buscar_artistas_do_
# genero), entao o nome e' o unico sinal disponivel pra filtrar.
_TERMOS_ARTISTA_MARCA = ["sessions", "session", "beat", "play", "mix", "cover", "covers", "playlist"]


def _parece_marca_ou_compilacao(nome_artista: str, genero: str) -> bool:
    nome_normalizado = _sem_acento(nome_artista.lower())
    if _sem_acento(genero.lower()).strip() in nome_normalizado:
        # Artista de verdade raramente leva o proprio genero no nome (ninguem se chama
        # "Henrique & Juliano Sertanejo") -- quem leva costuma ser canal/marca generica
        # ("Sertanejo Play", "Sertanejo Raiz e Sofrencia").
        return True
    return any(termo in nome_normalizado for termo in _TERMOS_ARTISTA_MARCA)


def _chave_cache_categoria(genero: str) -> str:
    return f"spotify:categoria:{genero.lower().strip()}"


def _obter_token() -> str | None:
    """Token de acesso via Client Credentials Flow (sem login de usuario -- so' acessa
    catalogo publico). Cacheado no Redis ate pouco antes de expirar, pra' nao autenticar de
    novo a cada busca de categoria."""
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        return None

    chave_cache = "cache:spotify_token"
    em_cache = redis_client.get(chave_cache)
    if em_cache is not None:
        return em_cache

    credenciais = b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()

    try:
        resposta = httpx.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {credenciais}"},
            timeout=8.0,
        )
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao autenticar na Spotify API", exc_info=True)
        return None

    dados = resposta.json()
    token = dados["access_token"]
    # Margem de 60s pra' nunca usar um token que expira no meio de uma chamada seguinte.
    redis_client.set(chave_cache, token, ex=max(dados.get("expires_in", 3600) - 60, 60))
    return token


def _buscar_artistas_do_genero(token: str, genero: str) -> list[dict]:
    """Artistas relevantes pro genero/estilo pedido, via busca livre por texto na Search API.

    O filtro dedicado 'genre:\"...\"' (type=artist) foi testado ao vivo contra a API de verdade
    e devolve ZERO resultado pra generos brasileiros ("sertanejo", "piseiro", "modao" etc) --
    a taxonomia de genero da propria Spotify so' reconhece um vocabulario fixo, majoritariamente
    ingles/ocidental, e nao inclui esses generos mesmo sendo reais e enormes (Henrique & Juliano,
    Jorge & Mateus...). Busca livre pelo texto puro do genero, sem filtro de campo, devolve
    exatamente os artistas certos -- mesma coisa que um ouvinte digitaria na propria Spotify."""
    try:
        resposta = httpx.get(
            f"{SPOTIFY_API_URL}/search",
            params={"q": genero, "type": "artist", "limit": _MAX_ARTISTAS_POR_GENERO},
            headers={"Authorization": f"Bearer {token}"},
            timeout=8.0,
        )
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao buscar artistas do genero na Spotify API: genero=%r", genero, exc_info=True)
        return []

    artistas = resposta.json().get("artists", {}).get("items", [])
    artistas = [
        artista for artista in artistas
        if artista.get("name") and not _parece_marca_ou_compilacao(artista["name"], genero)
    ]
    # popularity vem None nesta app (ver _faixas_do_artista) -- `or 0` evita depender de um
    # campo que a Spotify nao preenche mais; na pratica so' preserva a ordem de relevancia que
    # a propria Search API ja devolve.
    return sorted(artistas, key=lambda artista: artista.get("popularity") or 0, reverse=True)


def _faixas_do_artista(token: str, nome_artista: str) -> list[tuple[str, str]]:
    """(artista, titulo) das faixas do artista, via Track Search filtrada por 'artist:\"Nome\"'.

    'Get Several Artists' Top Tracks' (endpoint dedicado, por artist_id) foi testado ao vivo e
    devolve 403 Forbidden pra qualquer artista/mercado nesta app -- faz parte do pacote de
    endpoints que a Spotify restringiu pra apps criados depois de nov/2024 (Recommendations,
    Related Artists, Top Tracks e outros, mesma leva). Track Search (usada aqui) continua
    liberada; filtrar por nome em vez de artist_id tem uma desvantagem (nome ambiguo podendo
    casar com artista errado do mesmo nome), aceitavel porque o filtro de titulo/canal em
    app.live.music (TERMOS_QUALIDADE_DUVIDOSA etc) e' quem valida o resultado final de verdade,
    isto aqui e' so' geracao de candidatos."""
    try:
        resposta = httpx.get(
            f"{SPOTIFY_API_URL}/search",
            params={"q": f'artist:"{nome_artista}"', "type": "track", "limit": 10},
            headers={"Authorization": f"Bearer {token}"},
            timeout=8.0,
        )
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning(
            "Falha ao buscar faixas do artista na Spotify API: artista=%r", nome_artista, exc_info=True
        )
        return []

    resultado = []
    for faixa in resposta.json().get("tracks", {}).get("items", []):
        artistas_faixa = faixa.get("artists") or []
        titulo = faixa.get("name")
        if not artistas_faixa or not titulo:
            continue
        if _PADRAO_FAIXA_COMPOSTA.search(titulo):
            continue
        resultado.append((artistas_faixa[0]["name"], titulo))
    return resultado


def _buscar_faixas_do_spotify(genero: str) -> list[tuple[str, str]]:
    token = _obter_token()
    if not token:
        return []

    faixas: list[tuple[str, str]] = []
    vistos: set[tuple[str, str]] = set()
    for artista in _buscar_artistas_do_genero(token, genero):
        for artista_nome, titulo in _faixas_do_artista(token, artista["name"]):
            chave = (artista_nome.lower(), titulo.lower())
            if chave in vistos:
                continue
            vistos.add(chave)
            faixas.append((artista_nome, titulo))
    return faixas


def buscar_faixas_por_categoria(genero: str, excluir_titulos: set[str] | None = None) -> list[tuple[str, str]]:
    """Lista de faixas oficiais (artista, titulo) do genero pedido, vinda da Spotify Web API e
    cacheada no Redis (ver _CACHE_TTL_CATEGORIA_SEGUNDOS) -- so' consulta a API na 1a vez que o
    genero e' pedido, ou quando a lista some do cache (TTL expirado) ou fica pequena demais
    depois de tirar o que ja tocou (ver _MIN_FAIXAS_DISPONIVEIS), nunca a cada musica tocada.

    excluir_titulos e' o titulo normalizado (ver _titulo_normalizado em app.live.music) de cada
    faixa ja tocada no programa/radio -- mesma logica de titulos_tocados em buscar_musica, pra'
    nao sugerir de novo uma faixa que acabou de tocar so' porque ainda esta' na lista cacheada.

    Lista vazia (sem credenciais configuradas, genero sem match na Spotify, falha de rede) e' o
    caso normal de "integracao desativada ou indisponivel agora" -- caller (ver
    _escolher_query_musica em app.live.router) cai pro comportamento anterior a' esta
    integracao (sugestao de musica via LLM).
    """
    excluir_titulos = excluir_titulos or set()
    chave_cache = _chave_cache_categoria(genero)

    em_cache = redis_client.get(chave_cache)
    faixas_cacheadas: list[tuple[str, str]] | None = None
    if em_cache is not None:
        faixas_cacheadas = [tuple(item) for item in json.loads(em_cache)]
        disponiveis = [
            (artista, titulo) for artista, titulo in faixas_cacheadas
            if _titulo_normalizado(titulo) not in excluir_titulos
        ]
        if len(disponiveis) >= _MIN_FAIXAS_DISPONIVEIS:
            return disponiveis

    faixas_novas = _buscar_faixas_do_spotify(genero)
    if not faixas_novas:
        # Spotify indisponivel/sem match agora -- ainda assim devolve o que sobrou do cache
        # antigo (mesmo pequeno) em vez de forcar o caller direto pro fallback via LLM.
        return [
            (artista, titulo) for artista, titulo in (faixas_cacheadas or [])
            if _titulo_normalizado(titulo) not in excluir_titulos
        ]

    redis_client.set(chave_cache, json.dumps(faixas_novas), ex=_CACHE_TTL_CATEGORIA_SEGUNDOS)
    return [
        (artista, titulo) for artista, titulo in faixas_novas
        if _titulo_normalizado(titulo) not in excluir_titulos
    ]
