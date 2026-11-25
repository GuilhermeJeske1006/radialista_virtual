"""Onde a rádio fica: o bairro da sede e os outros bairros da cidade (Account.conhecimento_local).

O locutor dizia "aqui na Pomerânia", "aqui no São Pedro", "aqui no Lajeado Alto" numa rádio do Centro: o prompt
girava os bairros cadastrados como "detalhe do lugar onde a rádio fica". "Aqui" é sempre o bairro da sede; os
outros bairros são de onde o ouvinte fala ("lá do São Pedro").

Puro, sem banco e sem rede: o prompt (app.llm.prompt_builder) e o validador da fala (app.live.validacao_fala) usam
as mesmas funções.
"""

import re
import unicodedata

# "aqui no", "aqui mesmo na", "daqui do", "aqui pertinho, no bairro"... seguido do nome do bairro.
_ANTES_DO_BAIRRO = (
    r"\bd?aqui(?: (?:mesmo|pertinho|perto|bem))*"
    r" (?:no|na|nos|nas|em|do|da|de|pelo|pela|pro|pra|para o|para a)"
    r"(?: (?:nosso|nossa|o|a))?(?: bairro)? "
)
_SEPARADORES_ENDERECO = re.compile(r"\s*[-–,/|]\s*")
_PREFIXO_BAIRRO = re.compile(r"^(?:bairro|b\.)\s+", re.IGNORECASE)


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, só letras e números separados por um espaço."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def bairros_cadastrados(account) -> list[str]:
    local = getattr(account, "conhecimento_local", None) or {}
    return [b.strip() for b in local.get("bairros") or [] if isinstance(b, str) and b.strip()]


def bairro_da_sede(account) -> str:
    """O bairro onde a rádio fica: o campo `bairro_sede` do conhecimento local; vazio, o trecho do endereço que é um
    bairro cadastrado ou "Centro" ("Rua X, 100 - Centro"). "" quando não dá para saber."""
    local = getattr(account, "conhecimento_local", None) or {}
    informado = local.get("bairro_sede")
    if isinstance(informado, str) and informado.strip():
        return informado.strip()
    por_nome = {normalizar(b): b for b in bairros_cadastrados(account)}
    for trecho in _SEPARADORES_ENDERECO.split(getattr(account, "endereco", "") or ""):
        chave = normalizar(_PREFIXO_BAIRRO.sub("", trecho.strip()))
        if chave in por_nome:
            return por_nome[chave]
        if chave == "centro":
            return "Centro"
    return ""


def mesmo_bairro(a: str, b: str) -> bool:
    return bool(normalizar(a)) and normalizar(a) == normalizar(b)


def outros_bairros(account) -> list[str]:
    """Bairros cadastrados que não são a sede (todos, quando a sede não é conhecida) e não têm o nome da cidade."""
    sede, cidade = bairro_da_sede(account), getattr(account, "cidade", "") or ""
    return [b for b in bairros_cadastrados(account) if not mesmo_bairro(b, sede) and not mesmo_bairro(b, cidade)]


def aqui_em_outro_bairro(frase: str, account) -> str | None:
    """O bairro (que não é a sede) que a frase trata como "aqui" ("aqui na Pomerânia"), ou None."""
    texto = f" {normalizar(frase)} "
    for bairro in sorted(outros_bairros(account), key=len, reverse=True):
        if re.search(_ANTES_DO_BAIRRO + re.escape(normalizar(bairro)) + r"\b", texto):
            return bairro
    return None
