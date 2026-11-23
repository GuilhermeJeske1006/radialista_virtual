"""Simulação com o catálogo de formatos (F6, S1-S6 da auditoria §8; §6.14, §9, D19, D20 e D21).

- `--formato programa` (padrão) reproduz a F5 byte a byte: as fixtures de linha de base ficam intocadas (D19).
- `--formato fixture` aplica o campo `formato` da fixture em `programa.perfil_programacao`: as rodadas da F6 em diante.
- `resumo.json["formato"]` vem de `app.live.formatos.coerencia` (o simulador não tem detector próprio) e do canal
  lateral do dublê (a direção do formato estava no prompt de cada bloco de fala?). No modo fake o texto é do banco do
  dublê (fato 7): a coerência automática mede o que o backend decide (D20).
"""

import functools
import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
F5 = RAIZ / "docs" / "melhoria-radio" / "f5" / "simulacao"
# Desde a direção de energia (301717d) o formato programa dá tom próprio em musical e popular (um evento muda de
# "calmo" para "energico"). Essas gravações ficam separadas; a F5 e o formato fixture não mudam.
F6_PROGRAMA = RAIZ / "docs" / "melhoria-radio" / "f6" / "simulacao" / "programa"
TOM_PROPRIO_PROGRAMA = {"musical_adulto", "popular_sertanejo"}
PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
VARIANTES = {
    "relogio": dict(relogio_backend="fixture", wpm_real=145),
    "sem_relogio": dict(relogio_backend="nenhum", wpm_real=145),
    "voz_120": dict(relogio_backend="fixture", wpm_real=120.0),
    "sem_inicio_previsto": dict(relogio_backend="fixture", wpm_real=145, inicio_previsto=False),
}
COM_RELOGIO = ("relogio", "sem_inicio_previsto")


def _json(dados: dict) -> str:
    return json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@functools.lru_cache(maxsize=None)
def _rodar(perfil: str, variante: str, formato: str = "fixture"):
    from scripts.simular_hora import simular

    return simular(perfil, tts="duble", formato=formato, **VARIANTES[variante])


# ---------------------------------------------------------------------------------------------------------
# S1 (= C6): --formato programa é a F5
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("variante", list(VARIANTES))
@pytest.mark.parametrize("perfil", PERFIS)
def test_s1_formato_programa_e_a_f5_byte_a_byte(perfil, variante):
    resultado = _rodar(perfil, variante, "programa")
    base = F6_PROGRAMA if perfil in TOM_PROPRIO_PROGRAMA else F5
    pasta = base / perfil if variante == "relogio" else base / perfil / variante
    assert _json(resultado.as_run) == (pasta / "as_run.json").read_text(encoding="utf-8")
    assert resultado.resumo["config"]["formato"] == "programa"
    esperado = "musical_adulto" if perfil == "musical_adulto" else "padrao"
    assert resultado.resumo["formato"]["id"] == esperado


def test_s1_simular_sem_formato_e_o_programa():
    from scripts.simular_hora import simular

    padrao = simular("popular_sertanejo", tts="duble", **VARIANTES["sem_relogio"])
    assert _json(padrao.as_run) == _json(_rodar("popular_sertanejo", "sem_relogio", "programa").as_run)


def test_s1_formato_invalido_e_recusado():
    from scripts.simular_hora import simular

    for valor in ("hits", "inexistente"):
        with pytest.raises(ValueError, match="formato"):
            simular("popular_sertanejo", formato=valor)


# ---------------------------------------------------------------------------------------------------------
# S2: --formato fixture, critérios herdados e coerência do §9
# ---------------------------------------------------------------------------------------------------------

# Primeira rodada da F6 (calibração, auditoria §9, primeira linha): itens do §9, e o herdado fora_orcamento_pct, que
# não fecharam no modo fake, com o valor medido (PYTHONHASHSEED=0, semente 7). Valor e hipótese em
# docs/melhoria-radio/f6/pendencias.md, "Limites do §9 medidos na primeira rodada"; nada foi afrouxado. O teste falha
# se o conjunto de itens fora do limite ou o valor medido mudar (para pior ou para melhor).
MEDIDO_FORA_DO_LIMITE = {
    # dublê: abre com o banco da retomada (conta a vinheta como fala) e a retomada do banco sai com 4 s
    ("musical_adulto", "relogio"): {"falas_fora_da_unidade_pct": 16.7},
    ("musical_adulto", "sem_relogio"): {"falas_fora_da_unidade_pct": 12.5},
    ("musical_adulto", "sem_inicio_previsto"): {"falas_fora_da_unidade_pct": 16.7},
    # identificação de reserva com 7 s pelo espaço e voz a 145 palavras/min antes da calibração: 7,45 s (+6%, dentro
    # da tolerância de 15%; sem reescrita)
    ("popular_sertanejo", "relogio"): {"fora_orcamento_pct": 10.0},
    ("popular_sertanejo", "sem_inicio_previsto"): {"fora_orcamento_pct": 10.0},
    # dublê: a chamada do retorno não diz o nome (ignora a linha de reorientação do prompt)
    ("popular_sertanejo", "voz_120"): {"maior_intervalo_sem_reorientacao_s": 3052.05},
    # dublê: o banco do quadro tem uma frase de convite ("pode contar pelo WhatsApp") e não diz o nome do programa
    ("variedades_leves", "relogio"): {"convites_fora_da_politica": 2, "maior_intervalo_sem_reorientacao_s": 3466.5},
    ("variedades_leves", "sem_relogio"): {"convites_fora_da_politica": 3},
    ("variedades_leves", "voz_120"): {"convites_fora_da_politica": 3, "maior_intervalo_sem_reorientacao_s": 3471.85},
    ("variedades_leves", "sem_inicio_previsto"): {"convites_fora_da_politica": 2,
                                                  "maior_intervalo_sem_reorientacao_s": 3466.5},
}
ITEM_DA_METRICA = {"falas_fora_da_unidade_pct": "falas_fora_da_unidade", "convites_fora_da_politica":
                   "convites_fora_da_politica", "maior_intervalo_sem_reorientacao_s": "reorientacao"}


def _herdados(resumo: dict, variante: str, medido: dict) -> None:
    assert resumo["tentativas_rede"] == 0 and resumo["erros_http"] == 0
    assert resumo["anuncio_sem_confirmacao"] == 0
    assert resumo["promessa_vencida"] == 0 and resumo["promessa_sem_registro"] == 0
    assert resumo["pedido_indevido"] == 0 and resumo["ouvinte_inexistente"] == 0
    assert resumo["dado_sem_fonte"] == 0 and resumo["dado_vencido"] == 0
    assert resumo["orcamento_fala"]["max_chamadas_llm_por_fala"] <= 2
    assert resumo["orcamento_fala"]["max_sinteses_por_fala"] <= 1
    if variante in COM_RELOGIO:
        assert resumo["fora_orcamento_pct"] == medido.get("fora_orcamento_pct", 0)
        assert resumo["atraso_hard_time_s"] <= 5 and resumo["encerramento_no_ar"] is True


@pytest.mark.parametrize("variante", list(VARIANTES))
@pytest.mark.parametrize("perfil", PERFIS)
def test_s2_formato_da_fixture_herdados_e_coerencia(perfil, variante):
    resultado = _rodar(perfil, variante)
    resumo, medido = resultado.resumo, MEDIDO_FORA_DO_LIMITE.get((perfil, variante), {})
    assert resumo["config"]["formato"] == "fixture" and resumo["config"]["perfil_programacao"] == perfil
    assert resumo["formato"]["id"] == perfil
    _herdados(resumo, variante, medido)
    formato = resumo["formato"]
    assert formato["instrucao_no_prompt_pct"] == 100 and formato["instrucao_de_outro_formato"] == 0
    assert formato["temas_revisao_no_ar"] == 0 and formato["blocos_fora_do_formato"] == 0
    fora = {item for item, ok in formato["itens"].items() if not ok}
    assert fora == {ITEM_DA_METRICA[m] for m in medido if m in ITEM_DA_METRICA}, formato["itens"]
    for metrica, valor in medido.items():
        assert formato.get(metrica, resumo.get(metrica)) == valor, metrica
    assert formato["coerencia_automatica"] is (not fora)


def test_s2_o_que_fecha_nos_tres_perfis():
    """O que fecha em todas as 12 rodadas: direção do formato no prompt, nenhum tema de revisão nem bloco fora do
    formato, fala dentro da faixa do formato e, no musical, a sequência musical e as interrupções."""
    for perfil in PERFIS:
        for variante in VARIANTES:
            itens = _rodar(perfil, variante).resumo["formato"]["itens"]
            for item in ("instrucao_no_prompt", "instrucao_de_outro_formato", "fala_pct", "blocos_fora_do_formato",
                         "temas_revisao_no_ar", "maior_sequencia_musical", "interrupcoes_por_hora"):
                assert itens.get(item, True) is True, (perfil, variante, item)


def test_s2_cli_com_formato_fixture(tmp_path):
    import os
    import subprocess
    import sys

    backend = pathlib.Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(backend), "PYTHONHASHSEED": "0",
           "ANTHROPIC_API_KEY": "chave-falsa-do-teste", "ELEVENLABS_API_KEY": ""}

    def cli(*args):
        return subprocess.run([sys.executable, "scripts/simular_hora.py", "--programa", "popular_sertanejo",
                               "--saida", str(tmp_path / "saida"), *args], cwd=backend, env=env, capture_output=True,
                              text=True, timeout=120)

    processo = cli("--formato", "fixture")
    assert processo.returncode == 0, processo.stderr[-2000:]
    assert "formato=popular_sertanejo" in processo.stdout
    resumo = json.loads((tmp_path / "saida" / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["config"]["formato"] == "fixture" and resumo["formato"]["id"] == "popular_sertanejo"
    assert cli("--formato", "hits").returncode == 2


# ---------------------------------------------------------------------------------------------------------
# S3: alias de verdade
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("variante", ["relogio", "sem_relogio"])
def test_s3_alias_e_canonico_dao_o_mesmo_as_run(variante):
    canonico = _rodar("musical_adulto", variante, "musical_adulto")
    alias = _rodar("musical_adulto", variante, "musical_companhia")
    assert _json(canonico.as_run) == _json(alias.as_run)
    assert canonico.resumo["formato"] == alias.resumo["formato"]
    assert _json(canonico.as_run) == _json(_rodar("musical_adulto", variante).as_run)  # fixture = musical_adulto


# ---------------------------------------------------------------------------------------------------------
# S4: os três formatos são distintos no ar
# ---------------------------------------------------------------------------------------------------------

def _relogio_efetivo(as_run: dict) -> tuple:
    vistos, sequencia = set(), []
    for evento in as_run["eventos"]:
        relogio = evento.get("relogio")
        if not relogio or evento["bloco_n"] in vistos:
            continue
        vistos.add(evento["bloco_n"])
        sequencia.append((relogio["etapa"]["tipo"], evento["bloco"], tuple(relogio.get("orcamento_s") or ())))
    return tuple(sequencia)


def _orcamentos(as_run: dict) -> set:
    return {(e["categoria"], e["orcamento_s"]["min"], e["orcamento_s"]["max"])
            for e in as_run["eventos"] if e["tipo"] == "fala" and e.get("orcamento_s")}


def test_s4_instrucao_no_prompt_relogio_efetivo_e_orcamentos_distintos():
    resultados = {perfil: _rodar(perfil, "relogio") for perfil in PERFIS}
    for perfil, resultado in resultados.items():
        assert resultado.resumo["formato"]["instrucao_no_prompt_pct"] == 100, perfil
        assert resultado.resumo["formato"]["relogio_padrao"] == resultado.as_run["relogio"]["id"]
    for i, primeiro in enumerate(PERFIS):
        for segundo in PERFIS[i + 1:]:
            assert _relogio_efetivo(resultados[primeiro].as_run) != _relogio_efetivo(resultados[segundo].as_run)
            assert _orcamentos(resultados[primeiro].as_run) != _orcamentos(resultados[segundo].as_run)
    sem_relogio = {perfil: _orcamentos(_rodar(perfil, "sem_relogio").as_run) for perfil in PERFIS}
    assert len({frozenset(v) for v in sem_relogio.values()}) == 3


def test_s4_padrao_sem_instrucao_de_formato():
    formato = _rodar("popular_sertanejo", "relogio", "programa").resumo["formato"]
    assert formato["id"] == "padrao" and formato["instrucao_no_prompt_pct"] == 0
    assert formato["instrucao_de_outro_formato"] == 0


# ---------------------------------------------------------------------------------------------------------
# S5: metricas sem detector próprio (espião)
# ---------------------------------------------------------------------------------------------------------

def test_s5_metricas_delegam_a_coerencia_do_backend(monkeypatch):
    from app.live import formatos
    from scripts.simulacao import metricas

    chamadas = []
    original = formatos.coerencia

    def espiao(*args, **kwargs):
        chamadas.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(formatos, "coerencia", espiao)
    as_run = {"duracao_programa_s": 3600, "eventos": [
        {"n": 1, "bloco_n": 1, "tipo": "fala", "bloco": "retomada", "categoria": "abertura", "inicio_s": 0.0,
         "fim_s": 30.0, "duracao_prevista_s": 30.0, "duracao_medida_s": None, "orcamento_s": None, "relogio": None,
         "texto": "Mande sua mensagem pelo WhatsApp da rádio."},
        {"n": 2, "bloco_n": 2, "tipo": "musica", "bloco": "musica", "categoria": "musica", "inicio_s": 30.0,
         "fim_s": 230.0, "texto": ""},
    ]}
    resumo = metricas.metricas_formato(as_run, formato="musical_adulto", nomes=("Tarde Serena", "Rádio Serra Clara"),
                                       instrucao={"blocos": 1, "com_formato": 1, "com_outro": 0})
    assert len(chamadas) == 1
    falas = chamadas[0][0][1]
    assert [f.texto for f in falas] == ["Mande sua mensagem pelo WhatsApp da rádio."]
    assert resumo["convites_fora_da_politica"] == 1 and resumo["falas_fora_da_unidade"] == 1
    assert resumo["id"] == "musical_adulto" and resumo["relogio_padrao"] == "A"

    # Sem a função do backend, a métrica não tem como sair: nada é recalculado aqui.
    sentinela = original("padrao", [], duracao_programa_s=3600)
    monkeypatch.setattr(formatos, "coerencia", lambda *a, **k: sentinela)
    assert metricas.metricas_formato(as_run, formato="musical_adulto")["coerencia_automatica"] is True
    assert metricas.metricas_formato(as_run, formato="musical_adulto")["avisos"] == []


# ---------------------------------------------------------------------------------------------------------
# S6: injeções detectadas e nada removido (D21)
# ---------------------------------------------------------------------------------------------------------

CONVITE = "Mande sua mensagem pelo WhatsApp da rádio."
TEMA = "Quem toma remédio para pressão deve conversar com o médico antes de mudar a dose."


def _falas(as_run: dict) -> list[str]:
    return [e["texto"] for e in as_run["eventos"] if e["tipo"] == "fala"]


def test_s6_debate_longo_no_musical():
    from scripts.simular_hora import simular
    from scripts.simulacao.fixtures import Injecao

    resultado = simular("musical_adulto", tts="duble", formato="fixture", relogio_backend="fixture", wpm_real=145,
                        injecoes_extra=[Injecao(fala=4, tipo="debate_longo", segundos=90)])
    formato = resultado.resumo["formato"]
    assert resultado.resumo["dubles"]["contadores"]["injecao_debate_longo"] >= 1
    assert formato["falas_fora_da_unidade"] >= 1 and formato["avisos_por_codigo"]["fora_da_unidade"] >= 1
    longas = [e for e in resultado.as_run["eventos"] if e["tipo"] == "fala" and e["duracao_medida_s"]
              and e["duracao_medida_s"] > 60]
    assert longas, "a fala longa foi ao ar inteira (coerência não corta)"


def test_s6_convite_numa_retomada_do_musical():
    from scripts.simular_hora import simular
    from scripts.simulacao.fixtures import Injecao

    resultado = simular("musical_adulto", tts="duble", formato="fixture", relogio_backend="fixture", wpm_real=145,
                        injecoes_extra=[Injecao(fala=n, tipo="convite", frase=CONVITE) for n in (2, 4)])
    formato = resultado.resumo["formato"]
    assert resultado.resumo["dubles"]["contadores"]["injecao_convite"] >= 1
    assert formato["convites_fora_da_politica"] >= 1 and formato["coerencia_automatica"] is False
    assert any(CONVITE in texto for texto in _falas(resultado.as_run))  # nada removido


def test_s6_tema_de_revisao_no_popular():
    from scripts.simular_hora import simular
    from scripts.simulacao.fixtures import Injecao

    resultado = simular("popular_sertanejo", tts="duble", formato="fixture", relogio_backend="fixture", wpm_real=145,
                        injecoes_extra=[Injecao(fala=3, tipo="tema_revisao", frase=TEMA)])
    formato = resultado.resumo["formato"]
    assert resultado.resumo["dubles"]["contadores"]["injecao_tema_revisao"] >= 1
    assert formato["temas_revisao_no_ar"] >= 1 and formato["itens"]["temas_revisao_no_ar"] is False
    assert any(TEMA in texto for texto in _falas(resultado.as_run))
