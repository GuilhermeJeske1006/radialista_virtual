"""Espiada de pedido recente no fluxo legado (F4, decisão D7, I13 da auditoria §8).

A espiada (`_pedido_recente_nao_atendido`) não consome o pedido: só avisa o locutor que "chegou uma mensagem".
Ela só pode ver o legado aberto. Antes da F4 ela também via pedidos do fluxo novo ainda não aprovados pela equipe
(`aguardando_revisao`, com programa) e levava ao ar o nome e a música de um pedido sem moderação.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


@pytest.fixture()
def programa(db_session, account, monkeypatch):
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=["comentario"],
                        ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    return radialista, programa


def _prompt(client, account, auth_headers, radialista, prog, monkeypatch):
    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos.")
    resposta = client.post(f"/live/{radialista.id}/programas/{prog.id}/proxima", headers=auth_headers(account.id),
                           json={"incluir_audio": False, "total_falas": 1, "historico": ["musica: oi"]})
    assert resposta.status_code == 200, resposta.text
    return prompts[0]


@freeze_time("2026-08-10 15:00:00")
def test_i13_espiada_ignora_pedido_do_fluxo_novo_e_os_fechados(client, account, auth_headers, programa, db_session,
                                                              monkeypatch):
    radialista, prog = programa
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add_all([
        FilaAoVivo(radio_config_id=radialista.id, programa_id=prog.id, estado="aguardando_revisao", telefone="1",
                   nome="Rita Revisão", tipo="musica", mensagem_usuario="toca Varanda Azul",
                   musica_query="Varanda Azul", criado_em=agora),
        FilaAoVivo(radio_config_id=radialista.id, estado="cancelado", telefone="2", nome="Caio Cancelado",
                   tipo="abraco", mensagem_usuario="oi", criado_em=agora),
    ])
    db_session.commit()
    system = _prompt(client, account, auth_headers, radialista, prog, monkeypatch)
    assert "Acabou de chegar uma mensagem" not in system
    assert "Rita" not in system and "Caio" not in system


@freeze_time("2026-08-10 15:00:00")
def test_i13_espiada_continua_vendo_o_legado_aberto(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Rita Andrade", tipo="abraco",
                              mensagem_usuario="oi", criado_em=datetime.datetime.now(datetime.timezone.utc)))
    db_session.commit()
    system = _prompt(client, account, auth_headers, radialista, prog, monkeypatch)
    assert "Acabou de chegar uma mensagem nova no WhatsApp da rádio, de Rita Andrade" in system
