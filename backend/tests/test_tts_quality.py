import io
from pathlib import Path

import numpy as np
import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from app.tts.quality import analisar_amostras


def wav(audio):
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    return buf.getvalue()


def fala(ms=45000):
    raw = (Path(__file__).parent / "fixtures/webrtcvad/test-audio.raw").read_bytes()
    segmento = AudioSegment(raw, sample_width=2, frame_rate=8000, channels=1)
    return (segmento * (ms // len(segmento) + 1))[:ms]


@pytest.mark.parametrize("audio", [AudioSegment.silent(duration=21000), Sine(440).to_audio_segment(duration=21000).apply_gain(-18)])
def test_rejeita_silencio_e_tom_sem_fala(audio):
    with pytest.raises(ValueError, match="fala"):
        analisar_amostras([wav(audio)])


def test_rejeita_ruido_branco():
    ruido = np.random.default_rng(42).normal(0, 2000, 16000 * 25).astype("<i2")
    with pytest.raises(ValueError, match="fala"):
        analisar_amostras([wav(AudioSegment(ruido.tobytes(), sample_width=2, channels=1, frame_rate=16000))])


def test_conta_fala_entre_multiplas_amostras_e_avisa_duracao():
    a = wav(fala(22000))
    with pytest.raises(ValueError):
        analisar_amostras([a])
    resultado = analisar_amostras([a, a])
    assert 20 <= resultado.fala_segundos < resultado.duracao_segundos == 44
    assert any("60–120" in a for a in resultado.avisos)


def test_silencio_adicionado_nao_atinge_minimo_de_fala():
    with pytest.raises(ValueError, match="fala"):
        analisar_amostras([wav(fala(5000) + AudioSegment.silent(duration=60000))])


def test_rejeita_audio_corrompido():
    with pytest.raises(ValueError, match="ler o áudio"):
        analisar_amostras([b"not-an-audio"])


def test_limita_duracao_decodificada():
    with pytest.raises(ValueError, match="3 minutos"):
        analisar_amostras([wav(AudioSegment.silent(duration=182000))])


def test_aceita_gravacao_mp4_sem_rotular_como_webm():
    buf = io.BytesIO()
    fala().export(buf, format="mp4", codec="aac")
    assert analisar_amostras([buf.getvalue()]).fala_segundos >= 20


def test_avisa_clipping():
    resultado = analisar_amostras([wav(fala().apply_gain(8))])
    assert resultado.clipping_percentual > 0.1
    assert any("estourado" in a for a in resultado.avisos)
