"""Feriados nacionais do Brasil, calculados por formula -- nunca dependem do LLM
'lembrar' ou pesquisar a data certa (mesmo espirito de app.numeros: fato real e
deterministico, injetado pronto no prompt, ver app.llm.prompt_builder._contexto_atual).
"""

import datetime

_FERIADOS_NACIONAIS_FIXOS = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 25): "Natal",
}


def pascoa(ano: int) -> datetime.date:
    """Domingo de Pascoa do ano, pelo algoritmo anonimo gregoriano (Meeus/Jones/Butcher) --
    base pra calcular os feriados moveis (Carnaval, Sexta-feira Santa, Corpus Christi)."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(ano, mes, dia)


def feriados_nacionais(ano: int) -> dict[datetime.date, str]:
    """Feriados nacionais fixos + moveis de um ano. Inclui os estatutarios (Lei 662/1949 e
    alteracoes -- Confraternizacao, Tiradentes, Trabalho, Independencia, Nossa Senhora
    Aparecida, Finados, Proclamacao da Republica, Consciencia Negra desde a Lei 14.759/2023,
    Natal, Sexta-feira Santa) mais Pascoa, Carnaval e Corpus Christi -- estes tres ultimos sao
    ponto facultativo federal (nao feriado estatutario em todo municipio), mas culturalmente
    tratados como feriado por quase toda radio/comercio; o rotulo deixa a natureza clara pro
    locutor nao afirmar categoricamente 'hoje ninguem trabalha' quando nao e' garantido.
    """
    feriados = {datetime.date(ano, mes, dia): nome for (mes, dia), nome in _FERIADOS_NACIONAIS_FIXOS.items()}
    domingo_pascoa = pascoa(ano)
    feriados[domingo_pascoa] = "Páscoa"
    feriados[domingo_pascoa - datetime.timedelta(days=48)] = "Carnaval (ponto facultativo)"
    feriados[domingo_pascoa - datetime.timedelta(days=47)] = "Carnaval (ponto facultativo)"
    feriados[domingo_pascoa - datetime.timedelta(days=2)] = "Sexta-feira Santa"
    feriados[domingo_pascoa + datetime.timedelta(days=60)] = "Corpus Christi (ponto facultativo)"
    return feriados


def feriado_nacional_do_dia(data: datetime.date) -> str | None:
    return feriados_nacionais(data.year).get(data)
