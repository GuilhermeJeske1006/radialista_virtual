"""Verificador determinístico de oralidade (F7 da melhoria de rádio).

Só aponta trechos que soam mal no ar: frase longa, mais de uma ideia por frase, sigla sem expansão na primeira
ocorrência, número longo por extenso ou em dígitos e vocabulário burocrático. Não reescreve nada: quem decide o que
fazer com o aviso é o chamador (reescrita opcional e métricas).

Heurístico de propósito. Os limites são constantes do módulo para o teste de caracterização; não são medidos com
ouvinte real.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

LIMITE_PALAVRAS_FRASE = 25
LIMITE_PALAVRAS_MAIS_DE_UMA_IDEIA = 18
MIN_DIGITOS_NUMERO_LONGO = 5
MIN_PALAVRAS_NUMERICAS = 3

# Siglas que o ouvinte reconhece sem expansão no rádio.
SIGLAS_FALADAS = frozenset({"FM", "AM", "TV", "OK", "SP", "RJ", "MG", "BR", "EUA"})

CONECTIVOS_IDEIAS = frozenset({
    "que", "porque", "enquanto", "embora", "pois", "mas", "entretanto", "portanto", "quando", "onde", "sendo",
})

BUROCRATICO = (
    "municipalidade", "acarretar", "realizara", "outrossim", "doravante", "destarte", "ensejar", "supracitado",
    "mediante", "concernente", "no que tange", "por intermedio", "ademais", "bem como", "procedera", "providenciara",
)

PALAVRAS_NUMERICAS = frozenset({
    "zero", "dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
    "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove", "vinte", "trinta", "quarenta",
    "cinquenta", "sessenta", "setenta", "oitenta", "noventa", "cem", "cento", "duzentos", "duzentas", "trezentos",
    "trezentas", "quatrocentos", "quatrocentas", "quinhentos", "quinhentas", "seiscentos", "seiscentas",
    "setecentos", "setecentas", "oitocentos", "oitocentas", "novecentos", "novecentas", "mil", "milhao", "milhoes",
})

_STOPWORDS_SIGLA = frozenset({"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o", "no", "na"})


@dataclass(frozen=True)
class Aviso:
    regra: str
    trecho: str


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"[.!?;]+", texto) if f.strip()]


def _palavras(frase: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", _sem_acento(frase))


def _frase_longa(texto: str) -> list[Aviso]:
    return [
        Aviso("frase_longa", frase)
        for frase in _frases(texto)
        if len(_palavras(frase)) > LIMITE_PALAVRAS_FRASE
    ]


def _mais_de_uma_ideia(texto: str) -> list[Aviso]:
    avisos = []
    for frase in _frases(texto):
        palavras = _palavras(frase)
        if len(palavras) <= LIMITE_PALAVRAS_FRASE and len(palavras) >= LIMITE_PALAVRAS_MAIS_DE_UMA_IDEIA:
            conectivos = sum(1 for p in palavras if p in CONECTIVOS_IDEIAS)
            if conectivos >= 2:
                avisos.append(Aviso("mais_de_uma_ideia", frase))
    return avisos


def _iniciais_batem(sigla: str, expansao: str) -> bool:
    palavras = [p for p in _palavras(expansao) if p not in _STOPWORDS_SIGLA]
    iniciais = "".join(p[0] for p in palavras).upper()
    return iniciais.endswith(sigla) or iniciais.startswith(sigla)


def _sigla_expandida(texto: str, sigla: str, inicio: int) -> bool:
    # "Centro de Referência (CRAS)": as palavras antes de "(SIGLA)" dão a expansão.
    antes = texto[:inicio]
    if antes.endswith("("):
        antes_do_parentese = antes[:-1].rstrip()
        trecho = re.split(r"[.!?;,:]", antes_do_parentese)[-1]
        if _iniciais_batem(sigla, trecho):
            return True
    # "CRAS (Centro de Referência)": a expansão vem entre parênteses logo depois.
    depois = texto[inicio + len(sigla):]
    m = re.match(r"\s*\(([^)]+)\)", depois)
    return bool(m and _iniciais_batem(sigla, m.group(1)))


def _siglas_sem_expansao(texto: str) -> list[Aviso]:
    avisos = []
    vistas: set[str] = set()
    for m in re.finditer(r"\b[A-Z]{2,6}\b", texto):
        sigla = m.group(0)
        if sigla in vistas:
            continue
        vistas.add(sigla)
        if sigla in SIGLAS_FALADAS or _sigla_expandida(texto, sigla, m.start()):
            continue
        avisos.append(Aviso("sigla_sem_expansao", sigla))
    return avisos


def _numeros_longos(texto: str) -> list[Aviso]:
    avisos = [
        Aviso("numero_longo", m.group(0))
        for m in re.finditer(r"\d+(?:[.,]\d+)*", texto)
        if sum(c.isdigit() for c in m.group(0)) >= MIN_DIGITOS_NUMERO_LONGO
    ]
    tokens = _palavras(texto)
    corrida: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] in PALAVRAS_NUMERICAS:
            corrida = [tokens[i]]
            j = i + 1
            while j < len(tokens) and (
                tokens[j] in PALAVRAS_NUMERICAS or (tokens[j] == "e" and j + 1 < len(tokens)
                                                    and tokens[j + 1] in PALAVRAS_NUMERICAS)
            ):
                if tokens[j] in PALAVRAS_NUMERICAS:
                    corrida.append(tokens[j])
                j += 1
            if len(corrida) >= MIN_PALAVRAS_NUMERICAS:
                avisos.append(Aviso("numero_longo", " ".join(tokens[i:j])))
            i = j
        else:
            i += 1
    return avisos


def _burocratico(texto: str) -> list[Aviso]:
    normalizado = _sem_acento(texto)
    avisos = []
    for termo in BUROCRATICO:
        for m in re.finditer(r"\b" + re.escape(termo) + r"\w*", normalizado):
            avisos.append(Aviso("burocratico", m.group(0)))
    return avisos


def avisos(texto: str) -> list[Aviso]:
    """Lista de avisos de oralidade do texto de uma fala. Vazia quando nada chama atenção."""
    if not texto or not texto.strip():
        return []
    return (
        _frase_longa(texto)
        + _mais_de_uma_ideia(texto)
        + _siglas_sem_expansao(texto)
        + _numeros_longos(texto)
        + _burocratico(texto)
    )


verificar = avisos


_INSTRUCAO_POR_REGRA = {
    "frase_longa": "Quebre as frases longas em duas, com uma ideia em cada.",
    "mais_de_uma_ideia": "Separe as ideias em frases curtas, uma ideia por frase.",
    "sigla_sem_expansao": "Diga por extenso a sigla {trecho} na primeira vez que ela aparecer.",
    "numero_longo": "Diga os números em partes curtas, sem sequência longa de números por extenso ou em dígitos.",
    "burocratico": "Troque '{trecho}' por palavra do dia a dia.",
}


def instrucao_de_oralidade(lista: list[Aviso]) -> str:
    """Texto para a reescrita única, uma linha por tipo de aviso (sem repetir). Vazio quando não há avisos."""
    linhas: list[str] = []
    for aviso in lista:
        modelo = _INSTRUCAO_POR_REGRA.get(aviso.regra)
        if modelo is None:
            continue
        linha = modelo.format(trecho=aviso.trecho)
        if linha not in linhas:
            linhas.append(linha)
    if not linhas:
        return ""
    return "Oralidade: " + " ".join(linhas)
