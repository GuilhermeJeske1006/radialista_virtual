import datetime

from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig


def _radio_config(db_session, account):
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()
    db_session.refresh(radio_config)
    return radio_config


def _log(radio_config_id, telefone="5511999999999", status="guardado", origem="ouvinte", nome=None, **kwargs):
    return InteractionLog(
        radio_config_id=radio_config_id,
        telefone=telefone,
        nome=nome,
        mensagem_usuario=kwargs.pop("mensagem_usuario", "oi"),
        status=status,
        origem=origem,
        **kwargs,
    )


def test_summary_radialista_nao_encontrado(client, account, auth_headers):
    resposta = client.get("/metrics/summary?radialista_id=999999", headers=auth_headers(account.id))
    assert resposta.status_code == 404


def test_summary_conta_totais_por_status(client, account, auth_headers, db_session):
    radio_config = _radio_config(db_session, account)
    db_session.add_all(
        [
            _log(radio_config.id, status="guardado"),
            _log(radio_config.id, status="guardado"),
            _log(radio_config.id, status="fila_musica"),
        ]
    )
    db_session.commit()

    resposta = client.get(f"/metrics/summary?radialista_id={radio_config.id}", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 3
    assert corpo["por_status"]["guardado"] == 2
    assert corpo["por_status"]["fila_musica"] == 1


def test_interacoes_recentes_filtra_por_origem_ouvinte(client, account, auth_headers, db_session):
    radio_config = _radio_config(db_session, account)
    db_session.add_all(
        [
            _log(radio_config.id, origem="ouvinte"),
            _log(radio_config.id, origem="radio"),
        ]
    )
    db_session.commit()

    resposta = client.get(
        f"/metrics/interactions?radialista_id={radio_config.id}", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_interacoes_recentes_respeita_limite_maximo(client, account, auth_headers, db_session):
    radio_config = _radio_config(db_session, account)
    db_session.add_all([_log(radio_config.id) for _ in range(5)])
    db_session.commit()

    resposta = client.get(
        f"/metrics/interactions?radialista_id={radio_config.id}&limit=2", headers=auth_headers(account.id)
    )
    assert len(resposta.json()) == 2


def test_conversas_agrupa_por_telefone(client, account, auth_headers, db_session):
    radio_config = _radio_config(db_session, account)
    db_session.add_all(
        [
            _log(radio_config.id, telefone="5511111111111", nome="Ana"),
            _log(radio_config.id, telefone="5511111111111", nome="Ana"),
            _log(radio_config.id, telefone="5511222222222", nome="Beto"),
        ]
    )
    db_session.commit()

    resposta = client.get("/metrics/conversations", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 2
    telefones = {c["telefone"] for c in corpo["conversas"]}
    assert telefones == {"5511111111111", "5511222222222"}


def test_mensagens_da_conversa_paginadas(client, account, auth_headers, db_session):
    radio_config = _radio_config(db_session, account)
    agora = datetime.datetime.now(datetime.timezone.utc)
    for i in range(3):
        db_session.add(
            _log(
                radio_config.id,
                telefone="5511111111111",
                mensagem_usuario=f"mensagem {i}",
                criado_em=agora + datetime.timedelta(seconds=i),
            )
        )
    db_session.commit()

    resposta = client.get(
        "/metrics/conversations/5511111111111/messages?tamanho_pagina=2", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 3
    assert len(corpo["mensagens"]) == 2


def test_avatar_sem_whatsapp_conectado_devolve_none(client, account, auth_headers):
    resposta = client.get("/metrics/conversations/5511111111111/avatar", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json() == {"url": None}


def test_avatar_com_whatsapp_conectado(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="a@a.com", wuzapi_token="token-1")
    monkeypatch.setattr(
        "app.metrics.router.buscar_avatar", lambda telefone, token: "https://foto.com/x.jpg"
    )
    resposta = client.get("/metrics/conversations/5511111111111/avatar", headers=auth_headers(account.id))
    assert resposta.json() == {"url": "https://foto.com/x.jpg"}


def test_metrics_de_outra_conta_nao_e_visivel(client, account_factory, auth_headers, db_session):
    dono = account_factory(email="dono@a.com")
    outro = account_factory(email="outro@a.com")
    radio_config = _radio_config(db_session, dono)

    resposta = client.get(f"/metrics/summary?radialista_id={radio_config.id}", headers=auth_headers(outro.id))
    assert resposta.status_code == 404
