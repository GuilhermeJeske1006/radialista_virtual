import hashlib

from app.auth.security import COOKIE_TOKEN
from app.biblioteca_audio.sons_padrao import SONS_PADRAO
from app.categorias_vinheta.defaults import CATEGORIAS_PADRAO
from app.config.settings import settings
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

    categorias = client.get("/categorias-vinheta", headers={"Authorization": f"Bearer {token}"}).json()
    assert sorted((c["nome"], c["tipo"]) for c in categorias) == sorted(CATEGORIAS_PADRAO)


def test_registro_seeda_sons_padrao_no_cartwall(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    resposta = _registrar(client)
    assert resposta.status_code == 200
    token = resposta.json()["access_token"]

    itens = client.get("/biblioteca-audio", headers={"Authorization": f"Bearer {token}"}).json()
    assert {i["nome"] for i in itens} == {s["nome"] for s in SONS_PADRAO}


def test_registro_nao_falha_se_storage_dos_sons_padrao_estiver_indisponivel(client, monkeypatch):
    """Seed de sons padrao e' best-effort (ver criar_sons_padrao) -- storage fora do ar nao
    pode impedir o cadastro da conta em si."""

    def _quebrado(*args, **kwargs):
        raise RuntimeError("storage indisponivel")

    monkeypatch.setattr("app.auth.router.criar_sons_padrao", _quebrado)

    resposta = _registrar(client)
    assert resposta.status_code == 200


def test_registro_com_email_duplicado_falha(client):
    _registrar(client)
    resposta = _registrar(client)
    assert resposta.status_code == 400


def test_login_com_credenciais_corretas(client):
    _registrar(client)
    resposta = client.post("/auth/login", json={"email": "fulano@example.com", "senha": "senha12345"})
    assert resposta.status_code == 200
    assert resposta.json()["token_type"] == "bearer"


def test_registro_seta_cookie_httponly_de_sessao(client):
    resposta = _registrar(client)
    assert COOKIE_TOKEN in resposta.cookies
    set_cookie = resposta.headers["set-cookie"]
    assert "HttpOnly" in set_cookie


def test_login_seta_cookie_httponly_de_sessao(client):
    _registrar(client)
    resposta = client.post("/auth/login", json={"email": "fulano@example.com", "senha": "senha12345"})
    assert COOKIE_TOKEN in resposta.cookies


def test_me_autentica_via_cookie_de_sessao_sem_header(client):
    _registrar(client)
    # TestClient guarda o cookie recebido no registro e manda de volta sozinho --
    # sem passar Authorization, simulando o painel autenticado so' pelo cookie.
    resposta = client.get("/auth/me")
    assert resposta.status_code == 200
    assert resposta.json()["email"] == "fulano@example.com"


def test_logout_limpa_o_cookie_de_sessao(client):
    _registrar(client)
    resposta = client.post("/auth/logout")
    assert resposta.status_code == 204

    set_cookie = resposta.headers["set-cookie"]
    assert COOKIE_TOKEN in set_cookie
    assert "Max-Age=0" in set_cookie

    client.cookies.clear()
    sem_sessao = client.get("/auth/me")
    assert sem_sessao.status_code == 401


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
    assert registro.usuario_id is not None


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


def test_registro_cria_usuario_admin(client):
    resposta = _registrar(client)
    token = resposta.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "admin"


def test_dois_usuarios_da_mesma_conta_logam_separado(client, db_session, account, usuario_factory):
    usuario_factory(account.id, email="membro@example.com", senha="senha12345", role="membro")

    login_membro = client.post("/auth/login", json={"email": "membro@example.com", "senha": "senha12345"})
    assert login_membro.status_code == 200
    token_membro = login_membro.json()["access_token"]

    me_membro = client.get("/auth/me", headers={"Authorization": f"Bearer {token_membro}"})
    assert me_membro.json()["role"] == "membro"
    assert me_membro.json()["email"] == "membro@example.com"

    login_admin = client.post("/auth/login", json={"email": account.email, "senha": "senha12345"})
    assert login_admin.status_code == 200


def test_register_respeita_rate_limit_por_ip(client):
    for _ in range(5):
        resposta = _registrar(client, email=f"user{_}@example.com")
        assert resposta.status_code == 200

    bloqueado = _registrar(client, email="mais-um@example.com")
    assert bloqueado.status_code == 429
