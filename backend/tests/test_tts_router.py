import io

import httpx


def test_listar_vozes_publico(client):
    resposta = client.get("/tts/voices")
    assert resposta.status_code == 200
    assert len(resposta.json()) > 0


def test_listar_vozes_clonadas_vazio(client, account, auth_headers):
    resposta = client.get("/tts/vozes-clonadas", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_criar_voz_clonada_exige_plano_com_clonagem(client, account, auth_headers):
    assert account.plano == "starter"
    arquivo = io.BytesIO(b"fake-audio-bytes")
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 402


def test_criar_voz_clonada_com_sucesso(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, conteudo, content_type, filename: "voz-nova-1")

    arquivo = io.BytesIO(b"fake-audio-bytes")
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["voz_id"] == "voz-nova-1"
    assert corpo["nome"] == "Minha voz"


def test_criar_voz_clonada_formato_invalido(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    arquivo = io.BytesIO(b"fake-bytes")
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.exe", arquivo, "application/octet-stream")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_voz_clonada_falha_na_elevenlabs_devolve_502(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")

    def _falha(nome, conteudo, content_type, filename):
        raise httpx.HTTPStatusError("erro", request=None, response=httpx.Response(500, text="erro"))

    monkeypatch.setattr("app.tts.router.clonar_voz", _falha)
    arquivo = io.BytesIO(b"fake-audio-bytes")
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 502


def test_excluir_voz_clonada(client, account_factory, auth_headers, monkeypatch, db_session):
    account = account_factory(email="growth@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, conteudo, content_type, filename: "voz-nova-1")
    monkeypatch.setattr("app.tts.router.excluir_voz_clonada", lambda voz_id: None)

    arquivo = io.BytesIO(b"fake-audio-bytes")
    criada = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/tts/vozes-clonadas/{criada['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    listagem = client.get("/tts/vozes-clonadas", headers=auth_headers(account.id)).json()
    assert listagem == []


def test_excluir_voz_clonada_inexistente_falha(client, account, auth_headers):
    resposta = client.delete("/tts/vozes-clonadas/999999", headers=auth_headers(account.id))
    assert resposta.status_code == 404
