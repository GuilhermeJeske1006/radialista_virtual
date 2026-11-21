"""Autonomia graduada por categoria (F12, §12.9 da pesquisa): automático, revisão ou proibido.

Função pura: decide para o bloco se vai ao ar sozinho, se espera aprovação humana (`aguardando_revisao`) ou se é
bloqueado. Não toca banco, painel nem o ao vivo; a integração ao router e a tela de aprovação ficam para depois.

Regras, na ordem:
1. Texto com tópico proibido da rádio (`Programa.topicos_proibidos`) → proibido.
2. Categoria de revisão (plantão, repórter, entrevista real) → revisão.
3. Tema delicado no texto (ex.: vítimas fatais, crime, suicídio) → revisão.
4. Resto → automático.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

AUTOMATICO = "automatico"
REVISAO = "revisao"
PROIBIDO = "proibido"

# Categorias que sempre passam por aprovação humana.
CATEGORIAS_REVISAO = frozenset({"plantao", "reporter", "entrevista"})

# Temas delicados: entram em revisão quando aparecem no texto (sem diferença de caixa e acento).
TEMAS_DELICADOS = (
    r"vitimas? fatais?", r"morte", r"morreu", r"morre", r"homicidio", r"latrocinio", r"estupro", r"suicidio",
    r"sequestro", r"chacina", r"tiroteio", r"crianca desaparecida",
)
_TEMAS_RE = re.compile(r"\b(?:" + "|".join(TEMAS_DELICADOS) + r")\b")

# Estado do bloco conforme a rota.
ESTADO_NO_AR = "no_ar"
ESTADO_AGUARDANDO = "aguardando_revisao"
ESTADO_BLOQUEADO = "bloqueado"


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


def rotear(categoria: str, texto: str = "", topicos_proibidos: Iterable[str] = ()) -> str:
    """Rota do bloco: AUTOMATICO, REVISAO ou PROIBIDO."""
    normalizado = _sem_acento(texto or "")
    for topico in topicos_proibidos:
        t = _sem_acento(topico or "").strip()
        if t and t in normalizado:
            return PROIBIDO
    if categoria in CATEGORIAS_REVISAO:
        return REVISAO
    if _TEMAS_RE.search(normalizado):
        return REVISAO
    return AUTOMATICO


def estado_inicial(rota: str) -> str:
    """Estado do bloco ao ser gerado: no ar, aguardando aprovação no painel ou bloqueado."""
    if rota == PROIBIDO:
        return ESTADO_BLOQUEADO
    if rota == REVISAO:
        return ESTADO_AGUARDANDO
    return ESTADO_NO_AR
