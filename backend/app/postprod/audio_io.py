import io

import numpy as np
from pydub import AudioSegment

# ElevenLabs devolve mp3 puro em memoria (app/tts/client.py:sintetizar_audio), sem passar
# por disco -- por isso a conversao aqui e' toda em memoria via pydub/ffmpeg, sem arquivo
# temporario. pedalboard opera sobre numpy array float32, nao sobre mp3 diretamente.


def mp3_bytes_para_array(mp3_bytes: bytes) -> tuple[np.ndarray, int, int]:
    """Decodifica mp3 (bytes) num array float32 normalizado em [-1, 1], shape (canais, amostras).
    Retorna tambem sample_rate e sample_width (bytes) do audio original, pra re-encodar igual."""
    segmento = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")

    amostras = np.array(segmento.get_array_of_samples()).astype(np.float32)
    if segmento.channels > 1:
        amostras = amostras.reshape((-1, segmento.channels)).T
    else:
        amostras = amostras.reshape(1, -1)

    pico = float(1 << (8 * segmento.sample_width - 1))
    amostras /= pico

    return amostras, segmento.frame_rate, segmento.sample_width


def array_para_mp3_bytes(audio: np.ndarray, sample_rate: int, sample_width: int = 2) -> bytes:
    """Re-encoda um array float32 (canais, amostras) de volta pra mp3 (bytes)."""
    audio = np.clip(audio, -1.0, 1.0)
    pico = float(1 << (8 * sample_width - 1)) - 1
    tipo_inteiro = {2: np.int16, 4: np.int32}[sample_width]
    amostras_inteiras = (audio.T.reshape(-1) * pico).astype(tipo_inteiro)

    segmento = AudioSegment(
        amostras_inteiras.tobytes(),
        frame_rate=sample_rate,
        sample_width=sample_width,
        channels=audio.shape[0],
    )

    buffer = io.BytesIO()
    segmento.export(buffer, format="mp3")
    return buffer.getvalue()
