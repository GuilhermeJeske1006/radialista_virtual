"""Bancada com personas (F13): papéis fixos por participante e ordem de turnos.

Papéis fixos (decisão da auditoria F13): mediador, comentarista, contraponto. Atribuídos por participante em
`ProgramaRadialista.papel_bancada`. Sem papel definido, nada muda: o roster segue como sempre.
Turnos respondem ao anterior por instrução no prompt (ver app.llm.prompt_builder); o código só fixa a ordem.
"""

from __future__ import annotations

from collections.abc import Sequence

MEDIADOR = "mediador"
COMENTARISTA = "comentarista"
CONTRAPONTO = "contraponto"
PAPEIS_BANCADA = (MEDIADOR, COMENTARISTA, CONTRAPONTO)
_ORDEM = {papel: i for i, papel in enumerate(PAPEIS_BANCADA)}


def validar_papel_bancada(valor: str | None) -> str | None:
    """None (sem papel) ou um dos papéis fixos. Levanta ValueError (o router converte em 400)."""
    if valor is None or valor == "":
        return None
    if valor not in PAPEIS_BANCADA:
        raise ValueError(f"papel de bancada inválido: {valor!r}")
    return valor


def ordenar_turnos(participantes: Sequence, papel_de) -> list:
    """Ordem de fala: mediador, comentarista, contraponto; quem não tem papel mantém a ordem original no fim.
    Se nenhum participante tem papel, devolve a lista como veio (comportamento de sempre)."""
    if not any(papel_de(p) for p in participantes):
        return list(participantes)
    com_papel = [p for p in participantes if papel_de(p) in _ORDEM]
    sem_papel = [p for p in participantes if papel_de(p) not in _ORDEM]
    return sorted(com_papel, key=lambda p: _ORDEM[papel_de(p)]) + sem_papel


def instrucao_de_turnos() -> str:
    """Regra de conversa acrescentada ao prompt quando a bancada tem papéis."""
    return (
        "Na bancada, cada locutor responde ao que o anterior acabou de dizer, sem repetir o tema do zero. "
        "O mediador abre o assunto e passa a palavra; o comentarista opina; o contraponto discorda com respeito, "
        "sem atacar a pessoa."
    )
