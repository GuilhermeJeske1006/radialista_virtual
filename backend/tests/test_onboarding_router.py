import httpx


def test_criar_usuario_wuzapi_ja_existente(client, account_factory, auth_headers, db_session):
    account = account_factory(email="a@a.com", wuzapi_token="token-existente")
    resposta = client.post("/onboarding/wuzapi-user", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ja_existe", "wuzapi_token": "token-existente"}


def test_criar_usuario_wuzapi_cria_novo(client, account, auth_headers, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.onboarding.router.criar_usuario",
        lambda admin_token, nome, token, webhook_url: {"data": {"id": "wuzapi-id-1"}},
    )
    monkeypatch.setattr("app.onboarding.router.configurar_entrega_midia", lambda token: {})
    monkeypatch.setattr("app.onboarding.router.configurar_hmac", lambda token, hmac_key: {})

    resposta = client.post("/onboarding/wuzapi-user", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "criado"

    db_session.refresh(account)
    assert account.wuzapi_user_id == "wuzapi-id-1"
    assert account.wuzapi_hmac_key is not None


def test_criar_usuario_wuzapi_falha_no_wuzapi_devolve_502(client, account, auth_headers, monkeypatch):
    def _falha(*args, **kwargs):
        raise httpx.HTTPStatusError("erro", request=None, response=httpx.Response(500))

    monkeypatch.setattr("app.onboarding.router.criar_usuario", _falha)
    resposta = client.post("/onboarding/wuzapi-user", headers=auth_headers(account.id))
    assert resposta.status_code == 502


def test_criar_usuario_wuzapi_com_falha_best_effort_nao_trava_onboarding(
    client, account, auth_headers, db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.onboarding.router.criar_usuario",
        lambda admin_token, nome, token, webhook_url: {"data": {"id": "wuzapi-id-1"}},
    )

    def _falha_midia(*args, **kwargs):
        raise httpx.HTTPStatusError("erro", request=None, response=httpx.Response(500))

    monkeypatch.setattr("app.onboarding.router.configurar_entrega_midia", _falha_midia)
    monkeypatch.setattr("app.onboarding.router.configurar_hmac", _falha_midia)

    resposta = client.post("/onboarding/wuzapi-user", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "criado"


def test_conectar_sem_wuzapi_token_falha(client, account, auth_headers):
    resposta = client.post("/onboarding/connect", headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_conectar_com_token_chama_wuzapi(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="a@a.com", wuzapi_token="token-1")
    monkeypatch.setattr("app.onboarding.router.configurar_entrega_midia", lambda token: {})
    monkeypatch.setattr(
        "app.onboarding.router.conectar_sessao", lambda token: {"status": "connected"}
    )
    resposta = client.post("/onboarding/connect", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "connected"}


def test_qrcode_sem_token_falha(client, account, auth_headers):
    resposta = client.get("/onboarding/qrcode", headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_qrcode_com_token(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="a@a.com", wuzapi_token="token-1")
    monkeypatch.setattr("app.onboarding.router.obter_qrcode", lambda token: {"qrcode": "base64"})
    resposta = client.get("/onboarding/qrcode", headers=auth_headers(account.id))
    assert resposta.status_code == 200


def test_status_sessao_sem_token_devolve_desconectado(client, account, auth_headers):
    resposta = client.get("/onboarding/status", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == {"connected": False}


def test_logout_sem_token_falha(client, account, auth_headers):
    resposta = client.post("/onboarding/logout", headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_logout_com_token(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="a@a.com", wuzapi_token="token-1")
    monkeypatch.setattr(
        "app.onboarding.router.desconectar_sessao", lambda token: {"status": "logged_out"}
    )
    resposta = client.post("/onboarding/logout", headers=auth_headers(account.id))
    assert resposta.status_code == 200
