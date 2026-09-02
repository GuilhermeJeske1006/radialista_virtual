import json
import logging
import random
import re
import unicodedata
from dataclasses import dataclass, field

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

# Musica de fundo toca em loop e corta num ponto seguro (ver obter_fim_seguro/fim_segundos),
# entao nao precisa ser faixa unica curta -- ao contrario da busca normal (_DURACAO_MAX_SEGUNDOS),
# aqui um mix ambiente longo e' o resultado ESPERADO: busca por "instrumental radio fundo" no
# YouTube devolve quase so' mix de 1-3h+ (compilacao "radio" e' literalmente isso), entao um
# teto de 8min zera 100% dos candidatos nessa busca especifica.
_DURACAO_MAX_FUNDO_SEGUNDOS = 4 * 60 * 60


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


# Palavras que nao carregam sentido de genero sozinhas -- ignoradas ao extrair as palavras-chave
# de um genero pedido (ver _palavras_chave_genero), pra "chamame e xote" virar ["chamame", "xote"]
# em vez de incluir "e" como palavra-chave exigida.
_PALAVRAS_IGNORADAS_GENERO = {"e", "de", "da", "do", "dos", "das", "musica", "música"}


def _palavras_chave_genero(genero: str) -> list[str]:
    normalizado = _sem_acento(genero.lower())
    palavras = re.split(r"[\s,/]+", normalizado)
    return [p for p in palavras if p and p not in _PALAVRAS_IGNORADAS_GENERO]


@dataclass
class MusicaEncontrada:
    video_id: str
    titulo: str
    canal: str
    inicio_segundos: int = 0
    # Segundo em que cortar antes do fim do video (silencio longo ou fala apos a
    # musica -- ver app/live/audio_analysis.py). None = toca ate o fim do video.
    fim_segundos: int | None = None
    # Contexto real do video (descricao/tags/ano, ver _buscar_metadados_musica) -- usado pra
    # dar ao locutor material real pra comentar a musica antes de toca-la (ver
    # resumir_contexto_musica em app.llm.client), em vez de so' saber titulo/canal.
    descricao: str = ""
    tags: list[str] = field(default_factory=list)
    ano: str | None = None
    # Duracao real do video inteiro, em segundos (buscada via YouTube Data API, ver
    # _buscar_duracoes) -- ja era buscada so' pra filtrar candidatos na faixa valida e depois
    # descartada; guardada aqui pra caller (ver MusicaBlocoItem em app.live.router) saber
    # quanto tempo a musica realmente dura, em vez de nao ter dado nenhum.
    duracao_segundos: int | None = None


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

# Cover/karaoke amador feito em casa -- audio ruim/duvidoso mesmo quando a duracao e titulo
# passam nos outros filtros. Nunca relaxado (nem no ultimo recurso): radio profissional nao
# pode tocar isso no lugar da faixa oficial.
TERMOS_QUALIDADE_DUVIDOSA = [
    "cover", "covers", "karaoke", "karaokê", "playback", "caseiro", "amador",
    "gravado em casa", "gravado no quarto", "voz e violão", "voz e violao",
    "só violão", "so violao", "instrumental cover",
]

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
PADRAO_TOP_N = re.compile(r"top\s*\d+|\btop\b.{0,40}\b(19|20)\d{2}\b")
TERMOS_COLETANEA = [
    "as mais tocadas", "as mais ouvidas", "melhores musicas", "melhores músicas",
    "mega funk", "setlist", "coletanea", "coletânea", "playlist", "sequencia de",
    "sequência de", "só hits", "so hits", "sucessos", "grandes sucessos",
    "sem parar", "non stop", "nonstop", "hora de musica", "hora de música",
    "horas de musica", "horas de música", "musicas para trabalhar", "músicas para trabalhar",
]

# Conteudo educativo/institucional SOBRE musica (tutorial, bastidores de producao,
# entrevista) -- mesma familia de TERMOS_HISTORIA, so' que fala do "como fazer"
# em vez do "como a musica ficou" (ex: "This is how music producers make content...").
TERMOS_CONTEUDO_SOBRE = [
    "how to", "how music", "tutorial", "explained", "breakdown", "masterclass",
    "content for social media", "vlog", "podcast", "interview", "entrevista",
    "behind the scenes", "backstage", "episódio", "episodio", "episode",
]

# Shorts/Reels sao recorte vertical de poucos segundos, nunca a faixa completa --
# a duracao minima (acima) ja bloqueia o formato classico de ate 60s, isso aqui
# pega o que passa dela com o formato ainda marcado no titulo (shorts hoje aceita
# ate 3min). "reel"/"reels" solto fica de fora pra nao confundir com o genero/danca
# irlandes do mesmo nome (ex.: "Irish Reel", "fiddle reel").
PADRAO_SHORTS_REELS = re.compile(r"#shorts?\b|#reels?\b|\bshorts?\b|\(reels?\)|\[reels?\]")

# Trecho entre parenteses/colchetes costuma ser so' o "sotaque" do titulo (Official Video,
# Ao Vivo, Lyrics...), nunca parte do nome da musica -- removido antes de comparar com o
# historico da sessao (ver _titulo_normalizado).
PADRAO_PARENTESES = re.compile(r"[\(\[][^)\]]*[\)\]]")

# Palavras de "versao" que ainda descrevem a MESMA musica (estudio/ao vivo/remix/lyrics...) --
# removidas na normalizacao pra "Artista - Musica (Ao Vivo)" e "Artista - Musica (Official
# Video)" caírem no mesmo titulo normalizado e o historico da sessao barrar a repeticao mesmo
# quando o video_id (e o video em si) e' diferente.
_PADRAO_TERMOS_VERSAO = re.compile(
    r"\b("
    r"official video|official audio|official music video|official lyric video|"
    r"clipe oficial|audio oficial|video oficial|"
    r"lyric video|lyrics|letra|legendado|ao vivo|live|"
    r"remix|remaster|remastered|hd|hq|4k|visualizer|video|audio|clipe"
    r")\b"
)


def _titulo_normalizado(titulo: str) -> str:
    """Chave de comparacao pra detectar a MESMA musica em titulos com "sotaque" diferente
    (ver _PADRAO_TERMOS_VERSAO) -- usada pra nunca repetir uma faixa no mesmo programa, mesmo
    quando o locutor (ou o proprio YouTube) devolve uma versao/video_id diferente dela."""
    texto = _sem_acento(titulo.lower())
    texto = PADRAO_PARENTESES.sub(" ", texto)
    texto = _PADRAO_TERMOS_VERSAO.sub(" ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return texto.strip()


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


def _buscar_metadados_musica(video_id: str) -> dict:
    """Descricao, tags e ano de publicacao do video ESCOLHIDO -- contexto real pra injetar no
    prompt antes do locutor falar da musica (ver resumir_contexto_musica em app.llm.client),
    em vez dele so' saber titulo/canal. So busca pro video que ja venceu a escolha (nao pros
    candidatos descartados), pra nao gastar cota da API a toa; video_id nao muda depois de
    publicado, entao o cache e' de longa duracao igual o de duracao.
    """
    if not settings.youtube_api_key:
        return {}

    chave_cache = f"cache:youtube_metadados:{video_id}"
    em_cache = redis_client.get(chave_cache)
    if em_cache is not None:
        return json.loads(em_cache)

    params = {
        "key": settings.youtube_api_key,
        "part": "snippet",
        "id": video_id,
    }

    try:
        resposta = httpx.get(YOUTUBE_VIDEOS_URL, params=params, timeout=8.0)
        resposta.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Falha ao buscar metadados de video no YouTube: video_id=%r", video_id, exc_info=True)
        return {}

    itens = resposta.json().get("items", [])
    if not itens:
        return {}

    snippet = itens[0].get("snippet", {})
    metadados = {
        # descricao pode ser bem longa (varios paragrafos de credito/link) -- trunca pro
        # prompt nao inchar com coisa que o locutor nunca vai citar.
        "descricao": (snippet.get("description") or "").strip()[:500],
        "tags": snippet.get("tags") or [],
        "ano": (snippet.get("publishedAt") or "")[:4] or None,
    }
    redis_client.set(chave_cache, json.dumps(metadados), ex=_CACHE_TTL_DURACAO_SEGUNDOS)
    return metadados


def _preencher_extras(resultado: MusicaEncontrada, duracoes: dict[str, int]) -> MusicaEncontrada:
    resultado.duracao_segundos = duracoes.get(resultado.video_id)
    resultado.fim_segundos = obter_fim_seguro(resultado.video_id, duracoes.get(resultado.video_id))
    metadados = _buscar_metadados_musica(resultado.video_id)
    resultado.descricao = metadados.get("descricao", "")
    resultado.tags = metadados.get("tags") or []
    resultado.ano = metadados.get("ano")
    return resultado


_LIMITE_PADRAO_POR_CANAL = 2


def buscar_musica(
    query: str,
    genero: str | None = None,
    bloqueados: list[str] | None = None,
    evitar_video_ids: set[str] | None = None,
    titulos_tocados: set[str] | None = None,
    canais_recentes: dict[str, int] | None = None,
    limite_por_canal: int = _LIMITE_PADRAO_POR_CANAL,
    duracao_max_segundos: int = _DURACAO_MAX_SEGUNDOS,
    preferir_cantada: bool = False,
) -> MusicaEncontrada | None:
    """Busca a musica priorizando versao de estudio; se nao achar, cai pra versao ao vivo.

    evitar_video_ids/canais_recentes evitam repetir a mesma faixa ou saturar de um so
    artista num programa (ver _registrar_musica_tocada em app.live.router) -- passados
    pelo caller, que e' quem sabe o que ja tocou nessa sessao. Se o limite por canal
    deixar zero resultado (genero com pouca variedade), a 2a rodada ignora esse limite
    em vez de travar a busca -- so' o video_id exato, o titulo (ver titulos_tocados) e os
    bloqueados continuam valendo.

    titulos_tocados e' o pareceido de evitar_video_ids mas por MUSICA em vez de por video: guarda
    o titulo normalizado (ver _titulo_normalizado) de cada faixa ja tocada no programa, pra um
    reupload/versao diferente da mesma musica (estudio tocado antes, YouTube devolve a versao
    "Ao Vivo" ou "Remix" com video_id novo) nao passar como faixa inedita. Nunca relaxado, mesma
    logica de "nunca repetir" de evitar_video_ids.

    genero (opcional) exige que ao menos uma palavra-chave dele apareca no titulo/canal do
    resultado -- sem isso, a busca do YouTube as vezes deriva pra um genero vizinho (pedir
    "xote" e devolver "chamame", por exemplo, porque o algoritmo de relacionados do YouTube
    mistura generos regionais proximos). So relaxa (aceita qualquer genero) como ultimo
    recurso, mesma logica de "preferencia, nunca bloqueio duro" do limite por canal/duracao.

    preferir_cantada evita versao instrumental quando a musica vai tocar pros ouvintes (o
    locutor anuncia a faixa por nome/artista, instrumental sem voz quebra a expectativa) --
    False por padrao porque buscar_musica_fundo QUER instrumental (musica de fundo enquanto
    o locutor fala). Mesma logica de preferencia, nunca bloqueio duro: relaxa antes do
    genero (instrumental do genero certo ainda bate mais que vocal fora do genero).
    """
    if not settings.youtube_api_key:
        return None

    bloqueados_lower = [b.lower() for b in (bloqueados or [])]
    evitar_video_ids = evitar_video_ids or set()
    titulos_tocados = titulos_tocados or set()
    canais_recentes = canais_recentes or {}
    palavras_genero = _palavras_chave_genero(genero) if genero else []

    def escolher(
        itens: list[dict],
        permitir_ao_vivo: bool,
        respeitar_limite_canal: bool,
        duracoes: dict[str, int],
        respeitar_duracao: bool = True,
        respeitar_genero: bool = True,
        respeitar_vocal: bool = True,
    ) -> MusicaEncontrada | None:
        def repetido(canal: str) -> bool:
            return respeitar_limite_canal and canais_recentes.get(canal.lower(), 0) >= limite_por_canal

        def musica_repetida(titulo: str) -> bool:
            return _titulo_normalizado(titulo) in titulos_tocados

        def vocal_invalido(texto: str) -> bool:
            if not respeitar_vocal or not preferir_cantada:
                return False
            return "instrumental" in texto

        def genero_invalido(texto_sem_acento: str) -> bool:
            if not respeitar_genero or not palavras_genero:
                return False
            return not any(palavra in texto_sem_acento for palavra in palavras_genero)

        def duracao_invalida(video_id: str) -> bool:
            duracao = duracoes.get(video_id)
            # Duracao CONHECIDA fora da faixa e' sempre invalida, mesmo no passo relaxado --
            # bug corrigido aqui: antes, respeitar_duracao=False perdoava qualquer duracao
            # conhecida (inclusive medley/coletanea de 1h que passou reto pelo filtro de
            # titulo), quando o unico caso que deveria ser perdoado como ultimo recurso e'
            # duracao DESCONHECIDA (falha/cota da API de videos.list).
            if duracao is None:
                return respeitar_duracao
            return not (_DURACAO_MIN_SEGUNDOS <= duracao <= duracao_max_segundos)

        # 1a passada: canal oficial (auto-gerado "- Topic" ou VEVO) so' publica
        # faixa em si na maioria dos casos -- pula blocklist de reacao/historia/
        # tutorial, mas NAO pula coletanea/top-n: selo tambem publica playlist/
        # mix inteiro no canal oficial (ex: "Verao Brasil 2026 ... So Hits"),
        # so' respeita bloqueados/repeticao/duracao/coletanea.
        for item in itens:
            titulo = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            video_id = item["id"]["videoId"]
            texto = f"{titulo.lower()} {canal.lower()}"
            if video_id in evitar_video_ids or repetido(canal) or duracao_invalida(video_id):
                continue
            if musica_repetida(titulo):
                continue
            if genero_invalido(_sem_acento(texto)):
                continue
            if vocal_invalido(texto):
                continue
            if PADRAO_SHORTS_REELS.search(texto):
                continue
            if any(termo in texto for termo in TERMOS_QUALIDADE_DUVIDOSA):
                continue
            if any(termo in texto for termo in TERMOS_COLETANEA) or PADRAO_TOP_N.search(texto):
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
            if musica_repetida(titulo):
                continue
            if genero_invalido(_sem_acento(texto)):
                continue
            if vocal_invalido(texto):
                continue
            if any(termo in texto for termo in bloqueados_lower):
                continue
            if PADRAO_SHORTS_REELS.search(texto):
                continue
            if any(termo in texto for termo in TERMOS_HISTORIA):
                continue
            if any(termo in texto for termo in TERMOS_REACAO):
                continue
            if any(termo in texto for termo in TERMOS_QUALIDADE_DUVIDOSA):
                continue
            if any(termo in texto for termo in TERMOS_COLETANEA) or PADRAO_TOP_N.search(texto):
                continue
            if any(termo in texto for termo in TERMOS_CONTEUDO_SOBRE):
                continue
            if any(termo in texto for termo in TERMOS_BAIXA_RESOLUCAO):
                continue
            eh_ao_vivo = any(termo in texto for termo in TERMOS_AO_VIVO) or PADRAO_ANO_SOLTO.search(texto)
            if eh_ao_vivo and (not permitir_ao_vivo or not _eh_canal_oficial(canal)):
                # ao vivo so' e' aceitavel de canal oficial/grande produtora (selo/VEVO/"- Topic")
                # -- gravacao de show por canal qualquer e' exatamente o audio duvidoso que
                # preferir_cantada/TERMOS_QUALIDADE_DUVIDOSA ja tentam barrar, so' que pelo
                # lado "ao vivo" em vez de "caseiro".
                continue
            inicio = SEGUNDOS_PULAR_AO_VIVO if eh_ao_vivo else 0
            return MusicaEncontrada(video_id=video_id, titulo=titulo, canal=canal, inicio_segundos=inicio)
        return None

    itens_estudio = _buscar_itens(f"{query} estúdio")
    itens_geral = _buscar_itens(query)
    duracoes = _buscar_duracoes(
        [item["id"]["videoId"] for item in itens_estudio + itens_geral]
    )

    # respeitar_genero relaxa primeiro que tudo (loop mais externo): genero pedido e' o sinal
    # mais importante de acerto (ver docstring), so' aceita resultado de genero errado quando
    # nenhuma combinacao de duracao/canal/ao-vivo achou nada dentro do genero pedido.
    # respeitar_duracao relaxa por ultimo, so' quando nenhuma combinacao de canal/ao-vivo
    # deu resultado -- mesma logica de "nao trava a busca" do limite_por_canal: preferencia
    # de qualidade, nunca bloqueio duro (senao um genero onde toda gravacao disponivel foge
    # da faixa 40s-8min, ex. so' tem versao "ao vivo" longa, para de tocar musica nenhuma).
    for respeitar_genero in (True, False):
        if not palavras_genero and not respeitar_genero:
            break  # sem genero pedido, relaxar de novo e' repetir a mesma busca a toa.
        for respeitar_vocal in (True, False):
            if not preferir_cantada and not respeitar_vocal:
                break  # nao foi pedido vocal, relaxar de novo e' repetir a mesma busca a toa.
            for respeitar_duracao in (True, False):
                for respeitar_limite_canal in (True, False):
                    resultado = escolher(
                        itens_estudio,
                        permitir_ao_vivo=False,
                        respeitar_limite_canal=respeitar_limite_canal,
                        duracoes=duracoes,
                        respeitar_duracao=respeitar_duracao,
                        respeitar_genero=respeitar_genero,
                        respeitar_vocal=respeitar_vocal,
                    )
                    if resultado:
                        return _preencher_extras(resultado, duracoes)

                    resultado = escolher(
                        itens_geral,
                        permitir_ao_vivo=False,
                        respeitar_limite_canal=respeitar_limite_canal,
                        duracoes=duracoes,
                        respeitar_duracao=respeitar_duracao,
                        respeitar_genero=respeitar_genero,
                        respeitar_vocal=respeitar_vocal,
                    )
                    if resultado:
                        return _preencher_extras(resultado, duracoes)

                    resultado = escolher(
                        itens_geral,
                        permitir_ao_vivo=True,
                        respeitar_limite_canal=respeitar_limite_canal,
                        duracoes=duracoes,
                        respeitar_duracao=respeitar_duracao,
                        respeitar_genero=respeitar_genero,
                        respeitar_vocal=respeitar_vocal,
                    )
                    if resultado:
                        return _preencher_extras(resultado, duracoes)

    logger.warning("Nenhuma musica encontrada: query=%r genero=%r", query, genero)
    return None


def buscar_musica_fundo(generos_musicais: list[str], bloqueados: list[str] | None = None) -> MusicaEncontrada | None:
    """Musica instrumental pra tocar em loop, baixinho, enquanto o locutor fala (sem vazio entre falas)."""
    if generos_musicais:
        query = f"{random.choice(generos_musicais)} instrumental radio fundo"
    else:
        query = "musica instrumental radio fundo"

    return buscar_musica(query, bloqueados=bloqueados, duracao_max_segundos=_DURACAO_MAX_FUNDO_SEGUNDOS)
