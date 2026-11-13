"""Catálogo de formatos pela rota e pelo prompt do WhatsApp (F6, I3 e I9 da auditoria §8).

I3: o alias é alias de verdade. Os três cenários musicais dos goldens da F3 (gravados com `musical_companhia`) rodam
com `musical_adulto` e dão o mesmo prompt, resposta, Redis, banco e sorteios.
I9: `montar_system_prompt` (também usado pelo WhatsApp) é o mesmo para o alias e o canônico.
"""

import json

import pytest
from freezegun import freeze_time

import test_live_proxima_caracterizacao as caracterizacao

MUSICAIS = [c for c in caracterizacao.CENARIOS if c.nome.startswith("musical_")]


def _com_canonico(preparar):
    def preparar_canonico(db, account, radialista, programa, mp):
        preparar(db, account, radialista, programa, mp)
        assert programa.perfil_programacao == "musical_companhia"
        programa.perfil_programacao = "musical_adulto"
    return preparar_canonico


def test_i3_cenarios_musicais_existem():
    assert {c.nome for c in MUSICAIS} == {"musical_retomada_com_excesso", "musical_identificacao",
                                          "musical_musica_pedido"}


@pytest.mark.parametrize("cenario", MUSICAIS, ids=[c.nome for c in MUSICAIS])
def test_i3_alias_e_canonico_dao_o_mesmo_retrato(cenario, client, account, auth_headers, db_session, monkeypatch):
    import dataclasses

    canonico = dataclasses.replace(cenario, preparar=_com_canonico(cenario.preparar))
    retrato = json.loads(json.dumps(caracterizacao._rodar(canonico, client, account, auth_headers, db_session,
                                                          monkeypatch), ensure_ascii=False, default=str))
    esperado = json.loads((caracterizacao.DIR_GOLDEN / f"{cenario.nome}.json").read_text(encoding="utf-8"))
    for parte in ("chamadas_llm", "resposta", "redis", "banco", "random", "buscas_musica", "temas_em_background"):
        assert retrato[parte] == esperado[parte], f"{cenario.nome}: '{parte}' mudou com o id canônico"


@pytest.fixture
def _sem_clima_real(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)


@freeze_time("2026-08-10 15:00:00")
@pytest.mark.parametrize("ia", [False, True])
def test_i9_system_prompt_igual_para_alias_e_canonico(ia, _sem_clima_real):
    from test_live_formatos_caracterizacao import _system

    alias, canonico = _system("musical_companhia", ia), _system("musical_adulto", ia)
    assert alias == canonico
    assert "siga estritamente" in canonico and "fique livre pra inserir blocos extras" not in canonico


# ---------------------------------------------------------------------------------------------------------
# Formatos novos pela rota (I1, I2, I5, I6, I7 da auditoria §8)
# ---------------------------------------------------------------------------------------------------------

def _rodar(cenario, client, account, auth_headers, db_session, monkeypatch) -> dict:
    return json.loads(json.dumps(caracterizacao._rodar(cenario, client, account, auth_headers, db_session,
                                                       monkeypatch), ensure_ascii=False, default=str))


def _cenario(nome, corpo, *passos, perfil, respostas=None, **extra):
    return caracterizacao.Cenario(nome, corpo, preparar=caracterizacao._p_formato(perfil, *passos),
                                  respostas=respostas or ["Seguimos juntos nesta tarde de rádio."], **extra)


def test_golden_do_canonico_igual_ao_do_alias():
    canonico = json.loads((caracterizacao.DIR_GOLDEN / "formato_musical_adulto_identificacao.json").read_text())
    alias = json.loads((caracterizacao.DIR_GOLDEN / "musical_identificacao.json").read_text())
    assert canonico.pop("cenario") == "formato_musical_adulto_identificacao"
    assert alias.pop("cenario") == "musical_identificacao"
    assert canonico == alias


def test_i1_popular_sem_relogio_comentario_aplica_a_unidade_e_reescreve_uma_vez(
        client, account, auth_headers, db_session, monkeypatch):
    from app.live.formatos import FORMATOS

    cenario = _cenario("i1", {"total_falas": 4, "historico": caracterizacao.HIST_MUSICA}, perfil="popular_sertanejo",
                       respostas=[caracterizacao.LONGA * 3, "Seguimos com você, com prosa curta e moda boa."])
    retrato = _rodar(cenario, client, account, auth_headers, db_session, monkeypatch)
    resposta = retrato["resposta"]
    assert resposta["tipo"] == "comentario"
    assert resposta["orcamento_fala_s"] == {"min_s": 20.0, "alvo_s": 35.0, "max_s": 60.0, "fonte": "formato",
                                            "aplicado": True}
    assert resposta["duracao_alvo_segundos"] == [20, 60]
    assert len(retrato["chamadas_llm"]) == 2  # a reescrita única (no máximo 2 chamadas por fala)
    system = retrato["chamadas_llm"][0]["system"]
    cabecalho = FORMATOS["popular_sertanejo"].direcao_cabecalho
    assert any(linha.startswith(cabecalho) for linha in system)
    assert not any(FORMATOS[outro].direcao_cabecalho in linha for linha in system
                   for outro in ("musical_adulto", "variedades_leves"))
    assert "A promessa do formato prevalece sobre o perfil do horário." in system
    assert resposta["fala_ajuste"] == "reescrita"


def test_i2_variedades_quadro_fixo_usa_a_unidade_de_quadro_e_nao_convida(
        client, account, auth_headers, db_session, monkeypatch):
    cenario = _cenario("i2", {"total_falas": 3, "historico": caracterizacao.HIST_MUSICA}, caracterizacao._p_quadro,
                       perfil="variedades_leves")
    retrato = _rodar(cenario, client, account, auth_headers, db_session, monkeypatch)
    orcamento = retrato["resposta"]["orcamento_fala_s"]
    assert (orcamento["min_s"], orcamento["max_s"], orcamento["fonte"]) == (60.0, 180.0, "formato")
    assert "rotacao:convite_chamada_ouvinte:1" not in retrato["redis"]  # convite só na chamada
    assert "Reoriente quem acabou de chegar: nome do programa e da rádio em uma frase." in \
        retrato["chamadas_llm"][0]["system"]


def test_i2_variedades_convida_na_chamada_e_popular_em_qualquer_bloco(
        client, account, auth_headers, db_session, monkeypatch):
    chamada = _cenario("i2_chamada", {"total_falas": 4, "historico": caracterizacao.HIST_MUSICA},
                       perfil="variedades_leves")
    retrato = _rodar(chamada, client, account, auth_headers, db_session, monkeypatch)
    assert retrato["resposta"]["tipo"] == "chamada_ouvinte"
    assert "rotacao:convite_chamada_ouvinte:1" in retrato["redis"]


def test_i2_popular_convida_fora_da_chamada(client, account, auth_headers, db_session, monkeypatch):
    comentario = _cenario("i2_popular", {"total_falas": 4, "historico": caracterizacao.HIST_MUSICA},
                          perfil="popular_sertanejo")
    retrato = _rodar(comentario, client, account, auth_headers, db_session, monkeypatch)
    assert retrato["resposta"]["tipo"] == "comentario"
    assert "rotacao:convite_chamada_ouvinte:1" in retrato["redis"]


def test_i5_popular_com_relogio_a_no_link_e_comentario_de_20_a_35(
        client, account, auth_headers, db_session, monkeypatch):
    cenario = _cenario("i5_popular", {"total_falas": 3, "historico": caracterizacao.HIST_MUSICA,
                                      "inicio_previsto": "2026-11-10T12:12:30-03:00"},
                       caracterizacao._p_relogio("A", "0:40"), perfil="popular_sertanejo", agora="2026-11-10 15:12:20")
    resposta = _rodar(cenario, client, account, auth_headers, db_session, monkeypatch)["resposta"]
    assert (resposta["tipo"], resposta["relogio"]["etapa"]["tipo"]) == ("comentario", "link")
    assert resposta["relogio"]["orcamento_s"] == [20, 35] and resposta["duracao_alvo_segundos"] == [20, 35]
    assert resposta["orcamento_fala_s"]["fonte"] == "relogio"


def test_i5_variedades_com_relogio_c_no_quadro(client, account, auth_headers, db_session, monkeypatch):
    cenario = _cenario("i5_variedades", {"total_falas": 8, "historico": caracterizacao.HIST_MUSICA,
                                         "inicio_previsto": "2026-11-10T12:44:00-03:00"},
                       caracterizacao._p_relogio_c_quadro, perfil="variedades_leves", agora="2026-11-10 15:43:50")
    retrato = _rodar(cenario, client, account, auth_headers, db_session, monkeypatch)
    resposta = retrato["resposta"]
    assert (resposta["tipo"], resposta["relogio"]["etapa"]["tipo"]) == ("Quadro da Receita", "quadro")
    assert resposta["relogio"]["orcamento_s"][0] == 60 and resposta["relogio"]["orcamento_s"][1] <= 180
    assert "Reoriente quem acabou de chegar: nome do programa e da rádio em uma frase." in \
        retrato["chamadas_llm"][0]["system"]


@pytest.mark.parametrize("perfil, funcao", [("popular_sertanejo", "gerar_dialogo_multivoz"),
                                            ("variedades_leves", "gerar_dialogo_multivoz"),
                                            ("musical_adulto", "gerar_resposta")])
def test_i6_multivoz_nos_novos_e_desligado_no_musical(perfil, funcao, client, account, auth_headers, db_session,
                                                      monkeypatch):
    dialogo = json.dumps({"linhas": [{"locutor": "Ze do Radio", "texto": "Maria, você viu a feira de domingo?"},
                                     {"locutor": "Maria", "texto": "Vi sim, estava cheia de gente."}]},
                         ensure_ascii=False)
    cenario = _cenario("i6", {"total_falas": 3, "historico": caracterizacao.HIST_MUSICA}, caracterizacao._p_multivoz,
                       perfil=perfil, respostas=[dialogo if funcao == "gerar_dialogo_multivoz" else "Você ouve a rádio."])
    retrato = _rodar(cenario, client, account, auth_headers, db_session, monkeypatch)
    assert [c["funcao"] for c in retrato["chamadas_llm"]] == [funcao]


@pytest.mark.parametrize("perfil, preset", [("popular_sertanejo", "A"), ("variedades_leves", "C")])
def test_i7_painel_antigo_sem_inicio_previsto(perfil, preset, client, account, auth_headers, db_session, monkeypatch):
    """Painel antigo (sem `inicio_previsto`) em cada formato novo: sem erro, o servidor estima o horário e decide
    pelo relógio do formato (o hard time em uma hora inteira fica no S2 da simulação, variante sem_inicio_previsto)."""
    cenario = _cenario("i7", {"total_falas": 0, "historico": []}, caracterizacao._p_relogio(preset), perfil=perfil,
                       agora="2026-11-10 15:00:05")
    resposta = _rodar(cenario, client, account, auth_headers, db_session, monkeypatch)["resposta"]
    assert resposta["relogio"]["inicio_previsto_aceito"] is False
    assert resposta["relogio"]["preset"] == preset
