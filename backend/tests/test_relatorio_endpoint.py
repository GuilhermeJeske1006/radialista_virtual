"""Endpoint do relatório pós-programa (F11 item 2): POST /config/programas/{id}/relatorio."""

from tests.test_config_relogio import _criar_programa


def test_relatorio_monta_secoes_a_partir_do_resumo(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    resposta = client.post(
        f"/config/programas/{programa['id']}/relatorio",
        json={"promessas": {"vencidas": 2}, "fora_orcamento_pct": 0.0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["programa_id"] == programa["id"]
    assert corpo["secoes"]["promessas"]["vencidas"] == 2
    assert corpo["sugestoes"]  # promessa vencida gera sugestao de continuidade (ver montar_relatorio)


def test_relatorio_resumo_vazio_nao_quebra(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    resposta = client.post(f"/config/programas/{programa['id']}/relatorio", json={},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200


def test_relatorio_de_programa_de_outra_conta_404(client, account, auth_headers):
    resposta = client.post("/config/programas/999999/relatorio", json={}, headers=auth_headers(account.id))
    assert resposta.status_code == 404
