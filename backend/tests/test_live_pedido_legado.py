"""Fluxo legado de pedidos (conta com `atendimento_ouvinte_ativo=False`, o padrão).

C2 da auditoria F4 (docs/melhoria-radio/f4/auditoria.md §8) caracterizou o legado antes da decisão D1: a seleção
marcava `atendido` antes de tocar e a confirmação de reprodução recusava o pedido sem programa. Com a D1
(confirmada pelo usuário, opção A), o legado passa a ser selecionado com token e confirmado pelo player, como o
fluxo novo, sem moderação: as asserções do C2 foram invertidas de propósito (I12 da auditoria).
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

FAIXA = MusicaEncontrada(video_id="f1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200)
AGORA = "2026-08-10 15:00:00"


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
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *a, **kw: FAIXA)
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda system, msg: "A Joana pediu, e toca agora Estrada Aberta, com Banda Horizonte.")
    return radialista, programa


def _legado(db_session, radialista, nome="Joana", tipo="musica", telefone="1"):
    pedido = FilaAoVivo(radio_config_id=radialista.id, telefone=telefone, nome=nome, tipo=tipo,
                        mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta",
                        criado_em=datetime.datetime.now(datetime.timezone.utc))
    db_session.add(pedido)
    db_session.commit()
    return pedido


def _post(client, account, auth_headers, radialista, prog, total_falas=1):
    resposta = client.post(f"/live/{radialista.id}/programas/{prog.id}/proxima", headers=auth_headers(account.id),
                           json={"incluir_audio": False, "total_falas": total_falas,
                                 "historico": ["comentario: oi"]})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _reproducao(client, account, auth_headers, pedido, token, programa_id, resultado="executado"):
    return client.post(f"/ouvintes/pedidos/{pedido.id}/reproducao", headers=auth_headers(account.id),
                       json={"token": token, "programa_id": programa_id, "resultado": resultado})


@freeze_time(AGORA)
def test_d1_legado_seleciona_com_token_e_so_marca_atendido_depois_de_tocar(client, account, auth_headers, programa,
                                                                          db_session):
    radialista, prog = programa
    pedido = _legado(db_session, radialista)
    dados = _post(client, account, auth_headers, radialista, prog)
    db_session.refresh(pedido)
    # Invertido do C2: antes ficava ("historico_legado", True, None) e a resposta vinha sem pedido_id.
    assert (pedido.estado, pedido.atendido) == ("selecionado", False)
    assert pedido.selecao_token and pedido.selecionado_em is not None
    assert pedido.eventos[-1]["acao"] == "selecionar_legado"
    assert (dados["pedido_id"], dados["pedido_token"]) == (pedido.id, pedido.selecao_token)
    assert (dados["pedido_programa_id"], dados["pedido_radialista_id"]) == (prog.id, radialista.id)
    resposta = _reproducao(client, account, auth_headers, pedido, pedido.selecao_token, prog.id)
    assert resposta.status_code == 200 and resposta.json()["estado"] == "executado"
    db_session.refresh(pedido)
    assert pedido.atendido and pedido.atendido_em is not None and pedido.programa_id is None


@pytest.mark.parametrize("resultado", ["falhou", "interrompido"])
@freeze_time(AGORA)
def test_d1_player_falho_nao_marca_atendido(client, account, auth_headers, programa, db_session, resultado):
    radialista, prog = programa
    pedido = _legado(db_session, radialista)
    _post(client, account, auth_headers, radialista, prog)
    db_session.refresh(pedido)
    resposta = _reproducao(client, account, auth_headers, pedido, pedido.selecao_token, prog.id, resultado)
    assert resposta.json()["estado"] == "nao_atendido"
    db_session.refresh(pedido)
    assert not pedido.atendido


@freeze_time(AGORA)
def test_d1_confirmacao_exige_token_e_programa_do_mesmo_radio(client, account, auth_headers, programa, db_session):
    radialista, prog = programa
    pedido = _legado(db_session, radialista)
    _post(client, account, auth_headers, radialista, prog)
    db_session.refresh(pedido)
    outro_radio = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(outro_radio)
    db_session.flush()
    outro = Programa(radio_config_id=outro_radio.id, nome="Outro", horario_inicio=datetime.time(10, 0),
                     horario_fim=datetime.time(14, 0), estrutura_blocos=[])
    db_session.add(outro)
    db_session.commit()
    assert _reproducao(client, account, auth_headers, pedido, "errado", prog.id).status_code == 409
    assert _reproducao(client, account, auth_headers, pedido, pedido.selecao_token, outro.id).status_code == 409
    db_session.refresh(pedido)
    assert pedido.estado == "selecionado"


@freeze_time(AGORA)
def test_d1_selecionado_nao_e_escolhido_de_novo_nem_espiado_nem_conta_como_fila(client, account, auth_headers,
                                                                                programa, db_session,
                                                                                monkeypatch):
    from app.live import router

    radialista, prog = programa
    pedido = _legado(db_session, radialista)
    _post(client, account, auth_headers, radialista, prog)
    db_session.refresh(pedido)
    assert pedido.estado == "selecionado"
    assert router._proximo_pedido_fila_dentre(db_session, radialista, ("musica",)) is None
    assert router._ha_pedido_musica_pendente(db_session, radialista, prog, False) is False
    assert router._pedido_recente_nao_atendido(db_session, radialista, "musica") is None
    assert router._pedidos_em_fila(db_session, radialista, prog) == []
    # Um bloco de música seguinte não volta a anunciar o pedido.
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Agora vem Estrada Aberta.")
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=6)
    assert dados["tipo"] == "musica" and dados["pedido_id"] is None


@freeze_time(AGORA)
def test_d1_reenfileirar_legado_volta_para_em_fila(client, account, auth_headers, programa, db_session):
    radialista, prog = programa
    pedido = _legado(db_session, radialista)
    _post(client, account, auth_headers, radialista, prog)
    resposta = client.patch(f"/ouvintes/pedidos/{pedido.id}", headers=auth_headers(account.id),
                            json={"acao": "reenfileirar"})
    assert resposta.status_code == 200 and resposta.json()["estado"] == "em_fila"
    db_session.refresh(pedido)
    assert (pedido.selecao_token, pedido.atendido) == (None, False)
    dados = _post(client, account, auth_headers, radialista, prog)
    assert dados["pedido_id"] == pedido.id
