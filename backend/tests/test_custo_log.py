import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location("custo_log", pathlib.Path(__file__).parents[1] / "scripts" / "custo_log.py")
custo_log = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(custo_log)

LOG = [
    "2026-11-27T14:55:10Z INFO:radialista.llm.custos:llm_consumo modelo=claude-opus-5 entrada=10000 saida=240 cache_write=0 cache_read=0 usd=0.056000",
    "2026-11-27T14:56:10Z INFO:radialista.llm.custos:llm_consumo modelo=claude-haiku-4-5 entrada=3700 saida=50 cache_write=0 cache_read=0 usd=0.004000",
    "2026-11-27T15:25:10Z INFO:radialista.tts:tts_consumo modelo=eleven_v4 caracteres=500 usd=0.050000",
    "linha sem consumo",
]


def test_le_llm_e_voz_e_soma_por_modelo():
    llm, tts, instantes = custo_log.ler(LOG)
    assert llm["claude-opus-5"]["usd"] == 0.056 and llm["claude-opus-5"]["entrada"] == 10000
    assert tts["eleven_v4"]["caracteres"] == 500 and len(instantes) == 3


def test_margem_bate_com_a_simulacao_do_plano():
    # docs/simulacao-plano-consumo.md: sobra = 10,91 + 0,65 C e cliente paga 69,90 + 2C
    m = custo_log.margem(1.0, 100)  # C = 100
    assert round(m["receita"], 2) == 269.90
    assert round(m["sobra"], 2) == round(10.91 + 0.65 * 100, 2)


def test_saida_resume_custo_por_hora(capsys):
    assert custo_log.main(["--horas", "0.5"], entrada=LOG) == 0
    saida = capsys.readouterr().out
    assert "Custo por hora de programa: US$ 0.22" in saida and "margem" in saida
