import json
import logging
import random
import re
from dataclasses import dataclass

import httpx

from app.config.redis_client import redis_client
from app.config.settings import settings
from app.live.audio_analysis import obter_fim_seguro

logger = logging.getLogger("radialista.music")

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CATEGORIA_MUSICA = "10"

# Cota da YouTube Data API e' curta (100 buscas/dia no tier free, cada busca de musica
# gasta 1-2 chamadas aqui) -- cacheia o resultado bruto da API por query, nao o
# MusicaEncontrada final, porque o filtro de bloqueados varia por radio mesmo pra
# uma busca identica. 24h: lista de videos de uma musica praticamente nao muda.
_CACHE_TTL_SEGUNDOS = 24 * 60 * 60

# Duracao de video nao muda -- cache bem mais longo que a busca em si.
_CACHE_TTL_DURACAO_SEGUNDOS = 30 * 24 * 60 * 60

# Titulo sozinho nao pega toda "sequencia de musicas" (TERMOS_COLETANEA cobre so' os casos
# com palavra reveladora no titulo) -- video de 15-20min com varias faixas emendadas sem
# aviso nenhum no titulo passava reto e o sistema tratava como uma musica so'. Duracao real
# e' o sinal confiavel: abaixo do minimo costuma ser trailer/teaser sem a faixa inteira ou
# Short/Reel (formato classico de ate 60s), acima do maximo quase sempre e' medley/coletanea/
# podcast, nao uma cancao unica.
_DURACAO_MIN_SEGUNDOS = 61
_DURACAO_MAX_SEGUNDOS = 8 * 60


@dataclass
class MusicaEncontrada:
    video_id: str
    titulo: str
    canal: str
    inicio_segundos: int = 0
    # Segundo em que cortar antes do fim do video (silencio longo ou fala apos a
    # musica -- ver app/live/audio_analysis.py). None = toca ate o fim do video.
    fim_segundos: int | None = None


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

# Reaction/talent-show: cobre de programa tipo AGT/The Voice comentado por reagente
# ("Grammy Member Reacts", "SMASHES IT!") -- e' a performance embrulhada em comentario/
# hype de terceiro, nao a musica limpa (e o audio de plateia+reacao junto piora ainda mais).
TERMOS_REACAO = [
    "reacts", "reaction", "react to", "reacting to", "judge reacts",
    "agt", "america's got talent", "the voice", "idol", "callback", "audition",
]

# Ranking/coletanea (ex: "O TOP 50 MUDOU MUITO!", "AS MAIS TOCADAS") mistura varios
# artistas/musicas num video so' -- nunca e' a musica pedida sozinha, mesmo quando ela
# aparece no titulo pelo nome.
PADRAO_TOP_N = re.compile(r"top\s*\d+")
TERMOS_COLETANEA = [
    "as mais tocadas", "as mais ouvidas", "melhores musicas", "melhores músicas",
    "mega funk", "setlist", "coletanea", "coletânea", "playlist", "sequencia de",
]

# Conteudo educativo/institucional SOBRE musica (tutorial, bastidores de producao,
# entrevista) -- mesma familia de TERMOS_HISTORIA, so' que fala do "como fazer"
# em vez do "como a musica ficou" (ex: "This is how music producers make content...").
TERMOS_CONTEUDO_SOBRE = [
    "how to", "how music", "tutorial", "explained", "breakdown", "masterclass",
    "content for social media", "vlog", "podcast", "interview", "entrevista",
    "behind the scenes",
]

# Shorts/Reels sao recorte vertical de poucos segundos, nunca a faixa completa --
# a duracao minima (acima) ja bloqueia o formato classico de ate 60s, isso aqui
# pega o que passa dela com o formato ainda marcado no titulo (shorts hoje aceita
# ate 3min). "reel"/"reels" solto fica de fora pra nao confundir com o genero/danca
# irlandes do mesmo nome (ex.: "Irish Reel", "fiddle reel").
PADRAO_SHORTS_REELS = re.compile(r"#shorts?\b|#reels?\b|\bshorts?\b|\(reels?\)|\[reels?\]")

# Canal auto-gerado pelo YouTube pra faixa oficial (sufixo "- Topic") ou canal
# oficial de gravadora (VEVO) -- so' publica audio/clipe oficial da musica, nunca
# reacao/ranking/tutorial. Sinal positivo, prioriza sobre o blocklist abaixo.
def _eh_canal_oficial(canal: str) -> bool:
    canal_lower = canal.lower()
    return canal_lower.endswith("- topic") or "vevo" in canal_lower

# Versao "ao vivo" costuma abrir com fala/banter do artista antes da musica comecar --
# pula alguns segundos fixos pra reduzir chance de comecar no meio da fala.
SEGUNDOS_PULAR_AO_VIVO = 15


def _buscar_itens(query: str) -> list[dict]:
    if not settings.youtube_api_key:
        return []

    chave_cache = f"cache:youtube_busca:{query.lower().strip()}"
    em_cache = redis_client.get(chave_cache)
    if em_cache is not None:
        return json.loads(em_cache)

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
        logger.warning("Falha na busca do YouTube: query=%r", query, exc_info=True)
        return []

    itens = resposta.json().get("items", [])
    redis_client.set(chave_cache, json.dumps(itens), ex=_CACHE_TTL_SEGUNDOS)
    return itens


_ISO8601_DURACAO_RE = re.compile(r"^P(?:\d+D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def _parse_duracao_iso8601(duracao: str) -> int:
    match = _ISO8601_DURACAO_RE.match(duracao)
    if not match:
        return 0
    horas, minutos, segundos = (int(g) if g else 0 for g in match.groups())
    return horas * 3600 + minutos * 60 + segundos


def _buscar_duracoes(video_ids: list[str]) -> dict[str, int]:
    """Duracao em segundos de cada video_id (so' os que o YouTube conseguir devolver --
    id invalido/removido fica de fora do dict, e o caller trata ausencia como 'desconhecida'
    em vez de bloquear a musica por causa de uma falha de rede ou de cota da API)."""
    if not video_ids or not settings.youtube_api_key:
        return {}

    duracoes: dict[str, int] = {}
    faltantes = []
    for video_id in video_ids:
        em_cache = redis_client.get(f"cache:youtube_duracao:{video_id}")
        if em_cache is not None:
            duracoes[video_id] = int(em_cache)
        else:
            faltantes.append(video_id)

    if not faltantes:
        return duracoes

    params = {
        "key": settings.youtube_api_key,
        "part": "contentDetails",
        "id": ",".join(faltantes),
    }

    try:
        resposta = httpx.get(YOUTUBE_VIDEOS_URL, params=params, timeout=8.0)
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao buscar duracoes de videos no YouTube", exc_info=True)
        return duracoes

    for item in resposta.json().get("items", []):
        video_id = item["id"]
        segundos = _parse_duracao_iso8601(item["contentDetails"]["duration"])
        duracoes[video_id] = segundos
        redis_client.set(f"cache:youtube_duracao:{video_id}", segundos, ex=_CACHE_TTL_DURACAO_SEGUNDOS)

    return duracoes


_LIMITE_PADRAO_POR_CANAL = 2


def buscar_musica(
    query: str,
    bloqueados: list[str] | None = None,
    evitar_video_ids: set[str] | None = None,
    canais_recentes: dict[str, int] | None = None,
    limite_por_canal: int = _LIMITE_PADRAO_POR_CANAL,
) -> MusicaEncontrada | None:
    """Busca a musica priorizando versao de estudio; se nao achar, cai pra versao ao vivo.

    evitar_video_ids/canais_recentes evitam repetir a mesma faixa ou saturar de um so
    artista num programa (ver _registrar_musica_tocada em app.live.router) -- passados
    pelo caller, que e' quem sabe o que ja tocou nessa sessao. Se o limite por canal
    deixar zero resultado (genero com pouca variedade), a 2a rodada ignora esse limite
    em vez de travar a busca -- so' o video_id exato e os bloqueados continuam valendo.
    """
    if not settings.youtube_api_key:
        return None

    bloqueados_lower = [b.lower() for b in (bloqueados or [])]
    evitar_video_ids = evitar_video_ids or set()
    canais_recentes = canais_recentes or {}

    def escolher(
        itens: list[dict],
        permitir_ao_vivo: bool,
        respeitar_limite_canal: bool,
        duracoes: dict[str, int],
        respeitar_duracao: bool = True,
    ) -> MusicaEncontrada | None:
        def repetido(canal: str) -> bool:
            return respeitar_limite_canal and canais_recentes.get(canal.lower(), 0) >= limite_por_canal

        def duracao_invalida(video_id: str) -> bool:
            if not respeitar_duracao:
                return False
            duracao = duracoes.get(video_id)
            return duracao is not None and not (_DURACAO_MIN_SEGUNDOS <= duracao <= _DURACAO_MAX_SEGUNDOS)

        # 1a passada: canal oficial (auto-gerado "- Topic" ou VEVO) so' publica a
        # faixa em si -- pula direto o blocklist inteiro, so' respeita bloqueados/repeticao/duracao.
        for item in itens:
            titulo = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            video_id = item["id"]["videoId"]
            texto = f"{titulo.lower()} {canal.lower()}"
            if video_id in evitar_video_ids or repetido(canal) or duracao_invalida(video_id):
                continue
            if PADRAO_SHORTS_REELS.search(texto):
                continue
            if _eh_canal_oficial(canal) and not any(termo in texto for termo in bloqueados_lower):
                return MusicaEncontrada(video_id=video_id, titulo=titulo, canal=canal, inicio_segundos=0)

        for item in itens:
            titulo = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            video_id = item["id"]["videoId"]
            texto = f"{titulo.lower()} {canal.lower()}"
            if video_id in evitar_video_ids or repetido(canal) or duracao_invalida(video_id):
                continue
            if any(termo in texto for termo in bloqueados_lower):
                continue
            if PADRAO_SHORTS_REELS.search(texto):
                continue
            if any(termo in texto for termo in TERMOS_HISTORIA):
                continue
            if any(termo in texto for termo in TERMOS_REACAO):
                continue
            if any(termo in texto for termo in TERMOS_COLETANEA) or PADRAO_TOP_N.search(texto):
                continue
            if any(termo in texto for termo in TERMOS_CONTEUDO_SOBRE):
                continue
            if any(termo in texto for termo in TERMOS_BAIXA_RESOLUCAO):
                continue
            eh_ao_vivo = any(termo in texto for termo in TERMOS_AO_VIVO) or PADRAO_ANO_SOLTO.search(texto)
            if not permitir_ao_vivo and eh_ao_vivo:
                continue
            inicio = SEGUNDOS_PULAR_AO_VIVO if eh_ao_vivo else 0
            return MusicaEncontrada(video_id=video_id, titulo=titulo, canal=canal, inicio_segundos=inicio)
        return None

    itens_estudio = _buscar_itens(f"{query} estúdio")
    itens_geral = _buscar_itens(query)
    duracoes = _buscar_duracoes(
        [item["id"]["videoId"] for item in itens_estudio + itens_geral]
    )

    # respeitar_duracao relaxa por ultimo, so' quando nenhuma combinacao de canal/ao-vivo
    # deu resultado -- mesma logica de "nao trava a busca" do limite_por_canal: preferencia
    # de qualidade, nunca bloqueio duro (senao um genero onde toda gravacao disponivel foge
    # da faixa 40s-8min, ex. so' tem versao "ao vivo" longa, para de tocar musica nenhuma).
    for respeitar_duracao in (True, False):
        for respeitar_limite_canal in (True, False):
            resultado = escolher(
                itens_estudio,
                permitir_ao_vivo=False,
                respeitar_limite_canal=respeitar_limite_canal,
                duracoes=duracoes,
                respeitar_duracao=respeitar_duracao,
            )
            if resultado:
                resultado.fim_segundos = obter_fim_seguro(resultado.video_id, duracoes.get(resultado.video_id))
                return resultado

            resultado = escolher(
                itens_geral,
                permitir_ao_vivo=False,
                respeitar_limite_canal=respeitar_limite_canal,
                duracoes=duracoes,
                respeitar_duracao=respeitar_duracao,
            )
            if resultado:
                resultado.fim_segundos = obter_fim_seguro(resultado.video_id, duracoes.get(resultado.video_id))
                return resultado

            resultado = escolher(
                itens_geral,
                permitir_ao_vivo=True,
                respeitar_limite_canal=respeitar_limite_canal,
                duracoes=duracoes,
                respeitar_duracao=respeitar_duracao,
            )
            if resultado:
                resultado.fim_segundos = obter_fim_seguro(resultado.video_id, duracoes.get(resultado.video_id))
                return resultado

    logger.warning("Nenhuma musica encontrada: query=%r", query)
    return None


def buscar_musica_fundo(generos_musicais: list[str], bloqueados: list[str] | None = None) -> MusicaEncontrada | None:
    """Musica instrumental pra tocar em loop, baixinho, enquanto o locutor fala (sem vazio entre falas)."""
    if generos_musicais:
        query = f"{random.choice(generos_musicais)} instrumental radio fundo"
    else:
        query = "musica instrumental radio fundo"

    return buscar_musica(query, bloqueados=bloqueados)
