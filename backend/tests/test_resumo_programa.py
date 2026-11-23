"""F11 (item 2): relatório pós-programa montado do banco (as-run confirmado, promessas e pedidos do dia), sem
depender de resumo enviado pelo cliente."""

import datetime

from app.models.as_run_evento import AsRunEvento
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.promessa_no_ar import PromessaNoAr
from tests.test_config_relogio import _criar_programa

UTC = datetime.timezone.utc
# 2026-11-10 12:00 em São Paulo = 15:00 UTC; o dia seguinte começa às 03:00 UTC do dia 11.
NO_DIA = datetime.datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
DIA_SEGUINTE = datetime.datetime(2026, 11, 11, 15, 0, tzinfo=UTC)
FRASE_LONGA = ("Hoje a gente conversa sobre a feira que acontece na praça central da cidade e que reúne produtores "
               "rurais artesãos músicos e famílias inteiras que chegam cedo para aproveitar o sol da manhã.")


def _evento(account, programa_id, ordem, tipo, texto, status, quando):
    return AsRunEvento(account_id=account.id, programa_id=programa_id, ordem=ordem, tipo=tipo, texto=texto,
                       status=status, criado_em=quando)


def _promessa(programa_id, radio_config_id, estado, quando, contingencia=""):
    return PromessaNoAr(programa_id=programa_id, radio_config_id=radio_config_id, ocorrencia="manual:2026-11-10",
                        request_id="r", tipo="participacao", classe="c", marcador="m", trecho="t", evento_alvo="e",
                        evento_tipo="chamada_ouvinte", evento_rotulo="", estado=estado, motivo="",
                        contingencia=contingencia, eventos=[], criada_em=quando)


def _pedido(radio_config_id, programa_id, estado, quando):
    return FilaAoVivo(radio_config_id=radio_config_id, programa_id=programa_id, estado=estado, telefone="1",
                      nome="Ana", tipo="musica", mensagem_usuario="toca", criado_em=quando)


def test_relatorio_do_dia_vem_do_as_run_das_promessas_e_dos_pedidos(client, account, auth_headers, db_session):
    radialista, programa = _criar_programa(client, auth_headers, account.id)
    pid, rid = programa["id"], radialista["id"]
    db_session.add_all([
        _evento(account, pid, 1, "abertura", "Bom dia, gente! A feira abriu.", "confirmado", NO_DIA),
        _evento(account, pid, 2, "musica", "", "confirmado", NO_DIA),
        _evento(account, pid, 3, "comentario", f"Bom dia de novo. {FRASE_LONGA}", "confirmado", NO_DIA),
        _evento(account, pid, 4, "comentario", "Bom dia, pessoal. A chuva parou.", "confirmado", NO_DIA),
        _evento(account, pid, 5, "vinheta", "Rádio Serra.", "falhou", NO_DIA),
        _evento(account, pid, 6, "comentario", "Nunca tocou.", "enviado", NO_DIA),
        _evento(account, pid, 7, "comentario", "Outro dia.", "confirmado", DIA_SEGUINTE),
        _promessa(pid, rid, "cumprida", NO_DIA),
        _promessa(pid, rid, "vencida", NO_DIA),
        _promessa(pid, rid, "cancelada", NO_DIA, contingencia="Ainda não chegou recado."),
        _promessa(pid, rid, "aberta", NO_DIA),
        _promessa(pid, rid, "vencida", DIA_SEGUINTE),
        _pedido(rid, pid, "executado", NO_DIA),
        _pedido(rid, pid, "nao_atendido", NO_DIA),
        _pedido(rid, pid, "em_fila", NO_DIA),
        _pedido(rid, pid, "executado", DIA_SEGUINTE),
    ])
    db_session.commit()

    resposta = client.get(f"/config/programas/{pid}/relatorio?data=2026-11-10", headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["data"] == "2026-11-10"
    assert corpo["as_run"] == {"enviados": 6, "confirmados": 4, "falharam": 1, "sem_relato": 1}
    assert corpo["secoes"]["promessas"] == {"cumpridas": 1, "vencidas": 1, "canceladas_com_contingencia": 1,
                                            "abertas_no_fim": 1}
    assert corpo["secoes"]["pedidos"] == {"recebidos": 3, "executados": 1, "nao_atendidos": 1, "expirados": 0,
                                          "pendentes_fim": 1}
    assert corpo["secoes"]["oralidade"]["avisos"] >= 1  # a frase longa do comentário
    assert corpo["secoes"]["repeticao"]["estrutura"] == 1  # três falas seguidas abrindo com saudação
    assert "promessa vencida: 1" in corpo["alertas"]
    assert set(corpo["nao_medido"]) == {"orcamento", "hard_time"}


def test_relatorio_sem_data_usa_o_dia_de_hoje_no_fuso_da_radio(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    corpo = client.get(f"/config/programas/{programa['id']}/relatorio", headers=auth_headers(account.id)).json()
    hoje = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).date().isoformat()
    assert corpo["data"] == hoje
    assert corpo["as_run"] == {"enviados": 0, "confirmados": 0, "falharam": 0, "sem_relato": 0}


def test_relatorio_de_programa_inexistente_404(client, account, auth_headers):
    resposta = client.get("/config/programas/999999/relatorio", headers=auth_headers(account.id))
    assert resposta.status_code == 404
