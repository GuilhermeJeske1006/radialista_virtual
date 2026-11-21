"""Simulação com o validador pós-geração (F3, S1 e S3 da auditoria §6)."""

import pytest

PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")


def test_metricas_nao_tem_detector_proprio(monkeypatch):
    """S3: o simulador mede música anunciada com o mesmo detector do backend."""
    from app.live import validacao_fala
    from scripts.simulacao import metricas

    chamadas = []
    original = validacao_fala.mencoes_musica

    def espiao(*args, **kwargs):
        chamadas.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(validacao_fala, "mencoes_musica", espiao)
    citaveis = [("Estrada de Chão Batido", "Irmãos Taquara"), ("Viola no Alpendre", "Os Filhos da Serra")]
    texto = "Quem chega agora é Irmãos Taquara, com Estrada de Chão Batido."
    assert metricas.titulos_citados(texto, citaveis) == ["Estrada de Chão Batido - Irmãos Taquara"]
    assert chamadas == [texto]


@pytest.mark.parametrize("perfil", PERFIS)
def test_s1_sem_anuncio_sem_confirmacao_com_relogio_e_dublê_de_tts(perfil):
    from scripts.simular_hora import simular

    resultado = simular(perfil, relogio_backend="fixture", tts="duble", wpm_real=145)
    resumo = resultado.resumo
    assert resumo["anuncio_sem_confirmacao"] == 0
    assert resumo["tentativas_rede"] == 0 and resumo["erros_http"] == 0
    assert resumo["tempo_execucao_s"] < 30
    assert resumo["orcamento_fala"]["max_chamadas_llm_por_fala"] <= 2
    assert resumo["orcamento_fala"]["max_sinteses_por_fala"] <= 2
    assert all("validacao_fala" in e for e in resultado.as_run["eventos"])
    assert resultado.as_run["nomes_nao_musica"]
    if perfil == "musical_adulto":
        assert resumo["dubles"]["contadores"]["injecao_cita_musica"] >= 1
        assert resumo["validacao_fala"]["regras"]["musica_nao_confirmada"] >= 1
