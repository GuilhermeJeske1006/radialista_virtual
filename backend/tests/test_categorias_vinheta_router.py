import io

from pydub.generators import Sine


def _mp3_sintetico(duracao_ms: int = 1000) -> bytes:
    buffer = io.BytesIO()
    Sine(440).to_audio_segment(duration=duracao_ms).export(buffer, format="mp3")
    return buffer.getvalue()


def test_listar_categorias_vazio(client, account, auth_headers):
    resposta = client.get("/categorias-vinheta", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_criar_categoria_tipo_padrao_e_biblioteca(client, account, auth_headers):
    resposta = client.post("/categorias-vinheta", json={"nome": "Vinhetas"}, headers=auth_headers(account.id))
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Vinhetas"
    assert corpo["tipo"] == "biblioteca"


def test_criar_categoria_tipo_propaganda(client, account, auth_headers):
    resposta = client.post(
        "/categorias-vinheta", json={"nome": "Comerciais", "tipo": "propaganda"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201
    assert resposta.json()["tipo"] == "propaganda"


def test_criar_categoria_tipo_invalido_falha(client, account, auth_headers):
    resposta = client.post(
        "/categorias-vinheta", json={"nome": "X", "tipo": "video"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_criar_categoria_nome_vazio_falha(client, account, auth_headers):
    resposta = client.post("/categorias-vinheta", json={"nome": "   "}, headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_renomear_categoria(client, account, auth_headers):
    criada = client.post("/categorias-vinheta", json={"nome": "Vinhetas"}, headers=auth_headers(account.id)).json()

    resposta = client.put(
        f"/categorias-vinheta/{criada['id']}",
        json={"nome": "Comerciais", "tipo": "propaganda"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Comerciais"
    assert corpo["tipo"] == "propaganda"


def test_renomear_categoria_inexistente_falha(client, account, auth_headers):
    resposta = client.put(
        "/categorias-vinheta/999999", json={"nome": "X"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


def test_categoria_de_outra_conta_nao_e_visivel(client, account_factory, auth_headers):
    dono = account_factory(email="dono-categoria@a.com")
    outro = account_factory(email="outro-categoria@a.com")
    criada = client.post("/categorias-vinheta", json={"nome": "Vinhetas"}, headers=auth_headers(dono.id)).json()

    resposta = client.put(
        f"/categorias-vinheta/{criada['id']}", json={"nome": "Y"}, headers=auth_headers(outro.id)
    )
    assert resposta.status_code == 404


def test_criar_vinheta_em_categoria_de_propaganda_falha(client, account, auth_headers):
    categoria = client.post(
        "/categorias-vinheta", json={"nome": "Comerciais", "tipo": "propaganda"}, headers=auth_headers(account.id)
    ).json()

    resposta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta", "categoria_id": str(categoria["id"])},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico()), "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_propaganda_em_categoria_de_vinheta_falha(client, account, auth_headers):
    categoria = client.post("/categorias-vinheta", json={"nome": "Vinhetas"}, headers=auth_headers(account.id)).json()

    resposta = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "categoria_id": str(categoria["id"]), "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_excluir_categoria_de_vinheta_desvincula_vinheta(client, account, auth_headers):
    categoria = client.post("/categorias-vinheta", json={"nome": "Vinhetas"}, headers=auth_headers(account.id)).json()

    vinheta = client.post(
        "/biblioteca-audio",
        data={"nome": "Vinheta", "categoria_id": str(categoria["id"])},
        files={"arquivo": ("vinheta.mp3", io.BytesIO(_mp3_sintetico()), "audio/mpeg")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/categorias-vinheta/{categoria['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    vinheta_atualizada = client.get("/biblioteca-audio", headers=auth_headers(account.id)).json()[0]
    assert vinheta_atualizada["id"] == vinheta["id"]
    assert vinheta_atualizada["categoria_id"] is None


def test_excluir_categoria_de_propaganda_desvincula_propaganda(client, account, auth_headers):
    categoria = client.post(
        "/categorias-vinheta", json={"nome": "Comerciais", "tipo": "propaganda"}, headers=auth_headers(account.id)
    ).json()

    propaganda = client.post(
        "/patrocinadores",
        data={"nome": "Loja X", "categoria_id": str(categoria["id"]), "tipo_conteudo": "texto", "texto": "oi"},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/categorias-vinheta/{categoria['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    propaganda_atualizada = client.get("/patrocinadores", headers=auth_headers(account.id)).json()[0]
    assert propaganda_atualizada["id"] == propaganda["id"]
    assert propaganda_atualizada["categoria_id"] is None
