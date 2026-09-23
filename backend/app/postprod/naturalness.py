import numpy as np
from pedalboard import PitchShift

# tamanho da janela de pitch shift -- curta o bastante pra nao "derrapar" a fala,
# longa o bastante pra nao virar processamento por amostra (caro e sem efeito perceptivel).
_JANELA_JITTER_SEGUNDOS = 0.4


def aplicar_ruido_de_sala(audio: np.ndarray, room_noise_db: float) -> np.ndarray:
    """Soma uma camada de ruido de fundo bem baixo (room tone), pra tirar o "vacuo" digital
    dos silencios absolutos que o TTS gera. audio: shape (canais, amostras)."""
    amplitude = 10 ** (room_noise_db / 20)
    ruido = np.random.normal(0, amplitude, size=audio.shape).astype(np.float32)
    return audio + ruido


def aplicar_jitter_de_pitch(audio: np.ndarray, sr: int, jitter_cents: float) -> np.ndarray:
    """Varia sutilmente a afinacao em blocos curtos, pra quebrar a afinacao perfeita/mecanica
    do TTS. audio: shape (canais, amostras). jitter_cents <= 0 desliga o efeito."""
    if jitter_cents <= 0:
        return audio

    # pedalboard (Rubber Band) em vez de librosa.effects.pitch_shift: o librosa compilava numba
    # e alocava STFT por janela, subindo o pico de memoria em ~220MB num audio de 20s -- o
    # suficiente pra' estourar os 512MB do Render e derrubar o backend (OOM) no meio do /live.
    n_amostras = audio.shape[1]
    janela = max(int(_JANELA_JITTER_SEGUNDOS * sr), 1)
    resultado = np.empty_like(audio)

    for inicio in range(0, n_amostras, janela):
        fim = min(inicio + janela, n_amostras)
        semitons = np.random.uniform(-jitter_cents, jitter_cents) / 100.0
        resultado[:, inicio:fim] = PitchShift(semitones=semitons)(audio[:, inicio:fim], sr)[:, : fim - inicio]

    return resultado
