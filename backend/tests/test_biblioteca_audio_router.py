import io

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from app.biblioteca_audio.router import _duracao_segundos
from app.config.settings import settings


@pytest.fixture(autouse=True)
def _upload_dir_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))


def _mp3_sintetico(duracao_ms: int = 1000) -> bytes:
    segmento: AudioSegment = Sine(440).to_audio_segment(duration=duracao_ms)
    buffer = io.BytesIO()
    segmento.export(buffer, format="mp3")
    return buffer.getvalue()


def test_duracao_segundos_com_audio_valido():
    assert _duracao_segundos(_mp3_sintetico(1000)) == pytest.approx(1, abs=1)


def test_duracao_segundos_com_bytes_invalidos_nao_lanca():
    assert _duracao_segundos(b"nao e um audio de verdade") is None


def test_listar_itens_vazio(client, account, auth_headers):
    resposta = client.get("/biblioteca-audio", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_criar_item(client, account, auth_headers):
    categoria = client.post(
        "/categorias-vinheta", json={"nome": "Vinhetas"}, headers=auth_headers(account.id)
    ).json()

    arquivo = io.BytesIO(_mp3_sintetico())
    resposta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta de abertura", "categoria_id": str(categoria["id"]), "cor": "#E8A33D"},
        files={"arquivo": ("vinheta.mp3", arquivo, "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Vinheta de abertura"
    assert corpo["categoria_id"] == categoria["id"]
    assert corpo["cor"] == "#E8A33D"
    assert corpo["audio_nome_original"] == "vinheta.mp3"
    assert corpo["duracao_segundos"] == pytest.approx(1, abs=1)
    assert corpo["ativo"] is True


def test_criar_item_sem_arquivo_falha(client, account, auth_headers):
    resposta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 422


def test_criar_item_vazio_falha(client, account, auth_headers):
    resposta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(b""), "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_item_formato_invalido_falha(client, account, auth_headers):
    resposta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.exe", io.BytesIO(b"fake-bytes"), "application/octet-stream")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_item_maior_que_limite_falha(client, account, auth_headers, monkeypatch):
    import app.biblioteca_audio.router as router_module

    monkeypatch.setattr(router_module, "_TAMANHO_MAXIMO_BYTES", 10)
    resposta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico()), "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 413


def test_obter_audio_do_item(client, account, auth_headers):
    conteudo = _mp3_sintetico()
    criado = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(conteudo), "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.get(f"/biblioteca-audio/{criado['id']}/audio", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.content == conteudo


def test_obter_audio_de_item_inexistente_falha(client, account, auth_headers):
    resposta = client.get("/biblioteca-audio/999999/audio", headers=auth_headers(account.id))
    assert resposta.status_code == 404


def test_atualizar_item(client, account, auth_headers):
    categoria = client.post(
        "/categorias-vinheta", json={"nome": "Efeitos"}, headers=auth_headers(account.id)
    ).json()
    criado = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico()), "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.put(
        f"/biblioteca-audio/{criado['id']}",
        data={"nome": "Vinheta Nova", "categoria_id": str(categoria["id"]), "ordem": "2", "ativo": "false"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Vinheta Nova"
    assert corpo["categoria_id"] == categoria["id"]
    assert corpo["ordem"] == 2
    assert corpo["ativo"] is False


def test_atualizar_item_trocando_arquivo(client, account, auth_headers):
    criado = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico(1000)), "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    novo_conteudo = _mp3_sintetico(2000)
    resposta = client.put(
        f"/biblioteca-audio/{criado['id']}",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta2.mp3", io.BytesIO(novo_conteudo), "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["audio_nome_original"] == "vinheta2.mp3"

    audio = client.get(f"/biblioteca-audio/{criado['id']}/audio", headers=auth_headers(account.id))
    assert audio.content == novo_conteudo


def test_atualizar_item_inexistente_falha(client, account, auth_headers):
    resposta = client.put(
        "/biblioteca-audio/999999",
        data={"nome": "X"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 404


def test_excluir_item(client, account, auth_headers):
    criado = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico()), "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/biblioteca-audio/{criado['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    listagem = client.get("/biblioteca-audio", headers=auth_headers(account.id)).json()
    assert listagem == []


def test_item_de_outra_conta_nao_e_visivel(client, account_factory, auth_headers):
    dono = account_factory(email="dono-biblioteca@a.com")
    outro = account_factory(email="outro-biblioteca@a.com")
    criado = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta"},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico()), "audio/mpeg")},
        headers=auth_headers(dono.id),
    ).json()

    resposta = client.get(f"/biblioteca-audio/{criado['id']}/audio", headers=auth_headers(outro.id))
    assert resposta.status_code == 404
