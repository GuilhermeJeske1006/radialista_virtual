import base64

import httpx
import pytest

from app.stt import client as stt_client


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


class _FakeClient:
    def __init__(self, resposta):
        self._resposta = resposta

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        return self._resposta


def test_stt_habilitado_falso_sem_api_key(monkeypatch):
    monkeypatch.setattr(stt_client.settings, "elevenlabs_api_key", "")
    assert stt_client.stt_habilitado() is False


def test_stt_habilitado_true_com_api_key(monkeypatch):
    monkeypatch.setattr(stt_client.settings, "elevenlabs_api_key", "fake-key")
    assert stt_client.stt_habilitado() is True


def test_transcrever_audio_devolve_texto(monkeypatch):
    monkeypatch.setattr(stt_client.settings, "elevenlabs_api_key", "fake-key")
    fake = _FakeClient(_FakeResponse(json_data={"text": "  ola mundo  "}))
    monkeypatch.setattr(stt_client.httpx, "Client", lambda **kwargs: fake)

    audio_b64 = base64.b64encode(b"fake-audio-bytes").decode()
    resultado = stt_client.transcrever_audio(audio_b64)
    assert resultado == "ola mundo"


def test_transcrever_audio_levanta_em_falha(monkeypatch):
    monkeypatch.setattr(stt_client.settings, "elevenlabs_api_key", "fake-key")
    fake = _FakeClient(_FakeResponse(status_code=500))
    monkeypatch.setattr(stt_client.httpx, "Client", lambda **kwargs: fake)

    audio_b64 = base64.b64encode(b"fake-audio-bytes").decode()
    with pytest.raises(httpx.HTTPStatusError):
        stt_client.transcrever_audio(audio_b64)
