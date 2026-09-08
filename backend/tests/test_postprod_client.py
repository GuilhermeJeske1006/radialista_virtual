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


@pytest.mark.parametrize("canais", [1, 2])
def test_radio_fm_preserva_formato_e_controla_loudness(canais):
    import json
    import subprocess

    seg = Sine(220).to_audio_segment(duration=4000).apply_gain(-12).set_channels(canais)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    saida = postprod_client.processar_audio(buf.getvalue(), "radio_fm")
    decodificado = AudioSegment.from_file(io.BytesIO(saida), format="mp3")
    assert decodificado.channels == canais
    assert decodificado.frame_rate == seg.frame_rate
    assert abs(len(decodificado) - len(seg)) < 100
    medicao = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", "pipe:0", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        input=saida, capture_output=True, check=True,
    ).stderr.decode()
    dados = json.loads(medicao[medicao.rfind('{'):medicao.rfind('}') + 1])
    assert abs(float(dados['input_i']) - (-16)) < 1
    assert float(dados['input_tp']) <= -1


def test_radio_fm_nao_adiciona_ruido_ao_silencio():
    buf = io.BytesIO()
    AudioSegment.silent(duration=1000).export(buf, format="mp3")
    saida = postprod_client.processar_audio(buf.getvalue(), "radio_fm")
    assert AudioSegment.from_file(io.BytesIO(saida), format="mp3").rms == 0
