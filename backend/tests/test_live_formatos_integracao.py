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
