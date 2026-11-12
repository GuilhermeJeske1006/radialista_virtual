"""Simulação com promessas e participação (F4, S1-S3 da auditoria §8).

Aceite da F4 no modo fake: 0 promessas vencidas sem fala de contingência, 0 pedidos anunciados fora do estado
correto e nenhum ouvinte inexistente no ar, nos três perfis e nas quatro variantes da F3, sem piorar a F1-F3.
"""

import pytest

PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
VARIANTES = {
    "relogio": dict(relogio_backend="fixture", wpm_real=145),
    "sem_relogio": dict(relogio_backend="nenhum", wpm_real=145),
    "voz_120": dict(relogio_backend="fixture", wpm_real=120),
    "sem_inicio_previsto": dict(relogio_backend="fixture", wpm_real=145, inicio_previsto=False),
}


@pytest.mark.parametrize("variante", list(VARIANTES))
@pytest.mark.parametrize("perfil", PERFIS)
def test_s1_aceite_da_f4_nos_tres_perfis(perfil, variante):
    from scripts.simular_hora import simular

    resultado = simular(perfil, tts="duble", **VARIANTES[variante])
    resumo = resultado.resumo
    assert resumo["promessa_vencida"] == 0
    assert resumo["promessa_sem_registro"] == 0
    assert resumo["pedido_indevido"] == 0 and resumo["pedido_indevido_legado"] == 0
    assert resumo["ouvinte_inexistente"] == 0
    assert resumo["anuncio_sem_confirmacao"] == 0
    assert resumo["pedidos"]["atendidos_antes_de_tocar"] == 0  # D1: o legado também confirma depois de tocar
    assert all(p["estado"] != "aberta" for p in resultado.as_run["promessas"])
    contadores = resumo["dubles"]["contadores"]
    if perfil == "popular_sertanejo":
        assert contadores["injecao_promessa"] >= 1
    if perfil == "variedades_leves":
        assert contadores["injecao_cita_ouvinte"] >= 1
    # F1-F3 não pioram (voz 120 e sem relógio são estresse e linha de base: limites registrados na F2).
    assert resumo["orcamento_fala"]["max_chamadas_llm_por_fala"] <= 2
    assert resumo["orcamento_fala"]["max_sinteses_por_fala"] <= 2
    assert resumo["tempo_execucao_s"] < 30 and resumo["tentativas_rede"] == 0 and resumo["erros_http"] == 0
    if variante in ("relogio", "sem_inicio_previsto"):
        assert resumo["atraso_hard_time_s"] <= 5
        assert resumo["encerramento_no_ar"] is True
        assert resumo["fora_orcamento_pct"] == 0


def _injecao(fala, frase):
    from scripts.simulacao.fixtures import Injecao

    return Injecao(fala=fala, tipo="promessa", frase=frase)


def test_s2_cenario_dedicado_cumprida_contingencia_removida_e_simulada():
    """Popular (relógio A): a promessa da fala 2 para os recados é cumprida no retorno de 27:00 (Seu Ditinho);
    a receita de bolo não tem evento e sai; a mensagem inventada sai. Musical (relógio A): sem abraço na fila no
    retorno, a promessa da retomada vira a contingência, que vai ao ar."""
    from scripts.simular_hora import simular

    popular = simular("popular_sertanejo", relogio_backend="fixture", tts="duble", wpm_real=145, injecoes_extra=[
        _injecao(2, "Mais tarde a gente lê os recados de ouvinte."),
        _injecao(6, "Daqui a pouco tem receita de bolo."),
        _injecao(7, "Chegou agora uma mensagem de uma ouvinte pedindo um beijo para a mãe.")])
    musical = simular("musical_adulto", relogio_backend="fixture", tts="duble", wpm_real=145, injecoes_extra=[
        _injecao(2, "Mais tarde a gente lê os recados por aqui.")])
    for resultado in (popular, musical):
        assert resultado.resumo["promessa_vencida"] == 0
        assert resultado.resumo["promessa_sem_registro"] == 0
        assert resultado.resumo["pedido_indevido"] == 0
    assert popular.resumo["promessas"]["cumpridas"] >= 1
    assert popular.resumo["validacao_fala"]["regras"]["promessa_sem_evento"] >= 1
    assert popular.resumo["validacao_fala"]["regras"]["participacao_simulada"] >= 1
    falas = " ".join(e["texto"] for e in popular.as_run["eventos"] if e["tipo"] == "fala")
    assert "receita de bolo" not in falas and "Chegou agora uma mensagem" not in falas
    assert musical.resumo["promessas"]["canceladas_com_contingencia"] == 1
    contingencia = musical.resumo["promessas"]["contingencias_no_ar"][0]
    assert contingencia.startswith("Ainda não chegou recado para ler agora")
    assert any(contingencia in e["texto"] for e in musical.as_run["eventos"] if e["tipo"] == "fala")


def test_s3_metricas_usam_os_detectores_do_backend(monkeypatch):
    from app.live import participacao, promessas
    from scripts.simulacao import metricas

    chamadas = {"promessas": 0, "participacao": 0}
    detectar, mencoes = promessas.detectar, participacao.mencoes_participacao

    def espiao_promessas(*args, **kwargs):
        chamadas["promessas"] += 1
        return detectar(*args, **kwargs)

    def espiao_participacao(*args, **kwargs):
        chamadas["participacao"] += 1
        return mencoes(*args, **kwargs)

    monkeypatch.setattr(promessas, "detectar", espiao_promessas)
    monkeypatch.setattr(participacao, "mencoes_participacao", espiao_participacao)
    assert [p["padrao"] for p in metricas.detectar_promessas("Daqui a pouco tem recado.", 0, 3600, 1)] == \
        ["daqui a pouco"]
    assert metricas.detectar_promessas("Obrigado pela companhia, até amanhã.", 0, 3600, 2) == []
    as_run = {"duracao_programa_s": 600, "ouvintes": {"fixture": ["Cida Morais"], "inexistentes": []},
              "pedidos": [], "eventos": [
                  {"n": 1, "bloco_n": 1, "tipo": "fala", "texto": "Cida Morais pediu, e toca agora.",
                   "inicio_s": 0.0, "fim_s": 5.0, "pausa_antes_s": 0, "bloco": "musica", "categoria": "musica"}]}
    assert metricas.calcular_metricas(as_run)["pedido_indevido"] == 1
    assert chamadas["promessas"] >= 1 and chamadas["participacao"] >= 1
