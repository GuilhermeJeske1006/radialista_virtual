"""Bancada com personas (F13): papéis fixos, ordem de turnos, regra de resposta no prompt, API do vínculo."""

from types import SimpleNamespace

import pytest
from freezegun import freeze_time

from app.live.bancada import (
    COMENTARISTA,
    CONTRAPONTO,
    MEDIADOR,
    instrucao_de_turnos,
    ordenar_turnos,
    validar_papel_bancada,
)
from app.llm.prompt_builder import ParticipantePrograma, montar_system_prompt
from tests.test_llm_prompt_builder import _account, _programa, _radialista


def test_papel_fora_do_contrato_recusado():
    with pytest.raises(ValueError):
        validar_papel_bancada("apresentador")


def test_papel_vazio_vira_nulo_e_papel_valido_passa():
    assert validar_papel_bancada("") is None
    assert validar_papel_bancada(None) is None
    assert validar_papel_bancada(MEDIADOR) == MEDIADOR


def test_sem_nenhum_papel_a_ordem_nao_muda():
    gente = [SimpleNamespace(p=None, n="a"), SimpleNamespace(p=None, n="b")]
    assert [g.n for g in ordenar_turnos(gente, lambda g: g.p)] == ["a", "b"]


def test_com_papeis_mediador_comentarista_contraponto_nessa_ordem():
    gente = [
        SimpleNamespace(p=CONTRAPONTO, n="c"), SimpleNamespace(p=None, n="x"),
        SimpleNamespace(p=MEDIADOR, n="m"), SimpleNamespace(p=COMENTARISTA, n="o"),
    ]
    assert [g.n for g in ordenar_turnos(gente, lambda g: g.p)] == ["m", "o", "c", "x"]


def test_instrucao_de_turnos_pede_resposta_ao_anterior():
    texto = instrucao_de_turnos()
    assert "responde ao que o anterior acabou de dizer" in texto
    assert "mediador" in texto and "contraponto" in texto


@freeze_time("2026-08-10 15:00:00")
def test_prompt_multi_voz_com_bancada_inclui_papel_e_regra_de_resposta():
    dono = _radialista(id=1, nome_locutor="Ze")
    convidado = _radialista(id=2, nome_locutor="Maria")
    roster = [
        ParticipantePrograma(dono, "Apresentador principal", "animado", papel_bancada=MEDIADOR),
        ParticipantePrograma(convidado, "Comentarista", "calma", papel_bancada=COMENTARISTA),
    ]
    prompt = montar_system_prompt(_account(), dono, _programa(id=1), roster=roster)
    assert "papel na bancada: mediador" in prompt
    assert "responde ao que o anterior acabou de dizer" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_multi_voz_sem_bancada_fica_como_antes():
    dono = _radialista(id=1, nome_locutor="Ze")
    convidado = _radialista(id=2, nome_locutor="Maria")
    roster = [
        ParticipantePrograma(dono, "Apresentador principal", "animado"),
        ParticipantePrograma(convidado, "Comentarista", "calma"),
    ]
    prompt = montar_system_prompt(_account(), dono, _programa(id=1), roster=roster)
    assert "papel na bancada" not in prompt
    assert "responde ao que o anterior" not in prompt


def test_api_grava_papel_de_bancada_no_vinculo(client, account, auth_headers):
    from tests.test_config_relogio import _criar_programa
    radialista, programa = _criar_programa(client, auth_headers, account.id)
    url = f"/config/programas/{programa['id']}/radialistas/{radialista['id']}"
    resposta = client.put(url, json={"papel": "Mediador", "comportamento": "", "papel_bancada": "mediador"},
                          headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["papel_bancada"] == "mediador"


def test_api_papel_de_bancada_invalido_400(client, account, auth_headers):
    from tests.test_config_relogio import _criar_programa
    radialista, programa = _criar_programa(client, auth_headers, account.id)
    url = f"/config/programas/{programa['id']}/radialistas/{radialista['id']}"
    resposta = client.put(url, json={"papel": "X", "comportamento": "", "papel_bancada": "chefe"},
                          headers=auth_headers(account.id))
    assert resposta.status_code == 400


def test_api_salvar_sem_papel_de_bancada_mantem_o_atual(client, account, auth_headers):
    from tests.test_config_relogio import _criar_programa
    radialista, programa = _criar_programa(client, auth_headers, account.id)
    url = f"/config/programas/{programa['id']}/radialistas/{radialista['id']}"
    client.put(url, json={"papel": "Mediador", "comportamento": "", "papel_bancada": "mediador"},
               headers=auth_headers(account.id))
    resposta = client.put(url, json={"papel": "Mediador da tarde", "comportamento": "calmo"},
                          headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert resposta.json()["papel_bancada"] == "mediador"
