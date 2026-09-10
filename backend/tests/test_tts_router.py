import io
from pathlib import Path

import httpx
from pydub import AudioSegment


def _audio_valido_bytes(duracao_ms=45000):
    buf = io.BytesIO()
    raw = (Path(__file__).parent / "fixtures/webrtcvad/test-audio.raw").read_bytes()
    voz = AudioSegment(raw, sample_width=2, frame_rate=8000, channels=1)
    (voz * (duracao_ms // len(voz) + 1))[:duracao_ms].export(buf, format="wav")
    return buf.getvalue()


def test_listar_vozes_publico(client):
    resposta = client.get("/tts/voices")
    assert resposta.status_code == 200
    assert len(resposta.json()) > 0


def test_listar_vozes_clonadas_vazio(client, account, auth_headers):
    resposta = client.get("/tts/vozes-clonadas", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_listar_vozes_compartilhadas_inclui_apenas_de_outras_contas(
    client, account_factory, auth_headers, db_session, monkeypatch
):
    from app.models.voz_clonada import VozClonada

    monkeypatch.setattr("app.tts.router.obter_preview_url", lambda voz_id: None)

    dono = account_factory(email="dono-compartilhada@a.com")
    outro = account_factory(email="outro-compartilhada@a.com")
    db_session.add_all(
        [
            VozClonada(account_id=dono.id, nome="Voz aberta", voz_id="voz-compartilhada-1", compartilhada=True),
            VozClonada(account_id=dono.id, nome="Voz privada", voz_id="voz-privada-1", compartilhada=False),
        ]
    )
    db_session.commit()

    resposta = client.get("/tts/vozes-compartilhadas", headers=auth_headers(outro.id))
    assert resposta.status_code == 200
    nomes = [v["nome"] for v in resposta.json()]
    assert nomes == ["Voz aberta"]

    resposta_dono = client.get("/tts/vozes-compartilhadas", headers=auth_headers(dono.id))
    assert resposta_dono.json() == []


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
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, **kwargs: {"voice_id": "voz-nova-1", "requires_verification": False})
    monkeypatch.setattr("app.tts.router.obter_preview_url", lambda voz_id: "https://example.com/preview.mp3")

    arquivo = io.BytesIO(_audio_valido_bytes())
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["voz_id"] == "voz-nova-1"
    assert corpo["nome"] == "Minha voz"
    assert corpo["preview_url"] == "https://example.com/preview.mp3"
    assert corpo["qualidade"]["fala_segundos"] >= 20
    assert corpo["categoria"] == "cloned"


def test_silencio_nao_chama_provedor(client, account_factory, auth_headers, monkeypatch):
    from unittest.mock import Mock
    account = account_factory(plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    provedor = Mock()
    monkeypatch.setattr("app.tts.router.clonar_voz", provedor)
    buf = io.BytesIO(); AudioSegment.silent(duration=60000).export(buf, format="wav")
    r = client.post("/tts/vozes-clonadas", data={"nome": "Teste"}, files={"arquivo": ("silent.wav", buf.getvalue(), "audio/wav")}, headers=auth_headers(account.id))
    assert r.status_code == 400
    provedor.assert_not_called()


def test_multiplas_amostras_e_verificacao_pendente(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    capturado = {}
    def clone(nome, *, amostras):
        capturado["amostras"] = amostras
        return {"voice_id": "pendente", "requires_verification": True}
    monkeypatch.setattr("app.tts.router.clonar_voz", clone)
    audio = _audio_valido_bytes(22000)
    files = [("arquivos", ("a.wav", audio, "audio/wav")), ("arquivos", ("b.wav", audio, "audio/wav"))]
    r = client.post("/tts/vozes-clonadas", data={"nome": "Teste"}, files=files, headers=auth_headers(account.id))
    assert r.status_code == 201, r.text
    assert r.json()["requer_verificacao"] is True
    assert r.json()["preview_url"] is None
    assert [a[1] for a in capturado["amostras"]] == [audio, audio]
    assert client.get("/tts/vozes-clonadas", headers=auth_headers(account.id)).json()[0]["requer_verificacao"] is True


def test_analise_nao_cria_clone(client, account_factory, auth_headers, monkeypatch, db_session):
    from unittest.mock import Mock
    from app.models.voz_clonada import VozClonada
    account = account_factory(plano="growth")
    provedor = Mock(); monkeypatch.setattr("app.tts.router.clonar_voz", provedor)
    r = client.post("/tts/analisar-voz", files={"arquivo": ("a.wav", _audio_valido_bytes(), "audio/wav")}, headers=auth_headers(account.id))
    assert r.status_code == 200
    assert r.json()["fala_segundos"] >= 20
    assert db_session.query(VozClonada).count() == 0
    provedor.assert_not_called()


def test_limita_numero_e_total_de_arquivos(client, account_factory, auth_headers):
    account = account_factory(plano="growth")
    files = [("arquivos", (f"{i}.wav", b"a", "audio/wav")) for i in range(6)]
    assert client.post("/tts/analisar-voz", files=files, headers=auth_headers(account.id)).status_code == 400
    files = [("arquivos", (f"{i}.wav", b"x" * (8 * 1024 * 1024), "audio/wav")) for i in range(2)]
    assert client.post("/tts/analisar-voz", files=files, headers=auth_headers(account.id)).status_code == 413


def test_criar_voz_clonada_audio_curto_demais(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth2@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, **kwargs: {"voice_id": "voz-nova-1", "requires_verification": False})

    arquivo = io.BytesIO(_audio_valido_bytes(duracao_ms=5000))
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


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

    def _falha(nome, **kwargs):
        raise httpx.HTTPStatusError("erro", request=None, response=httpx.Response(500, text="erro"))

    monkeypatch.setattr("app.tts.router.clonar_voz", _falha)
    arquivo = io.BytesIO(_audio_valido_bytes())
    resposta = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 502


def test_excluir_voz_clonada(client, account_factory, auth_headers, monkeypatch, db_session):
    account = account_factory(email="growth@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, **kwargs: {"voice_id": "voz-nova-1", "requires_verification": False})
    monkeypatch.setattr("app.tts.router.excluir_voz_clonada", lambda voz_id: None)
    monkeypatch.setattr("app.tts.router.obter_preview_url", lambda voz_id: None)

    arquivo = io.BytesIO(_audio_valido_bytes())
    criada = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/tts/vozes-clonadas/{criada['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    listagem = client.get("/tts/vozes-clonadas", headers=auth_headers(account.id)).json()
    assert listagem == []


def test_excluir_voz_clonada_inexistente_falha(client, account, auth_headers):
    resposta = client.delete("/tts/vozes-clonadas/999999", headers=auth_headers(account.id))
    assert resposta.status_code == 404


def test_renomear_voz_clonada(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth3@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, **kwargs: {"voice_id": "voz-nova-1", "requires_verification": False})
    monkeypatch.setattr("app.tts.router.obter_preview_url", lambda voz_id: None)
    renomeacoes = []
    monkeypatch.setattr("app.tts.router.renomear_voz", lambda voz_id, nome: renomeacoes.append((voz_id, nome)))

    arquivo = io.BytesIO(_audio_valido_bytes())
    criada = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.patch(
        f"/tts/vozes-clonadas/{criada['id']}",
        json={"nome": "Voz do Zé"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Voz do Zé"
    assert renomeacoes == [("voz-nova-1", "Voz do Zé")]


def test_renomear_voz_clonada_nome_vazio_falha(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth4@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, **kwargs: {"voice_id": "voz-nova-1", "requires_verification": False})
    monkeypatch.setattr("app.tts.router.obter_preview_url", lambda voz_id: None)

    arquivo = io.BytesIO(_audio_valido_bytes())
    criada = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(account.id),
    ).json()

    resposta = client.patch(
        f"/tts/vozes-clonadas/{criada['id']}",
        json={"nome": "   "},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_renomear_voz_clonada_inexistente_falha(client, account, auth_headers):
    resposta = client.patch(
        "/tts/vozes-clonadas/999999", json={"nome": "Nova"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


def test_renomear_voz_clonada_de_outra_conta_falha(client, account_factory, auth_headers, monkeypatch):
    dono = account_factory(email="growth5@a.com", plano="growth")
    outro = account_factory(email="growth6@a.com", plano="growth")
    monkeypatch.setattr("app.config.settings.settings.elevenlabs_api_key", "fake-key")
    monkeypatch.setattr("app.tts.router.clonar_voz", lambda nome, **kwargs: {"voice_id": "voz-nova-1", "requires_verification": False})
    monkeypatch.setattr("app.tts.router.obter_preview_url", lambda voz_id: None)

    arquivo = io.BytesIO(_audio_valido_bytes())
    criada = client.post(
        "/tts/vozes-clonadas",
        data={"nome": "Minha voz"},
        files={"arquivo": ("amostra.wav", arquivo, "audio/wav")},
        headers=auth_headers(dono.id),
    ).json()

    resposta = client.patch(
        f"/tts/vozes-clonadas/{criada['id']}",
        json={"nome": "Roubada"},
        headers=auth_headers(outro.id),
    )
    assert resposta.status_code == 404
