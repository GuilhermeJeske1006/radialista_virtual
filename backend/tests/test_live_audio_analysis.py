import subprocess
from types import SimpleNamespace


from app.live import audio_analysis


def test_obter_fim_seguro_sem_duracao_devolve_none():
    assert audio_analysis.obter_fim_seguro("video1", None) is None


def test_obter_fim_seguro_duracao_curta_demais_devolve_none():
    assert audio_analysis.obter_fim_seguro("video1", 10) is None


def test_obter_fim_seguro_usa_cache(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        audio_analysis, "_calcular_fim_seguro", lambda video_id, duracao: chamadas.append(1) or 120
    )
    primeiro = audio_analysis.obter_fim_seguro("video1", 200)
    segundo = audio_analysis.obter_fim_seguro("video1", 200)
    assert primeiro == segundo == 120
    assert len(chamadas) == 1


def test_obter_fim_seguro_cache_sem_corte_devolve_none(monkeypatch):
    monkeypatch.setattr(audio_analysis, "_calcular_fim_seguro", lambda video_id, duracao: None)
    assert audio_analysis.obter_fim_seguro("video2", 200) is None
    # segunda chamada bate no cache "sem_corte", nao chama _calcular_fim_seguro de novo
    monkeypatch.setattr(
        audio_analysis,
        "_calcular_fim_seguro",
        lambda video_id, duracao: (_ for _ in ()).throw(AssertionError("nao deveria ser chamado")),
    )
    assert audio_analysis.obter_fim_seguro("video2", 200) is None


def test_url_audio_direta_devolve_url(monkeypatch):
    class _FakeYoutubeDL:
        def __init__(self, opcoes):
            self.opcoes = opcoes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            return {"url": "https://audio.direto/stream.m4a"}

    monkeypatch.setattr(audio_analysis.yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    assert audio_analysis._url_audio_direta("video1") == "https://audio.direto/stream.m4a"


def test_url_audio_direta_falha_devolve_none(monkeypatch):
    class _FakeYoutubeDL:
        def __init__(self, opcoes):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            raise RuntimeError("falha no yt-dlp")

    monkeypatch.setattr(audio_analysis.yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    assert audio_analysis._url_audio_direta("video1") is None


def test_pontos_de_silencio_extrai_do_stderr(monkeypatch):
    stderr = "silence_start: 12.5\nsome other line\nsilence_start: 30.0\n"
    monkeypatch.setattr(
        audio_analysis.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stderr=stderr, stdout=""),
    )
    pontos = audio_analysis._pontos_de_silencio("https://audio.direto/x.m4a", offset_segundos=100.0)
    assert pontos == [112.5, 130.0]


def test_pontos_de_silencio_timeout_devolve_lista_vazia(monkeypatch):
    def _levanta(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15)

    monkeypatch.setattr(audio_analysis.subprocess, "run", _levanta)
    assert audio_analysis._pontos_de_silencio("url", 0.0) == []


def test_calcular_fim_seguro_sem_url_devolve_none(monkeypatch):
    monkeypatch.setattr(audio_analysis, "_url_audio_direta", lambda video_id: None)
    assert audio_analysis._calcular_fim_seguro("video1", 200) is None


def test_calcular_fim_seguro_sem_candidatos_devolve_none(monkeypatch):
    monkeypatch.setattr(audio_analysis, "_url_audio_direta", lambda video_id: "https://audio/x.m4a")
    monkeypatch.setattr(audio_analysis, "_pontos_de_silencio", lambda url, offset: [])
    assert audio_analysis._calcular_fim_seguro("video1", 200) is None


def test_calcular_fim_seguro_devolve_menor_candidato(monkeypatch):
    monkeypatch.setattr(audio_analysis, "_url_audio_direta", lambda video_id: "https://audio/x.m4a")
    monkeypatch.setattr(audio_analysis, "_pontos_de_silencio", lambda url, offset: [180.7, 175.2])
    assert audio_analysis._calcular_fim_seguro("video1", 200) == 175
