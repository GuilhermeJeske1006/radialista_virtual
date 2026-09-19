import httpx
import pytest

from app.whatsapp import session_manager


class _FakeResponse:
    def __init__(self, json_data=None, status_code=None):
        self._json_data = json_data or {"status": "ok"}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code is not None and self.status_code >= 400:
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
        self.chamada = ("post", url, kwargs)
        return self._resposta

    def get(self, url, **kwargs):
        self.chamada = ("get", url, kwargs)
        return self._resposta


def test_criar_usuario_envia_payload_correto(monkeypatch):
    fake = _FakeClient(_FakeResponse({"data": {"id": "123"}}))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    resultado = session_manager.criar_usuario("admin-token", "radio-1", "user-token", "http://webhook")
    assert resultado == {"data": {"id": "123"}}

    metodo, url, kwargs = fake.chamada
    assert metodo == "post"
    assert url.endswith("/admin/users")
    assert kwargs["headers"]["Authorization"] == "admin-token"
    assert kwargs["json"]["name"] == "radio-1"


def test_configurar_hmac_envia_chave(monkeypatch):
    fake = _FakeClient(_FakeResponse())
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    session_manager.configurar_hmac("user-token", "hmac-key-123")
    _, url, kwargs = fake.chamada
    assert url.endswith("/session/hmac/config")
    assert kwargs["json"] == {"hmac_key": "hmac-key-123"}


def test_conectar_sessao(monkeypatch):
    fake = _FakeClient(_FakeResponse({"status": "connected"}))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    assert session_manager.conectar_sessao("user-token") == {"status": "connected"}


def test_obter_qrcode_usa_get(monkeypatch):
    fake = _FakeClient(_FakeResponse({"qrcode": "base64png"}))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    resultado = session_manager.obter_qrcode("user-token")
    assert resultado == {"qrcode": "base64png"}
    assert fake.chamada[0] == "get"


def test_desconectar_sessao(monkeypatch):
    fake = _FakeClient(_FakeResponse({"status": "logged_out"}))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    assert session_manager.desconectar_sessao("user-token") == {"status": "logged_out"}


def test_obter_status_sessao(monkeypatch):
    fake = _FakeClient(_FakeResponse({"connected": True}))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    assert session_manager.obter_status_sessao("user-token") == {"connected": True}


def test_token_wuzapi_orfao_falso_quando_wuzapi_reconhece_token(monkeypatch):
    fake = _FakeClient(_FakeResponse({"connected": True}, status_code=200))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    assert session_manager.token_wuzapi_orfao("user-token") is False


def test_token_wuzapi_orfao_verdadeiro_no_401(monkeypatch):
    """401 e' o unico sinal inequivoco de "WuzAPI nao conhece mais esse token" -- caso
    real do incidente: WuzAPI perdeu o banco (SQLite efemero) e nao tinha mais o
    usuario, mascarando /onboarding/connect com 502 pra sempre."""
    fake = _FakeClient(_FakeResponse(status_code=401))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    assert session_manager.token_wuzapi_orfao("user-token") is True


@pytest.mark.parametrize("status_code", [500, 503])
def test_token_wuzapi_orfao_falso_em_erro_5xx_nao_apaga_token_bom(monkeypatch, status_code):
    """5xx (WuzAPI com problema, nao ausencia do token) nao pode derrubar um token bom --
    so' 401 e' prova de que o token sumiu."""
    fake = _FakeClient(_FakeResponse(status_code=status_code))
    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: fake)

    assert session_manager.token_wuzapi_orfao("user-token") is False


def test_token_wuzapi_orfao_falso_quando_wuzapi_inalcancavel(monkeypatch):
    class _FakeClientOffline:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(session_manager.httpx, "Client", lambda **kwargs: _FakeClientOffline())

    assert session_manager.token_wuzapi_orfao("user-token") is False
