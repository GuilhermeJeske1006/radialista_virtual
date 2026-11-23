"""Energia do programa compartilhada pelo roteiro, pela síntese e pela trilha.

Só a apresentação musical recebe esse ajuste; notícia, serviço e reações
editoriais continuam com a direção do próprio bloco.
"""
import re

from app.live.formatos import ID_MUSICAL, ID_POPULAR, formato_do_programa
from app.util.texto import sem_acento

_APRESENTACAO_MUSICAL = frozenset({"abertura", "musica", "encerramento"})
_TOM_CALMO = re.compile(r"\b(calmo|calma|tranquilo|tranquila|relaxante|sereno|serena|suave|contemplativo)\b")


def energia_do_programa(programa) -> str:
    persona = getattr(programa, "persona", None)
    energia = persona.get("energia") if isinstance(persona, dict) else None
    if type(energia) is int and 1 <= energia <= 5:
        return "calmo" if energia <= 2 else "neutro" if energia == 3 else "energico"
    tom = sem_acento((getattr(programa, "tom", None) or "").lower())
    return "calmo" if _TOM_CALMO.search(tom) else "energico"


def tom_musical(programa, categoria: str, tom_bloco: str) -> str:
    musical = getattr(programa, "perfil", None) == "musical" or formato_do_programa(programa).id in {
        ID_MUSICAL, ID_POPULAR,
    }
    if musical and categoria in _APRESENTACAO_MUSICAL:
        return energia_do_programa(programa)
    return tom_bloco


def instrucao_energia(programa, categoria: str) -> str | None:
    if tom_musical(programa, categoria, "neutro") != "energico":
        return None
    return (
        "DIREÇÃO VOCAL DO PROGRAMA MUSICAL: entre com presença, sorriso na voz e entusiasmo desde a "
        "primeira frase. Use ritmo vivo e ênfase nas chamadas e na identificação, com articulação clara. "
        "Mantenha a energia até a despedida, sem soar desanimado, arrastado ou sonolento. "
        "Não confunda animação com gritar, ofegar ou correr; preserve o jeito do apresentador."
    )
