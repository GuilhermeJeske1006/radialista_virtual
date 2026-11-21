"""Peças de reserva aprovadas (F11, item 3): o que entra no ar quando convidado, fonte, pedido, áudio ou
estouro falham.

A peça é cadastrada pelo operador e nasce NÃO aprovada. Só vale depois de aprovada explicitamente; editar o
texto desaprova de novo (o texto que foi ao ar tem que ser o que o operador leu). Guardada em
`Programa.pecas_reserva` (coluna própria: `Programa.quadros_fixos` continua sendo label -> pool de textos).
"""

from __future__ import annotations

from typing import Any

TIPOS_CONTINGENCIA = ("convidado", "fonte", "pedido", "audio", "estouro")
MAX_PECAS = 20
MAX_CARACTERES_TEXTO = 600


def normalizar_pecas(entrada: list[dict[str, Any]], atuais: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Valida a lista enviada pelo operador. `id` existente mantém a aprovação só se tipo e texto não mudaram.
    Levanta ValueError (o router converte em 400)."""
    if len(entrada) > MAX_PECAS:
        raise ValueError(f"no máximo {MAX_PECAS} peças de reserva")
    por_id = {p["id"]: p for p in (atuais or [])}
    proximo = max(por_id, default=0) + 1
    saida: list[dict[str, Any]] = []
    for item in entrada:
        tipo = (item.get("tipo") or "").strip()
        texto = (item.get("texto") or "").strip()
        if tipo not in TIPOS_CONTINGENCIA:
            raise ValueError(f"tipo invalido: {tipo!r}")
        if not texto:
            raise ValueError("peça sem texto")
        if len(texto) > MAX_CARACTERES_TEXTO:
            raise ValueError(f"texto com mais de {MAX_CARACTERES_TEXTO} caracteres")
        anterior = por_id.get(item.get("id"))
        mantem = anterior is not None and anterior["tipo"] == tipo and anterior["texto"] == texto
        if anterior is not None:
            peca_id = anterior["id"]
        else:
            peca_id, proximo = proximo, proximo + 1
        saida.append({"id": peca_id, "tipo": tipo, "texto": texto,
                      "aprovada": bool(anterior and mantem and anterior.get("aprovada"))})
    return saida


def aprovar(pecas: list[dict[str, Any]], peca_id: int) -> dict[str, Any] | None:
    """Marca a peça como aprovada pelo operador. None quando o id não existe."""
    for peca in pecas:
        if peca["id"] == peca_id:
            peca["aprovada"] = True
            return peca
    return None


def escolher_reserva(pecas: list[dict[str, Any]], tipo: str, ja_usadas: set[int] | frozenset[int] = frozenset()
                     ) -> dict[str, Any] | None:
    """Primeira peça aprovada do tipo que ainda não foi usada neste programa. None quando não há reserva válida:
    nesse caso o ao vivo não improvisa a contingência (segue a regra atual)."""
    for peca in pecas or []:
        if peca.get("tipo") == tipo and peca.get("aprovada") and peca["id"] not in ja_usadas:
            return peca
    return None
