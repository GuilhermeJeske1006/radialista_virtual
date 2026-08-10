import random
import re
from dataclasses import dataclass

import httpx

from app.config.settings import settings

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
CATEGORIA_MUSICA = "10"


@dataclass
class MusicaEncontrada:
    video_id: str
    titulo: str
    canal: str
    inicio_segundos: int = 0


TERMOS_AO_VIVO = [
    "ao vivo", "live", "live session", "live performance",
    # gravacao amadora em festa/salao/CTG (Centro de Tradicoes Gauchas) -- audio
    # de plateia, baixa qualidade, mesmo quando titulo nao usa "ao vivo"/"live"
    "ctg", "baile", "rodeio", "fandango", "camarim", "plateia",
]

# Titulo com ano solto (ex: "Banda X 1998 (720HD)") quase sempre eh gravacao
# de arquivo/fã feita em evento, nao o audio oficial da musica.
PADRAO_ANO_SOLTO = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")

# Resolucoes de webcam/celular antigo -- audio junto costuma ser ruim mesmo
# quando o video em si "roda".
TERMOS_BAIXA_RESOLUCAO = ["240p", "360p", "480p"]

# Videos que falam SOBRE a musica em vez de toca-la -- documentario/curiosidade,
# nao e' a cancao em si, nunca deve ser escolhido em nenhuma camada da busca.
TERMOS_HISTORIA = ["a história de", "a historia de", "por trás da música", "por tras da musica", "curiosidades sobre", "making of", "documentário", "documentario"]

# Versao "ao vivo" costuma abrir com fala/banter do artista antes da musica comecar --
# pula alguns segundos fixos pra reduzir chance de comecar no meio da fala.
SEGUNDOS_PULAR_AO_VIVO = 15


def _buscar_itens(query: str) -> list[dict]:
    if not settings.youtube_api_key:
        return []

    params = {
        "key": settings.youtube_api_key,
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoEmbeddable": "true",
        "videoCategoryId": CATEGORIA_MUSICA,
        "videoDefinition": "high",
        "safeSearch": "strict",
        "maxResults": 5,
    }

    try:
        resposta = httpx.get(YOUTUBE_SEARCH_URL, params=params, timeout=8.0)
        resposta.raise_for_status()
    except httpx.HTTPError:
        return []

    return resposta.json().get("items", [])


def buscar_musica(query: str, bloqueados: list[str] | None = None) -> MusicaEncontrada | None:
    """Busca a musica priorizando versao de estudio; se nao achar, cai pra versao ao vivo."""
    if not settings.youtube_api_key:
        return None

    bloqueados_lower = [b.lower() for b in (bloqueados or [])]

    def escolher(itens: list[dict], permitir_ao_vivo: bool) -> MusicaEncontrada | None:
        for item in itens:
            titulo = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            texto = f"{titulo.lower()} {canal.lower()}"
            if any(termo in texto for termo in bloqueados_lower):
                continue
            if any(termo in texto for termo in TERMOS_HISTORIA):
                continue
            if any(termo in texto for termo in TERMOS_BAIXA_RESOLUCAO):
                continue
            eh_ao_vivo = any(termo in texto for termo in TERMOS_AO_VIVO) or PADRAO_ANO_SOLTO.search(texto)
            if not permitir_ao_vivo and eh_ao_vivo:
                continue
            inicio = SEGUNDOS_PULAR_AO_VIVO if eh_ao_vivo else 0
            return MusicaEncontrada(video_id=item["id"]["videoId"], titulo=titulo, canal=canal, inicio_segundos=inicio)
        return None

    itens_estudio = _buscar_itens(f"{query} estúdio")
    resultado = escolher(itens_estudio, permitir_ao_vivo=False)
    if resultado:
        return resultado

    itens = _buscar_itens(query)

    resultado = escolher(itens, permitir_ao_vivo=False)
    if resultado:
        return resultado

    return escolher(itens, permitir_ao_vivo=True)


def buscar_musica_fundo(generos_musicais: list[str], bloqueados: list[str] | None = None) -> MusicaEncontrada | None:
    """Musica instrumental pra tocar em loop, baixinho, enquanto o locutor fala (sem vazio entre falas)."""
    if generos_musicais:
        query = f"{random.choice(generos_musicais)} instrumental radio fundo"
    else:
        query = "musica instrumental radio fundo"

    return buscar_musica(query, bloqueados=bloqueados)
