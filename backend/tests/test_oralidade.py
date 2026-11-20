"""Verificador determinístico de oralidade (F7). Só aponta; não reescreve."""

import json
from pathlib import Path

from app.live.oralidade import LIMITE_PALAVRAS_FRASE, avisos

CASOS = Path(__file__).resolve().parents[2] / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"


def _regras(texto: str) -> set[str]:
    return {a.regra for a in avisos(texto)}


def test_fala_curta_e_limpa_nao_gera_aviso():
    assert avisos("Você está na Rádio Serra Clara. Agora, Rua das Acácias, com Duo Estrada Velha.") == []


def test_texto_vazio_nao_gera_aviso():
    assert avisos("") == []
    assert avisos("   ") == []


def test_frase_longa_passa_do_limite():
    frase = " ".join(["palavra"] * (LIMITE_PALAVRAS_FRASE + 1)) + "."
    assert "frase_longa" in _regras(frase)


def test_frase_no_limite_nao_e_longa():
    frase = " ".join(["palavra"] * LIMITE_PALAVRAS_FRASE) + "."
    assert "frase_longa" not in _regras(frase)


def test_mais_de_uma_ideia_com_dois_conectivos():
    texto = "Guardar sacola dentro de sacola parece bobagem, mas a casa que faz isso ganha espaço porque organiza tudo."
    assert "mais_de_uma_ideia" in _regras(texto)


def test_sigla_sem_expansao_aponta_na_primeira_ocorrencia_so():
    texto = "Quem precisa do CRAS pode procurar o CRAS do bairro."
    trechos = [a.trecho for a in avisos(texto) if a.regra == "sigla_sem_expansao"]
    assert trechos == ["CRAS"]


def test_sigla_com_expansao_entre_parenteses_antes_nao_aponta():
    texto = "Procure o Centro de Referência de Assistência Social (CRAS) do bairro."
    assert "sigla_sem_expansao" not in _regras(texto)


def test_sigla_com_expansao_entre_parenteses_depois_nao_aponta():
    texto = "Procure o CRAS (Centro de Referência de Assistência Social) do bairro."
    assert "sigla_sem_expansao" not in _regras(texto)


def test_sigla_falada_no_radio_nao_aponta():
    assert "sigla_sem_expansao" not in _regras("Vem aí a FM 101.")


def test_numero_em_digitos_longo():
    avisos_num = [a for a in avisos("Ligue 12345678 agora.") if a.regra == "numero_longo"]
    assert [a.trecho for a in avisos_num] == ["12345678"]


def test_numero_curto_em_digitos_nao_aponta():
    assert "numero_longo" not in _regras("Ligue 1234 agora.")


def test_numero_por_extenso_longo():
    texto = "Separe trezentos e quarenta e sete gramas de farinha."
    trechos = [a.trecho for a in avisos(texto) if a.regra == "numero_longo"]
    assert trechos == ["trezentos e quarenta e sete"]


def test_numero_por_extenso_curto_nao_aponta():
    assert "numero_longo" not in _regras("São vinte e três reais.")


def test_burocratico_municipalidade_e_realizara():
    texto = "Segundo a prefeitura, a municipalidade realizará intervenções viárias."
    regras = [a.regra for a in avisos(texto)]
    assert regras.count("burocratico") == 2


def test_burocratico_ignora_acento_e_caixa():
    assert "burocratico" in _regras("A MUNICIPALIDADE avisa.")


def test_casos_rotulados_do_benchmark_pegam_o_minimo_esperado():
    dados = json.loads(CASOS.read_text(encoding="utf-8"))
    positivos = [
        (f["texto"], f["esperado"]["avisos_oralidade_min"])
        for c in dados["casos"]
        for f in c["falas_rotuladas"]
        if f["esperado"].get("avisos_oralidade_min")
    ]
    assert len(positivos) == 4
    for texto, minimo in positivos:
        assert len(avisos(texto)) >= minimo, texto
