"""Cortes do as-run (F14, item 2): trechos que fazem sentido sozinhos, marcados depois de ir ao ar.

Um corte é uma sequência contígua de eventos CONFIRMADOS (ver app.live.as_run) que:
- começa e termina em fala (não em vinheta, patrocinador ou música);
- não tem evento "falhou" nem pedido de ouvinte no meio (pedido depende de contexto que não sai no corte);
- tem entre `minimo` e `maximo` eventos.
Os cortes não se sobrepõem: o primeiro válido ganha.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

MINIMO_EVENTOS = 2
MAXIMO_EVENTOS = 6


def _e_fala(evento: dict[str, Any]) -> bool:
    return evento.get("tipo") == "fala"


def _valido_no_meio(evento: dict[str, Any]) -> bool:
    return evento.get("status") == "confirmado" and not evento.get("pedido_id")


def cortes_do_as_run(eventos: Sequence[dict[str, Any]], minimo: int = MINIMO_EVENTOS,
                     maximo: int = MAXIMO_EVENTOS) -> list[dict[str, Any]]:
    ordenados = sorted(eventos, key=lambda e: e.get("ordem", 0))
    cortes: list[dict[str, Any]] = []
    i = 0
    while i < len(ordenados):
        if not (_valido_no_meio(ordenados[i]) and _e_fala(ordenados[i])):
            i += 1
            continue
        j = i
        while j + 1 < len(ordenados) and _valido_no_meio(ordenados[j + 1]) and (j - i + 1) < maximo:
            j += 1
        # recua até encontrar fala no fim do trecho
        fim = j
        while fim > i and not _e_fala(ordenados[fim]):
            fim -= 1
        tamanho = fim - i + 1
        if tamanho >= minimo and _e_fala(ordenados[fim]):
            trecho = ordenados[i:fim + 1]
            cortes.append({
                "ordem_inicio": trecho[0]["ordem"], "ordem_fim": trecho[-1]["ordem"],
                "eventos": tamanho, "tipos": [e.get("tipo") for e in trecho],
            })
            i = fim + 1
        else:
            i += 1
    return cortes
