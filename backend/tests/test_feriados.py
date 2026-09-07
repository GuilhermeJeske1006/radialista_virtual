import datetime

import pytest

from app.feriados import feriado_nacional_do_dia, feriados_nacionais, pascoa


@pytest.mark.parametrize(
    "ano,esperado",
    [
        (2024, datetime.date(2024, 3, 31)),
        (2025, datetime.date(2025, 4, 20)),
        (2026, datetime.date(2026, 4, 5)),
        (2027, datetime.date(2027, 3, 28)),
    ],
)
def test_pascoa_datas_conhecidas(ano, esperado):
    assert pascoa(ano) == esperado


def test_feriados_fixos_presentes():
    feriados = feriados_nacionais(2026)
    assert feriados[datetime.date(2026, 1, 1)] == "Confraternização Universal"
    assert feriados[datetime.date(2026, 9, 7)] == "Independência do Brasil"
    assert feriados[datetime.date(2026, 11, 20)] == "Dia Nacional de Zumbi e da Consciência Negra"
    assert feriados[datetime.date(2026, 12, 25)] == "Natal"


def test_feriados_moveis_relativos_a_pascoa():
    feriados = feriados_nacionais(2026)
    domingo_pascoa = pascoa(2026)
    assert feriados[domingo_pascoa] == "Páscoa"
    assert feriados[domingo_pascoa - datetime.timedelta(days=2)] == "Sexta-feira Santa"
    assert feriados[domingo_pascoa - datetime.timedelta(days=47)].startswith("Carnaval")
    assert feriados[domingo_pascoa - datetime.timedelta(days=48)].startswith("Carnaval")
    assert feriados[domingo_pascoa + datetime.timedelta(days=60)].startswith("Corpus Christi")


def test_feriado_nacional_do_dia_encontra_feriado():
    assert feriado_nacional_do_dia(datetime.date(2026, 9, 7)) == "Independência do Brasil"


def test_feriado_nacional_do_dia_none_em_dia_comum():
    assert feriado_nacional_do_dia(datetime.date(2026, 8, 10)) is None
