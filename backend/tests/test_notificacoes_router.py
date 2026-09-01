from app.auth.security import criar_token
from app.models.usuario import Usuario
from app.notificacoes.service import criar_notificacao


def _admin_id(db_session, account_id: int) -> int:
    return db_session.query(Usuario).filter_by(account_id=account_id, role="admin").first().id


def test_listar_vazio(client, account, auth_headers):
    resposta = client.get("/notificacoes", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["notificacoes"] == []
    assert corpo["total"] == 0


def test_listar_apos_criar_notificacao(client, account, auth_headers, db_session):
    admin_id = _admin_id(db_session, account.id)
    criar_notificacao(db_session, admin_id, "billing", "Assinatura ativada", "Seu plano foi ativado.", link="/billing")

    resposta = client.get("/notificacoes", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["notificacoes"][0]["titulo"] == "Assinatura ativada"
    assert corpo["notificacoes"][0]["lida"] is False


def test_contagem_nao_lidas(client, account, auth_headers, db_session):
    admin_id = _admin_id(db_session, account.id)
    criar_notificacao(db_session, admin_id, "billing", "A", "mensagem a")
    criar_notificacao(db_session, admin_id, "equipe", "B", "mensagem b")

    resposta = client.get("/notificacoes/contagem-nao-lidas", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 2


def test_marcar_lida(client, account, auth_headers, db_session):
    admin_id = _admin_id(db_session, account.id)
    notificacao = criar_notificacao(db_session, admin_id, "billing", "A", "mensagem a")

    resposta = client.post(f"/notificacoes/{notificacao.id}/marcar-lida", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["lida"] is True

    contagem = client.get("/notificacoes/contagem-nao-lidas", headers=auth_headers(account.id))
    assert contagem.json()["total"] == 0


def test_marcar_lida_de_outro_usuario_404(client, account, auth_headers, usuario_factory, db_session):
    membro = usuario_factory(account.id, email="membro@example.com", role="membro")
    notificacao = criar_notificacao(db_session, membro.id, "billing", "A", "mensagem a")

    resposta = client.post(f"/notificacoes/{notificacao.id}/marcar-lida", headers=auth_headers(account.id))
    assert resposta.status_code == 404


def test_marcar_todas_lidas(client, account, auth_headers, db_session):
    admin_id = _admin_id(db_session, account.id)
    criar_notificacao(db_session, admin_id, "billing", "A", "mensagem a")
    criar_notificacao(db_session, admin_id, "equipe", "B", "mensagem b")

    resposta = client.post("/notificacoes/marcar-todas-lidas", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    contagem = client.get("/notificacoes/contagem-nao-lidas", headers=auth_headers(account.id))
    assert contagem.json()["total"] == 0


def test_exige_autenticacao(client):
    resposta = client.get("/notificacoes")
    assert resposta.status_code == 401


def test_isolamento_entre_usuarios_da_mesma_conta(client, account, auth_headers, usuario_factory, db_session):
    membro = usuario_factory(account.id, email="membro@example.com", role="membro")
    criar_notificacao(db_session, membro.id, "equipe", "Notificacao do membro", "so' o membro ve isso")

    resposta_admin = client.get("/notificacoes", headers=auth_headers(account.id))
    assert resposta_admin.json()["total"] == 0

    headers_membro = {"Authorization": f"Bearer {criar_token(membro.id)}"}
    resposta_membro = client.get("/notificacoes", headers=headers_membro)
    assert resposta_membro.json()["total"] == 1
