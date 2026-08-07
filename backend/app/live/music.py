import random
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


TERMOS_AO_VIVO = ["ao vivo", "live", "live session", "live performance"]


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
            if not permitir_ao_vivo and any(termo in texto for termo in TERMOS_AO_VIVO):
                continue
            return MusicaEncontrada(video_id=item["id"]["videoId"], titulo=titulo, canal=canal)
        return None

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
