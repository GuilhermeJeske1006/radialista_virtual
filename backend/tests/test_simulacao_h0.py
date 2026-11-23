"""Simulação com sinais de IA injetados (H0; docs/humanizacao/h0/auditoria.md §5.4 e §6, itens 7, 8 e 10).

O banco do dublê não tem nenhum sinal (fato 3 da auditoria): sem injeção, a linha de base fake fica em zero por
construção. O cenário `h0_popular_sinais` é o popular_sertanejo com três vazamentos, um sinal denso e o slogan em três
falas dentro de 30 minutos, todos copiados do corpus. Os detectores ainda não existem (H1, H4, H5): os testes usam
dublês no lugar deles e conferem consistência, não um número fixo, para continuarem válidos depois da H1.
"""

import importlib.util
import json
import pathlib
import sys
import types

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
CENARIO = BACKEND / "tests" / "fixtures" / "programas" / "cenarios" / "h0_popular_sinais.json"
BASE = BACKEND / "tests" / "fixtures" / "programas" / "popular_sertanejo.json"
CORPUS = BACKEND / "tests" / "fixtures" / "humanizacao" / "corpus.json"
TIPOS_H0 = ("vazamento", "sinal_ia", "bordao")
CHAVES_HUMANIZACAO = ("vazamento_grave", "sinais_ia_media", "sinais_ia_p90", "bordao_repetido")
# As-run mínimo para o recálculo: duas falas com texto, uma vazia e uma música.
AS_RUN_CURTO = {"programa": "artificial", "duracao_programa_s": 600, "eventos": [
    {"n": 1, "tipo": "fala", "inicio_s": 0.0, "texto": "Você ouve a Rádio Serra Clara nesta tarde."},
    {"n": 2, "tipo": "musica", "inicio_s": 10.0, "texto": ""},
    {"n": 3, "tipo": "fala", "inicio_s": 200.0, "texto": ""},
    {"n": 4, "tipo": "fala", "inicio_s": 210.0, "texto": "Obrigado pela companhia nesta tarde."},
]}
# Até a H1 nenhum validador tira um vazamento (o módulo não existe); depois dela, a frase pode sair do ar.
SEM_H1 = importlib.util.find_spec("app.live.sinais_ia") is None


def _ler(caminho: pathlib.Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _injecoes(tipo: str) -> list[dict]:
    return [i for i in _ler(CENARIO)["injecoes"] if i["tipo"] == tipo]


@pytest.fixture(scope="module")
def rodada_cenario():
    """O cenário com os padrões do CLI (relógio da fixture, dublê de TTS a 145 wpm, --formato fixture), sem dublê de
    detector: até a H1, as métricas novas valem None."""
    from scripts.simular_hora import simular

    return simular(CENARIO, relogio_backend="fixture", tts="duble", wpm_real=145, formato="fixture")


def _falas(as_run: dict) -> list[str]:
    return [e["texto"] for e in as_run["eventos"] if e["tipo"] == "fala"]


def test_cenario_e_o_popular_com_outras_injecoes():
    from scripts.simulacao.fixtures import FixturePrograma

    cenario, base = _ler(CENARIO), _ler(BASE)
    assert {k: v for k, v in cenario.items() if k not in ("id", "descricao", "injecoes")} == {
        k: v for k, v in base.items() if k not in ("id", "descricao", "injecoes")}
    assert cenario["id"] == CENARIO.stem
    FixturePrograma.model_validate(cenario)
    # As injeções da linha de base continuam; as da H0 se somam a elas.
    assert all(i in cenario["injecoes"] for i in base["injecoes"])
    assert {i["tipo"] for i in cenario["injecoes"]} >= set(TIPOS_H0)
    assert len(_injecoes("vazamento")) == 3


def test_frases_injetadas_vem_do_corpus():
    corpus = _ler(CORPUS)
    por_grupo = {}
    for texto in corpus["textos"]:
        por_grupo.setdefault(texto["grupo"], {})[texto["texto"]] = texto
    for injecao in _injecoes("vazamento"):
        assert injecao["frase"] in por_grupo["vazamento"], injecao
    categorias = {c for i in _injecoes("vazamento") for c in por_grupo["vazamento"][i["frase"]]["categorias"]}
    assert {"recusa", "identidade_ia", "markdown"} <= categorias
    (sinal,) = _injecoes("sinal_ia")
    assert por_grupo["sinal"][sinal["frase"]]["esperado"]["acima_do_limite"] is True
    slogan = _ler(BASE)["conta"]["slogan"]
    bordoes = {b for s in corpus["sequencias"] for b in s["bordoes"]}
    for injecao in _injecoes("bordao"):
        assert injecao["frase"].rstrip(".") == slogan and slogan in bordoes


def test_slogan_em_tres_falas_dentro_de_trinta_minutos(rodada_cenario):
    slogan = _ler(BASE)["conta"]["slogan"]
    inicios = [e["inicio_s"] for e in rodada_cenario.as_run["eventos"] if e["tipo"] == "fala" and slogan in e["texto"]]
    assert len(inicios) >= 3
    assert inicios[2] - inicios[0] < 1800


def test_cenario_sem_detector_mantem_os_criterios_herdados(rodada_cenario):
    resumo = rodada_cenario.resumo
    contadores = resumo["dubles"]["contadores"]
    for tipo in TIPOS_H0:
        assert contadores.get(f"injecao_{tipo}", 0) >= 1, tipo
    assert resumo["orcamento_fala"]["max_chamadas_llm_por_fala"] <= 2
    assert (resumo["anuncio_sem_confirmacao"], resumo["promessa_vencida"], resumo["pedido_indevido"]) == (0, 0, 0)
    assert resumo["tentativas_rede"] == 0 and resumo["erros_http"] == 0
    if SEM_H1:
        assert resumo["vazamento_grave"] is None


@pytest.mark.skipif(not SEM_H1, reason="depois da H1 o validador tira o vazamento antes do ar")
def test_antes_da_h1_os_vazamentos_vao_ao_ar(rodada_cenario):
    """Nenhum validador da F3 à F6 tira as frases injetadas (auditoria §5.4): a lacuna que a H1 fecha é visível."""
    falas = _falas(rodada_cenario.as_run)
    for injecao in _injecoes("vazamento") + _injecoes("sinal_ia"):
        assert any(injecao["frase"] in texto for texto in falas), injecao["frase"]


def test_cenario_com_detector_duble(monkeypatch):
    from app.live import memoria
    from scripts.simular_hora import simular

    frases = [i["frase"] for i in _injecoes("vazamento")]
    modulo = types.ModuleType("app.live.sinais_ia")
    modulo.vazamentos = lambda texto: [f for f in frases if f in texto]
    modulo.pontuar = lambda texto: types.SimpleNamespace(nota=float(len(texto.split())), violacoes=[])
    chamadas = []

    def bordoes_repetidos(falas, bordoes, *, janela_s, maximo):
        chamadas.append(bordoes)
        return sum(1 for _, texto in falas if any(b in texto for b in bordoes))

    monkeypatch.setitem(sys.modules, "app.live.sinais_ia", modulo)
    monkeypatch.setattr(memoria, "bordoes_repetidos", bordoes_repetidos, raising=False)
    resultado = simular(CENARIO, relogio_backend="fixture", tts="duble", wpm_real=145, formato="fixture")
    resumo, falas = resultado.resumo, [t for t in _falas(resultado.as_run) if t.strip()]
    assert resumo["vazamento_grave"] == sum(1 for texto in falas if any(f in texto for f in frases))
    assert resumo["sinais_ia_falas"] == len(falas)
    assert resumo["sinais_ia_media"] == round(sum(len(t.split()) for t in falas) / len(falas), 1)
    assert resumo["sinais_ia_p90"] is not None and resumo["sinais_ia_p90"] >= resumo["sinais_ia_media"]
    # O bordão do simulador antes da H8 é o slogan da conta (DH0-3).
    assert chamadas == [[_ler(CENARIO)["conta"]["slogan"]]]
    assert resumo["bordao_repetido"] == sum(1 for t in falas if _ler(CENARIO)["conta"]["slogan"] in t)


def test_recalcular_humanizacao_sobre_as_run_gravado(tmp_path, monkeypatch, capsys):
    from scripts import recalcular_humanizacao
    from scripts.simulacao import ambiente

    monkeypatch.setattr(ambiente, "preparar_processo", lambda modo: None)  # o conftest já preparou o processo
    monkeypatch.setitem(sys.modules, "app.live.sinais_ia", None)
    arquivo = tmp_path / "as_run.json"
    arquivo.write_text(json.dumps(AS_RUN_CURTO, ensure_ascii=False), encoding="utf-8")
    saida = tmp_path / "humanizacao.json"
    assert recalcular_humanizacao.main(["--as-run", str(arquivo), "--slogan", "Rádio Serra Clara",
                                        "--saida", str(saida)]) == 0
    gravado = json.loads(saida.read_text(encoding="utf-8"))
    impresso = json.loads(capsys.readouterr().out)
    assert gravado == impresso
    for chave in CHAVES_HUMANIZACAO:
        assert chave in gravado and gravado[chave] is None, chave
    assert gravado["sinais_ia_falas"] == 2 and gravado["bordoes"] == ["Rádio Serra Clara"]
    assert gravado["as_run"] == str(arquivo)


def test_recalcular_usa_o_slogan_da_fixture_e_recusa_arquivo_ausente(tmp_path, monkeypatch, capsys):
    from scripts import recalcular_humanizacao
    from scripts.simulacao import ambiente

    monkeypatch.setattr(ambiente, "preparar_processo", lambda modo: None)
    as_run = {"programa": "h0_popular_sinais", "eventos": [
        {"n": 1, "tipo": "fala", "inicio_s": 0.0, "texto": "A viola que acompanha o seu dia."}]}
    arquivo = tmp_path / "as_run.json"
    arquivo.write_text(json.dumps(as_run, ensure_ascii=False), encoding="utf-8")
    assert recalcular_humanizacao.main(["--as-run", str(arquivo)]) == 0
    assert json.loads(capsys.readouterr().out)["bordoes"] == [_ler(CENARIO)["conta"]["slogan"]]
    assert recalcular_humanizacao.main(["--as-run", str(tmp_path / "nao_existe.json")]) == 2
