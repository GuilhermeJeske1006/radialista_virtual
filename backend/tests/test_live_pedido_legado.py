"""Fluxo legado de pedidos (conta com `atendimento_ouvinte_ativo=False`, o padrão).

C2 da auditoria F4 (docs/melhoria-radio/f4/auditoria.md §8): caracteriza o legado antes da decisão D1. O commit
da D1 inverte as asserções de propósito, para a mudança ficar explícita no histórico.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

FAIXA = MusicaEncontrada(video_id="f1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200)


@pytest.fixture()
def programa(db_session, account, monkeypatch):
    account.nome_radio = "Rádio Teste"
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=[], ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    monkeypatch.setattr("app.live.router.extrair_musicas_citadas", lambda fala, ja_tocadas=None: [])
    monkeypatch.setattr("app.live.router.buscar_musica", lambda query, **kw: FAIXA)
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda system, msg: "A Joana pediu, e toca agora Estrada Aberta, com Banda Horizonte.")
    return radialista, programa


def _legado(db_session, radialista, nome="Joana", tipo="musica"):
    pedido = FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome=nome, tipo=tipo,
                        mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta")
    db_session.add(pedido)
    db_session.commit()
    return pedido


def _post(client, account, auth_headers, radialista, prog):
    resposta = client.post(f"/live/{radialista.id}/programas/{prog.id}/proxima", headers=auth_headers(account.id),
                           json={"incluir_audio": False, "total_falas": 1, "historico": ["comentario: oi"]})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@freeze_time("2026-08-10 15:00:00")
def test_c2_legado_marca_atendido_na_selecao_e_nao_confirma(client, account, auth_headers, programa, db_session):
    radialista, prog = programa
    pedido = _legado(db_session, radialista)
    dados = _post(client, account, auth_headers, radialista, prog)
    db_session.refresh(pedido)
    assert (pedido.estado, pedido.atendido, pedido.selecao_token) == ("historico_legado", True, None)
    assert dados["pedido_id"] is None and dados["pedido_token"] is None
    resposta = client.post(f"/ouvintes/pedidos/{pedido.id}/reproducao", headers=auth_headers(account.id),
                           json={"token": "qualquer", "programa_id": prog.id, "resultado": "executado"})
    assert resposta.status_code == 409
