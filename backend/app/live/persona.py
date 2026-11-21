"""Persona do programa (F7 da melhoria de rádio): o jeito da rádio, não uma pessoa.

Cinco escalas de 1 a 5 (proximidade, formalidade, energia, humor, ritmo) e até cinco exemplos aprovados de fala. Sem
persona gravada (nulo), nenhuma linha vai ao prompt: o comportamento de hoje fica intacto.

A regra de não imitar apresentador real vale para o texto que o operador escreve (aviso no painel) e é repetida no
prompt. O código não consegue detectar imitação; a responsabilidade é do operador e da revisão.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger("radialista.live")

MAX_EXEMPLOS = 5
MAX_CARACTERES_EXEMPLO = 280

# Texto por faixa da escala: 1-2 baixa, 3 média, 4-5 alta.
DESCRICOES: dict[str, tuple[str, str, str]] = {
    "proximidade": (
        "distante e respeitoso, sem intimidade",
        "cordial, sem intimidade excessiva",
        "próximo, como quem conversa com um conhecido",
    ),
    "formalidade": (
        "informal, com linguagem de rua e gíria leve de rádio",
        "linguagem comum, nem formal nem gíria",
        "formal, sem gíria nem expressão coloquial",
    ),
    "energia": (
        "calmo, voz baixa de fim de noite",
        "animado na medida",
        "vibrante, com frases de impacto",
    ),
    "humor": (
        "sério, sem brincadeira",
        "humor leve e ocasional",
        "bem-humorado, com graça quando couber",
    ),
    "ritmo": (
        "frases longas e pausadas",
        "ritmo normal de conversa",
        "frases curtas e rápidas",
    ),
}


def _faixa(valor: int) -> int:
    return 0 if valor <= 2 else (1 if valor == 3 else 2)


class Persona(BaseModel):
    proximidade: int = Field(default=3, ge=1, le=5)
    formalidade: int = Field(default=3, ge=1, le=5)
    energia: int = Field(default=3, ge=1, le=5)
    humor: int = Field(default=3, ge=1, le=5)
    ritmo: int = Field(default=3, ge=1, le=5)
    exemplos: list[str] = Field(default_factory=list)

    @field_validator("exemplos")
    @classmethod
    def _exemplos_limpos(cls, valores: list[str]) -> list[str]:
        limpos = [v.strip() for v in valores if v and v.strip()]
        if len(limpos) > MAX_EXEMPLOS:
            raise ValueError(f"no máximo {MAX_EXEMPLOS} exemplos de fala")
        for valor in limpos:
            if len(valor) > MAX_CARACTERES_EXEMPLO:
                raise ValueError(f"exemplo com mais de {MAX_CARACTERES_EXEMPLO} caracteres")
        return limpos


def persona_ou_none(valor: Any) -> Persona | None:
    """Lê a persona gravada. Nulo, vazio ou inválido vira None (com log): a leitura nunca derruba o ao vivo."""
    if valor is None or valor == {}:
        return None
    if isinstance(valor, Persona):
        return valor
    try:
        return Persona.model_validate(valor)
    except ValidationError:
        log.warning("persona_invalida_ignorada")
        return None


def linhas_da_persona(valor: Any) -> list[str]:
    """Linhas do system para a persona. Lista vazia quando não há persona."""
    persona = persona_ou_none(valor)
    if persona is None:
        return []
    linhas = ["Persona da rádio (o jeito de falar da emissora, não uma pessoa):"]
    for escala in ("proximidade", "formalidade", "energia", "humor", "ritmo"):
        nivel = getattr(persona, escala)
        texto = DESCRICOES[escala][_faixa(nivel)]
        linhas.append(f"- {escala} {nivel}/5: {texto}.")
    if persona.exemplos:
        linhas.append("Exemplos de fala aprovados (referência de tom; não copie palavra por palavra):")
        linhas.extend(f"- {exemplo}" for exemplo in persona.exemplos)
    linhas.append(
        "Não imite nem cite apresentador ou pessoa real. Se algum exemplo trouxer um nome de pessoa real, "
        "ignore o nome e mantenha só o tom."
    )
    return linhas
