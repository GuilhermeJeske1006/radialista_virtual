import io

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from app.postprod import client as postprod_client


def _mp3_teste(duracao_ms=300, sr=22050) -> bytes:
    seg = Sine(440).to_audio_segment(duration=duracao_ms).set_frame_rate(sr).set_channels(1)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return buf.getvalue()


def test_carregar_perfil_desconhecido_levanta_value_error():
    with pytest.raises(ValueError):
        postprod_client.carregar_perfil("perfil-que-nao-existe")


@pytest.mark.parametrize("perfil", ["alfa_fm", "jovem_pan", "classico"])
def test_carregar_perfil_existente(perfil):
    dados = postprod_client.carregar_perfil(perfil)
    assert "eq" in dados
    assert "compression" in dados
    assert "naturalness" in dados


def test_processar_audio_devolve_mp3_valido():
    entrada = _mp3_teste()
    saida = postprod_client.processar_audio(entrada, "alfa_fm")

    assert isinstance(saida, bytes)
    assert len(saida) > 0

    segmento = AudioSegment.from_file(io.BytesIO(saida), format="mp3")
    assert segmento.frame_rate == 22050
    assert segmento.channels == 1
    # duracao deve ficar proxima da original (tolerancia por causa do encode/decode mp3)
    assert abs(len(segmento) - 300) < 50


def test_processar_audio_perfil_invalido_levanta_value_error():
    with pytest.raises(ValueError):
        postprod_client.processar_audio(_mp3_teste(), "perfil-que-nao-existe")
