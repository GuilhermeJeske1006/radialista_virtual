"""Processamento de voz, mixagem com trilha e master das vinhetas -- ffmpeg via subprocess.

Tudo trabalha com bytes na entrada/saida e arquivos temporarios por dentro (o ffmpeg precisa de
arquivo pra ler duas entradas com seek). Qualquer falha vira ErroAudio, que o servico transforma
em status="erro" na vinheta (ver app/vinhetas/servico.py).
"""
import json
import logging
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("radialista.vinhetas.audio")

_TIMEOUT_SEGUNDOS = 60

SAMPLE_RATE = 44100

# Alvo do master. O TTS do ao vivo com perfil "radio_fm" (o que o painel pede, ver
# useLiveEngine.ts) sai em -16 LUFS (app/postprod/perfis/radio_fm.json) -- vinheta no mesmo
# nivel nao da salto de volume na troca fala -> vinheta.
LUFS_ALVO = -16.0
TRUE_PEAK_ALVO = -1.5

# Nivel da trilha antes do ducking: a trilha "cheia" (intro/cauda) fica um pouco abaixo da voz.
_LUFS_TRILHA = -18.0

_RAMPA_DUCKING_S = 0.2
_FADE_IN_TRILHA_S = 0.3


class ErroAudio(RuntimeError):
    pass


@dataclass(frozen=True)
class PresetMix:
    intro_s: float
    cauda_s: float
    fade_out_s: float
    # Eco curto so' na cauda da voz -- desligavel por parametro.
    eco: bool = False
    # De onde recortar a trilha: "inicio" ou "fim" (encerramento pega o final marcado da trilha).
    recorte: str = "inicio"


PRESETS: dict[str, PresetMix] = {
    "abertura": PresetMix(intro_s=1.5, cauda_s=2.0, fade_out_s=1.0, eco=True),
    "passagem": PresetMix(intro_s=0.5, cauda_s=1.0, fade_out_s=0.5),
    "encerramento": PresetMix(intro_s=1.0, cauda_s=3.0, fade_out_s=2.0, recorte="fim"),
}

# Sem trilha: so' um respiro curto antes/depois da voz.
_PRE_SEM_TRILHA_S = 0.1
_POS_SEM_TRILHA_S = 0.4


def _executar(args: list[str], timeout: int = _TIMEOUT_SEGUNDOS) -> subprocess.CompletedProcess:
    comando = ["ffmpeg", "-hide_banner", "-nostdin", "-y", *args]
    try:
        return subprocess.run(comando, capture_output=True, timeout=timeout, check=True)
    except subprocess.CalledProcessError as exc:
        detalhe = exc.stderr.decode("utf-8", errors="replace")[-600:]
        logger.warning("ffmpeg falhou: %s", detalhe)
        raise ErroAudio(f"ffmpeg falhou: {detalhe.strip().splitlines()[-1] if detalhe.strip() else exc}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ErroAudio(f"ffmpeg indisponivel ou travou: {exc}") from exc


def duracao_segundos(caminho: Path) -> float:
    try:
        resultado = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(caminho)],
            capture_output=True, timeout=_TIMEOUT_SEGUNDOS, check=True,
        )
        return float(json.loads(resultado.stdout)["format"]["duration"])
    except (OSError, subprocess.SubprocessError, KeyError, ValueError) as exc:
        raise ErroAudio(f"nao foi possivel medir a duracao do audio: {exc}") from exc


def duracao_bytes(conteudo: bytes, sufixo: str = ".mp3") -> float:
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / f"audio{sufixo}"
        caminho.write_bytes(conteudo)
        return duracao_segundos(caminho)


def medir_loudness(caminho: Path, filtro_prefixo: str = "") -> dict:
    """loudnorm em modo de analise -- devolve input_i (LUFS integrado), input_tp etc."""
    filtro = f"{filtro_prefixo}loudnorm=I={LUFS_ALVO}:TP={TRUE_PEAK_ALVO}:LRA=11:print_format=json"
    resultado = _executar(["-i", str(caminho), "-af", filtro, "-f", "null", "-"])
    log = resultado.stderr.decode("utf-8", errors="replace")
    try:
        return json.loads(log[log.rfind("{"): log.rfind("}") + 1])
    except ValueError as exc:
        raise ErroAudio("saida de analise do loudnorm ilegivel") from exc


def processar_voz(tts_mp3: bytes) -> bytes:
    """Voz TTS crua -> voz seca de vinheta (WAV mono 44,1 kHz): corta silencio do inicio/fim,
    tira grave abaixo de 80 Hz, realce leve de presenca (~3 kHz, +2 dB), compressao 3:1 com
    attack rapido e limiter. Guardada em WAV (sem perda) porque vai ser remixada varias vezes."""
    corte_silencio = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    filtro = ",".join([
        corte_silencio, "areverse", corte_silencio, "areverse",
        "highpass=f=80",
        "equalizer=f=3000:t=q:w=1.2:g=2",
        "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2",
        "alimiter=limit=0.89:level=false",
    ])
    with tempfile.TemporaryDirectory() as tmp:
        entrada, saida = Path(tmp) / "tts.mp3", Path(tmp) / "voz.wav"
        entrada.write_bytes(tts_mp3)
        _executar(["-i", str(entrada), "-af", filtro, "-ac", "1", "-ar", str(SAMPLE_RATE), str(saida)])
        conteudo = saida.read_bytes()
        if duracao_segundos(saida) < 0.2:
            raise ErroAudio("voz ficou vazia depois do corte de silencio")
        return conteudo


def _envelope_ducking(inicio_voz: float, fim_voz: float, volume_db: float) -> str:
    """Expressao do filtro volume: trilha cheia (1.0) fora da voz, `volume_db` durante a voz,
    com rampas lineares de 200 ms. Escolhido no lugar de sidechaincompress porque o compressor
    reduz proporcional ao nivel do sinal (a reducao real varia com a trilha e o TTS) -- aqui o
    nivel sob a voz e' exatamente volume_trilha_db, previsivel e remixavel."""
    g = 10 ** (volume_db / 20)
    a, b = max(inicio_voz - _RAMPA_DUCKING_S, 0.0), inicio_voz
    c, d = fim_voz, fim_voz + _RAMPA_DUCKING_S
    rampa_desce = f"1+({g:.6f}-1)*(t-{a:.3f})/{max(b - a, 0.001):.3f}"
    rampa_sobe = f"{g:.6f}+(1-{g:.6f})*(t-{c:.3f})/{d - c:.3f}"
    return (
        f"if(lt(t,{a:.3f}),1,if(lt(t,{b:.3f}),{rampa_desce},"
        f"if(lt(t,{c:.3f}),{g:.6f},if(lt(t,{d:.3f}),{rampa_sobe},1))))"
    )


def _filtro_eco_cauda(duracao_voz: float) -> str:
    """Eco so' nos ultimos 400 ms da voz: esse trecho vira eco "molhado" puro (in_gain=0) e soma
    por cima da voz seca, sem ecoar a frase inteira."""
    inicio_cauda = max(duracao_voz - 0.4, 0.0)
    atraso_ms = int(inicio_cauda * 1000)
    return (
        "[voz]asplit=2[seca][cauda];"
        f"[cauda]atrim=start={inicio_cauda:.3f},asetpts=PTS-STARTPTS,"
        "aecho=in_gain=0.0001:out_gain=1:delays=160|320:decays=0.35|0.18,"
        f"adelay={atraso_ms}:all=1[eco];"
        "[seca][eco]amix=inputs=2:duration=longest:normalize=0[vozfx]"
    )


# apad SEMPRE com whole_dur: "apad,atrim" sozinho nao termina no ffmpeg 7.1 (o do container
# de producao) quando a voz passa pelo ramo de eco -- o grafo fica gerando silencio pra sempre
# (chegou a escrever 6 GB de wav ate' o timeout). O "-t" na saida e' a segunda trava.
def mixar(
    voz_wav: bytes,
    trilha: bytes | None,
    papel: str,
    volume_trilha_db: float = -14.0,
    eco: bool | None = None,
) -> bytes:
    """Voz seca + trilha (ou so' voz) -> vinheta mixada e masterizada (MP3 44,1 kHz 192 kbps).

    Duracao final = intro + voz + cauda do preset do papel; a trilha e' recortada nesse tamanho
    (do inicio, ou do fim no encerramento), com fade in de 300 ms e fade out do preset."""
    preset = PRESETS.get(papel, PRESETS["passagem"])
    usar_eco = preset.eco if eco is None else eco

    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        caminho_voz = pasta / "voz.wav"
        caminho_voz.write_bytes(voz_wav)
        duracao_voz = duracao_segundos(caminho_voz)
        mix = pasta / "mix.wav"

        formato = f"aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
        cadeia_voz = f"[0:a]{formato}[voz];"
        if usar_eco:
            cadeia_voz += _filtro_eco_cauda(duracao_voz) + ";"
            rotulo_voz = "vozfx"
        else:
            rotulo_voz = "voz"

        if trilha is None:
            total = _PRE_SEM_TRILHA_S + duracao_voz + _POS_SEM_TRILHA_S
            filtro = (
                cadeia_voz
                + f"[{rotulo_voz}]adelay={int(_PRE_SEM_TRILHA_S * 1000)}:all=1,"
                f"apad=whole_dur={total:.3f},atrim=duration={total:.3f}[saida]"
            )
            _executar([
                "-i", str(caminho_voz), "-filter_complex", filtro, "-map", "[saida]", "-t", f"{total:.3f}", str(mix),
            ])
        else:
            caminho_trilha = pasta / "trilha.audio"
            caminho_trilha.write_bytes(trilha)
            duracao_trilha = duracao_segundos(caminho_trilha)
            total = preset.intro_s + duracao_voz + preset.cauda_s
            inicio_recorte = (
                max(duracao_trilha - total, 0.0) if preset.recorte == "fim" and duracao_trilha > total else 0.0
            )
            inicio_voz = preset.intro_s
            fim_voz = preset.intro_s + duracao_voz
            envelope = _envelope_ducking(inicio_voz, fim_voz, volume_trilha_db)
            filtro = (
                cadeia_voz
                + f"[1:a]{formato},atrim=start={inicio_recorte:.3f},asetpts=PTS-STARTPTS,"
                f"loudnorm=I={_LUFS_TRILHA}:TP=-2:LRA=11,{formato},"
                f"atrim=duration={total:.3f},"
                f"afade=t=in:d={_FADE_IN_TRILHA_S},"
                f"afade=t=out:st={max(total - preset.fade_out_s, 0):.3f}:d={preset.fade_out_s},"
                f"volume='{envelope}':eval=frame[cama];"
                f"[{rotulo_voz}]adelay={int(inicio_voz * 1000)}:all=1,apad=whole_dur={total:.3f},"
                f"atrim=duration={total:.3f}[vozpos];"
                "[cama][vozpos]amix=inputs=2:duration=first:normalize=0,"
                f"atrim=duration={total:.3f}[saida]"
            )
            # -stream_loop: trilha mais curta que a vinheta repete em vez de cortar no seco.
            _executar([
                "-i", str(caminho_voz), "-stream_loop", "-1", "-i", str(caminho_trilha),
                "-filter_complex", filtro, "-map", "[saida]", "-t", f"{total:.3f}", str(mix),
            ])

        return masterizar(mix)


def masterizar(caminho: Path) -> bytes:
    """loudnorm em duas passadas (-16 LUFS integrado, true peak -1,5 dBTP) -> MP3 44,1 kHz 192k."""
    medidas = medir_loudness(caminho)
    filtro = f"loudnorm=I={LUFS_ALVO}:TP={TRUE_PEAK_ALVO}:LRA=11"
    chaves = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if all(math.isfinite(float(medidas.get(k, "nan"))) for k in chaves):
        filtro += (
            f":measured_I={medidas['input_i']}:measured_TP={medidas['input_tp']}"
            f":measured_LRA={medidas['input_lra']}:measured_thresh={medidas['input_thresh']}"
            f":offset={medidas['target_offset']}:linear=true"
        )
    saida = caminho.with_name("master.mp3")
    _executar([
        "-i", str(caminho), "-af", filtro, "-ar", str(SAMPLE_RATE),
        "-c:a", "libmp3lame", "-b:a", "192k", str(saida),
    ])
    return saida.read_bytes()


def preparar_trilha(conteudo: bytes, sufixo: str = ".mp3") -> tuple[bytes, int]:
    """Qualquer trilha (IA, banco, upload) -> MP3 44,1 kHz estereo padronizado + duracao em ms,
    sem silencio no comeco nem no fim. Sem o corte, o encerramento (que recorta o FIM da trilha,
    ver PresetMix.recorte) caia no rabo mudo que a Music API as vezes deixa e saia sem musica.
    Tambem valida de verdade: arquivo que o ffmpeg nao decodifica nao e' audio."""
    # Fim com limiar mais alto que o comeco: tira tambem o decaimento longo depois do ultimo
    # acorde, nao so' o silencio digital.
    corte_inicio = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
    corte_fim = "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.05"
    with tempfile.TemporaryDirectory() as tmp:
        entrada, saida = Path(tmp) / f"entrada{sufixo}", Path(tmp) / "trilha.mp3"
        entrada.write_bytes(conteudo)
        _executar(["-i", str(entrada), "-vn", "-af", f"{corte_inicio},areverse,{corte_fim},areverse",
                   "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k", str(saida)])
        duracao = duracao_segundos(saida)
        if duracao < 1.0:
            raise ErroAudio("trilha vazia ou so' silencio")
        return saida.read_bytes(), int(duracao * 1000)
