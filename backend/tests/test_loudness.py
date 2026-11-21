"""Loudness por segmento (F10, item 3): ffmpeg ebur128 e diferença entre segmentos."""

import shutil
import subprocess

import pytest

from app.postprod.loudness import diferencas_entre_segmentos, medir_loudness_lufs

requer_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg indisponível")


def _tom(caminho, volume_db: float) -> str:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
         "-af", f"volume={volume_db}dB", str(caminho)],
        check=True,
    )
    return str(caminho)


@requer_ffmpeg
def test_mais_6_db_de_ganho_sobe_cerca_de_6_lufs(tmp_path):
    baixo = medir_loudness_lufs(_tom(tmp_path / "baixo.wav", -20))
    alto = medir_loudness_lufs(_tom(tmp_path / "alto.wav", -14))
    assert baixo is not None and alto is not None
    assert alto - baixo == pytest.approx(6.0, abs=0.5)


@requer_ffmpeg
def test_arquivo_inexistente_nao_devolve_medida(tmp_path):
    assert medir_loudness_lufs(str(tmp_path / "nao-existe.wav")) is None


def test_diferenca_usa_a_fala_como_referencia():
    assert diferencas_entre_segmentos({"fala": -18.0, "musica": -14.0, "vinheta": -16.0}) == {
        "musica": 4.0, "vinheta": 2.0,
    }


def test_sem_fala_medida_nao_ha_referencia():
    assert diferencas_entre_segmentos({"fala": None, "musica": -14.0}) == {}


def test_segmento_sem_medida_fica_de_fora():
    assert diferencas_entre_segmentos({"fala": -18.0, "musica": None}) == {}
