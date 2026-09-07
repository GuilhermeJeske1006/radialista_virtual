import pytest

from app.numeros import numero_por_extenso, substituir_valores_monetarios, valor_monetario_por_extenso


@pytest.mark.parametrize(
    "numero,esperado",
    [
        (0, "zero"),
        (7, "sete"),
        (15, "quinze"),
        (23, "vinte e três"),
        (30, "trinta"),
        (99, "noventa e nove"),
        (100, "cem"),
        (101, "cento e um"),
        (200, "duzentos"),
        (235, "duzentos e trinta e cinco"),
        (1000, "mil"),
        (1001, "mil e um"),
        (2024, "dois mil e vinte e quatro"),
        (-5, "menos cinco"),
        (-100, "menos cem"),
    ],
)
def test_numero_por_extenso(numero, esperado):
    assert numero_por_extenso(numero) == esperado


@pytest.mark.parametrize(
    "reais,centavos,esperado",
    [
        (19, 90, "dezenove reais e noventa centavos"),
        (1, 0, "um real"),
        (2, 0, "dois reais"),
        (0, 50, "cinquenta centavos"),
        (0, 1, "um centavo"),
        (0, 0, "zero reais"),
        (100, 0, "cem reais"),
    ],
)
def test_valor_monetario_por_extenso(reais, centavos, esperado):
    assert valor_monetario_por_extenso(reais, centavos) == esperado


def test_substituir_valores_monetarios_com_centavos():
    resultado = substituir_valores_monetarios("So hoje por R$ 19,90!")
    assert resultado == "So hoje por dezenove reais e noventa centavos!"


def test_substituir_valores_monetarios_sem_centavos():
    resultado = substituir_valores_monetarios("Custa R$ 100 na loja.")
    assert resultado == "Custa cem reais na loja."


def test_substituir_valores_monetarios_com_separador_de_milhar():
    resultado = substituir_valores_monetarios("Combo por R$ 1.499,90.")
    assert resultado == "Combo por mil e quatrocentos e noventa e nove reais e noventa centavos."


def test_substituir_valores_monetarios_multiplas_ocorrencias():
    resultado = substituir_valores_monetarios("De R$ 39,90 por R$ 19,90.")
    assert resultado == "De trinta e nove reais e noventa centavos por dezenove reais e noventa centavos."


def test_substituir_valores_monetarios_sem_valor_nao_altera_texto():
    assert substituir_valores_monetarios("Sem preco nenhum aqui.") == "Sem preco nenhum aqui."
