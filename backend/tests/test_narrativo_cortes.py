"""F14: quadro narrativo (instrução no bloco de quadro fixo) e cortes do as-run."""

from app.live.cortes import cortes_do_as_run
from app.live.narrativo import eh_quadro_narrativo, instrucao_narrativa


def _ev(ordem, tipo="fala", status="confirmado", pedido_id=None):
    return {"ordem": ordem, "tipo": tipo, "status": status, "pedido_id": pedido_id}


def test_quadro_narrativo_reconhecido_por_prefixo_sem_acento_e_caixa():
    assert eh_quadro_narrativo("Narrativo: a feira")
    assert eh_quadro_narrativo("HISTÓRIA da semana")
    assert eh_quadro_narrativo("historia do bairro")
    assert not eh_quadro_narrativo("Curiosidade das 10")
    assert not eh_quadro_narrativo(None)


def test_instrucao_narrativa_traz_as_quatro_partes_nessa_ordem():
    texto = instrucao_narrativa()
    ordem = [texto.index(p) for p in ("personagem", "situação", "mudança", "consequência")]
    assert ordem == sorted(ordem)


def test_prompt_de_quadro_narrativo_recebe_a_instrucao():
    from app.live import prompt_emissao
    assert prompt_emissao.eh_quadro_narrativo is eh_quadro_narrativo  # ligado no prompt


def test_corte_de_falas_confirmadas_sem_pedido_aceita_musica_no_meio():
    eventos = [_ev(1), _ev(2), _ev(3, "musica"), _ev(4), _ev(5)]
    cortes = cortes_do_as_run(eventos)
    # música no meio não quebra o corte (confirmada, sem pedido); começa e termina em fala
    assert cortes == [
        {"ordem_inicio": 1, "ordem_fim": 5, "eventos": 5, "tipos": ["fala", "fala", "musica", "fala", "fala"]},
    ]


def test_corte_nao_atravessa_falhou_nem_pedido():
    eventos = [_ev(1), _ev(2, status="falhou"), _ev(3), _ev(4, pedido_id=9), _ev(5), _ev(6)]
    cortes = cortes_do_as_run(eventos)
    assert [(c["ordem_inicio"], c["ordem_fim"]) for c in cortes] == [(5, 6)]


def test_corte_comeca_e_termina_em_fala():
    eventos = [_ev(1, "vinheta"), _ev(2), _ev(3, "vinheta")]
    assert cortes_do_as_run(eventos) == []


def test_corte_respeita_tamanho_maximo_sem_sobrepor():
    eventos = [_ev(i) for i in range(1, 11)]
    cortes = cortes_do_as_run(eventos, maximo=4)
    assert [(c["ordem_inicio"], c["ordem_fim"]) for c in cortes] == [(1, 4), (5, 8), (9, 10)]


def test_api_lista_cortes_do_as_run(client, account, auth_headers, db_session):
    import datetime as dt

    from app.models.as_run_evento import AsRunEvento
    from tests.test_config_relogio import _criar_programa
    _, programa = _criar_programa(client, auth_headers, account.id)
    agora = dt.datetime.now(dt.timezone.utc)
    for ordem, tipo in [(1, "fala"), (2, "fala"), (3, "musica")]:
        db_session.add(AsRunEvento(account_id=account.id, programa_id=programa["id"], ordem=ordem, tipo=tipo,
                                   texto="", status="confirmado", criado_em=agora))
    db_session.commit()
    resposta = client.get(f"/config/programas/{programa['id']}/cortes", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()[0]["eventos"] == 2
