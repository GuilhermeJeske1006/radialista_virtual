"""Relatório pós-programa (F11, item 2): montado a partir do resumo do simulador."""

import json
from pathlib import Path

from app.live.relatorio_programa import montar_relatorio

PASTA_F5 = Path(__file__).resolve().parents[2] / "docs" / "melhoria-radio" / "f5" / "simulacao"


def test_resumo_limpo_nao_gera_alerta_nem_sugestao():
    relatorio = montar_relatorio({"promessas": {"vencidas": 0}, "pedidos": {"nao_atendidos": 0, "expirados": 0}})
    assert relatorio["alertas"] == []
    assert relatorio["sugestoes"] == []


def test_resumo_vazio_nao_quebra():
    relatorio = montar_relatorio({})
    assert relatorio["secoes"]["promessas"]["vencidas"] == 0
    assert relatorio["secoes"]["pedidos"]["recebidos"] == 0


def test_problemas_viram_sugestao_e_critico_vira_alerta():
    relatorio = montar_relatorio({
        "anuncio_sem_confirmacao": 1,
        "promessas": {"vencidas": 2},
        "fora_orcamento_pct": 10.0,
        "aviso_oralidade": 3,
        "repeticao_estrutura": 1,
        "pedidos": {"nao_atendidos": 1},
        "hard_times_perdidos": 1,
    })
    assert relatorio["alertas"] == ["anúncio de música sem confirmação: 1"]
    assert len(relatorio["sugestoes"]) == 6
    assert any("10.0%" in s for s in relatorio["sugestoes"])


def test_relatorio_a_partir_de_um_resumo_real_do_simulador():
    resumo = json.loads((PASTA_F5 / "popular_sertanejo" / "resumo.json").read_text(encoding="utf-8"))
    relatorio = montar_relatorio(resumo)
    assert relatorio["secoes"]["pedidos"]["executados"] == resumo["pedidos"]["executados"]
    assert relatorio["secoes"]["promessas"]["cumpridas"] == resumo["promessas"]["cumpridas"]
    assert relatorio["alertas"] == []
