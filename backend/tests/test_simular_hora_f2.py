"""Simulação com o dublê de TTS (F2): duração medida no as-run, orçamento do backend e custo.

O dublê de TTS devolve um mp3 silencioso com a duração de uma voz a `wpm_real` palavras/min; o simulador
chama o /tts como o painel e usa a duração medida (cabeçalho X-Duracao-Fala-S). Critérios de aceite da F2
(docs/melhoria-radio/f2/auditoria.md §6, itens 26 a 29): 95% das falas dentro do orçamento, nenhuma acima
de 130% do máximo, no máximo 2 chamadas de LLM e 2 sínteses por fala, e a calibração convergindo.
"""

import pytest

PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
WPM_REAL = 145  # voz ~10% mais lenta que o padrão do modelo v3 (162): a estimativa começa otimista


@pytest.fixture(scope="module")
def simulacoes_tts():
    from scripts.simular_hora import simular

    return {perfil: simular(perfil, relogio_backend="fixture", tts="duble", wpm_real=WPM_REAL) for perfil in PERFIS}


def _falas(as_run):
    return [e for e in as_run["eventos"] if e["tipo"] == "fala"]


def test_duble_tts_gera_mp3_silencioso_com_a_duracao_da_voz():
    from app.postprod.audio_io import duracao_mp3_s
    from scripts.simulacao.dubles import DubleTTS

    duble = DubleTTS(wpm_real=120, pausa_s=1.2)
    texto = "um dois três quatro cinco seis sete oito nove dez onze doze treze catorze quinze dezesseis"
    audio = duble.sintetizar_audio(texto, "voz", tipo_bloco="comentario")
    assert duracao_mp3_s(audio) == pytest.approx(8.0, abs=0.05)
    assert duracao_mp3_s(duble.sintetizar_audio(texto + "...... fim", "voz")) == pytest.approx(8.5 + 1.2, abs=0.05)
    # Mesmo texto, mesmos bytes (como o cache de TTS); texto diferente com a mesma duração, bytes diferentes.
    assert duble.sintetizar_audio(texto, "voz") == audio
    assert duble.sintetizar_audio(texto.replace("um", "um,"), "voz") != audio
    assert b"".join(duble.sintetizar_audio_stream(texto, "voz")) == audio
    assert duble.contadores["sintetizar_audio"] == 5


@pytest.mark.parametrize("perfil", PERFIS)
def test_simulador_le_orcamento_e_duracao_medida_do_backend(simulacoes_tts, perfil):
    resultado = simulacoes_tts[perfil]
    falas = _falas(resultado.as_run)
    assert falas
    for fala in falas:
        assert fala["orcamento_s"]["fonte"] in ("relogio", "formato", "observacao")
        assert "aplicado" in fala["orcamento_s"]
        assert fala["fala_ajuste"] in ("nenhum", "reescrita", "encurtada", "cortada", "acima_do_teto")
        assert fala["duracao_medida_s"] is not None and fala["duracao_medida_s"] > 0
        assert fala["duracao_estimada_backend_s"] is not None
    assert resultado.resumo["config"]["tts"] == "duble"
    assert resultado.resumo["chamadas_tts"] == len({f["bloco_n"] for f in falas}) + resultado.resumo[
        "blocos_fala_nao_tocados"]
    assert resultado.resumo["tentativas_rede"] == 0 and resultado.resumo["erros_http"] == 0


@pytest.mark.parametrize("perfil", PERFIS)
def test_criterios_de_orcamento_e_custo(simulacoes_tts, perfil):
    resumo = simulacoes_tts[perfil].resumo
    assert resumo["fora_orcamento_pct"] <= 5.0
    assert resumo["estouro_max_pct"] <= 30.0
    assert resumo["acima_teto_orcamento"] == 0
    custo = resumo["orcamento_fala"]
    assert custo["max_chamadas_llm_por_fala"] <= 2
    assert custo["max_sinteses_por_fala"] <= 2
    assert resumo["chamadas_llm"]["total"] <= 2 * resumo["chamadas_llm"]["falas"]
    for chave in ("revisoes_por_duracao", "reescritas", "encurtadas", "cortadas", "acima_do_teto", "ressinteses_tts"):
        assert isinstance(custo[chave], int)


def test_excesso_persistente_passa_pelo_encurtamento():
    """O dublê ignora o limite da reescrita: o backend não chama o LLM uma terceira vez e encurta por frases."""
    from scripts.simulacao.fixtures import Injecao, carregar_fixture
    from scripts.simular_hora import simular

    fixture = carregar_fixture("popular_sertanejo")
    fixture = fixture.model_copy(update={"injecoes": [
        Injecao(fala=2, tipo="excesso_persistente", fator=2.5), Injecao(fala=4, tipo="excesso_persistente", fator=2.5),
    ]})
    resultado = simular(fixture, relogio_backend="fixture", tts="duble", wpm_real=WPM_REAL)
    resumo = resultado.resumo
    assert resumo["dubles"]["contadores"]["injecao_excesso_persistente"] >= 2
    assert resumo["orcamento_fala"]["encurtadas"] + resumo["orcamento_fala"]["acima_do_teto"] >= 1
    assert resumo["orcamento_fala"]["max_chamadas_llm_por_fala"] <= 2
    assert resumo["acima_teto_orcamento"] == 0


@pytest.mark.parametrize("wpm_real", [120, 190])
def test_calibracao_converge(wpm_real):
    """Depois das primeiras amostras, a estimativa do backend fica a até 10% da duração medida."""
    from app.config.settings import settings
    from scripts.simular_hora import simular

    resultado = simular("variedades_leves", relogio_backend="fixture", tts="duble", wpm_real=wpm_real)
    medidas = [f for f in _falas(resultado.as_run)
               if f["duracao_medida_s"] and f["duracao_estimada_backend_s"] and f["palavras"] >= 8]
    calibradas = medidas[settings.fala_calibracao_min_amostras:]
    assert len(calibradas) >= 3
    erros = [abs(f["duracao_estimada_backend_s"] - f["duracao_medida_s"]) / f["duracao_medida_s"] for f in calibradas]
    assert max(erros) <= 0.10, erros
    assert resultado.resumo["duracao_fala"]["erro_estimativa_calibrada_pct"] <= 10.0
