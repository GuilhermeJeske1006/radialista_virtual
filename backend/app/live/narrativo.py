"""Quadro narrativo (F14, item 1): história curta em quatro passos, no quadro fixo do programa.

O narrativo NÃO é categoria nova: é um quadro fixo (`Programa.quadros_fixos`) cujo label começa com "narrativo"
ou "historia" (sem acento, sem diferença de caixa). O conteúdo do pool é a semente da história de hoje; a estrutura
personagem -> situação -> mudança -> consequência entra na instrução do bloco.
"""

from __future__ import annotations

import unicodedata

PREFIXOS_NARRATIVOS = ("narrativo", "historia")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").casefold()


def eh_quadro_narrativo(tipo: str | None) -> bool:
    return bool(tipo) and _sem_acento(tipo.strip()).startswith(PREFIXOS_NARRATIVOS)


def instrucao_narrativa() -> str:
    return (
        "Conte o quadro como uma história curta em quatro passos, nesta ordem: personagem (quem é, em uma frase), "
        "situação (onde está e o que acontece), mudança (o que muda na situação) e consequência (o que isso deixa "
        "para quem ouve). Feche na consequência. Não invente fato sobre pessoa real."
    )
