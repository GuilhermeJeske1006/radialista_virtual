"""Checagem de dado na fala (F5, docs/melhoria-radio/f5/auditoria.md §6.5): `dado_sem_fonte` e `dado_vencido`.

Regras 5 e 6 da skill referencia-radio: temperatura, tempo lá fora, trânsito, placar e promoção só com dado de fonte,
dentro da validade; vencido, só com o horário da última atualização; nunca preencher lacuna factual com inferência.

- `afirmacoes(texto)`: detector puro (o simulador usa o mesmo, scripts/simulacao/metricas.py). Uma afirmação por
  categoria e frase (a mesma divisão de frases do encurtamento da F2), sem diferença de acento e caixa.
- `checar_fala(fala, dados, instante, tz, cobertura_extra=(), isentas=())`: o contrato da F3. Cada frase com
  afirmação que nenhum dado válido cobre vira uma `Violacao` (a mesma da F3 e da F4): `dado_vencido` quando só um
  dado vencido (ou velho demais para a categoria) a cobre e a frase não diz o horário; `dado_sem_fonte` no resto.

Determinístico, sem LLM e sem rede. Gatilhos, coberturas e instruções ficam em `CONFIG_CHECAGEM`.
"""

import dataclasses
import datetime
import re
import unicodedata
from typing import Iterable

from app.dados.verificavel import DadoVerificavel, estado, horario_falado, velho_para_afirmar
from app.live.orcamento import frases
from app.live.validacao_fala import Violacao
from app.numeros import cardinal_feminino, numero_por_extenso


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento; mantém dígitos, "%" e "°"; o resto vira espaço."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%°]+", " ", sem_acento)).strip()


def _numeros_por_extenso(maximo: int) -> dict[str, int]:
    valores: dict[str, int] = {}
    for n in range(0, maximo + 1):
        for forma in {numero_por_extenso(n), cardinal_feminino(n)}:
            valores[normalizar(forma)] = n
    valores["quatorze"] = 14
    return valores


_VALOR_NUMERO = _numeros_por_extenso(99)
_NUM = "|".join(sorted((re.escape(k) for k in _VALOR_NUMERO), key=len, reverse=True))
_NUMERO = rf"(?:menos\s)?(?:{_NUM})|\d+"

CONFIG_CHECAGEM = {
    # Gatilho de cada categoria (sobre o texto normalizado). Grupos nomeados "n", "a" e "b" capturam os números.
    "padroes": {
        "temperatura": rf"\b(?P<n>{_NUMERO})\s(?:graus?)\b|(?P<d>\d+)\s?°",
        "condicao_tempo": r"\b(?:esta|ta|continua|segue)\s(?:chovendo|garoando|ventando|nublado|ensolarado|abafado"
                          r"|frio|quente|fresco|gelado)\b|\bfaz\s(?:um\s)?(?:frio|calor)\b"
                          r"|\bceu\s(?:esta\s)?(?:limpo|nublado|aberto|fechado|encoberto)\b|\bchove\b|\bsol\sforte\b",
        "previsao": r"\b(?:vai|deve|pode)\s(?:chover|garoar|esfriar|esquentar|ventar|gear|fazer\s(?:frio|calor|sol))\b"
                    r"|\bprevisao\s(?:de|do tempo|para|indica)\b|\bfrente\sfria\b|\btemporal\b",
        "transito": r"\b(?:transito|avenida|rua|rodovia|estrada|pista|ponte|br|marginal|viaduto|tunel|rotatoria"
                    r"|cruzamento)\b(?:\s\S+){0,6}?\s(?:parad[oa]s?|lent[oa]s?|lentidao|congestionad[oa]s?"
                    r"|engarrafad[oa]s?|interditad[oa]s?|interdicao|bloquead[oa]s?|bloqueio|liberad[oa]s?"
                    r"|desvios?|obras?|acidentes?|fechad[oa]s?|vai mudar|complicad[oa]s?|travad[oa]s?"
                    r"|meia pista)\b|\b(?:congestionamentos?|engarrafamentos?|lentidao)\b",
        "placar": rf"\b(?P<a>{_NUMERO})\s(?:a|x)\s(?P<b>{_NUMERO})\b|\b(?P<a2>\d+)x(?P<b2>\d+)\b",
        "comercial": rf"\b(?:descontos?|promocao|promocoes|metade do preco|gratis|de graca|premios?|cupom|cupons"
                     rf"|sorteados?|sorteadas?|ganhador(?:es)?|liquidacao)\b|\d+\s?%|\b(?:{_NUM}|\d+)\spor cento\b",
    },
    # Placar só conta com contexto esportivo na frase ("duas a três horas" não é placar).
    "contexto_placar": r"\b(?:time|times|jogo|partida|placar|gol|gols|ganhando|vencendo|perdendo|empat\w*|venceu"
                       r"|vence|perdeu|derrot\w*|campeonato|rodada|classifica\w*|clube|selecao|final|semifinal)\b",
    # Marca de horário na frase: o dado vencido pode ir ao ar assim ("na última atualização, ao meio-dia").
    "marca_horario": rf"\b(?:ultima atualizacao|ultima leitura|ultimo boletim|atualizad[oa]s?\s(?:as|ao|a)"
                     rf"|boletim\sd[aoe]s?|marcava|marcavam|registrava|registravam|medicao\sd[aoe]s?"
                     rf"|(?:as|ao|a)\s(?:meio dia|meia noite|(?:{_NUM})\s(?:horas?|e\s(?:{_NUM}))))\b",
    # Frases de ausência não afirmam dado (a contingência da F4 e a omissão da §10).
    "frases_ausencia": ["nao temos atualizacao", "sem atualizacao", "sem informacao confirmada",
                        "nao ha informacao", "nao temos informacao", "nao temos dado", "sem dado confirmado",
                        "ainda nao temos", "nao tem atualizacao"],
    # Tipo de dado válido que cobre a categoria inteira.
    "cobertura_por_tipo": {
        "temperatura": ("clima",), "condicao_tempo": ("clima",), "previsao": ("previsao",),
        "transito": ("transito", "aviso", "servico"), "placar": ("esporte",), "comercial": (),
    },
    # Vocabulário que, no texto de um dado válido de qualquer tipo, cobre a categoria (radicais normalizados).
    # Comercial só pelo próprio gatilho: é o que a injeção pede ("desconto"), e a limpeza tira a ordem do dado.
    "vocabulario_cobertura": {
        "previsao": ("chuv", "chov", "temporal", "tempestade", "frente fria", "previsao", "geada", "granizo",
                     "ventania", "esfri", "frio", "calor", "garoa"),
        "transito": ("transito", "avenida", "rua", "rodovia", "estrada", "pista", "ponte", "viaduto", "tunel",
                     "interdi", "bloque", "desvio", "obra", "acidente", "congestion", "engarraf", "lentidao",
                     "fechad", "liberad"),
    },
    # Afirmação de momento: a idade máxima da categoria (ConfigDados.idade_max_afirmacao_s) vale para ela. Temperatura
    # e tempo lá fora sempre; trânsito só a condição ("parado", "lento"), não a obra ou a interdição de dias; placar
    # só o jogo em andamento ("está ganhando"), não o resultado final ("venceu").
    "de_momento": {
        "temperatura": "", "condicao_tempo": "",
        "transito": r"\b(?:parad\w*|lent[oa]s?|lentidao|congestion\w*|engarraf\w*|travad\w*|complicad\w*|fluindo)\b",
        "placar": r"\b(?:ganhando|vencendo|perdendo|empatando|esta|segue|agora)\b",
    },
    "tolerancia_temperatura": 0,
    "instrucoes": {
        "dado_sem_fonte": "Você afirmou '{trecho}' sem dado de referência. Use só os dados de referência da mensagem; "
                          "sem dado, não fale de temperatura, tempo lá fora, trânsito, placar, promoção ou prêmio.",
        "dado_vencido": "O dado que você usou em '{trecho}' é da última atualização, {hora}: diga 'na última "
                        "atualização, {hora}' ou não cite.",
    },
}

_PADROES = {categoria: re.compile(p) for categoria, p in CONFIG_CHECAGEM["padroes"].items()}
_CONTEXTO_PLACAR = re.compile(CONFIG_CHECAGEM["contexto_placar"])
_MARCA_HORARIO = re.compile(CONFIG_CHECAGEM["marca_horario"])
_DE_MOMENTO = {categoria: re.compile(p) if p else None for categoria, p in CONFIG_CHECAGEM["de_momento"].items()}
_TEMPERATURA_DADO = re.compile(rf"\b(?P<n>{_NUMERO})\s(?:graus?)\b|(?P<d>-?\d+)\s?°")
_PLACAR_DADO = re.compile(rf"\b(?P<a>{_NUMERO})\s(?:a|x)\s(?P<b>{_NUMERO})\b|\b(?P<a2>\d+)x(?P<b2>\d+)\b")


@dataclasses.dataclass(frozen=True)
class Afirmacao:
    categoria: str              # temperatura | condicao_tempo | previsao | transito | placar | comercial
    frase: str                  # a frase como está na fala
    gatilho: str                # o trecho normalizado que disparou
    numeros: tuple[int, ...] = ()
    com_horario: bool = False
    de_momento: bool = False    # a idade máxima da categoria vale (CONFIG_CHECAGEM["de_momento"])


def _numero(trecho: str | None) -> int | None:
    if not trecho:
        return None
    trecho = trecho.strip()
    negativo = trecho.startswith("menos ")
    trecho = trecho.removeprefix("menos ").strip()
    valor = int(trecho) if trecho.isdigit() else _VALOR_NUMERO.get(trecho)
    return -valor if negativo and valor is not None else valor


def _numeros(categoria: str, achado: re.Match) -> tuple[int, ...]:
    if categoria == "temperatura":
        valor = _numero(achado.group("n") or achado.group("d"))
        return (valor,) if valor is not None else ()
    if categoria == "placar":
        a, b = _numero(achado.group("a") or achado.group("a2")), _numero(achado.group("b") or achado.group("b2"))
        return (a, b) if a is not None and b is not None else ()
    return ()


def _ausencia(normalizada: str) -> bool:
    return any(f" {m} " in f" {normalizada} " for m in CONFIG_CHECAGEM["frases_ausencia"])


def _de_momento(categoria: str, normalizada: str) -> bool:
    if categoria not in _DE_MOMENTO:
        return False
    padrao = _DE_MOMENTO[categoria]
    return padrao is None or padrao.search(normalizada) is not None


def afirmacoes(texto: str) -> list[Afirmacao]:
    """Afirmações de dado no texto, na ordem das frases; uma por categoria e frase. Frases de ausência ("não temos
    atualização...") não afirmam nada. Puro."""
    achadas: list[Afirmacao] = []
    for frase in frases(texto):
        normalizada = normalizar(frase)
        if not normalizada or _ausencia(normalizada):
            continue
        com_horario = _MARCA_HORARIO.search(normalizada) is not None
        for categoria, padrao in _PADROES.items():
            for achado in padrao.finditer(normalizada):
                if categoria == "placar" and not _CONTEXTO_PLACAR.search(normalizada):
                    continue
                achadas.append(Afirmacao(categoria, frase, achado.group(0), _numeros(categoria, achado),
                                         com_horario, _de_momento(categoria, normalizada)))
                break
    return achadas


# ---------------------------------------------------------------------------------------------------------
# Cobertura
# ---------------------------------------------------------------------------------------------------------

def _texto_do_dado(dado: DadoVerificavel) -> str:
    detalhes = dado.detalhes or {}
    if dado.tipo == "assunto":
        # Notas de abordagem e falas antigas não comprovam uma afirmação factual nova.
        detalhes = {k: v for k, v in detalhes.items() if k in ("fatos", "contexto", "pergunta")}
    return normalizar(" ".join([dado.valor, *(str(v) for v in detalhes.values() if v)]))


def _radical(palavra: str) -> str:
    """Radical para casar a flexão ("desconto"/"descontos", "parado"/"parada"): tira duas letras das palavras longas
    e uma das médias; palavra curta fica inteira. Mais curto que isso casaria palavra comum ("para" com "parado")."""
    if len(palavra) > 6:
        return palavra[:-2]
    if len(palavra) > 4:
        return palavra[:-1]
    return palavra


def _tem_palavra(texto: str, termo: str, ja_radical: bool = False) -> bool:
    """`termo` (uma palavra ou expressão) aparece no texto: expressão inteira, ou palavra pelo radical (o próprio
    termo quando ele já é um radical, como no vocabulário de cobertura)."""
    termo = normalizar(termo)
    if not termo:
        return False
    if " " in termo:
        return f" {termo} " in f" {texto} "
    radical = termo if ja_radical else _radical(termo)
    return any(p.startswith(radical) for p in texto.split())


def _numeros_do_dado(texto: str, padrao: re.Pattern, pares: bool) -> set[tuple[int, ...]]:
    encontrados = set()
    for achado in padrao.finditer(texto):
        if pares:
            a, b = _numero(achado.group("a") or achado.group("a2")), _numero(achado.group("b") or achado.group("b2"))
            if a is not None and b is not None:
                encontrados |= {(a, b), (b, a)}
        else:
            valor = _numero(achado.group("n") or achado.group("d"))
            if valor is not None:
                encontrados.add((valor,))
    return encontrados


def cobre(afirmacao: Afirmacao, dado: DadoVerificavel) -> bool:
    """O dado (qualquer estado) sustenta a afirmação: tipo e número para temperatura e placar; tipo ou vocabulário
    para condição, previsão e trânsito; o próprio gatilho para comercial."""
    texto = _texto_do_dado(dado)
    categoria = afirmacao.categoria
    tipos = CONFIG_CHECAGEM["cobertura_por_tipo"][categoria]
    if categoria == "temperatura":
        if dado.tipo not in tipos or not afirmacao.numeros:
            return False
        alvo, tolerancia = afirmacao.numeros[0], CONFIG_CHECAGEM["tolerancia_temperatura"]
        return any(abs(n[0] - alvo) <= tolerancia for n in _numeros_do_dado(texto, _TEMPERATURA_DADO, False))
    if categoria == "placar":
        return dado.tipo in tipos and bool(afirmacao.numeros) and \
            tuple(afirmacao.numeros) in _numeros_do_dado(texto, _PLACAR_DADO, True)
    if categoria == "comercial":
        return _tem_palavra(texto, afirmacao.gatilho)
    if dado.tipo in tipos:
        return True
    return any(_tem_palavra(texto, termo, ja_radical=True)
               for termo in CONFIG_CHECAGEM["vocabulario_cobertura"].get(categoria, ()))


def _palavra_chave(afirmacao: Afirmacao) -> str:
    """O gatilho inteiro na categoria comercial ("metade do preco"); nas outras, a última palavra ("parado")."""
    return afirmacao.gatilho if afirmacao.categoria == "comercial" else afirmacao.gatilho.split()[-1]


def _coberta_por_texto(afirmacao: Afirmacao, textos: Iterable[str]) -> bool:
    """Cobertura extra (D17): textos configurados pela rádio contam só pela palavra-gatilho; número de temperatura
    e placar nunca vêm daí."""
    if afirmacao.categoria in ("temperatura", "placar"):
        return False
    return _tem_palavra(normalizar(" ".join(textos)), _palavra_chave(afirmacao))


def _isenta(frase: str, isentas: Iterable[str]) -> bool:
    """A frase é parte de um texto isento (a contingência da F4, a reorientação neutra)."""
    alvo = normalizar(frase)
    return bool(alvo) and any(f" {alvo} " in f" {normalizar(texto)} " for texto in isentas)


def _instrucao(regra: str, trecho: str, hora: str = "") -> str:
    return CONFIG_CHECAGEM["instrucoes"][regra].format(trecho=trecho.strip()[:120], hora=hora)


def checar_fala(fala: str, dados: Iterable[DadoVerificavel], instante: datetime.datetime, tz: str,
                cobertura_extra: Iterable[str] = (), isentas: Iterable[str] = ()) -> list[Violacao]:
    """Uma violação por frase com afirmação sem cobertura válida (a primeira categoria da frase decide)."""
    dados = list(dados)
    validos = [d for d in dados if estado(d, instante) == "valido"]
    vencidos = [d for d in dados if estado(d, instante) == "vencido"]
    extras = [t for t in cobertura_extra if t]
    isentas = [t for t in isentas if t]
    violacoes: list[Violacao] = []
    frases_vistas: set[str] = set()
    for afirmacao in afirmacoes(fala):
        if afirmacao.frase in frases_vistas or _isenta(afirmacao.frase, isentas):
            continue
        cobrem = [d for d in validos if cobre(afirmacao, d)]
        if any(not (afirmacao.de_momento and velho_para_afirmar(d, afirmacao.categoria, instante)) for d in cobrem):
            continue
        if not cobrem and extras and _coberta_por_texto(afirmacao, extras):
            continue
        antigos = cobrem or [d for d in vencidos if cobre(afirmacao, d)]
        if antigos:
            if afirmacao.com_horario:
                continue
            dado = max(antigos, key=lambda d: d.atualizado_em or instante)
            hora = horario_falado(dado.atualizado_em, tz) if dado.atualizado_em is not None else ""
            violacoes.append(Violacao("dado_vencido", afirmacao.frase, dado.id,
                                      _instrucao("dado_vencido", afirmacao.frase, hora)))
        else:
            violacoes.append(Violacao("dado_sem_fonte", afirmacao.frase, afirmacao.categoria,
                                      _instrucao("dado_sem_fonte", afirmacao.frase)))
        frases_vistas.add(afirmacao.frase)
    return violacoes
