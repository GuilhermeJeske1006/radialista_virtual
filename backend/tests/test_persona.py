"""Persona do programa (F7): escalas 1-5, até 5 exemplos, linhas no system e leitura tolerante.

Sem persona gravada, o prompt não muda (os goldens do `padrao` seguem idênticos).
"""

import pytest
from pydantic import ValidationError

from app.live.persona import MAX_CARACTERES_EXEMPLO, MAX_EXEMPLOS, Persona, linhas_da_persona, persona_ou_none
from app.live.prompt_emissao import _persona, montar_prompt
from tests.test_live_formatos_prompt import contexto


def _com_persona(valor, **kw):
    ctx = contexto("padrao", "comentario", **kw)
    ctx.programa.persona = valor
    return ctx


def test_sem_persona_nenhuma_linha_no_system():
    ctx = contexto("padrao", "comentario")
    assert _persona(ctx) == []
    assert "Jeito de falar neste programa" not in montar_prompt(ctx).system


@pytest.mark.parametrize("valor", [None, {}])
def test_nulo_ou_vazio_e_sem_persona(valor):
    assert persona_ou_none(valor) is None
    assert linhas_da_persona(valor) == []


def test_escalas_default_sao_media_e_sem_exemplos():
    persona = Persona()
    assert (persona.proximidade, persona.formalidade, persona.energia, persona.humor, persona.ritmo) == (3, 3, 3, 3, 3)
    assert persona.exemplos == []


@pytest.mark.parametrize("campo", ["proximidade", "formalidade", "energia", "humor", "ritmo"])
@pytest.mark.parametrize("valor", [0, 6])
def test_escala_fora_de_1_a_5_e_rejeitada(campo, valor):
    with pytest.raises(ValidationError):
        Persona(**{campo: valor})


def test_mais_de_cinco_exemplos_e_rejeitado():
    with pytest.raises(ValidationError):
        Persona(exemplos=[f"fala {i}" for i in range(MAX_EXEMPLOS + 1)])


def test_exemplo_longo_demais_e_rejeitado():
    with pytest.raises(ValidationError):
        Persona(exemplos=["x" * (MAX_CARACTERES_EXEMPLO + 1)])


def test_exemplos_vazios_e_espacos_sao_descartados():
    persona = Persona(exemplos=["  ", "Bom dia, gente.", ""])
    assert persona.exemplos == ["Bom dia, gente."]


def test_faixas_viram_texto_de_baixa_media_e_alta():
    linhas = linhas_da_persona({"proximidade": 1, "formalidade": 3, "energia": 5, "humor": 2, "ritmo": 4})
    assert "- proximidade 1/5: distante e respeitoso, sem intimidade." in linhas
    assert "- formalidade 3/5: linguagem comum, nem formal nem gíria." in linhas
    assert "- energia 5/5: vibrante, com frases de impacto." in linhas
    assert "- humor 2/5: sério, sem brincadeira." in linhas
    assert "- ritmo 4/5: frases curtas e rápidas." in linhas


def test_linhas_trazem_exemplos_e_regra_de_nao_imitar():
    linhas = linhas_da_persona({"exemplos": ["Vamos juntos nessa tarde."]})
    texto = "\n".join(linhas)
    assert "Exemplos de fala aprovados" in texto
    assert "- Vamos juntos nessa tarde." in texto
    assert "Não imite nem cite apresentador ou pessoa real" in texto


def test_sem_exemplos_nao_ha_bloco_de_exemplos():
    assert "Exemplos de fala aprovados" not in "\n".join(linhas_da_persona({}))


def test_persona_invalida_no_banco_vira_none_sem_derrubar_a_leitura():
    assert persona_ou_none({"proximidade": 9}) is None
    assert linhas_da_persona({"exemplos": "isto não é lista"}) == []


def test_persona_entra_no_system_depois_do_formato():
    ctx = _com_persona({"energia": 5, "exemplos": ["Boa tarde!"]})
    system = montar_prompt(ctx).system
    assert "Jeito de falar neste programa" in system
    assert "- energia 5/5: vibrante, com frases de impacto." in system
    assert "- Boa tarde!" in system


def test_persona_nao_vai_para_a_mensagem_do_bloco():
    ctx = _com_persona({"exemplos": ["Segredo de estilo."]})
    assert "Segredo de estilo." not in montar_prompt(ctx).mensagem


def _payload_programa(**extra):
    return dict(nome="Cultura", tom="leve", horario_inicio="08:00", horario_fim="09:00", dose_noticia="nenhuma", **extra)


def test_programa_request_aceita_e_serializa_persona():
    from app.config.router import ProgramaRequest

    programa = ProgramaRequest(**_payload_programa(persona={"energia": 4, "exemplos": ["Oi, gente."]}))
    gravado = programa.model_dump()["persona"]
    assert gravado["energia"] == 4
    assert gravado["exemplos"] == ["Oi, gente."]
    assert gravado["humor"] == 3


def test_programa_request_sem_persona_grava_nulo():
    from app.config.router import ProgramaRequest

    assert ProgramaRequest(**_payload_programa()).model_dump()["persona"] is None


def test_programa_request_rejeita_persona_fora_da_escala():
    from app.config.router import ProgramaRequest

    with pytest.raises(ValidationError):
        ProgramaRequest(**_payload_programa(persona={"humor": 7}))


def test_programa_response_le_persona_invalida_do_banco_como_nula():
    from app.config.router import ProgramaResponse

    dados = dict(_payload_programa(), id=1, radio_config_id=1, persona={"humor": 99})
    assert ProgramaResponse.model_validate(dados).persona is None


def test_persona_antiga_adota_girias_automaticas_sem_orientacoes():
    persona = persona_ou_none({"formalidade": 2, "exemplos": []})
    assert persona.girias == "automatico"
    assert persona.orientacoes == ""


@pytest.mark.parametrize("girias,trecho", [
    ("evitar", "Evite gírias"), ("moderadas", "gírias leves ocasionalmente"),
    ("frequentes", "gírias naturais com mais frequência"),
])
def test_vocabulario_do_programa_entra_no_prompt(girias, trecho):
    texto = "\n".join(linhas_da_persona({"girias": girias, "orientacoes": "  Seja direto nos boletins.  "}))
    assert trecho in texto
    assert "Seja direto nos boletins." in texto
    assert "prevalecem sobre a personalidade geral" in texto
    assert "somente a este programa" in texto


@pytest.mark.parametrize("dados", [{"girias": "qualquer"}, {"orientacoes": "x" * 1201}])
def test_rejeita_configuracao_de_estilo_invalida(dados):
    with pytest.raises(ValidationError):
        Persona(**dados)
