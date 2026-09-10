"""Inspeção local de amostras; os bytes originais seguem intactos ao provedor.

VAD não identifica pessoas nem garante ausência de música/reverberação. Os
limiares são conservadores e os avisos não equivalem a certificação de qualidade.
"""
import subprocess
import tempfile

import numpy as np
import webrtcvad
from pydantic import BaseModel

MAX_SEGUNDOS = 180
MIN_FALA_SEGUNDOS = 20


class QualidadeAudio(BaseModel):
    duracao_segundos: float
    fala_segundos: float
    clipping_percentual: float
    avisos: list[str]


def analisar_amostras(amostras: list[bytes]) -> QualidadeAudio:
    duracao = fala = clipping = total = 0
    niveis_fala = []
    niveis_fundo = []
    for conteudo in amostras:
        try:
            # MP4 pode ter o índice no final e precisar de seek. O arquivo
            # temporário é removido também em erro; playlists não são aceitas.
            with tempfile.NamedTemporaryFile() as fonte:
                fonte.write(conteudo)
                fonte.flush()
                resultado = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                     "-protocol_whitelist", "file,pipe", "-format_whitelist", "wav,mp3,mov,ogg,matroska,webm",
                     "-i", fonte.name, "-vn", "-t", str(MAX_SEGUNDOS + 1),
                     "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"],
                    capture_output=True, timeout=20, check=True,
                )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Não foi possível ler o áudio. Envie outro arquivo de áudio válido.") from exc
        pcm = np.frombuffer(resultado.stdout, dtype="<i2")
        if not len(pcm):
            raise ValueError("O arquivo não contém áudio decodificável.")
        duracao += len(pcm) / 16000
        if duracao > MAX_SEGUNDOS:
            raise ValueError("Envie até 3 minutos no total; selecione os trechos de melhor qualidade.")
        samples = pcm.astype(np.float32) / 32768
        total += len(samples)
        clipping += int(np.count_nonzero(np.abs(samples) >= 0.999))
        vad = webrtcvad.Vad(2)
        # 30 ms de PCM mono, 16 bits, 16 kHz, conforme contrato WebRTC.
        for inicio in range(0, len(pcm) - 479, 480):
            frame = samples[inicio:inicio + 480]
            rms = float(np.sqrt(np.mean(frame ** 2)))
            power = np.abs(np.fft.rfft(frame * np.hanning(480))) ** 2
            # Rejeita sinais quase puramente tonais que alguns modos de VAD
            # classificam como voz. Não pretende separar música de fala.
            tonal = float(np.partition(power, -3)[-3:].sum() / max(power.sum(), 1e-12)) > 0.85
            flatness = float(np.exp(np.mean(np.log(power + 1e-12))) / max(np.mean(power), 1e-12))
            speech = vad.is_speech(pcm[inicio:inicio + 480].tobytes(), 16000)
            if speech and rms > 0.0001 and not tonal and flatness < 0.45:
                fala += 0.03
                niveis_fala.append(rms)
            elif rms > 0:
                niveis_fundo.append(rms)
    avisos = []
    if fala < MIN_FALA_SEGUNDOS:
        raise ValueError(f"Detectamos apenas {fala:.1f}s de fala. Envie pelo menos 20s de fala audível; recomendamos 60–120s, sem música ou silêncio longo.")
    if fala < 60:
        avisos.append("Para maior fidelidade, envie 60–120 segundos de fala do mesmo locutor.")
    percentual = 100 * clipping / max(total, 1)
    if percentual > 0.1:
        avisos.append("Há indícios de áudio estourado. Reduza o ganho e grave novamente.")
    if niveis_fala and np.median(niveis_fala) < 10 ** (-38 / 20):
        avisos.append("A fala está baixa. Aproxime o microfone sem estourar o nível.")
    if len(niveis_fundo) >= 30 and niveis_fala:
        contraste = 20 * np.log10(max(float(np.median(niveis_fala)), 1e-8) / max(float(np.median(niveis_fundo)), 1e-8))
        if contraste < 12:
            avisos.append("O fundo tem nível próximo da fala. Confira ruído, música ou eco e prefira regravar em local silencioso.")
    if fala / duracao < 0.5:
        avisos.append("Boa parte do áudio não foi reconhecida como fala. Prefira trechos com menos pausas longas.")
    return QualidadeAudio(duracao_segundos=round(duracao, 2), fala_segundos=round(fala, 2),
                          clipping_percentual=round(percentual, 3), avisos=avisos)
