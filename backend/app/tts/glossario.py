"""Glossário de pronúncia (F9 da melhoria de rádio): precedência rádio x voz e sugestões de termos novos.

O glossário da rádio (`Account.glossario_pronuncia`) vale para todas as vozes. O da voz (`ConfiguracaoVoz.pronuncias`)
sobrescreve o da rádio quando a chave é a mesma, sem diferença de caixa. A aplicação no texto continua em
`app.numeros.normalizar_texto_fala`; aqui só se monta o mapa efetivo.

Sugestões: termos que o TTS tende a errar (siglas, nomes com w/y/k/ph) tirados de textos que a rádio já tem
(artistas, patrocinadores, cidade). Heurística; quem decide é a pessoa que cadastra.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

MAX_TERMOS_RADIO = 100
MAX_TERMOS_VOZ = 30
MAX_CARACTERES_TERMO = 60

_SIGLA_RE = re.compile(r"\b[A-Z]{2,5}\b")
_PALAVRA_CAPITALIZADA_RE = re.compile(r"\b[A-ZÀ-Ú][a-zà-ú]{2,}\b")
_LETRA_ESTRANHA_RE = re.compile(r"[wyk]|ph")
# Empréstimos comuns que têm w, y, k ou ph e o TTS já fala bem: não entram como sugestão.
_EMPRESTIMOS_COMUNS = frozenset({"show", "shopping", "kit", "web", "yoga", "happy", "fashion", "ok"})


def normalizar_glossario(valores: Mapping[str, str] | None, limite: int) -> dict[str, str]:
    """Limpa o glossário: descarta chave ou valor vazio, remove duplicata sem diferença de caixa (vence a primeira),
    e recusa termo longo demais ou glossário acima do limite. Levanta ValueError (o validador da API converte)."""
    limpos: dict[str, str] = {}
    vistos: set[str] = set()
    for chave, valor in (valores or {}).items():
        termo, pronuncia = (chave or "").strip(), (valor or "").strip()
        if not termo or not pronuncia:
            continue
        if len(termo) > MAX_CARACTERES_TERMO or len(pronuncia) > MAX_CARACTERES_TERMO:
            raise ValueError(f"termo com mais de {MAX_CARACTERES_TERMO} caracteres")
        if termo.casefold() in vistos:
            continue
        vistos.add(termo.casefold())
        limpos[termo] = pronuncia
    if len(limpos) > limite:
        raise ValueError(f"no máximo {limite} termos")
    return limpos


def mesclar_glossarios(da_radio: Mapping[str, str] | None, da_voz: Mapping[str, str] | None) -> dict[str, str]:
    """Glossário efetivo de uma voz: o da rádio, sobrescrito pelo da voz (mesma chave, sem diferença de caixa)."""
    voz = dict(da_voz or {})
    voz_casefold = {k.casefold() for k in voz}
    efetivo = {k: v for k, v in (da_radio or {}).items() if k.casefold() not in voz_casefold}
    efetivo.update(voz)
    return efetivo


def sugerir_termos(textos: Iterable[str], ja_cadastrados: Iterable[str] = (), limite: int = 20) -> list[str]:
    """Termos que o TTS tende a errar, nos textos da rádio, sem os que já estão no glossário.

    Critérios: siglas em maiúsculas (2 a 5 letras) e nomes próprios com w, y, k ou ph (ex.: "Wesley", "Kelly",
    "Phelipe"). Ordem de primeira aparição, sem repetição, até `limite`.
    """
    ja = {t.casefold() for t in ja_cadastrados}
    achados: list[str] = []
    vistos: set[str] = set()
    for texto in textos:
        candidatos = [m.group(0) for m in _SIGLA_RE.finditer(texto or "")]
        candidatos += [
            m.group(0) for m in _PALAVRA_CAPITALIZADA_RE.finditer(texto or "")
            if _LETRA_ESTRANHA_RE.search(m.group(0).lower())
        ]
        for termo in candidatos:
            if termo.casefold() in ja or termo.casefold() in vistos or termo.casefold() in _EMPRESTIMOS_COMUNS:
                continue
            vistos.add(termo.casefold())
            achados.append(termo)
            if len(achados) >= limite:
                return achados
    return achados
