import httpx

from app.whatsapp import sender


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
        self.chamada = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        self.chamada = (url, kwargs)
        return self._resposta


def test_enviar_mensagem_chama_url_correta(monkeypatch):
    fake = _FakeClient(_FakeResponse())
    monkeypatch.setattr(sender.httpx, "Client", lambda **kwargs: fake)

    sender.enviar_mensagem("5511999999999", "ola", "token-123")

    url, kwargs = fake.chamada
    assert url.endswith("/chat/send/text")
    assert kwargs["headers"]["token"] == "token-123"
    assert kwargs["json"] == {"Phone": "5511999999999", "Body": "ola"}


def test_enviar_audio_codifica_em_base64(monkeypatch):
    fake = _FakeClient(_FakeResponse())
    monkeypatch.setattr(sender.httpx, "Client", lambda **kwargs: fake)

    sender.enviar_audio("5511999999999", b"audio-bytes", "token-123")

    url, kwargs = fake.chamada
    assert url.endswith("/chat/send/audio")
    assert kwargs["json"]["Audio"].startswith("data:audio/mpeg;base64,")


def test_buscar_avatar_devolve_url(monkeypatch):
    fake = _FakeClient(_FakeResponse(json_data={"URL": "https://foto.com/avatar.jpg"}))
    monkeypatch.setattr(sender.httpx, "Client", lambda **kwargs: fake)

    assert sender.buscar_avatar("5511999999999", "token-123") == "https://foto.com/avatar.jpg"


def test_buscar_avatar_sem_foto_devolve_none(monkeypatch):
    fake = _FakeClient(_FakeResponse(json_data={}))
    monkeypatch.setattr(sender.httpx, "Client", lambda **kwargs: fake)

    assert sender.buscar_avatar("5511999999999", "token-123") is None


def test_buscar_avatar_em_falha_de_rede_devolve_none(monkeypatch):
    class _ClienteComErro(_FakeClient):
        def post(self, url, **kwargs):
            raise httpx.HTTPError("falha")

    monkeypatch.setattr(sender.httpx, "Client", lambda **kwargs: _ClienteComErro(None))
    assert sender.buscar_avatar("5511999999999", "token-123") is None
