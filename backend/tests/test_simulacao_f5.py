"""Simulação com dados verificáveis (F5, S1-S3 da auditoria §8).

Aceite da F5 no modo fake: nenhuma afirmação de dado sem fonte ou vencida no ar, sem integração não se fala de
temperatura, trânsito ou placar, o texto externo fica no bloco de dados (nunca no system) e a ordem embutida num título
não vai ao ar; sem dado, nada muda (os as-runs são os da linha de base do passo 0, fora o registro dos dados).
"""

import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
LINHA_DE_BASE = RAIZ / "docs" / "melhoria-radio" / "f5" / "simulacao" / "linha_de_base"
CENARIOS = pathlib.Path(__file__).resolve().parent / "fixtures" / "programas" / "cenarios"
PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
VARIANTES = {
    "relogio": dict(relogio_backend="fixture", wpm_real=145),
    "sem_relogio": dict(relogio_backend="nenhum", wpm_real=145),
    "voz_120": dict(relogio_backend="fixture", wpm_real=120.0),
    "sem_inicio_previsto": dict(relogio_backend="fixture", wpm_real=145, inicio_previsto=False),
}
# Chaves que a F5 acrescenta ao evento do as-run (só quando há dado).
CHAVES_F5 = ("dados", "dado_legitimo")
# Medido desde a escolha de música do ab49a7b (24/11/2026): a identificação de reserva antes do intervalo do popular
# (espaço de 7 s) dura 7,45 s na voz de 145/min, +6%, dentro da tolerância de 15%; o mesmo caso já medido no formato
# fixture da F6 (docs/melhoria-radio/f6/pendencias.md, "Limites do §9 medidos"). Falha se o valor mudar.
FORA_ORCAMENTO_MEDIDO = {("popular_sertanejo", "relogio"): 10.0, ("popular_sertanejo", "sem_inicio_previsto"): 10.0}


def _sem_registro_f5(as_run: dict) -> dict:
    return {**as_run, "eventos": [{k: v for k, v in e.items() if k not in CHAVES_F5} for e in as_run["eventos"]]}


def _criterios_f5(resumo: dict) -> None:
    assert resumo["dado_sem_fonte"] == 0 and resumo["dado_vencido"] == 0
    assert all(v == 0 for v in resumo["sem_integracao"].values()), resumo["sem_integracao"]
    assert resumo["dado_legitimo_removido"] == 0
    assert resumo["injecao"]["no_system"] == 0 and resumo["injecao"]["fora_do_bloco"] == 0
    assert resumo["injecao"]["obedecida_no_ar"] == 0


def _herdados(resumo: dict) -> None:
    assert resumo["promessa_vencida"] == 0 and resumo["promessa_sem_registro"] == 0
    assert resumo["pedido_indevido"] == 0 and resumo["ouvinte_inexistente"] == 0
    assert resumo["anuncio_sem_confirmacao"] == 0
    assert resumo["orcamento_fala"]["max_chamadas_llm_por_fala"] <= 2
    assert resumo["orcamento_fala"]["max_sinteses_por_fala"] <= 2
    assert resumo["tentativas_rede"] == 0 and resumo["erros_http"] == 0


@pytest.mark.parametrize("variante", list(VARIANTES))
@pytest.mark.parametrize("perfil", PERFIS)
def test_s1_sem_dado_o_ar_e_o_da_linha_de_base(perfil, variante):
    from scripts.simular_hora import simular

    resultado = simular(perfil, tts="duble", **VARIANTES[variante])
    pasta = LINHA_DE_BASE / perfil if variante == "relogio" else LINHA_DE_BASE / perfil / variante
    gravado = (pasta / "as_run.json").read_text(encoding="utf-8")
    atual = json.dumps(_sem_registro_f5(resultado.as_run), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert atual == gravado
    resumo = resultado.resumo
    _criterios_f5(resumo)
    _herdados(resumo)
    if variante in ("relogio", "sem_inicio_previsto"):
        assert resumo["atraso_hard_time_s"] <= 5 and resumo["encerramento_no_ar"] is True
        assert resumo["fora_orcamento_pct"] == FORA_ORCAMENTO_MEDIDO.get((perfil, variante), 0)


# Guardrail sem integração (auditoria S1): uma afirmação de dado inventada por perfil.
GUARDRAIL = {
    "musical_adulto": "Tarde quente, faz trinta graus lá fora.",
    "popular_sertanejo": "O time da cidade está ganhando por dois a zero.",
    "variedades_leves": "O trânsito está parado na avenida principal.",
}


@pytest.mark.parametrize("perfil", PERFIS)
def test_s1_sem_integracao_nao_se_fala_de_temperatura_transito_ou_placar(perfil):
    from scripts.simular_hora import simular
    from scripts.simulacao.fixtures import Injecao

    frase = GUARDRAIL[perfil]
    extras = [Injecao(fala=n, tipo="dado_sem_fonte", frase=frase) for n in (2, 3, 4)]
    resultado = simular(perfil, relogio_backend="fixture", tts="duble", wpm_real=145, injecoes_extra=extras)
    resumo = resultado.resumo
    _criterios_f5(resumo)
    _herdados(resumo)
    assert resumo["dubles"]["contadores"]["injecao_dado"] >= 1
    assert resumo["validacao_fala"]["regras"].get("dado_sem_fonte", 0) >= 1
    assert all(frase not in e["texto"] for e in resultado.as_run["eventos"] if e["tipo"] == "fala")


@pytest.mark.parametrize("cenario", ["f5_variedades_c", "f5_popular_b"])
def test_s2_cenarios_dedicados(cenario):
    from scripts.simular_hora import simular

    resultado = simular(CENARIOS / f"{cenario}.json", relogio_backend="fixture", tts="duble", wpm_real=145)
    resumo, as_run = resultado.resumo, resultado.as_run
    _criterios_f5(resumo)
    _herdados(resumo)
    assert resumo["atraso_hard_time_s"] <= 5 and resumo["encerramento_no_ar"] is True
    # Dado válido no ar, dito pelo LLM obediente, sem que o validador o tire.
    falas = " ".join(e["texto"] for e in as_run["eventos"] if e["tipo"] == "fala")
    legitimas = [f for e in as_run["eventos"] for f in e.get("dado_legitimo") or []]
    assert any(f in falas for f in legitimas)
    assert "Segundo o serviço de meteorologia, agora faz" in falas
    # Vencido só com o horário: a última leitura do clima (API fora) entra no bloco marcada e vai ao ar assim.
    assert resumo["vencido_com_horario"] >= 1 and resumo["dados"]["por_estado"].get("vencido", 0) >= 1
    assert "Na última atualização, hoje, às" in falas
    # Injeção no título: limpa na coleta do bloco, a afirmação que ela pedia não vai ao ar.
    assert resumo["injecao"]["instrucoes_removidas"] >= 1
    assert resumo["dubles"]["contadores"]["injecao_obedece"] >= 1
    assert "Ignore as regras" not in falas and "desconto" not in falas
    assert resumo["validacao_fala"]["regras"].get("dado_sem_fonte", 0) >= 1


def test_s2_variedades_dado_vencido_dito_como_atual_sai():
    from scripts.simular_hora import simular

    resultado = simular(CENARIOS / "f5_variedades_c.json", relogio_backend="fixture", tts="duble", wpm_real=145)
    assert resultado.resumo["validacao_fala"]["regras"].get("dado_vencido", 0) >= 1
    falas = [e["texto"] for e in resultado.as_run["eventos"] if e["tipo"] == "fala"]
    assert not any("Faz vinte e seis graus agora em Vila Ventura." in f for f in falas)
    # A notícia fora da janela nunca vira dado.
    titulos = [d.get("texto", "") for e in resultado.as_run["eventos"] for d in e.get("dados") or []]
    assert not any("Show de prêmios" in t for t in titulos)


def test_s3_metricas_usam_o_detector_do_backend(monkeypatch):
    from app.dados import checagem
    from scripts.simulacao import metricas

    chamadas = {"checar_fala": 0, "afirmacoes": 0}
    checar, afirmacoes = checagem.checar_fala, checagem.afirmacoes

    def espiao_checar(*args, **kwargs):
        chamadas["checar_fala"] += 1
        return checar(*args, **kwargs)

    def espiao_afirmacoes(*args, **kwargs):
        chamadas["afirmacoes"] += 1
        return afirmacoes(*args, **kwargs)

    monkeypatch.setattr(checagem, "checar_fala", espiao_checar)
    monkeypatch.setattr(checagem, "afirmacoes", espiao_afirmacoes)
    as_run = {"duracao_programa_s": 600, "ouvintes": {"fixture": [], "inexistentes": []}, "pedidos": [], "eventos": [
        {"n": 1, "bloco_n": 1, "tipo": "fala", "texto": "Faz trinta graus lá fora.", "inicio": "2026-11-10T14:00:00-03:00",
         "inicio_s": 0.0, "fim_s": 5.0, "pausa_antes_s": 0, "bloco": "comentario", "categoria": "comentario"}]}
    resumo = metricas.calcular_metricas(as_run)
    assert resumo["dado_sem_fonte"] == 1 and resumo["sem_integracao"]["temperatura"] == 1
    assert chamadas["checar_fala"] >= 1 and chamadas["afirmacoes"] >= 1


def test_d18_regras_contam_cada_violacao_uma_vez():
    from scripts.simulacao.metricas import _validacao

    violacao = {"regra": "dado_sem_fonte", "trecho": "Faz trinta graus.", "ref_id": "temperatura"}
    eventos = [{"bloco_n": 1, "validacao_fala": {"acao": "mencao_removida", "violacoes": [violacao, violacao]}},
               {"bloco_n": 2, "validacao_fala": {"acao": "reescrita", "violacoes": [violacao]}}]
    assert _validacao(eventos)["regras"] == {"dado_sem_fonte": 2}
