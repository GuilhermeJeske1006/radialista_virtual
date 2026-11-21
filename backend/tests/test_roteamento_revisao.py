"""Autonomia graduada (F12): roteamento por categoria e tema, e estado inicial do bloco."""

import pytest

from app.live.roteamento_revisao import (
    AUTOMATICO,
    ESTADO_AGUARDANDO,
    ESTADO_BLOQUEADO,
    ESTADO_NO_AR,
    PROIBIDO,
    REVISAO,
    estado_inicial,
    rotear,
)


@pytest.mark.parametrize("categoria", ["musica", "comentario", "chamada_ouvinte", "abertura", "vinheta"])
def test_categorias_comuns_vao_ao_ar_sozinhas(categoria):
    assert rotear(categoria, "Bom dia, gente, vamos com a música.") == AUTOMATICO


@pytest.mark.parametrize("categoria", ["plantao", "reporter", "entrevista"])
def test_categorias_de_revisao_passam_por_aprovacao(categoria):
    assert rotear(categoria, "Notícia comum") == REVISAO


@pytest.mark.parametrize("texto", [
    "Houve um acidente com vítimas fatais na BR.",
    "Um homicídio foi registrado no bairro.",
    "Caso de suicídio na cidade.",
])
def test_tema_delicado_no_texto_vai_para_revisao(texto):
    assert rotear("comentario", texto) == REVISAO


def test_topico_proibido_bloqueia_mesmo_em_categoria_automatica():
    assert rotear("comentario", "Vamos falar de política partidária hoje.", ["política partidária"]) == PROIBIDO


def test_proibido_tem_prioridade_sobre_revisao():
    assert rotear("plantao", "Tiroteio na zona norte", ["tiroteio"]) == PROIBIDO


def test_topico_proibido_ignora_acento_e_caixa():
    assert rotear("comentario", "FALAR DE POLITICA PARTIDARIA", ["política partidária"]) == PROIBIDO


def test_palavra_parecida_nao_dispara_tema_delicado():
    # "morteiro" e "mortefeita" não são o termo "morte" inteiro.
    assert rotear("comentario", "Um morteiro de festa junina.") == AUTOMATICO


@pytest.mark.parametrize("rota, estado", [
    (AUTOMATICO, ESTADO_NO_AR),
    (REVISAO, ESTADO_AGUARDANDO),
    (PROIBIDO, ESTADO_BLOQUEADO),
])
def test_estado_inicial_por_rota(rota, estado):
    assert estado_inicial(rota) == estado
