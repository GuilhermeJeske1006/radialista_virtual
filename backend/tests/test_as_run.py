"""As-run persistente (F11, item 1): /proxima grava "enviado"; o player confirma ou marca falha."""

from app.models.as_run_evento import AsRunEvento
import datetime

import pytest
from freezegun import freeze_time

from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from tests.test_live_router import _url_proxima


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Programa Principal",
        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0), estrutura_blocos=[],
    )
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa

AGORA = "2026-08-10 15:00:00"  # 12:00 local, dentro de um programa 10:00-14:00


def _url_confirmacao(radialista_id, programa_id, evento_id):
    return f"/live/{radialista_id}/programas/{programa_id}/as-run/{evento_id}"


@freeze_time(AGORA)
def test_proxima_grava_envio_e_devolve_id(client, account, auth_headers, radialista_e_programa, db_session, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Bom dia, pessoal da rádio.")
    resposta = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": [], "total_falas": 0},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200
    evento_id = resposta.json()["as_run_evento_id"]
    evento = db_session.get(AsRunEvento, evento_id)
    assert evento.status == "enviado"
    assert evento.ordem == 1
    assert evento.programa_id == programa.id
    assert evento.tipo == resposta.json()["tipo"]


@freeze_time(AGORA)
def test_player_confirma_evento(client, account, auth_headers, radialista_e_programa, db_session, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Bom dia, pessoal da rádio.")
    evento_id = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": [], "total_falas": 0},
                            headers=auth_headers(account.id)).json()["as_run_evento_id"]

    confirmado = client.post(_url_confirmacao(radio_config.id, programa.id, evento_id),
                             json={"status": "confirmado"}, headers=auth_headers(account.id))
    assert confirmado.status_code == 200
    assert confirmado.json() == {"id": evento_id, "status": "confirmado"}
    db_session.expire_all()
    assert db_session.get(AsRunEvento, evento_id).confirmado_em is not None


@freeze_time(AGORA)
def test_status_fora_do_contrato_do_player_recusado(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Bom dia, pessoal da rádio.")
    evento_id = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": [], "total_falas": 0},
                            headers=auth_headers(account.id)).json()["as_run_evento_id"]
    resposta = client.post(_url_confirmacao(radio_config.id, programa.id, evento_id),
                           json={"status": "enviado"}, headers=auth_headers(account.id))
    assert resposta.status_code == 400


@freeze_time(AGORA)
def test_confirmacao_de_evento_inexistente_404(client, account, auth_headers, radialista_e_programa):
    radio_config, programa = radialista_e_programa
    resposta = client.post(_url_confirmacao(radio_config.id, programa.id, 999999),
                           json={"status": "confirmado"}, headers=auth_headers(account.id))
    assert resposta.status_code == 404


@freeze_time(AGORA)
def test_ordem_cresce_a_cada_bloco(client, account, auth_headers, radialista_e_programa, db_session, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Bom dia, pessoal da rádio.")
    historico = []
    for i in range(2):
        resposta = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": historico, "total_falas": i},
                               headers=auth_headers(account.id))
        historico.append(f"{resposta.json()['tipo']}: {resposta.json()['fala']}")
    ordens = sorted(e.ordem for e in db_session.query(AsRunEvento).filter_by(programa_id=programa.id).all())
    assert ordens == [1, 2]
