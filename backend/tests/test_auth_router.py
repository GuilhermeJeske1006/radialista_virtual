import hashlib

from app.models.password_reset_token import PasswordResetToken


def _registrar(client, email="fulano@example.com", senha="senha12345", nome="Fulano"):
    return client.post("/auth/register", json={"nome": nome, "email": email, "senha": senha})


def test_registro_cria_conta_radio_config_e_programa_padrao(client, db_session):
    resposta = _registrar(client)
    assert resposta.status_code == 200
    token = resposta.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    corpo = me.json()
    assert corpo["email"] == "fulano@example.com"
    assert corpo["tem_radio_config"] is True


def test_registro_com_email_duplicado_falha(client):
    _registrar(client)
    resposta = _registrar(client)
    assert resposta.status_code == 400


def test_login_com_credenciais_corretas(client):
    _registrar(client)
    resposta = client.post("/auth/login", json={"email": "fulano@example.com", "senha": "senha12345"})
    assert resposta.status_code == 200
    assert resposta.json()["token_type"] == "bearer"


def test_login_com_senha_errada_falha(client):
    _registrar(client)
    resposta = client.post("/auth/login", json={"email": "fulano@example.com", "senha": "errada"})
    assert resposta.status_code == 401


def test_login_com_email_inexistente_falha(client):
    resposta = client.post("/auth/login", json={"email": "naoexiste@example.com", "senha": "senha12345"})
    assert resposta.status_code == 401


def test_me_sem_token_falha(client):
    resposta = client.get("/auth/me")
    assert resposta.status_code == 401


def test_atualizar_perfil(client, account, auth_headers):
    resposta = client.patch(
        "/auth/perfil", json={"nome": "Novo Nome"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Novo Nome"


def test_atualizar_perfil_com_nome_vazio_falha(client, account, auth_headers):
    resposta = client.patch("/auth/perfil", json={"nome": "   "}, headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_alterar_senha(client, account, auth_headers):
    resposta = client.put(
        "/auth/senha",
        json={"senha_atual": "senha12345", "senha_nova": "novasenha123"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 204

    login = client.post("/auth/login", json={"email": account.email, "senha": "novasenha123"})
    assert login.status_code == 200


def test_alterar_senha_com_senha_atual_errada_falha(client, account, auth_headers):
    resposta = client.put(
        "/auth/senha",
        json={"senha_atual": "errada", "senha_nova": "novasenha123"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_alterar_senha_muito_curta_falha(client, account, auth_headers):
    resposta = client.put(
        "/auth/senha",
        json={"senha_atual": "senha12345", "senha_nova": "curta"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_esqueci_senha_para_conta_existente_cria_token(client, account, db_session, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.auth.router.enviar_email_redefinicao_senha",
        lambda email, token: enviados.append((email, token)),
    )

    resposta = client.post("/auth/esqueci-senha", json={"email": account.email})
    assert resposta.status_code == 204
    assert len(enviados) == 1
    assert enviados[0][0] == account.email

    token_gerado = enviados[0][1]
    token_hash = hashlib.sha256(token_gerado.encode()).hexdigest()
    registro = db_session.query(PasswordResetToken).filter_by(token_hash=token_hash).first()
    assert registro is not None
    assert registro.account_id == account.id


def test_esqueci_senha_para_conta_inexistente_ainda_devolve_204(client, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.auth.router.enviar_email_redefinicao_senha",
        lambda email, token: enviados.append((email, token)),
    )

    resposta = client.post("/auth/esqueci-senha", json={"email": "ninguem@example.com"})
    assert resposta.status_code == 204
    assert enviados == []


def test_redefinir_senha_com_token_valido(client, account, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.auth.router.enviar_email_redefinicao_senha",
        lambda email, token: enviados.append((email, token)),
    )
    client.post("/auth/esqueci-senha", json={"email": account.email})
    token = enviados[0][1]

    resposta = client.post(
        "/auth/redefinir-senha", json={"token": token, "senha_nova": "novasenha123"}
    )
    assert resposta.status_code == 204

    login = client.post("/auth/login", json={"email": account.email, "senha": "novasenha123"})
    assert login.status_code == 200


def test_redefinir_senha_com_token_invalido_falha(client):
    resposta = client.post(
        "/auth/redefinir-senha", json={"token": "token-invalido", "senha_nova": "novasenha123"}
    )
    assert resposta.status_code == 400


def test_redefinir_senha_reutilizando_token_falha(client, account, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.auth.router.enviar_email_redefinicao_senha",
        lambda email, token: enviados.append((email, token)),
    )
    client.post("/auth/esqueci-senha", json={"email": account.email})
    token = enviados[0][1]

    primeira = client.post("/auth/redefinir-senha", json={"token": token, "senha_nova": "novasenha123"})
    assert primeira.status_code == 204

    segunda = client.post("/auth/redefinir-senha", json={"token": token, "senha_nova": "outrasenha123"})
    assert segunda.status_code == 400


def test_register_respeita_rate_limit_por_ip(client):
    for _ in range(5):
        resposta = _registrar(client, email=f"user{_}@example.com")
        assert resposta.status_code == 200

    bloqueado = _registrar(client, email="mais-um@example.com")
    assert bloqueado.status_code == 429
