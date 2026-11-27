"""Cortes de música pro ao vivo: início (silêncio/locução de videoclipe), fim (silêncio, fala ou cauda
longa) e início do vocal (pra locutor falar sobre a introdução, o "ramp" de rádio).

Mesmo critério das automações de rádio (Autocue/Liquidsoap, PlayIt, Airtime): o silêncio é medido RELATIVO ao
volume da própria faixa, não por um dBFS fixo -- um limiar absoluto confundia introdução baixinha de balada com
silêncio. Tudo é melhor esforço: qualquer falha (yt-dlp, ffmpeg, rede, STT) devolve "sem corte" e a música toca
inteira, como sempre tocou; nunca bloqueia a geração do próximo bloco.
"""
import json
import logging
import subprocess
from dataclasses import dataclass

import httpx
import numpy as np
import yt_dlp

from app.config.redis_client import redis_client, redis_sessao
from app.config.settings import settings
from app.guardrails.provedores import executar

logger = logging.getLogger("radialista.audio_analysis")

# Cache por video_id -- o corte de uma música não muda, mesmo cache longo da duração
# (app/live/music.py::_CACHE_TTL_DURACAO_SEGUNDOS).
_CACHE_TTL_SEGUNDOS = 30 * 24 * 60 * 60
# Falha de rede/yt-dlp/STT: tenta de novo em alguns minutos em vez de gravar "sem corte" por 30 dias.
_CACHE_TTL_FALHA_SEGUNDOS = 10 * 60
_FALHA = "falha"
_SEM_VOCAL = "sem_vocal"

# --- envelope de volume -------------------------------------------------------------------------
_TAXA_HZ = 8000  # só o envelope interessa: mono 8 kHz decodifica rápido e basta pra medir volume
_PASSO_S = 0.05  # um quadro de volume (RMS) a cada 50 ms

# silêncio = quadro mais de _SILENCIO_REL_DB abaixo do volume típico da faixa (percentil 90 dos quadros).
_PERCENTIL_REFERENCIA = 90
_SILENCIO_REL_DB = 32
_PISO_SILENCIO_DB = -75.0
# faixa inteira abaixo disso (dBFS) é áudio mudo/corrompido: não há referência confiável, não corta.
_PISO_MUSICA_DB = -50.0
_DURACAO_MIN_SILENCIO_S = 1.2

# --- início ---------------------------------------------------------------------------------------
# janela do COMEÇO onde procurar o fim de um silêncio (locução/vinheta/dead air antes da música): a maior
# introdução falada de videoclipe raramente passa disso.
_JANELA_INICIAL_SEGUNDOS_MAX = 20
_JANELA_INICIAL_FRACAO = 0.15
# corte de início menor que isso não vale a pena (silêncio curto é só o ataque natural da faixa).
_CORTE_INICIO_MINIMO_SEGUNDOS = 2
# folga antes do primeiro som: o startSeconds do YouTube é inteiro e o ataque não pode ser comido.
_PRE_ROLL_S = 0.15

# --- fim --------------------------------------------------------------------------------------------
_JANELA_FINAL_SEGUNDOS_MIN = 45
_JANELA_FINAL_FRACAO = 0.25
# nunca corta nos primeiros segundos por erro de detecção.
_CORTE_MINIMO_SEGUNDOS = 20
# "cauda longa": depois do último trecho forte (>= ref - _CAUDA_REL_DB) a faixa ainda soa por mais de
# _CAUDA_MAX_S -- reverb/acorde sustentado/aplauso baixinho. Corta _CAUDA_MANTER_S depois do último trecho
# forte (o player faz o fade de saída antes do corte, ver FADE_MUSICA_SAIDA_S no useLiveEngine).
_CAUDA_REL_DB = 18
_CAUDA_MAX_S = 8.0
_CAUDA_MANTER_S = 4.0
_SUAVIZACAO_QUADROS = 10  # 0,5 s: uma batida isolada não conta como "trecho forte"
# corte a menos que isso do fim do vídeo não compensa.
_GANHO_MIN_FIM_S = 2.0

# --- janelas de decodificação -----------------------------------------------------------------------
# até isso decodifica a faixa inteira (referência de volume mais confiável); acima (mix de horas da música de
# fundo) só cabeça e final.
_DURACAO_MAX_INTEIRA_S = 10 * 60
_CABECA_FAIXA_LONGA_S = 90
_FINAL_FAIXA_LONGA_S = 180

# limites de tempo pra nunca travar a geração do próximo bloco ao vivo por causa de uma análise de áudio.
_TIMEOUT_EXTRACAO_SEGUNDOS = 10
_TIMEOUT_FFMPEG_SEGUNDOS = 25

# --- início do vocal (ramp) -----------------------------------------------------------------------
# quanto da música, a partir do início tocado, vai pro STT: introdução maior que isso não cabe numa fala de
# locutor de qualquer jeito (ver lib/falaSobreIntro.ts no painel).
_JANELA_VOCAL_SEGUNDOS = 70
_TIMEOUT_STT_SEGUNDOS = 25
_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


@dataclass(frozen=True)
class Cortes:
    inicio: int = 0
    fim: int | None = None


# ====================================================================================================
# Núcleo puro (numpy) -- testável sem rede nem ffmpeg
# ====================================================================================================

def envelope_db(amostras: np.ndarray, taxa_hz: int = _TAXA_HZ, passo_s: float = _PASSO_S) -> np.ndarray:
    """Volume RMS em dBFS de cada quadro de `passo_s` (amostras float em [-1, 1])."""
    por_quadro = max(1, int(taxa_hz * passo_s))
    n_quadros = len(amostras) // por_quadro
    if n_quadros == 0:
        return np.empty(0)
    quadros = amostras[: n_quadros * por_quadro].astype(np.float64).reshape(n_quadros, por_quadro)
    rms = np.sqrt((quadros ** 2).mean(axis=1))
    return 20.0 * np.log10(np.maximum(rms, 1e-6))


def referencia_db(db: np.ndarray, passo_s: float = _PASSO_S) -> float | None:
    """Volume típico da faixa (percentil 90). None quando não há áudio suficiente/audível pra medir."""
    if len(db) < int(5 / passo_s):
        return None
    ref = float(np.percentile(db, _PERCENTIL_REFERENCIA))
    return ref if ref >= _PISO_MUSICA_DB else None


def limiar_silencio_db(ref: float) -> float:
    return max(ref - _SILENCIO_REL_DB, _PISO_SILENCIO_DB)


def trechos_silenciosos(db: np.ndarray, limiar: float, duracao_min_s: float,
                        passo_s: float = _PASSO_S) -> list[tuple[float, float]]:
    """(início, fim) em segundos de cada trecho contínuo abaixo de `limiar` com ao menos `duracao_min_s`.
    O fim de um trecho que vai até o último quadro é o próprio fim do array (não houve "fim do silêncio")."""
    if len(db) == 0:
        return []
    mascara = np.concatenate(([0], (db < limiar).astype(np.int8), [0]))
    bordas = np.diff(mascara)
    inicios = np.flatnonzero(bordas == 1)
    fins = np.flatnonzero(bordas == -1)
    return [(i * passo_s, f * passo_s) for i, f in zip(inicios, fins) if (f - i) * passo_s >= duracao_min_s]


def detectar_inicio(db: np.ndarray, ref: float, duracao_total: float, passo_s: float = _PASSO_S) -> int:
    """Segundo em que a música de fato começa (depois de silêncio/locução separados dela por um silêncio), ou 0.

    `db` começa em t=0 do vídeo. Só o FIM de um silêncio que termine dentro da janela inicial conta como início
    (silêncio que continua além da janela não diz onde a música começa); o menor desses fins, a partir de
    _CORTE_INICIO_MINIMO_SEGUNDOS, é o início."""
    janela = min(_JANELA_INICIAL_SEGUNDOS_MAX, duracao_total * _JANELA_INICIAL_FRACAO)
    limite = int(janela / passo_s)
    fins = [
        fim for _, fim in trechos_silenciosos(db[:limite], limiar_silencio_db(ref), _DURACAO_MIN_SILENCIO_S, passo_s)
        if fim < limite * passo_s - passo_s and fim >= _CORTE_INICIO_MINIMO_SEGUNDOS
    ]
    if not fins:
        return 0
    return max(0, int(min(fins) - _PRE_ROLL_S))


def detectar_fim(db: np.ndarray, deslocamento_s: float, ref: float, duracao_total: float,
                 passo_s: float = _PASSO_S) -> int | None:
    """Segundo em que cortar a faixa, ou None. `db` é o trecho FINAL da faixa, que começa em `deslocamento_s`.

    Dois sinais, vale o que vier primeiro: (1) início de um silêncio longo (dead air, fala/créditos depois do
    silêncio); (2) cauda longa -- a faixa continua soando baixinho por muito tempo depois do último trecho forte."""
    candidatos: list[float] = []

    for inicio_silencio, _ in trechos_silenciosos(db, limiar_silencio_db(ref), _DURACAO_MIN_SILENCIO_S, passo_s):
        candidatos.append(deslocamento_s + inicio_silencio)

    if len(db) >= _SUAVIZACAO_QUADROS:
        suavizado = np.lib.stride_tricks.sliding_window_view(db, _SUAVIZACAO_QUADROS).max(axis=1)
        fortes = np.flatnonzero(suavizado >= ref - _CAUDA_REL_DB)
        audiveis = np.flatnonzero(db >= limiar_silencio_db(ref))
        if len(fortes) and len(audiveis):
            ultimo_forte = (fortes[-1] + _SUAVIZACAO_QUADROS) * passo_s
            ultimo_audivel = (audiveis[-1] + 1) * passo_s
            if ultimo_audivel - ultimo_forte > _CAUDA_MAX_S:
                candidatos.append(deslocamento_s + ultimo_forte + _CAUDA_MANTER_S)

    validos = [c for c in candidatos if _CORTE_MINIMO_SEGUNDOS <= c <= duracao_total - _GANHO_MIN_FIM_S]
    return round(min(validos)) if validos else None


# ====================================================================================================
# Entrada de áudio (yt-dlp + ffmpeg)
# ====================================================================================================

# Disjuntor do bloqueio anti-bot do YouTube: 3 erros em 10 min desligam a extração por 1 h. Em prod (IP da OVH)
# cada vídeo falhava 2x por bloco, com traceback, dentro do /proxima; cortes/ramp só ficam "sem corte".
_CHAVE_BOT_CONTAGEM = "cb:ytdlp_bot:contagem"
_CHAVE_BOT_BLOQUEIO = "cb:ytdlp_bot:bloqueado"
_BOT_LIMITE = 3
_BOT_JANELA_S = 10 * 60
_BOT_PAUSA_S = 60 * 60
_TTL_URL_S = 5 * 60  # a mesma URL serve ao corte do fim, do início e do vocal da mesma faixa


def _extracao_bloqueada() -> bool:
    return bool(redis_sessao.get(_CHAVE_BOT_BLOQUEIO))


def _registrar_bloqueio_bot() -> None:
    total = int(redis_sessao.incr(_CHAVE_BOT_CONTAGEM) or 0)
    if total == 1:
        redis_sessao.expire(_CHAVE_BOT_CONTAGEM, _BOT_JANELA_S)
    if total >= _BOT_LIMITE and redis_sessao.set(_CHAVE_BOT_BLOQUEIO, "1", ex=_BOT_PAUSA_S, nx=True):
        logger.warning("yt-dlp bloqueado pelo YouTube (anti-bot): extração de áudio pausada por %ss", _BOT_PAUSA_S)


def _url_audio_direta(video_id: str) -> str | None:
    if _extracao_bloqueada():
        return None
    chave_url = f"cache:ytdlp_url:{video_id}"
    em_cache = redis_sessao.get(chave_url)
    if em_cache:
        return em_cache
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
    if settings.ytdlp_cookies_file:
        opcoes["cookiefile"] = settings.ytdlp_cookies_file
    if settings.ytdlp_proxy:
        opcoes["proxy"] = settings.ytdlp_proxy
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        url = info.get("url")
        if url:
            redis_sessao.set(chave_url, url, ex=_TTL_URL_S)
        return url
    except Exception as erro:
        if "confirm you" in str(erro) and "bot" in str(erro):
            _registrar_bloqueio_bot()
            # sem traceback: eram ~500 por 90 min; o disjuntor já registra a pausa
            logger.warning("Falha ao extrair URL de audio direta (anti-bot): video_id=%s", video_id)
        else:
            logger.warning("Falha ao extrair URL de audio direta: video_id=%s", video_id, exc_info=True)
        return None


def _decodificar(url_audio: str, inicio_s: float = 0.0, duracao_s: float | None = None) -> np.ndarray | None:
    """Áudio mono 8 kHz (float) do trecho pedido, ou None se o ffmpeg falhar/estourar o tempo."""
    comando = ["ffmpeg", "-nostdin", "-loglevel", "error"]
    if inicio_s > 0:
        comando += ["-ss", f"{inicio_s:.2f}"]
    comando += ["-i", url_audio]
    if duracao_s is not None:
        comando += ["-t", f"{duracao_s:.2f}"]
    comando += ["-vn", "-ac", "1", "-ar", str(_TAXA_HZ), "-f", "s16le", "-"]
    try:
        resultado = subprocess.run(comando, capture_output=True, timeout=_TIMEOUT_FFMPEG_SEGUNDOS)
    except (subprocess.TimeoutExpired, OSError):
        logger.warning("Falha ao decodificar audio pra analise de cortes")
        return None
    if resultado.returncode != 0 or not resultado.stdout:
        return None
    return np.frombuffer(resultado.stdout, dtype="<i2").astype(np.float32) / 32768.0


def _inicio_janela_final(duracao_total: int) -> float:
    return max(
        float(_CORTE_MINIMO_SEGUNDOS),
        duracao_total - max(_JANELA_FINAL_SEGUNDOS_MIN, duracao_total * _JANELA_FINAL_FRACAO),
    )


def _analisar(video_id: str, duracao_total: int) -> Cortes | None:
    """Cortes da faixa, ou None quando a análise não pôde rodar (falha transitória, não vale cachear longo)."""
    url_audio = _url_audio_direta(video_id)
    if url_audio is None:
        return None

    if duracao_total <= _DURACAO_MAX_INTEIRA_S:
        amostras = _decodificar(url_audio)
        if amostras is None:
            return None
        db = envelope_db(amostras)
        db_cabeca, db_final, deslocamento_final = db, db[int(_inicio_janela_final(duracao_total) / _PASSO_S):], \
            int(_inicio_janela_final(duracao_total) / _PASSO_S) * _PASSO_S
        db_referencia = db
    else:
        # mix longo (música de fundo): decodifica só cabeça e final -- a faixa inteira seria lenta demais.
        amostras_cabeca = _decodificar(url_audio, 0.0, _CABECA_FAIXA_LONGA_S)
        deslocamento_final = float(duracao_total - _FINAL_FAIXA_LONGA_S)
        amostras_final = _decodificar(url_audio, deslocamento_final, _FINAL_FAIXA_LONGA_S)
        if amostras_cabeca is None or amostras_final is None:
            return None
        db_cabeca, db_final = envelope_db(amostras_cabeca), envelope_db(amostras_final)
        db_referencia = np.concatenate((db_cabeca, db_final))

    ref = referencia_db(db_referencia)
    if ref is None:
        return Cortes()
    inicio = detectar_inicio(db_cabeca, ref, duracao_total)
    fim = detectar_fim(db_final, deslocamento_final, ref, duracao_total)
    if fim is not None and fim <= inicio + _CORTE_MINIMO_SEGUNDOS:
        fim = None
    return Cortes(inicio=inicio, fim=fim)


def obter_cortes(video_id: str, duracao_total: int | None) -> Cortes:
    """Início e fim seguros da faixa. Só analisa vídeo de duração conhecida (sem ela não dá pra delimitar a
    janela final). Qualquer falha devolve Cortes() (sem corte) e a música toca inteira."""
    if not duracao_total or duracao_total <= _CORTE_MINIMO_SEGUNDOS:
        return Cortes()

    chave = f"cache:musica_cortes:{video_id}"
    em_cache = redis_client.get(chave)
    if em_cache is not None:
        if em_cache == _FALHA:
            return Cortes()
        dados = json.loads(em_cache)
        return Cortes(inicio=int(dados["inicio"]), fim=dados["fim"])

    cortes = _analisar(video_id, duracao_total)
    if cortes is None:
        redis_client.set(chave, _FALHA, ex=_CACHE_TTL_FALHA_SEGUNDOS)
        return Cortes()
    redis_client.set(chave, json.dumps({"inicio": cortes.inicio, "fim": cortes.fim}), ex=_CACHE_TTL_SEGUNDOS)
    return cortes


def obter_inicio_seguro(video_id: str, duracao_total: int | None) -> int:
    """Segundo em que a música de fato começa (0 = sem corte)."""
    return obter_cortes(video_id, duracao_total).inicio


def obter_fim_seguro(video_id: str, duracao_total: int | None) -> int | None:
    """Segundo em que cortar a música antes de silêncio/fala/cauda longa no final (None = toca até o fim)."""
    return obter_cortes(video_id, duracao_total).fim


# ====================================================================================================
# Início do vocal (ramp)
# ====================================================================================================

def primeira_palavra_s(resposta_stt: dict) -> float | None:
    """Início (s) da primeira PALAVRA da transcrição (marcação de áudio como "[música suave]" não conta)."""
    for palavra in resposta_stt.get("words") or []:
        if palavra.get("type") == "word" and palavra.get("start") is not None:
            return float(palavra["start"])
    return None


def _extrair_mp3(url_audio: str, inicio_s: float, duracao_s: float) -> bytes | None:
    comando = ["ffmpeg", "-nostdin", "-loglevel", "error"]
    if inicio_s > 0:
        comando += ["-ss", f"{inicio_s:.2f}"]
    comando += ["-i", url_audio, "-t", f"{duracao_s:.2f}", "-vn", "-ac", "1", "-ar", "16000",
                "-b:a", "48k", "-f", "mp3", "-"]
    try:
        resultado = subprocess.run(comando, capture_output=True, timeout=_TIMEOUT_FFMPEG_SEGUNDOS)
    except (subprocess.TimeoutExpired, OSError):
        logger.warning("Falha ao extrair trecho de audio pra deteccao do vocal")
        return None
    return resultado.stdout if resultado.returncode == 0 and resultado.stdout else None


def _transcrever_palavras(audio_mp3: bytes) -> dict:
    """Scribe com timestamp de palavra. Levanta em erro de rede/HTTP -- quem chama trata como falha."""
    cabecalhos = {"xi-api-key": settings.elevenlabs_api_key}
    dados = {"model_id": settings.ramp_musica_stt_modelo, "timestamps_granularity": "word",
             "tag_audio_events": "true"}

    with httpx.Client(timeout=_TIMEOUT_STT_SEGUNDOS) as cliente:
        resposta = executar(
            "stt", settings.ramp_musica_stt_modelo,
            lambda restante: cliente.post(_STT_URL, headers=cabecalhos, data=dados,
                                          files={"file": ("trecho.mp3", audio_mp3, "audio/mpeg")}, timeout=restante),
            timeout_s=_TIMEOUT_STT_SEGUNDOS,
        )
        resposta.raise_for_status()
        return resposta.json()


def _calcular_inicio_vocal(video_id: str, inicio_segundos: int) -> float | None | str:
    """Segundo (do vídeo) em que o vocal entra; None = sem palavra na janela; _FALHA = não deu pra medir."""
    url_audio = _url_audio_direta(video_id)
    if url_audio is None:
        return _FALHA
    audio = _extrair_mp3(url_audio, float(inicio_segundos), _JANELA_VOCAL_SEGUNDOS)
    if audio is None:
        return _FALHA
    try:
        primeira = primeira_palavra_s(_transcrever_palavras(audio))
    except Exception:
        logger.warning("Falha ao transcrever trecho pra achar o inicio do vocal: video_id=%s", video_id, exc_info=True)
        return _FALHA
    return None if primeira is None else inicio_segundos + primeira


def obter_inicio_vocal(video_id: str, inicio_segundos: int, duracao_total: int | None) -> float | None:
    """Segundo (do vídeo) em que o vocal entra, medido pela primeira palavra cantada (STT com timestamp), ou None
    quando não dá pra saber -- nesse caso o locutor fala ANTES da música, como sempre falou. A introdução
    instrumental (inicio_vocal - inicio_segundos) é o espaço que o locutor pode usar falando por cima.

    PlayIt/Airtime e outras automações não detectam isso sozinhas (a marca de intro é manual); aqui a transcrição
    faz o papel do operador. Resultado cacheado por faixa+início (custo de STT só na 1a vez)."""
    if not settings.ramp_musica_habilitado or not settings.elevenlabs_api_key:
        return None
    if not duracao_total or duracao_total <= _CORTE_MINIMO_SEGUNDOS:
        return None

    chave = f"cache:musica_inicio_vocal:{video_id}:{inicio_segundos}"
    em_cache = redis_client.get(chave)
    if em_cache is not None:
        return None if em_cache in (_SEM_VOCAL, _FALHA) else float(em_cache)

    vocal = _calcular_inicio_vocal(video_id, inicio_segundos)
    if vocal == _FALHA:
        redis_client.set(chave, _FALHA, ex=_CACHE_TTL_FALHA_SEGUNDOS)
        return None
    redis_client.set(chave, _SEM_VOCAL if vocal is None else f"{vocal:.2f}", ex=_CACHE_TTL_SEGUNDOS)
    return vocal
