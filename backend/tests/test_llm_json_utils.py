import pytest

from app.llm.json_utils import extrair_json


def test_json_puro():
    assert extrair_json('{"acao": "guardar"}') == {"acao": "guardar"}


def test_json_com_fence_markdown_com_linguagem():
    texto = '```json\n{"acao": "musica"}\n```'
    assert extrair_json(texto) == {"acao": "musica"}


def test_json_com_fence_markdown_sem_linguagem():
    texto = '```\n{"acao": "abraco"}\n```'
    assert extrair_json(texto) == {"acao": "abraco"}


def test_json_com_espacos_ao_redor():
    texto = '   {"acao": "guardar"}   '
    assert extrair_json(texto) == {"acao": "guardar"}


def test_json_invalido_levanta_erro():
    with pytest.raises(Exception):
        extrair_json("isso nao e json")
