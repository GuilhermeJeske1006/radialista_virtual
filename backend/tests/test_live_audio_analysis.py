import subprocess

import numpy as np
import pytest

from app.live import audio_analysis as aa

SR = aa._TAXA_HZ


# --- sinais sintéticos -----------------------------------------------------------------------------

def _musica(segundos: float, nivel: float = 0.1, semente: int = 0) -> np.ndarray:
    """Ruído rosa-ish com volume estável: o suficiente pra um envelope de RMS constante."""
    return (np.random.default_rng(semente).standard_normal(int(segundos * SR)) * nivel).astype(np.float32)


def _silencio(segundos: float) -> np.ndarray:
    return np.zeros(int(segundos * SR), dtype=np.float32)


def _cauda(segundos: float, nivel_ini: float = 0.1, nivel_fim: float = 0.0005) -> np.ndarray:
    """Decaimento exponencial (reverb/acorde sustentado) do nível da música até quase o silêncio."""
    n = int(segundos * SR)
    envelope = np.geomspace(nivel_ini, nivel_fim, n)
    return (np.random.default_rng(1).standard_normal(n) * envelope).astype(np.float32)


def _cortes(sinal: np.ndarray):
    duracao = len(sinal) / SR
    db = aa.envelope_db(sinal)
    ref = aa.referencia_db(db)
    inicio = aa.detectar_inicio(db, ref, duracao)
    deslocamento = aa._inicio_janela_final(int(duracao))
    idx = int(deslocamento / aa._PASSO_S)
    fim = aa.detectar_fim(db[idx:], idx * aa._PASSO_S, ref, duracao)
    return inicio, fim


# --- envelope / referência -------------------------------------------------------------------------

def test_envelope_db_mede_rms_por_quadro():
    sinal = np.concatenate([_musica(1.0, 0.1), _silencio(1.0)])
    db = aa.envelope_db(sinal)
    assert len(db) == 40
    assert db[:20].mean() == pytest.approx(20 * np.log10(0.1), abs=1.0)
    assert db[20:].max() < -100


def test_envelope_db_vazio():
    assert len(aa.envelope_db(np.empty(0, dtype=np.float32))) == 0


def test_referencia_none_sem_audio_suficiente_ou_mudo():
    assert aa.referencia_db(aa.envelope_db(_musica(2.0))) is None
    assert aa.referencia_db(aa.envelope_db(_silencio(30.0))) is None


def test_limiar_e_relativo_ao_volume_da_faixa():
    assert aa.limiar_silencio_db(-10.0) == -42.0
    assert aa.limiar_silencio_db(-50.0) == aa._PISO_SILENCIO_DB  # faixa baixinha: nunca abaixo do piso


# --- início ----------------------------------------------------------------------------------------

def test_inicio_pula_silencio_de_videoclipe():
    assert _cortes(np.concatenate([_silencio(12.0), _musica(180.0)]))[0] == 11


def test_inicio_ignora_silencio_curto_do_ataque():
    assert _cortes(np.concatenate([_silencio(1.0), _musica(180.0)]))[0] == 0


def test_inicio_sem_silencio_nao_corta():
    assert _cortes(_musica(180.0))[0] == 0


def test_inicio_silencio_que_passa_da_janela_nao_corta():
    # silêncio de 25 s: o fim dele fica fora da janela inicial (20 s) -- sem como saber onde a música começa
    assert _cortes(np.concatenate([_silencio(25.0), _musica(180.0)]))[0] == 0


def test_inicio_introducao_baixinha_nao_e_silencio():
    # balada: 10 s bem baixinhos (-30 dB do resto) e depois a música: um limiar fixo de -35 dBFS cortaria aqui
    baixinho = _musica(10.0, nivel=0.1 * 10 ** (-30 / 20))
    assert _cortes(np.concatenate([baixinho, _musica(180.0)]))[0] == 0


# --- fim -------------------------------------------------------------------------------------------

def test_fim_corta_no_silencio_longo_do_final():
    inicio, fim = _cortes(np.concatenate([_musica(180.0), _silencio(15.0)]))
    assert inicio == 0
    assert fim == 180


def test_fim_corta_cauda_longa_que_nunca_vira_silencio():
    # música + 25 s de cauda decaindo (-1,8 dB/s): corta 4 s depois do último trecho forte (18 dB abaixo do
    # nível da faixa, ~10 s de cauda), em vez de tocar os 25 s até quase o silêncio
    fim = _cortes(np.concatenate([_musica(180.0), _cauda(25.0)]))[1]
    assert fim is not None
    assert 190 < fim < 200


def test_fim_cauda_curta_e_natural_nao_corta():
    # fade de 5 s no final e vídeo termina: finalização normal de música, sem corte
    assert _cortes(np.concatenate([_musica(180.0), _cauda(5.0, nivel_fim=0.01)]))[1] is None


def test_fim_sem_silencio_nem_cauda_toca_ate_o_fim():
    assert _cortes(_musica(180.0))[1] is None


def test_fim_passagem_baixinha_no_meio_da_janela_nao_e_silencio():
    # breakdown de 3 s a -25 dB no meio da janela final: não é o fim da faixa
    quieto = _musica(3.0, nivel=0.1 * 10 ** (-25 / 20))
    assert _cortes(np.concatenate([_musica(150.0), quieto, _musica(27.0)]))[1] is None


def test_fim_nunca_corta_nos_primeiros_segundos():
    # faixa de 25 s com silêncio em 10 s: abaixo do corte mínimo, ignora
    assert _cortes(np.concatenate([_musica(10.0), _silencio(5.0), _musica(10.0)]))[1] is None


def test_fim_corte_colado_no_fim_do_video_e_descartado():
    assert _cortes(np.concatenate([_musica(180.0), _silencio(1.3)]))[1] is None


# --- obter_cortes: cache, falha, janelas ------------------------------------------------------------

def test_obter_cortes_sem_duracao_ou_muito_curta_nao_analisa(monkeypatch):
    monkeypatch.setattr(aa, "_analisar", lambda *a: pytest.fail("nao deveria analisar"))
    assert aa.obter_cortes("v", None) == aa.Cortes()
    assert aa.obter_cortes("v", 10) == aa.Cortes()
    assert aa.obter_inicio_seguro("v", None) == 0
    assert aa.obter_fim_seguro("v", None) is None


def test_obter_cortes_usa_cache(monkeypatch):
    chamadas = []
    monkeypatch.setattr(aa, "_analisar", lambda v, d: chamadas.append(1) or aa.Cortes(8, 120))
    assert aa.obter_cortes("video1", 200) == aa.Cortes(8, 120)
    assert aa.obter_inicio_seguro("video1", 200) == 8
    assert aa.obter_fim_seguro("video1", 200) == 120
    assert len(chamadas) == 1


def test_obter_cortes_sem_corte_tambem_e_cacheado(monkeypatch):
    chamadas = []
    monkeypatch.setattr(aa, "_analisar", lambda v, d: chamadas.append(1) or aa.Cortes())
    assert aa.obter_fim_seguro("video2", 200) is None
    assert aa.obter_fim_seguro("video2", 200) is None
    assert len(chamadas) == 1


def test_obter_cortes_falha_vira_sem_corte_com_cache_curto(monkeypatch):
    chamadas = []
    monkeypatch.setattr(aa, "_analisar", lambda v, d: chamadas.append(1))  # None = análise não rodou
    assert aa.obter_cortes("video3", 200) == aa.Cortes()
    assert aa.obter_cortes("video3", 200) == aa.Cortes()
    assert len(chamadas) == 1
    assert 0 < aa.redis_client.ttl("cache:musica_cortes:video3") <= aa._CACHE_TTL_FALHA_SEGUNDOS


def test_analisar_sem_url_devolve_none(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: None)
    assert aa._analisar("v", 200) is None


def test_analisar_ffmpeg_falhou_devolve_none(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_decodificar", lambda *a, **k: None)
    assert aa._analisar("v", 200) is None


def test_analisar_faixa_inteira(monkeypatch):
    sinal = np.concatenate([_silencio(12.0), _musica(180.0), _silencio(15.0)])
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_decodificar", lambda url, inicio=0.0, dur=None: sinal)
    cortes = aa._analisar("v", int(len(sinal) / SR))
    assert cortes == aa.Cortes(inicio=11, fim=192)


def test_analisar_faixa_muda_nao_corta(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_decodificar", lambda *a, **k: _silencio(100.0))
    assert aa._analisar("v", 100) == aa.Cortes()


def test_analisar_mix_longo_decodifica_so_cabeca_e_final(monkeypatch):
    chamadas = []

    def falso(url, inicio=0.0, dur=None):
        chamadas.append((inicio, dur))
        return _musica(dur)

    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_decodificar", falso)
    cortes = aa._analisar("v", 3 * 3600)
    assert chamadas == [(0.0, aa._CABECA_FAIXA_LONGA_S), (3 * 3600 - aa._FINAL_FAIXA_LONGA_S, aa._FINAL_FAIXA_LONGA_S)]
    assert cortes == aa.Cortes()


def test_analisar_descarta_fim_colado_no_inicio(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    # início em 2 s e silêncio longo em 21 s (<= início + corte mínimo): vira "sem fim", a música não é picotada
    sinal = np.concatenate([_silencio(3.0), _musica(18.0), _silencio(10.0), _musica(8.0)])
    monkeypatch.setattr(aa, "_decodificar", lambda *a, **k: sinal)
    cortes = aa._analisar("v", int(len(sinal) / SR))
    assert cortes.inicio == 2
    assert cortes.fim is None


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

    monkeypatch.setattr(aa.yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    assert aa._url_audio_direta("video1") == "https://audio.direto/stream.m4a"


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

    monkeypatch.setattr(aa.yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    assert aa._url_audio_direta("video1") is None


def test_decodificar_le_pcm_do_ffmpeg(monkeypatch):
    pcm = (np.array([0, 16384, -16384], dtype="<i2")).tobytes()
    capturado = {}

    def falso(comando, **kw):
        capturado["comando"] = comando
        return subprocess.CompletedProcess(comando, 0, stdout=pcm, stderr=b"")

    monkeypatch.setattr(aa.subprocess, "run", falso)
    amostras = aa._decodificar("https://audio/x", inicio_s=30.0, duracao_s=60.0)
    assert amostras.tolist() == [0.0, 0.5, -0.5]
    assert capturado["comando"][capturado["comando"].index("-ss") + 1] == "30.00"
    assert capturado["comando"][capturado["comando"].index("-t") + 1] == "60.00"


def test_decodificar_timeout_ou_erro_devolve_none(monkeypatch):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=25)

    monkeypatch.setattr(aa.subprocess, "run", timeout)
    assert aa._decodificar("url") is None

    monkeypatch.setattr(aa.subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 1, stdout=b"", stderr=b"x"))
    assert aa._decodificar("url") is None


# --- início do vocal (ramp) ------------------------------------------------------------------------

def test_primeira_palavra_ignora_eventos_de_audio():
    resposta = {"words": [
        {"text": "[música suave]", "type": "audio_event", "start": 0.1},
        {"text": " ", "type": "spacing", "start": 0.5},
        {"text": "Quando", "type": "word", "start": 24.3},
        {"text": "eu", "type": "word", "start": 24.8},
    ]}
    assert aa.primeira_palavra_s(resposta) == 24.3


def test_primeira_palavra_instrumental_devolve_none():
    assert aa.primeira_palavra_s({"words": [{"text": "[música]", "type": "audio_event", "start": 0.0}]}) is None
    assert aa.primeira_palavra_s({}) is None


@pytest.fixture
def stt_ligado(monkeypatch):
    monkeypatch.setattr(aa.settings, "elevenlabs_api_key", "chave-de-teste")
    monkeypatch.setattr(aa.settings, "ramp_musica_habilitado", True)


def test_inicio_vocal_desligado_ou_sem_chave_nao_chama_stt(monkeypatch):
    monkeypatch.setattr(aa, "_calcular_inicio_vocal", lambda *a: pytest.fail("nao deveria chamar"))
    monkeypatch.setattr(aa.settings, "elevenlabs_api_key", "chave")
    monkeypatch.setattr(aa.settings, "ramp_musica_habilitado", False)
    assert aa.obter_inicio_vocal("v", 0, 200) is None
    monkeypatch.setattr(aa.settings, "ramp_musica_habilitado", True)
    monkeypatch.setattr(aa.settings, "elevenlabs_api_key", "")
    assert aa.obter_inicio_vocal("v", 0, 200) is None


def test_inicio_vocal_duracao_desconhecida_ou_curta(stt_ligado, monkeypatch):
    monkeypatch.setattr(aa, "_calcular_inicio_vocal", lambda *a: pytest.fail("nao deveria chamar"))
    assert aa.obter_inicio_vocal("v", 0, None) is None
    assert aa.obter_inicio_vocal("v", 0, 10) is None


def test_inicio_vocal_usa_cache_por_faixa_e_inicio(stt_ligado, monkeypatch):
    chamadas = []
    monkeypatch.setattr(aa, "_calcular_inicio_vocal", lambda v, i: chamadas.append((v, i)) or 18.9)
    assert aa.obter_inicio_vocal("v1", 0, 200) == 18.9
    assert aa.obter_inicio_vocal("v1", 0, 200) == 18.9
    assert aa.obter_inicio_vocal("v1", 15, 200) == 18.9  # outro início = outra medição
    assert chamadas == [("v1", 0), ("v1", 15)]


def test_inicio_vocal_sem_palavra_e_cacheado_como_sem_vocal(stt_ligado, monkeypatch):
    chamadas = []
    monkeypatch.setattr(aa, "_calcular_inicio_vocal", lambda v, i: chamadas.append(1))
    assert aa.obter_inicio_vocal("v2", 0, 200) is None
    assert aa.obter_inicio_vocal("v2", 0, 200) is None
    assert len(chamadas) == 1
    assert aa.redis_client.ttl("cache:musica_inicio_vocal:v2:0") > aa._CACHE_TTL_FALHA_SEGUNDOS


def test_inicio_vocal_falha_cache_curto(stt_ligado, monkeypatch):
    monkeypatch.setattr(aa, "_calcular_inicio_vocal", lambda v, i: aa._FALHA)
    assert aa.obter_inicio_vocal("v3", 0, 200) is None
    assert 0 < aa.redis_client.ttl("cache:musica_inicio_vocal:v3:0") <= aa._CACHE_TTL_FALHA_SEGUNDOS


def test_calcular_inicio_vocal_soma_inicio_e_primeira_palavra(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_extrair_mp3", lambda url, ini, dur: b"mp3")
    monkeypatch.setattr(aa, "_transcrever_palavras", lambda audio: {"words": [{"type": "word", "start": 3.5}]})
    assert aa._calcular_inicio_vocal("v", 15) == 18.5


def test_calcular_inicio_vocal_falhas_viram_falha(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: None)
    assert aa._calcular_inicio_vocal("v", 0) == aa._FALHA

    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_extrair_mp3", lambda *a: None)
    assert aa._calcular_inicio_vocal("v", 0) == aa._FALHA

    monkeypatch.setattr(aa, "_extrair_mp3", lambda *a: b"mp3")

    def explode(audio):
        raise RuntimeError("stt fora do ar")

    monkeypatch.setattr(aa, "_transcrever_palavras", explode)
    assert aa._calcular_inicio_vocal("v", 0) == aa._FALHA


def test_calcular_inicio_vocal_instrumental_devolve_none(monkeypatch):
    monkeypatch.setattr(aa, "_url_audio_direta", lambda v: "https://audio/x")
    monkeypatch.setattr(aa, "_extrair_mp3", lambda *a: b"mp3")
    monkeypatch.setattr(aa, "_transcrever_palavras", lambda audio: {"words": []})
    assert aa._calcular_inicio_vocal("v", 0) is None


def test_transcrever_palavras_pede_timestamp_de_palavra_e_passa_pela_admissao(monkeypatch):
    monkeypatch.setattr(aa.settings, "elevenlabs_api_key", "chave-de-teste")
    registro = {}

    class _Resposta:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"words": [{"type": "word", "start": 1.0}]}

    def executar_falso(servico, modelo, operacao, *, timeout_s):
        registro["servico"] = servico
        registro["timeout_s"] = timeout_s
        return operacao(5.0)

    class _Cliente:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers, data, files, timeout):
            registro.update(url=url, headers=headers, data=data, timeout=timeout)
            return _Resposta()

    monkeypatch.setattr(aa, "executar", executar_falso)
    monkeypatch.setattr(aa.httpx, "Client", _Cliente)
    assert aa._transcrever_palavras(b"mp3") == {"words": [{"type": "word", "start": 1.0}]}
    assert registro["servico"] == "stt"
    assert registro["headers"] == {"xi-api-key": "chave-de-teste"}
    assert registro["data"]["timestamps_granularity"] == "word"
    assert registro["url"] == aa._STT_URL
