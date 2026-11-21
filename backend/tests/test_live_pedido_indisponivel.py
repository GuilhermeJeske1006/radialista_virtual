"""Pedido de música indisponível não vai ao ar com o nome do ouvinte (F4, decisão D2, I11 da auditoria §8).

Pesquisa §10: "não anunciar execução imediata; manter status na fila". O pedido vira "nao_atendido" (Música
indisponível) antes da geração, à vista da equipe no painel, e o bloco segue como música comum.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

AUTOMATICA = MusicaEncontrada(video_id="auto", titulo="Varanda Azul", canal="Trio Maré", duracao_segundos=190)


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
    monkeypatch.setattr("app.live.router.buscar_musica",
                        lambda query, **kw: None if "Inexistente" in query else AUTOMATICA)
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *a, **kw: AUTOMATICA)
    return radialista, programa


def _pedido(db_session, account, radialista, prog, novo: bool):
    campos = dict(radio_config_id=radialista.id, telefone="1", nome="Rosa Bezerra", tipo="musica",
                  mensagem_usuario="toca a Moda Inexistente", musica_query="Moda Inexistente")
    if novo:
        from app.whatsapp.atendimento import ocorrencia

        account.atendimento_ouvinte_ativo = True
        campos.update(programa_id=prog.id, transmissao=ocorrencia(prog, radialista.timezone), estado="em_fila",
                      texto_autorizado="Pediu a Moda Inexistente.")
    pedido = FilaAoVivo(**campos)
    db_session.add(pedido)
    db_session.commit()
    return pedido


def _post(client, account, auth_headers, radialista, prog):
    resposta = client.post(f"/live/{radialista.id}/programas/{prog.id}/proxima", headers=auth_headers(account.id),
                           json={"incluir_audio": False, "total_falas": 1, "historico": ["comentario: oi"]})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@pytest.mark.parametrize("novo", [False, True], ids=["legado", "fluxo_novo"])
@freeze_time("2026-08-10 15:00:00")
def test_i11_formato_padrao_anuncia_a_faixa_automatica_sem_o_nome(client, account, auth_headers, programa,
                                                                   db_session, monkeypatch, novo):
    radialista, prog = programa
    pedido = _pedido(db_session, account, radialista, prog, novo)
    vistos = []

    def gerar(system, mensagem):
        db_session.expire_all()
        vistos.append((system, db_session.get(FilaAoVivo, pedido.id).estado))
        return "Agora vem Varanda Azul, com Trio Maré."

    monkeypatch.setattr("app.live.router.gerar_resposta", gerar)
    dados = _post(client, account, auth_headers, radialista, prog)
    assert dados["tipo"] == "musica" and dados["video_id"] == "auto"
    assert dados["fala"] == "Agora vem Varanda Azul, com Trio Maré."
    assert dados["pedido_id"] is None and dados["pedido_token"] is None
    system, estado_na_geracao = vistos[0]
    assert estado_na_geracao == "nao_atendido"  # reprovado antes da geração
    assert "Rosa" not in system and "não foi encontrada" not in system
    db_session.refresh(pedido)
    assert (pedido.estado, pedido.motivo) == ("nao_atendido", "Música indisponível")
    assert pedido.eventos[-1]["acao"] == "musica_indisponivel"


@pytest.mark.parametrize("novo", [False, True], ids=["legado", "fluxo_novo"])
@freeze_time("2026-08-10 15:00:00")
def test_i11_formato_musical_vira_so_musica(client, account, auth_headers, programa, db_session, monkeypatch,
                                            novo):
    radialista, prog = programa
    prog.perfil_programacao = "musical_companhia"
    db_session.commit()
    pedido = _pedido(db_session, account, radialista, prog, novo)
    chamadas = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: chamadas.append(1) or "não deveria")
    dados = _post(client, account, auth_headers, radialista, prog)
    assert dados["fala"] == "" and chamadas == []
    assert dados["video_id"] == "auto" and dados["pedido_id"] is None
    db_session.refresh(pedido)
    assert pedido.estado == "nao_atendido"
