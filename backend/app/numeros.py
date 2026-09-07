"""Conversao de numero pra portugues por extenso -- usado em todo texto que vai direto pro
sintetizador de voz (ver app.tts.client, app.llm.prompt_builder), porque o eleven_v3 (e a
maioria dos modelos de TTS) le algarismo em portugues errado com frequencia (ver comentario em
app.live.router._hora_certa_por_extenso, mesmo problema resolvido la' so' pra hora).

Escopo deliberadamente pratico pra numero de temperatura/preco de anuncio (tipicamente de 0 a
poucos milhares): a regra de "e" entre grupo de milhar e grupo de centena nao segue a norma
gramatical 100% (ex.: "mil duzentos e cinquenta" sai como "mil e duzentos e cinquenta" aqui) --
aceitavel pro caso de uso (fala de radio, nao texto formal), sem justificar o esforco de
implementar a regra completa.
"""

import re

_UNIDADES = (
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
    "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove",
)
_DEZENAS = {2: "vinte", 3: "trinta", 4: "quarenta", 5: "cinquenta", 6: "sessenta", 7: "setenta", 8: "oitenta", 9: "noventa"}
_CENTENAS = {1: "cento", 2: "duzentos", 3: "trezentos", 4: "quatrocentos", 5: "quinhentos", 6: "seiscentos", 7: "setecentos", 8: "oitocentos", 9: "novecentos"}


def _extenso_0_99(numero: int) -> str:
    if numero < 20:
        return _UNIDADES[numero]
    dezena, resto = divmod(numero, 10)
    palavra = _DEZENAS[dezena]
    return f"{palavra} e {_UNIDADES[resto]}" if resto else palavra


def _extenso_0_999(numero: int) -> str:
    if numero < 100:
        return _extenso_0_99(numero)
    centena, resto = divmod(numero, 100)
    palavra = "cem" if centena == 1 and resto == 0 else _CENTENAS[centena]
    return f"{palavra} e {_extenso_0_99(resto)}" if resto else palavra


def numero_por_extenso(numero: int) -> str:
    """Cardinal por extenso em portugues, de qualquer inteiro (negativo incluido, via 'menos').
    Sem limite superior rigido, mas so' testado/pensado pra faixa de temperatura e preco de
    anuncio (na pratica, ate' poucos milhares -- ver aviso de escopo no topo do modulo)."""
    if numero < 0:
        return f"menos {numero_por_extenso(-numero)}"
    if numero == 0:
        return "zero"
    if numero < 1000:
        return _extenso_0_999(numero)

    milhar, resto = divmod(numero, 1000)
    prefixo = "mil" if milhar == 1 else f"{_extenso_0_999(milhar)} mil"
    return f"{prefixo} e {_extenso_0_999(resto)}" if resto else prefixo


def valor_monetario_por_extenso(reais: int, centavos: int = 0) -> str:
    """Ex.: (19, 90) -> 'dezenove reais e noventa centavos'; (1, 0) -> 'um real';
    (0, 50) -> 'cinquenta centavos'."""
    parte_reais = "um real" if reais == 1 else f"{numero_por_extenso(reais)} reais"
    if centavos == 0:
        return parte_reais if reais else "zero reais"
    parte_centavos = "um centavo" if centavos == 1 else f"{numero_por_extenso(centavos)} centavos"
    return f"{parte_reais} e {parte_centavos}" if reais else parte_centavos


# "R$" seguido de valor com ou sem separador de milhar (ponto) e centavos (virgula) -- ex.:
# "R$19,90", "R$ 1.499", "R$ 1.499,90". So' reconhece o formato com "R$" explicito: texto de
# anuncio de patrocinador (ver _substituir_valores_monetarios) nunca teve garantia de passar pelo
# LLM (ver Patrocinador.texto em app.live.router, conteudo fixo que nunca passa pelo LLM), por
# isso essa normalizacao roda direto no TTS em vez de depender da instrucao de prompt.
_VALOR_MONETARIO_RE = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?")


def substituir_valores_monetarios(texto: str) -> str:
    def _substituir(match: re.Match) -> str:
        reais = int(match.group(1).replace(".", ""))
        centavos = int(match.group(2)) if match.group(2) else 0
        return valor_monetario_por_extenso(reais, centavos)

    return _VALOR_MONETARIO_RE.sub(_substituir, texto)
