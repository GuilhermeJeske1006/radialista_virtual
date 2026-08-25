import io

import pytest
from pydub.generators import Sine

from app.config.settings import settings


@pytest.fixture(autouse=True)
def _upload_dir_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))


def _mp3_sintetico(duracao_ms: int = 1000) -> bytes:
    buffer = io.BytesIO()
    Sine(440).to_audio_segment(duration=duracao_ms).export(buffer, format="mp3")
    return buffer.getvalue()


def test_listar_patrocinadores_vazio(client, account, auth_headers):
    resposta = client.get("/patrocinadores", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_criar_patrocinador_texto(client, account, auth_headers):
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "texto", "texto": "Compre na loja X"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Loja X"
    assert corpo["tipo_conteudo"] == "texto"
    assert corpo["texto"] == "Compre na loja X"


def test_criar_patrocinador_texto_sem_texto_falha(client, account, auth_headers):
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "texto"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_patrocinador_tipo_invalido_falha(client, account, auth_headers):
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "video"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_patrocinador_audio(client, account, auth_headers):
    arquivo = io.BytesIO(b"fake-mp3-bytes")
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja Y", "tipo_conteudo": "audio"},
        files={"arquivo": ("anuncio.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tipo_conteudo"] == "audio"
    assert corpo["audio_nome_original"] == "anuncio.mp3"


def test_criar_patrocinador_audio_sem_arquivo_falha(client, account, auth_headers):
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja Y", "tipo_conteudo": "audio"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_patrocinador_audio_formato_invalido_falha(client, account, auth_headers):
    arquivo = io.BytesIO(b"fake-bytes")
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja Y", "tipo_conteudo": "audio"},
        files={"arquivo": ("anuncio.exe", arquivo, "application/octet-stream")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_patrocinador_audio_calcula_duracao(client, account, auth_headers):
    arquivo = io.BytesIO(_mp3_sintetico(1000))
    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja Y", "tipo_conteudo": "audio"},
        files={"arquivo": ("anuncio.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    assert resposta.json()["duracao_segundos"] == pytest.approx(1, abs=1)


def test_obter_audio_de_patrocinador(client, account, auth_headers):
    arquivo = io.BytesIO(b"fake-mp3-bytes")
    criado = client.post(
        "/patrocinadores",
        data={"nome": "Loja Y", "tipo_conteudo": "audio"},
        files={"arquivo": ("anuncio.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.get(f"/patrocinadores/{criado['id']}/audio", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.content == b"fake-mp3-bytes"


def test_obter_audio_de_patrocinador_texto_falha(client, account, auth_headers):
    criado = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.get(f"/patrocinadores/{criado['id']}/audio", headers=auth_headers(account.id))
    assert resposta.status_code == 404


def test_atualizar_patrocinador(client, account, auth_headers):
    criado = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.put(
        f"/patrocinadores/{criado['id']}",
        data={"nome": "Loja X Atualizada", "tipo_conteudo": "texto", "texto": "novo texto", "ativo": "false"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Loja X Atualizada"
    assert corpo["ativo"] is False


def test_atualizar_patrocinador_inexistente_falha(client, account, auth_headers):
    resposta = client.put(
        "/patrocinadores/999999",
        data={"nome": "X", "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 404


def test_excluir_patrocinador(client, account, auth_headers):
    criado = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/patrocinadores/{criado['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    listagem = client.get("/patrocinadores", headers=auth_headers(account.id)).json()
    assert listagem == []


def test_patrocinador_de_outra_conta_nao_e_visivel(client, account_factory, auth_headers):
    dono = account_factory(email="dono@a.com")
    outro = account_factory(email="outro@a.com")
    criado = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(dono.id),
    ).json()

    resposta = client.get(f"/patrocinadores/{criado['id']}/audio", headers=auth_headers(outro.id))
    assert resposta.status_code == 404
