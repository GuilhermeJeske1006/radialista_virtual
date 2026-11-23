"""F14: quadro narrativo (instrução no bloco de quadro fixo) e cortes do as-run."""

import datetime

import pytest
from freezegun import freeze_time

from app.live.cortes import cortes_do_as_run
from app.live.narrativo import eh_quadro_narrativo, instrucao_narrativa
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from tests.test_live_router import AGORA_UTC, _url_proxima


@pytest.fixture()
def programa_com_quadro(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Programa Principal",
                        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0), estrutura_blocos=[])
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


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


@pytest.mark.parametrize("quadro,narrativo", [("História do bairro", True), ("Curiosidade das 10", False)])
def test_proxima_poe_a_instrucao_narrativa_so_no_quadro_narrativo(
    client, account, auth_headers, programa_com_quadro, db_session, monkeypatch, quadro, narrativo
):
    """O system do /proxima traz a instrução de quatro passos no quadro narrativo e não em outro quadro fixo."""
    radio_config, programa = programa_com_quadro
    programa.estrutura_blocos = [quadro]
    programa.quadros_fixos = {quadro: ["a padaria que voltou a abrir"]}
    programa.ia_pode_adicionar_blocos = False
    db_session.commit()
    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", lambda nome: "comentario")
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda system, msg: prompts.append(system) or "Dona Rosa reabriu a padaria da esquina.")
    with freeze_time(AGORA_UTC):
        resposta = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": [], "total_falas": 1},
                               headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert f"quadro fixo '{quadro}'" in prompts[0]
    assert (instrucao_narrativa() in prompts[0]) is narrativo


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


def test_corte_reconhece_os_tipos_que_a_proxima_grava_no_as_run():
    """O /proxima grava o tipo do bloco (abertura, comentario, Música Sertaneja...), nunca "fala"."""
    eventos = [_ev(1, "vinheta"), _ev(2, "abertura"), _ev(3, "Música Sertaneja"), _ev(4, "comentario"),
               _ev(5, "patrocinador"), _ev(6, "servico"), _ev(7, "intervalo"), _ev(8, "Notícia local")]
    cortes = cortes_do_as_run(eventos)
    assert [(c["ordem_inicio"], c["ordem_fim"]) for c in cortes] == [(2, 6)]
    assert cortes[0]["tipos"] == ["abertura", "Música Sertaneja", "comentario", "patrocinador", "servico"]


def test_bloco_de_fala_com_texto_vazio_nao_abre_nem_fecha_corte():
    eventos = [{**_ev(1, "comentario"), "texto": "  "}, _ev(2, "comentario"), _ev(3, "noticia"),
               {**_ev(4, "comentario"), "texto": ""}]
    assert [(c["ordem_inicio"], c["ordem_fim"]) for c in cortes_do_as_run(eventos)] == [(2, 3)]


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
    for ordem, tipo, texto in [(1, "abertura", "Bom dia!"), (2, "comentario", "Hoje tem feira."), (3, "musica", ""),
                               (4, "comentario", "")]:
        db_session.add(AsRunEvento(account_id=account.id, programa_id=programa["id"], ordem=ordem, tipo=tipo,
                                   texto=texto, status="confirmado", criado_em=agora))
    db_session.commit()
    resposta = client.get(f"/config/programas/{programa['id']}/cortes", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()[0]["eventos"] == 2
