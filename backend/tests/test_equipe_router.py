from app.auth.security import COOKIE_TOKEN
from app.models.convite_usuario import ConviteUsuario


def _convidar(client, headers, email="novo@example.com", role="membro"):
    return client.post("/equipe/convites", json={"email": email, "role": role}, headers=headers)


def test_listar_equipe(client, account, auth_headers, usuario_factory):
    usuario_factory(account.id, email="membro@example.com", role="membro")

    resposta = client.get("/equipe", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    emails = {u["email"] for u in resposta.json()}
    assert emails == {account.email, "membro@example.com"}


def test_membro_nao_admin_nao_acessa_convites(client, account, usuario_factory):
    membro = usuario_factory(account.id, email="membro@example.com", role="membro")
    from app.auth.security import criar_token

    headers = {"Authorization": f"Bearer {criar_token(membro.id)}"}

    resposta = client.post("/equipe/convites", json={"email": "x@example.com"}, headers=headers)
    assert resposta.status_code == 403


def test_convidar_gera_convite_e_envia_email(client, account, auth_headers, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.equipe.router.enviar_email_convite",
        lambda email, token, nome_radio: enviados.append((email, token)),
    )

    resposta = _convidar(client, auth_headers(account.id))
    assert resposta.status_code == 201
    assert resposta.json()["email"] == "novo@example.com"
    assert resposta.json()["role"] == "membro"
    assert len(enviados) == 1


def test_convidar_email_ja_cadastrado_falha(client, account, auth_headers, usuario_factory):
    usuario_factory(account.id, email="ja-existe@example.com")
    resposta = _convidar(client, auth_headers(account.id), email="ja-existe@example.com")
    assert resposta.status_code == 400


def test_aceitar_convite_cria_usuario_e_loga(client, account, auth_headers, db_session, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.equipe.router.enviar_email_convite",
        lambda email, token, nome_radio: enviados.append((email, token)),
    )
    _convidar(client, auth_headers(account.id))
    token = enviados[0][1]

    resposta = client.post(
        "/convites/aceitar", json={"token": token, "nome": "Novo Membro", "senha": "senha12345"}
    )
    assert resposta.status_code == 200
    assert "access_token" in resposta.json()
    assert COOKIE_TOKEN in resposta.cookies

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {resposta.json()['access_token']}"})
    assert me.json()["role"] == "membro"
    assert me.json()["email"] == "novo@example.com"


def test_aceitar_convite_token_invalido_falha(client):
    resposta = client.post(
        "/convites/aceitar", json={"token": "invalido", "nome": "X", "senha": "senha12345"}
    )
    assert resposta.status_code == 400


def test_aceitar_convite_ja_aceito_falha(client, account, auth_headers, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.equipe.router.enviar_email_convite",
        lambda email, token, nome_radio: enviados.append((email, token)),
    )
    _convidar(client, auth_headers(account.id))
    token = enviados[0][1]

    primeira = client.post(
        "/convites/aceitar", json={"token": token, "nome": "X", "senha": "senha12345"}
    )
    assert primeira.status_code == 200

    segunda = client.post(
        "/convites/aceitar", json={"token": token, "nome": "Y", "senha": "outrasenha123"}
    )
    assert segunda.status_code == 400


def test_revogar_convite(client, account, auth_headers, db_session, monkeypatch):
    monkeypatch.setattr("app.equipe.router.enviar_email_convite", lambda *a, **k: None)
    resposta = _convidar(client, auth_headers(account.id))
    convite_id = resposta.json()["id"]

    revogar = client.delete(f"/equipe/convites/{convite_id}", headers=auth_headers(account.id))
    assert revogar.status_code == 204

    convite = db_session.query(ConviteUsuario).filter_by(id=convite_id).first()
    assert convite.revogado_em is not None

    listar = client.get("/equipe/convites", headers=auth_headers(account.id))
    assert listar.json() == []


def test_alterar_role_de_membro(client, account, auth_headers, usuario_factory):
    membro = usuario_factory(account.id, email="membro@example.com", role="membro")

    resposta = client.patch(
        f"/equipe/{membro.id}/role", json={"role": "admin"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["role"] == "admin"


def test_nao_pode_rebaixar_o_unico_admin(client, account, auth_headers):
    usuario_admin = _usuario_admin_id(client, account, auth_headers)

    resposta = client.patch(
        f"/equipe/{usuario_admin}/role", json={"role": "membro"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_nao_pode_remover_o_unico_admin(client, account, auth_headers):
    usuario_admin = _usuario_admin_id(client, account, auth_headers)

    resposta = client.delete(f"/equipe/{usuario_admin}", headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_remover_membro(client, account, auth_headers, usuario_factory):
    membro = usuario_factory(account.id, email="membro@example.com", role="membro")

    resposta = client.delete(f"/equipe/{membro.id}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    equipe = client.get("/equipe", headers=auth_headers(account.id)).json()
    membro_listado = next(u for u in equipe if u["id"] == membro.id)
    assert membro_listado["ativo"] is False


def _usuario_admin_id(client, account, auth_headers) -> int:
    equipe = client.get("/equipe", headers=auth_headers(account.id)).json()
    return next(u["id"] for u in equipe if u["role"] == "admin")
