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
import datetime

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

    for escala, singular, plural in ((1_000_000_000, "bilhão", "bilhões"), (1_000_000, "milhão", "milhões")):
        if numero >= escala:
            grupo, resto = divmod(numero, escala)
            prefixo = f"{numero_por_extenso(grupo)} {singular if grupo == 1 else plural}"
            return prefixo + (f" e {numero_por_extenso(resto)}" if resto else "")

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
_VALOR_MONETARIO_RE = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{2}))?")


def substituir_valores_monetarios(texto: str) -> str:
    def _substituir(match: re.Match) -> str:
        reais = int(match.group(1).replace(".", ""))
        centavos = int(match.group(2)) if match.group(2) else 0
        return valor_monetario_por_extenso(reais, centavos)

    return _VALOR_MONETARIO_RE.sub(_substituir, texto)


def normalizar_texto_fala(texto: str, pronuncias: dict[str, str] | None = None) -> str:
    """Normalização pt-BR de formatos explícitos; aliases não alteram o roteiro salvo."""
    if pronuncias:
        mapa = {k.casefold(): v for k, v in pronuncias.items()}
        padrao = r"(?<!\w)(?:" + "|".join(re.escape(k) for k in sorted(pronuncias, key=len, reverse=True)) + r")(?!\w)"
        texto = re.sub(padrao, lambda m: mapa[m.group().casefold()], texto, flags=re.IGNORECASE)
    texto = substituir_valores_monetarios(texto)

    def telefone(m):
        return " ".join(_UNIDADES[int(d)] for d in m.group() if d.isdigit())

    texto = re.sub(r"(?<!\d)(?:\+55\s*)?(?:\(\d{2}\)\s*|\d{2}\s+)\d{4,5}[- ]\d{4}(?!\d)", telefone, texto)
    texto = re.sub(r"(?<!\d)\d{4,5}-\d{4}(?!\d)", telefone, texto)

    def horario(m):
        h, minuto = int(m[1]), int(m[2])
        if h > 23 or minuto > 59:
            return m.group()
        horas = "uma hora" if h == 1 else ("duas horas" if h == 2 else f"{numero_por_extenso(h)} horas")
        return horas + (f" e {numero_por_extenso(minuto)}" if minuto else "")

    texto = re.sub(r"\b(\d{1,2})[:h](\d{2})\b", horario, texto)
    def data_por_extenso(m):
        dia, mes, ano = map(int, m.groups())
        try:
            datetime.date(ano, mes, dia)
        except ValueError:
            return m.group()
        meses = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
        return f"{numero_por_extenso(dia)} de {meses[mes - 1]} de {numero_por_extenso(ano)}"
    texto = re.sub(r"\b(\d{2})/(\d{2})/(\d{4})\b", data_por_extenso, texto)
    texto = re.sub(r"\b(\d{1,3})[,.](\d{1,2})\s*(FM|MHz)\b",
                   lambda m: f"{numero_por_extenso(int(m[1]))} vírgula {numero_por_extenso(int(m[2]))} " + ("efe eme" if m[3].lower() == "fm" else "megahertz"), texto, flags=re.I)
    # Só números isolados de até seis dígitos; evita fragmentar identificadores,
    # URLs, datas e decimais que não se encaixam em um formato conhecido.
    texto = re.sub(r"(?<![\w.,/+:\-])-?\d{1,6}(?![\w/:]|[.,]\d|-\d)", lambda m: numero_por_extenso(int(m.group())), texto)
    texto = re.sub(r"\s*°\s*C\b", " graus Celsius", texto)
    texto = re.sub(r"\s*%", " por cento", texto)
    return texto
