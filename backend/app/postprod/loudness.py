"""Loudness integrada por segmento (F10, item 3 da melhoria de rádio): fala, vinheta e música.

Mede com o filtro `ebur128` do ffmpeg (EBU R128, LUFS integrado). Sem alvo universal: o relatório mostra a diferença
entre segmentos, e cada destino decide o próprio alvo (configuração, não constante).
"""

from __future__ import annotations

import re
import shutil
import subprocess

_INTEGRADA_RE = re.compile(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS")


def medir_loudness_lufs(caminho: str, timeout_s: int = 120) -> float | None:
    """Loudness integrada do arquivo em LUFS, ou None quando o ffmpeg não está disponível ou não devolveu o resumo."""
    if shutil.which("ffmpeg") is None:
        return None
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", caminho, "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, timeout=timeout_s, check=False,
    )
    achados = _INTEGRADA_RE.findall(proc.stderr or "")
    return float(achados[-1]) if achados else None


def diferencas_entre_segmentos(medidos: dict[str, float | None]) -> dict[str, float]:
    """Diferença (dB) de cada segmento para o de referência: a fala, quando medida. Segmentos sem medida ficam de fora.
    Ex.: {"fala": -18.0, "musica": -14.0} -> {"musica": 4.0} (música 4 dB acima da fala)."""
    referencia = medidos.get("fala")
    if referencia is None:
        return {}
    return {
        segmento: round(valor - referencia, 2)
        for segmento, valor in medidos.items()
        if segmento != "fala" and valor is not None
    }
