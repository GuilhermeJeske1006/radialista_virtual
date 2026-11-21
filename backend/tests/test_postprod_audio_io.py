"""Medição da duração do mp3 final da fala (F2): tolera bytes que não são mp3."""

import io

import pytest
from pydub import AudioSegment
from pydub.generators import Sine


def _mp3(duracao_ms: int, canais: int = 1) -> bytes:
    segmento = Sine(330).to_audio_segment(duration=duracao_ms).apply_gain(-12).set_channels(canais)
    buffer = io.BytesIO()
    segmento.export(buffer, format="mp3")
    return buffer.getvalue()


@pytest.mark.parametrize("canais", [1, 2])
def test_duracao_mp3_s(canais):
    from app.postprod.audio_io import duracao_mp3_s

    assert duracao_mp3_s(_mp3(1000, canais)) == pytest.approx(1.0, abs=0.05)
    assert duracao_mp3_s(_mp3(2500, canais)) == pytest.approx(2.5, abs=0.05)


@pytest.mark.parametrize("entrada", [b"mp3", b"", None, b"audio-cru-processado:alfa_fm"])
def test_duracao_mp3_s_devolve_none_sem_excecao(entrada):
    from app.postprod.audio_io import duracao_mp3_s

    assert duracao_mp3_s(entrada) is None


def test_duracao_mp3_s_silencio():
    from app.postprod.audio_io import duracao_mp3_s

    buffer = io.BytesIO()
    AudioSegment.silent(duration=3000).export(buffer, format="mp3")
    assert duracao_mp3_s(buffer.getvalue()) == pytest.approx(3.0, abs=0.06)
