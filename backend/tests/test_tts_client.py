import httpx
import pytest

from app.tts import client as tts_client


class _FakeResponse:
    def __init__(self, status_code=200, content=b"audio-bytes", json_data=None, headers=None):
        self.status_code = status_code
        self.content = content
        self._json_data = json_data or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


class _FakeClient:
    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        self.chamadas.append(("post", url, kwargs))
        return self._respostas.pop(0)

    def delete(self, url, **kwargs):
        self.chamadas.append(("delete", url, kwargs))
        return self._respostas.pop(0)

    def get(self, url, **kwargs):
        self.chamadas.append(("get", url, kwargs))
        return self._respostas.pop(0)


def _habilitar_elevenlabs(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "fake-key")
    monkeypatch.setattr(tts_client.settings, "elevenlabs_voice_id", "voz-padrao")


def test_tts_habilitado_falso_sem_api_key(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "")
    assert tts_client.tts_habilitado() is False


def test_tts_habilitado_com_voice_id_explicito(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "fake-key")
    monkeypatch.setattr(tts_client.settings, "elevenlabs_voice_id", "")
    assert tts_client.tts_habilitado("voz-especifica") is True


def test_construir_voice_settings_aplica_preset_do_tipo_bloco():
    settings_musica = tts_client._construir_voice_settings("musica", None)
    settings_comentario = tts_client._construir_voice_settings("comentario", None)
    assert settings_musica["speed"] > settings_comentario["speed"]


def test_construir_voice_settings_bloco_customizado_reconhece_prefixo():
    a = tts_client._construir_voice_settings("Musica Vaneira", None)
    b = tts_client._construir_voice_settings("musica", None)
    assert a == b


def test_construir_voice_settings_clampa_valores(monkeypatch):
    resultado = tts_client._construir_voice_settings("noticia", "calmo")
    assert 0.0 <= resultado["stability"] <= 1.0
    assert 0.0 <= resultado["style"] <= 1.0
    assert 0.7 <= resultado["speed"] <= 1.2


def test_sintetizar_audio_devolve_bytes(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    audio = tts_client.sintetizar_audio("ola ouvintes", tipo_bloco="abertura", tom="energico")
    assert audio == b"mp3-data"


def test_sintetizar_audio_faz_retry_em_429(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.time, "sleep", lambda segundos: None)
    fake = _FakeClient(
        [
            _FakeResponse(status_code=429, headers={"retry-after": "0"}),
            _FakeResponse(status_code=200, content=b"mp3-final"),
        ]
    )
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    audio = tts_client.sintetizar_audio("ola")
    assert audio == b"mp3-final"
    assert len(fake.chamadas) == 2


def test_sintetizar_audio_levanta_erro_em_falha_definitiva(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=500)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    with pytest.raises(httpx.HTTPStatusError):
        tts_client.sintetizar_audio("ola")


def test_clonar_voz_devolve_voice_id(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200, json_data={"voice_id": "novo-id"})])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    voice_id = tts_client.clonar_voz("Minha voz", b"audio", "audio/mpeg", "amostra.mp3")
    assert voice_id == "novo-id"


def test_obter_preview_url_sem_api_key(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "")
    assert tts_client.obter_preview_url("voz-1") is None


def test_obter_preview_url_devolve_url(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200, json_data={"preview_url": "https://example.com/preview.mp3"})])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    assert tts_client.obter_preview_url("voz-1") == "https://example.com/preview.mp3"


def test_obter_preview_url_devolve_none_em_falha(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=500)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    assert tts_client.obter_preview_url("voz-1") is None


def test_excluir_voz_clonada_chama_delete(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.excluir_voz_clonada("voz-1")
    assert fake.chamadas[0][0] == "delete"
