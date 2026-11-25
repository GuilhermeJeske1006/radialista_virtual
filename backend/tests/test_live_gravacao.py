"""POST /live/gravacao/mp3: webm da gravação da aba vira MP3 do programa completo."""
import io
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")


def _webm_de_um_segundo() -> bytes:
    r = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:a", "libopus", "-f", "webm", "pipe:1"], capture_output=True, check=True)
    return r.stdout


def test_converte_webm_em_mp3(client, account, auth_headers):
    resp = client.post("/live/gravacao/mp3", content=_webm_de_um_segundo(), headers=auth_headers(account.id))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    from pydub import AudioSegment
    seg = AudioSegment.from_file(io.BytesIO(resp.content), format="mp3")
    assert 0.8 < seg.duration_seconds < 1.4


def test_corpo_vazio_400(client, account, auth_headers):
    assert client.post("/live/gravacao/mp3", content=b"", headers=auth_headers(account.id)).status_code == 400


def test_lixo_422(client, account, auth_headers):
    assert client.post("/live/gravacao/mp3", content=b"nao e audio", headers=auth_headers(account.id)).status_code == 422


def test_exige_login(client):
    assert client.post("/live/gravacao/mp3", content=b"x").status_code in (401, 403)
