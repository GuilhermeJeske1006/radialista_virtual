"""Notas editoriais estruturadas, compatíveis com assuntos antigos sem repertório."""

import re
from typing import Any

from app.util.texto import sem_acento

FAMILIAS = {
    "cotidiano": "rotina, pequenos hábitos e situações reconhecíveis",
    "memoria_afetiva": "lembranças do ouvinte, objetos e costumes de outras épocas",
    "musica": "descoberta de músicas, formas de ouvir e associações com canções",
    "cultura_regional": "costumes e expressões documentados nas referências da rádio",
    "participacao": "histórias, dúvidas e respostas autorizadas da audiência",
    "vida_pratica": "organização do dia e informação útil sustentada por dados",
    "entretenimento": "hobbies, leitura, cinema e outras atividades permitidas",
}


def texto(valor: Any, limite: int = 600) -> str:
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def lista_textos(valor: Any, max_itens: int = 3) -> list[str]:
    if not isinstance(valor, list):
        return []
    return list(dict.fromkeys(t for v in valor if (t := texto(v))))[:max_itens]


def normalizar(valor: Any) -> dict:
    if not isinstance(valor, dict):
        return {}
    resultado = {}
    if isinstance(valor.get("familia"), str) and valor["familia"] in FAMILIAS:
        resultado["familia"] = valor["familia"]
    for campo in ("recorte", "pergunta_origem"):
        if t := texto(valor.get(campo)):
            resultado[campo] = t
    for campo in ("abordagens", "contextos"):
        if itens := lista_textos(valor.get(campo)):
            resultado[campo] = itens
    return resultado


def identidade(valor: str) -> str:
    return " ".join(re.findall(r"\w+", sem_acento(valor.lower())))


_IRRELEVANTES = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
                 "um", "uma", "que", "para", "com", "voce", "seu", "sua", "por"}


def recortes_parecidos(a: str, b: str) -> bool:
    """Deduplicação lexical conservadora; não pretende reconhecer sinônimos semanticamente."""
    a, b = identidade(a), identidade(b)
    if not a or not b:
        return False
    if a == b:
        return True
    tokens_a, tokens_b = set(a.split()) - _IRRELEVANTES, set(b.split()) - _IRRELEVANTES
    return len(tokens_a & tokens_b) >= 4 and len(tokens_a & tokens_b) / len(tokens_a | tokens_b) >= 0.75
