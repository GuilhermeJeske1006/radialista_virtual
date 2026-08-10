import datetime
import json

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local, dentro de um programa 10:00-14:00


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Principal",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        estrutura_blocos=[],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(radio_config)
    db_session.refresh(programa)
    return radio_config, programa


def _url_proxima(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_primeira_e_abertura(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "E ai galera, tudo bem?")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "abertura"
    assert corpo["fala"] == "E ai galera, tudo bem?"
    assert corpo["programa_atual"] == "Programa Principal"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_radialista_inexistente_404(client, account, auth_headers, radialista_e_programa):
    _, programa = radialista_e_programa
    resposta = client.post(
        _url_proxima(999999, programa.id), json={"historico": []}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_programa_inexistente_404(client, account, auth_headers, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    resposta = client.post(
        _url_proxima(radio_config.id, 999999), json={"historico": []}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_bloco_musica_inclui_dados_da_musica(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa!")
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Musica Teste", canal="Canal Teste"),
    )

    # total_falas=1 -> proximo bloco do roteiro padrao apos abertura(0) e' "musica" (indice 0 do roteiro).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "musica"
    assert corpo["video_id"] == "abc123"
    assert corpo["titulo_musica"] == "Musica Teste"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_patrocinador_nao_passa_pelo_llm(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    patrocinador = Patrocinador(account_id=account.id, nome="Loja X", tipo_conteudo="texto", texto="Visite a loja X!")
    db_session.add(patrocinador)
    db_session.flush()
    programa.estrutura_blocos = [f"patrocinador:{patrocinador.id}"]
    db_session.commit()

    chamou_llm = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: chamou_llm.append(1) or "nunca deveria chegar aqui"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "patrocinador"
    assert corpo["fala"] == "Visite a loja X!"
    assert corpo["patrocinador_id"] == patrocinador.id
    assert chamou_llm == []


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_patrocinador_desativado_cai_para_comentario(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    patrocinador = Patrocinador(
        account_id=account.id, nome="Loja X", tipo_conteudo="texto", texto="Visite!", ativo=False
    )
    db_session.add(patrocinador)
    db_session.flush()
    programa.estrutura_blocos = [f"patrocinador:{patrocinador.id}"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "comentario generico")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"


@freeze_time("2026-08-10 16:58:00")  # 13:58 local -- 2 min antes do fim (14:00)
def test_gerar_proxima_fala_perto_do_fim_vira_encerramento(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Foi um prazer, ate mais!")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "encerramento"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_multi_voz_gera_dialogo(
    client, account_factory, auth_headers, db_session, monkeypatch
):
    account = account_factory(email="growth@a.com", plano="growth")
    dono = RadioConfig(account_id=account.id, nome_locutor="Ze", timezone="America/Sao_Paulo")
    convidado = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone="America/Sao_Paulo")
    db_session.add_all([dono, convidado])
    db_session.commit()

    programa = Programa(
        radio_config_id=dono.id,
        nome="Programa Duplo",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=convidado.id))
    db_session.commit()

    resposta_llm = json.dumps(
        {
            "linhas": [
                {"locutor": "Ze", "texto": "E ai Maria, bora comecar o programa?"},
                {"locutor": "Maria", "texto": "Bora sim, ja to na sintonia!"},
            ]
        }
    )
    monkeypatch.setattr("app.live.router.gerar_configuracao", lambda system, msg: resposta_llm)

    resposta = client.post(
        _url_proxima(dono.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["falas"] is not None
    assert len(corpo["falas"]) == 2
    assert corpo["falas"][0]["nome_locutor"] == "Ze"
    assert corpo["falas"][1]["nome_locutor"] == "Maria"


@freeze_time(AGORA_UTC)
def test_musica_de_fundo_endpoint(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.buscar_musica_fundo",
        lambda generos, bloqueados=None: MusicaEncontrada(video_id="bg1", titulo="Fundo", canal="Canal"),
    )
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["video_id"] == "bg1"


@freeze_time(AGORA_UTC)
def test_musica_de_fundo_sem_resultado_404(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.buscar_musica_fundo", lambda generos, bloqueados=None: None)
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


def test_tts_endpoint_nao_habilitado_503(client, account, auth_headers, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 503


def test_tts_endpoint_com_sucesso(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None: b"audio-bytes"
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola ouvintes"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.content == b"audio-bytes"


def test_tts_endpoint_com_voz_invalida_400(client, account, auth_headers, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    resposta = client.post(
        f"/live/{radio_config.id}/tts",
        json={"texto": "ola", "voz_id": "voz-invalida"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400
