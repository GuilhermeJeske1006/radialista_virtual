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


def buscar_musica(query: str, bloqueados: list[str] | None = None) -> MusicaEncontrada | None:
    if not settings.youtube_api_key:
        return None

    bloqueados_lower = [b.lower() for b in (bloqueados or [])]
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
        return None

    for item in resposta.json().get("items", []):
        titulo = item["snippet"]["title"]
        canal = item["snippet"]["channelTitle"]
        if any(termo in titulo.lower() or termo in canal.lower() for termo in bloqueados_lower):
            continue
        return MusicaEncontrada(video_id=item["id"]["videoId"], titulo=titulo, canal=canal)

    return None


def buscar_musica_fundo(generos_musicais: list[str], bloqueados: list[str] | None = None) -> MusicaEncontrada | None:
    """Musica instrumental pra tocar em loop, baixinho, enquanto o locutor fala (sem vazio entre falas)."""
    if generos_musicais:
        query = f"{random.choice(generos_musicais)} instrumental radio fundo"
    else:
        query = "musica instrumental radio fundo"

    return buscar_musica(query, bloqueados=bloqueados)
