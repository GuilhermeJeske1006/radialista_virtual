import datetime

import pytest
from fastapi import HTTPException

from app.models.perfil_voz import ConfiguracaoVoz, MetadadosVoz
from app.models.voz_clonada import VozClonada
from app.tts.profiles import consultar_metadados, parametros_sintese
from app.tts.voices import VOZES_DISPONIVEIS, voz_valida_para_conta


@pytest.mark.parametrize("categoria,clonada", [("professional", False), ("cloned", True), ("desconhecida", False)])
def test_tipo_real_define_ajustes(db_session, account, monkeypatch, categoria, clonada):
    monkeypatch.setattr("app.tts.profiles.obter_metadados_voz", lambda _: {"categoria": categoria})
    assert parametros_sintese(db_session, account.id, "voz-1")["eh_clonada"] is clonada
    assert db_session.get(MetadadosVoz, "voz-1").categoria == categoria


def test_padrao_do_servidor_tambem_consulta_categoria(db_session, account, monkeypatch):
    monkeypatch.setattr("app.tts.profiles.settings.elevenlabs_voice_id", "padrao-real")
    monkeypatch.setattr("app.tts.profiles.obter_metadados_voz", lambda _: {"categoria": "professional"})
    assert parametros_sintese(db_session, account.id, None) == {"eh_clonada": False}
    assert db_session.get(MetadadosVoz, "padrao-real").categoria == "professional"


def test_cache_persistido_evitar_consulta_em_cada_bloco(db_session, monkeypatch):
    chamadas = []
    monkeypatch.setattr("app.tts.profiles.obter_metadados_voz", lambda voz: chamadas.append(voz) or {"categoria": "professional"})
    consultar_metadados(db_session, "id")
    consultar_metadados(db_session, "id")
    assert chamadas == ["id"]


def test_falha_de_consulta_nao_libera_verificacao(db_session, account):
    db_session.add(MetadadosVoz(voz_id="pendente", categoria="cloned", requer_verificacao=True))
    db_session.commit()
    consultar_metadados(db_session, "pendente", atualizar=True)
    with pytest.raises(HTTPException) as exc:
        parametros_sintese(db_session, account.id, "pendente")
    assert exc.value.status_code == 409


def test_pendente_nao_pode_ser_selecionada(db_session, account):
    db_session.add_all([VozClonada(account_id=account.id, nome="Voz", voz_id="pendente"), MetadadosVoz(voz_id="pendente", requer_verificacao=True)])
    db_session.commit()
    assert not voz_valida_para_conta(db_session, account.id, "pendente")
    assert voz_valida_para_conta(db_session, account.id, "pendente", incluir_pendente=True)


def test_configuracao_por_conta_e_por_voz(client, account_factory, auth_headers, db_session):
    a = account_factory(email="a@test.com")
    b = account_factory(email="b@test.com")
    voz = VOZES_DISPONIVEIS[0]["voz_id"]
    path = f"/tts/configuracao-voz/{voz}"
    body = {"modelo": "eleven_multilingual_v2", "perfil": "natural", "formato": "mp3_44100_192", "pronuncias": {"Locufy": "Locufai"}}
    assert client.patch(path, json=body, headers=auth_headers(a.id)).status_code == 200
    assert client.get(path, headers=auth_headers(a.id)).json()["pronuncias"] == body["pronuncias"]
    assert client.get(path, headers=auth_headers(b.id)).json()["pronuncias"] == {}
    assert parametros_sintese(db_session, a.id, voz)["modelo"] == body["modelo"]
    assert "modelo" not in parametros_sintese(db_session, b.id, voz)


def test_nao_configura_voz_privada_de_outra_conta(client, account_factory, auth_headers, db_session):
    a = account_factory(email="a@test.com")
    b = account_factory(email="b@test.com")
    db_session.add(VozClonada(account_id=a.id, nome="Privada", voz_id="privada")); db_session.commit()
    for method in (client.get, client.patch):
        kwargs = {"json": {}} if method == client.patch else {}
        assert method("/tts/configuracao-voz/privada", headers=auth_headers(b.id), **kwargs).status_code == 404


@pytest.mark.parametrize("body", [{"modelo": "inexistente"}, {"pronuncias": {"a": "[laughs]"}}, {"pronuncias": {"a": ""}}, {"pronuncias": {"Foo": "bar", "foo": "baz"}}, {"formato": "pcm_44100"}])
def test_rejeita_perfil_invalido(client, account, auth_headers, body):
    voz = VOZES_DISPONIVEIS[0]["voz_id"]
    assert client.patch(f"/tts/configuracao-voz/{voz}", headers=auth_headers(account.id), json=body).status_code == 422
