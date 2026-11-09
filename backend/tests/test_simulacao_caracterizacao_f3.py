"""Caracterização da simulação durante a extração de gerar_proxima_fala (F3, C2 da auditoria §6).

Digest de (bloco, texto, música tocada, chamadas de LLM, ação do relógio) por evento, nos três perfis, com o
relógio da fixture e sem relógio no backend, dublê de TTS a 145 palavras/min (padrão do CLI). Vale nos passos
de extração (1 a 5), que não podem mudar nada. A F0 pede não travar o as_run de forma permanente: o passo 6
(validador) muda o comportamento de propósito e retira este teste, com registro no relatório.
Regravar: ATUALIZAR_GOLDEN=1.
"""

import hashlib
import json
import os
import pathlib

import pytest

CAMINHO = pathlib.Path(__file__).resolve().parent / "fixtures" / "caracterizacao_proxima" / "simulacao.json"
PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
RELOGIOS = ("fixture", "nenhum")


def _digest(as_run: dict) -> dict:
    linhas = [
        [e["bloco"], e["texto"], e["musica_tocada"], e["chamadas_llm"], (e.get("relogio") or {}).get("acao")]
        for e in as_run["eventos"]
    ]
    bruto = json.dumps(linhas, ensure_ascii=False, sort_keys=True)
    return {"sha256": hashlib.sha256(bruto.encode()).hexdigest(), "eventos": linhas}


def test_simulacao_caracterizacao_f3():
    from scripts.simular_hora import simular

    atual = {}
    for perfil in PERFIS:
        for relogio in RELOGIOS:
            resultado = simular(perfil, relogio_backend=relogio, tts="duble", wpm_real=145)
            atual[f"{perfil}/{relogio}"] = _digest(resultado.as_run)
    if os.environ.get("ATUALIZAR_GOLDEN") == "1":
        CAMINHO.parent.mkdir(parents=True, exist_ok=True)
        CAMINHO.write_text(json.dumps(atual, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return
    if not CAMINHO.exists():
        pytest.fail("golden da simulação ausente (rode com ATUALIZAR_GOLDEN=1)")
    esperado = json.loads(CAMINHO.read_text(encoding="utf-8"))
    for chave, digest in atual.items():
        assert digest["eventos"] == esperado[chave]["eventos"], f"simulação {chave} mudou"
