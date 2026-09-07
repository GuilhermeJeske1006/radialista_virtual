import logging
import re
import subprocess

import yt_dlp

from app.config.redis_client import redis_client

logger = logging.getLogger("radialista.audio_analysis")

# Cache por video_id -- o corte seguro de uma musica nao muda, mesmo cache
# longo do que a duracao (app/live/music.py::_CACHE_TTL_DURACAO_SEGUNDOS).
_CACHE_TTL_SEGUNDOS = 30 * 24 * 60 * 60

# Sentinela gravado no cache quando a analise rodou mas nao achou corte
# seguro (ex.: musica sem trecho de silencio/fala no final) -- sem isso o
# proximo pedido tentaria a analise de novo pra sempre.
_SEM_CORTE = "sem_corte"

# so' considera silencio como "fim da faixa" se ele comecar depois de uma
# fatia minima do video (evita cortar break/silencio no meio da musica) --
# usa o maior entre um piso fixo e uma fracao da duracao total.
_JANELA_FINAL_SEGUNDOS_MIN = 45
_JANELA_FINAL_FRACAO = 0.25

# janela onde procurar fala/silencio no COMECO do video (locucao de radio, vinheta
# do canal, "confira" antes da musica comecar) -- bem mais curta que a do fim,
# intro falada raramente passa disso.
_JANELA_INICIAL_SEGUNDOS_MAX = 20
_JANELA_INICIAL_FRACAO = 0.15

# limiar de "silencio" pro ffmpeg (dB) e duracao minima pra contar (segundos) --
# curto demais pega respiracao/pausa natural da musica, nao o fim dela.
_RUIDO_DB = "-35dB"
_DURACAO_MIN_SILENCIO = "1.2"

# nao deixa cortar nos primeiros segundos por erro de deteccao.
_CORTE_MINIMO_SEGUNDOS = 20

# corte de inicio menor que isso nao vale a pena aplicar (silence_end proximo de
# zero costuma ser so' o ataque natural da faixa/fade-in, nao locucao de verdade).
_CORTE_INICIO_MINIMO_SEGUNDOS = 2

# limites de tempo pra nunca travar a geracao do proximo bloco ao vivo por
# causa de uma analise de audio -- falha ou timeout aqui e' sempre "sem
# corte", nunca bloqueia a musica.
_TIMEOUT_EXTRACAO_SEGUNDOS = 10
_TIMEOUT_FFMPEG_SEGUNDOS = 15

_SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")


def _url_audio_direta(video_id: str) -> str | None:
    opcoes = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": _TIMEOUT_EXTRACAO_SEGUNDOS,
        # client "web" (padrao) costuma vir sem os formatos de audio de fato
        # disponiveis (exige token que o yt-dlp nem sempre resolve) -- "android"
        # devolve a URL direta de forma bem mais confiavel.
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        return info.get("url")
    except Exception:
        logger.warning("Falha ao extrair URL de audio direta: video_id=%s", video_id, exc_info=True)
        return None


def _pontos_de_silencio(url_audio: str, offset_segundos: float) -> list[float]:
    """So decodifica a partir de offset_segundos (a janela final da faixa) -- analisar
    o audio inteiro seria muito mais lento pra um sinal que so' nos interessa no final."""
    try:
        resultado = subprocess.run(
            [
                "ffmpeg", "-ss", str(offset_segundos), "-i", url_audio,
                "-af", f"silencedetect=noise={_RUIDO_DB}:d={_DURACAO_MIN_SILENCIO}",
                "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_FFMPEG_SEGUNDOS,
        )
    except (subprocess.TimeoutExpired, OSError):
        logger.warning("Falha ao rodar ffmpeg pra deteccao de silencio")
        return []

    return [offset_segundos + float(m.group(1)) for m in _SILENCE_START_RE.finditer(resultado.stderr)]


def _pontos_de_fim_de_silencio_inicial(url_audio: str, duracao_segundos: float) -> list[float]:
    """So decodifica os primeiros duracao_segundos (a janela inicial da faixa). Ponto onde
    um trecho de silencio TERMINA nessa janela costuma marcar onde a musica de fato comeca,
    separando ela de locucao/vinheta falada antes (ao contrario do fim, aqui o que interessa
    e' o fim do silencio, nao o inicio dele)."""
    try:
        resultado = subprocess.run(
            [
                "ffmpeg", "-i", url_audio, "-t", str(duracao_segundos),
                "-af", f"silencedetect=noise={_RUIDO_DB}:d={_DURACAO_MIN_SILENCIO}",
                "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_FFMPEG_SEGUNDOS,
        )
    except (subprocess.TimeoutExpired, OSError):
        logger.warning("Falha ao rodar ffmpeg pra deteccao de silencio (janela inicial)")
        return []

    return [float(m.group(1)) for m in _SILENCE_END_RE.finditer(resultado.stderr)]


def obter_inicio_seguro(video_id: str, duracao_total: int | None) -> int:
    """Segundo em que a musica de fato comeca (depois de locucao/vinheta falada no
    comeco do video), ou 0 se nao ha corte necessario/possivel.

    Mesmo espirito best-effort de obter_fim_seguro: qualquer falha (yt-dlp, ffmpeg,
    timeout) devolve 0 e a musica toca desde o inicio do video, como sempre tocou.
    """
    if not duracao_total or duracao_total <= _CORTE_MINIMO_SEGUNDOS:
        return 0

    chave_cache = f"cache:musica_inicio_seguro:{video_id}"
    em_cache = redis_client.get(chave_cache)
    if em_cache is not None:
        return int(em_cache)

    inicio_seguro = _calcular_inicio_seguro(video_id, duracao_total)
    redis_client.set(chave_cache, str(inicio_seguro), ex=_CACHE_TTL_SEGUNDOS)
    return inicio_seguro


def _calcular_inicio_seguro(video_id: str, duracao_total: int) -> int:
    url_audio = _url_audio_direta(video_id)
    if url_audio is None:
        return 0

    janela_inicial = min(_JANELA_INICIAL_SEGUNDOS_MAX, duracao_total * _JANELA_INICIAL_FRACAO)

    candidatos = [
        t for t in _pontos_de_fim_de_silencio_inicial(url_audio, janela_inicial)
        if t >= _CORTE_INICIO_MINIMO_SEGUNDOS
    ]
    if not candidatos:
        return 0

    return round(min(candidatos))


def obter_fim_seguro(video_id: str, duracao_total: int | None) -> int | None:
    """Segundo em que e' seguro cortar a musica (antes de silencio longo ou trecho
    falado no final do video), ou None se nao ha corte necessario/possivel.

    So analisa video com duracao conhecida -- sem duracao nao da pra delimitar a
    janela final com seguranca. Melhor esforco: qualquer falha (yt-dlp, ffmpeg,
    timeout) devolve None e a musica toca inteira, como sempre tocou.
    """
    if not duracao_total or duracao_total <= _CORTE_MINIMO_SEGUNDOS:
        return None

    chave_cache = f"cache:musica_fim_seguro:{video_id}"
    em_cache = redis_client.get(chave_cache)
    if em_cache is not None:
        return None if em_cache == _SEM_CORTE else int(em_cache)

    fim_seguro = _calcular_fim_seguro(video_id, duracao_total)
    redis_client.set(chave_cache, str(fim_seguro) if fim_seguro is not None else _SEM_CORTE, ex=_CACHE_TTL_SEGUNDOS)
    return fim_seguro


def _calcular_fim_seguro(video_id: str, duracao_total: int) -> int | None:
    url_audio = _url_audio_direta(video_id)
    if url_audio is None:
        return None

    inicio_janela_final = max(
        _CORTE_MINIMO_SEGUNDOS,
        duracao_total - max(_JANELA_FINAL_SEGUNDOS_MIN, duracao_total * _JANELA_FINAL_FRACAO),
    )

    candidatos = _pontos_de_silencio(url_audio, inicio_janela_final)
    if not candidatos:
        return None

    return round(min(candidatos))
