"""Limpeza de texto externo antes de ele entrar no prompt (F5, docs/melhoria-radio/f5/auditoria.md §6.6).

Título e resumo do RSS, retificação, apuração web, mensagem e nome do ouvinte, contexto da faixa: tudo isso é dado,
nunca instrução (item 3 de docs/auditoria.md). `limpar` tira caracteres de controle, as frases com ordem embutida
dirigida ao locutor ou ao sistema ("ignore as regras", "a partir de agora você", "anuncie que") e corta no limite.
Os padrões ficam em `CONFIG_TEXTO_EXTERNO` e são só imperativos: manchete legítima ("Prefeitura anuncia obra",
"Governo diz que...", "Ignorado pela prefeitura, buraco cresce") não é tocada.

A limpeza é parte da garantia, não enfeite: sem ela, a palavra pedida pela injeção ("desconto") ficaria no texto do
dado e passaria a "cobrir" a fala no validador (app.dados.checagem). Puro: sem rede, sem banco.
"""

import re
import unicodedata

from app.dados.verificavel import CONFIG_DADOS

CONFIG_TEXTO_EXTERNO = {
    # Expressões (sobre o texto sem acento e em minúsculas) que marcam uma frase como ordem embutida.
    "instrucoes": [
        r"\b(?:ignore|ignorem|ignorar|desconsidere|desconsiderem|desconsiderar|esqueca|esquecam|esquecer)\s"
        r"(?:(?:as|os|a|o|todas|todos|suas|seus|essas|esses|estas|estes|qualquer|quaisquer|tais|minhas|nossas)\s)*"
        r"(?:regras?|instrucoes?|ordens?|orientacoes?|diretrizes?|comandos?|configuracao|configuracoes)\b",
        r"\b(?:a partir de agora|de agora em diante|daqui pra frente|daqui para frente)\s(?:,\s)?voce\b",
        r"\bvoce\sdeve\s(?:dizer|falar|anunciar|ler|responder|obedecer|ignorar|seguir|repetir|divulgar|avisar)\b",
        r"\b(?:anuncie|anunciem|diga|digam|fale|falem|leia|leiam|avise|avisem|informe|informem|divulgue|divulguem)"
        r"\s(?:que|no ar|ao vivo|aos ouvintes|para os ouvintes|pros ouvintes)\b",
        r"\b(?:system\s)?prompt\b",
        r"\binstrucoes\santeriores\b",
        r"\bmodo\s(?:desenvolvedor|administrador)\b",
    ],
    # Caracteres invisíveis que somem (largura zero, direção de texto); os de controle viram espaço.
    "invisiveis": "​‌‍‎‏⁠﻿‪‫‬‭‮⁦⁧⁨⁩",
    # O que nunca fica no nome do ouvinte (aspas, colchetes, chaves, sinais de marcação).
    "proibidos_no_nome": "\"'“”‘’`[]{}<>\\|",
}

_INSTRUCAO_RE = re.compile("|".join(CONFIG_TEXTO_EXTERNO["instrucoes"]))
_CONTROLE_RE = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")
_INVISIVEIS = {ord(c): None for c in CONFIG_TEXTO_EXTERNO["invisiveis"]}
_FRASE_RE = re.compile(r"(?<=[.!?…])\s+")
_ESPACOS_RE = re.compile(r"\s+")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def tem_instrucao(texto: str | None) -> bool:
    """O texto tem uma ordem embutida dirigida ao locutor ou ao sistema."""
    return bool(texto) and _INSTRUCAO_RE.search(_ESPACOS_RE.sub(" ", _sem_acento(texto))) is not None


def _normalizar_espacos(texto: str) -> str:
    texto = (texto or "").translate(_INVISIVEIS)
    return _ESPACOS_RE.sub(" ", _CONTROLE_RE.sub(" ", texto)).strip()


def _cortar(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto
    cortado = texto[:limite]
    if texto[limite] != " " and " " in cortado:
        cortado = cortado.rsplit(" ", 1)[0]
    return cortado.rstrip(" ,;:")


def limpar(texto: str | None, limite: int | None = None) -> tuple[str, tuple[str, ...]]:
    """(texto limpo, frases removidas). Controle e quebras viram espaço; frase com ordem embutida sai; o resto é
    cortado em `limite` caracteres (padrão `ConfigDados.limite_texto`) sem partir palavra. Nunca reescreve."""
    limite = CONFIG_DADOS.limite_texto if limite is None else limite
    normalizado = _normalizar_espacos(texto or "")
    if not normalizado:
        return "", ()
    ficam, removidas = [], []
    for frase in _FRASE_RE.split(normalizado):
        if not frase.strip():
            continue
        (removidas if tem_instrucao(frase) else ficam).append(frase.strip())
    return _cortar(" ".join(ficam), limite), tuple(removidas)


def nome_seguro(nome: str | None, limite: int | None = None) -> str:
    """Nome do ouvinte (PushName do WhatsApp) como entra no prompt e nos detectores (D15): sem controle, aspas,
    colchetes nem chaves, até `limite` caracteres; com ordem embutida, vira o substituto da configuração."""
    limite = CONFIG_DADOS.limite_nome if limite is None else limite
    proibidos = {ord(c): " " for c in CONFIG_TEXTO_EXTERNO["proibidos_no_nome"]}
    limpo = _normalizar_espacos((nome or "").translate(proibidos))
    if not limpo:
        return ""
    if tem_instrucao(limpo):
        return CONFIG_DADOS.nome_substituto
    return _cortar(limpo, limite)
