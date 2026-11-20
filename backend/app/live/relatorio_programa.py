"""Relatório pós-programa (F11, item 2 da melhoria de rádio).

Função pura sobre o `resumo` de um programa (o mesmo dicionário que o simulador grava e que o as-run persistente
vai alimentar). Não lê banco nem rede. Ausente = zero: um resumo antigo não derruba o relatório.
"""

from __future__ import annotations


def _n(valor, padrao=0):
    return padrao if valor is None else valor


def montar_relatorio(resumo: dict) -> dict:
    promessas = resumo.get("promessas") or {}
    pedidos = resumo.get("pedidos") or {}

    secoes = {
        "promessas": {
            "cumpridas": _n(promessas.get("cumpridas")),
            "vencidas": _n(promessas.get("vencidas")),
            "canceladas_com_contingencia": _n(promessas.get("canceladas_com_contingencia")),
            "abertas_no_fim": _n(promessas.get("abertas_no_fim")),
        },
        "orcamento": {
            "fora_pct": _n(resumo.get("fora_orcamento_pct"), 0.0),
            "estouro_max_pct": _n(resumo.get("estouro_max_pct"), 0.0),
            "falas_abaixo_minimo": _n(resumo.get("falas_abaixo_minimo")),
        },
        "oralidade": {"avisos": _n(resumo.get("aviso_oralidade"))},
        "pedidos": {
            "recebidos": _n(pedidos.get("recebidos")),
            "executados": _n(pedidos.get("executados")),
            "nao_atendidos": _n(pedidos.get("nao_atendidos")),
            "expirados": _n(pedidos.get("expirados")),
            "pendentes_fim": _n(pedidos.get("pendentes_fim")),
        },
        "repeticao": {"estrutura": _n(resumo.get("repeticao_estrutura"))},
        "hard_time": {"perdidos": _n(resumo.get("hard_times_perdidos"))},
    }

    alertas = []
    for chave, rotulo in (
        ("anuncio_sem_confirmacao", "anúncio de música sem confirmação"),
        ("pedido_indevido", "pedido indevido no ar"),
        ("dado_sem_fonte", "dado sem fonte no ar"),
        ("promessa_vencida", "promessa vencida"),
    ):
        if _n(resumo.get(chave)) > 0:
            alertas.append(f"{rotulo}: {resumo[chave]}")

    sugestoes = []
    if secoes["promessas"]["vencidas"] > 0:
        sugestoes.append("Cumprir ou dar contingência às promessas antes da hora marcada.")
    if secoes["orcamento"]["fora_pct"] > 0:
        sugestoes.append(f"Ajustar o relógio: {secoes['orcamento']['fora_pct']}% das falas passaram do orçamento.")
    if secoes["oralidade"]["avisos"] > 0:
        sugestoes.append(f"Revisar frases longas, siglas e números ({secoes['oralidade']['avisos']} avisos de oralidade).")
    if secoes["repeticao"]["estrutura"] > 0:
        sugestoes.append(f"Variar as aberturas: {secoes['repeticao']['estrutura']} janelas com a mesma construção.")
    if secoes["pedidos"]["nao_atendidos"] > 0 or secoes["pedidos"]["expirados"] > 0:
        sugestoes.append("Revisar a fila de pedidos: há pedidos sem atendimento ou expirados.")
    if secoes["hard_time"]["perdidos"] > 0:
        sugestoes.append(f"Encurtar a fala antes do hard time: {secoes['hard_time']['perdidos']} eventos perdidos.")

    return {"secoes": secoes, "alertas": alertas, "sugestoes": sugestoes}
