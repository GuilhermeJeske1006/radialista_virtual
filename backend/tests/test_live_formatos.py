"""Catálogo de formatos (F6): integridade, resolvedor, flags, unidade, direção, relógio e roteiro.

Numeração dos casos (U1-U9) em docs/melhoria-radio/f6/auditoria.md §8. O catálogo tem `padrao`, `musical_adulto`
(alias `musical_companhia`), `popular_sertanejo` e `variedades_leves` implementados (os dois últimos desde a leva 2,
tabela do §6.4) e os sete formatos futuros com `implementado=False`. `padrao` e o musical continuam iguais (os
retratos de tests/test_live_formatos_caracterizacao.py não mudam).
"""

import ast
import dataclasses
import datetime
import json
import logging
import math
import pathlib
import re
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.live import formatos as f
from app.live import relogio as r
from app.live.formato import ORCAMENTOS, ROTEIRO_MUSICAL, ROTEIRO_PADRAO, direcao_musical, orcamento_fala

BACKEND = pathlib.Path(__file__).resolve().parents[1]
GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "caracterizacao_formatos"
SP = ZoneInfo("America/Sao_Paulo")
FUTUROS = ("hits", "regional", "noturno", "religioso", "morning", "esportivo", "jornalistico")
MUSICAL, PADRAO = f.FORMATOS["musical_adulto"], f.FORMATOS["padrao"]
POPULAR, VARIEDADES = f.FORMATOS["popular_sertanejo"], f.FORMATOS["variedades_leves"]
NOVOS = (POPULAR, VARIEDADES)


# ---------------------------------------------------------------------------------------------------------
# U1: integridade do catálogo
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("formato", list(f.FORMATOS.values()), ids=list(f.FORMATOS))
def test_u1_campos_obrigatorios_e_unidades_coerentes(formato):
    assert formato.id and formato.id == formato.id.strip().lower()
    for campo in ("nome", "promessa", "conteudo", "conducao", "unidade_principal", "fonte"):
        assert getattr(formato, campo).strip(), (formato.id, campo)
    assert "*" in formato.unidades
    for papel, unidade in formato.unidades.items():
        assert 0 < unidade.min_s <= unidade.alvo_s <= unidade.max_s, (formato.id, papel)
        assert unidade.max_palavras is None or unidade.max_palavras > 0
    assert formato.relogio_padrao is None or formato.relogio_padrao in r.PRESETS
    assert set(formato.blocos_relogio) <= set(r.BLOCOS_POR_TIPO), formato.id
    assert formato.roteiro_padrao
    if formato.faixa_fala_pct is not None:
        assert 0 <= formato.faixa_fala_pct[0] < formato.faixa_fala_pct[1] <= 100
    if formato.direcao_cabecalho:
        assert "*" in formato.funcoes and formato.aplica_orcamento


def test_u1_implementados_e_futuros():
    implementados = {chave for chave, formato in f.FORMATOS.items() if formato.implementado}
    assert implementados == {"padrao", "musical_adulto", "popular_sertanejo", "variedades_leves", "flashback"}
    assert set(FUTUROS) <= set(f.FORMATOS)
    for chave in FUTUROS:
        futuro = f.FORMATOS[chave]
        assert not futuro.implementado
        assert futuro.promessa and futuro.conteudo and futuro.conducao and futuro.unidade_principal
        assert re.search(r"\d", futuro.unidade_principal), futuro.unidade_principal
        assert futuro.requer or chave == "hits"
    # A unidade principal dos futuros é a da pesquisa §3 / skill referencia-radio.
    assert f.FORMATOS["jornalistico"].relogio_padrao == "B" and "F5" in f.FORMATOS["jornalistico"].requer
    assert f.FORMATOS["morning"].relogio_padrao == "C"


# Tabela do §6.4 (mín / alvo / máx, em segundos); o papel ausente cai em "*".
UNIDADES_NOVOS = {
    "popular_sertanejo": {
        "abertura": (20, 40, 60), "retomada": (15, 25, 40), "identificacao": (3, 6, 10), "musica": (8, 15, 25),
        "chamada_ouvinte": (20, 40, 60), "comentario": (20, 35, 60), "encerramento": (15, 30, 45),
        "*": (20, 35, 60),
    },
    "variedades_leves": {
        "abertura": (30, 60, 90), "retomada": (15, 25, 40), "identificacao": (3, 6, 10), "musica": (8, 15, 25),
        "chamada_ouvinte": (20, 40, 60), "comentario": (20, 45, 60), "quadro": (60, 120, 180),
        "encerramento": (20, 35, 45), "*": (20, 35, 60),
    },
}


@pytest.mark.parametrize("formato", NOVOS, ids=[n.id for n in NOVOS])
def test_u1_formatos_novos_seguem_a_tabela_do_catalogo(formato):
    assert {papel: (u.min_s, u.alvo_s, u.max_s) for papel, u in formato.unidades.items()} == \
        UNIDADES_NOVOS[formato.id]
    assert all(u.max_palavras is None for u in formato.unidades.values())  # teto só pelo ritmo da voz
    assert formato.aplica_orcamento and formato.implementado and formato.aliases == ()
    assert formato.comportamento.ciclo == "padrao"
    assert set(formato.funcoes) == set(formato.unidades)
    assert formato.temas_revisao and formato.participacao and formato.direcao_cabecalho
    assert formato.reorientacao_s == {"popular_sertanejo": 1200, "variedades_leves": 900}[formato.id]
    assert formato.faixa_fala_pct == {"popular_sertanejo": (4.0, 20.0), "variedades_leves": (15.0, 45.0)}[formato.id]
    assert formato.relogio_padrao == {"popular_sertanejo": "A", "variedades_leves": "C"}[formato.id]


def test_u1_roteiros_e_blocos_do_relogio_dos_novos():
    assert POPULAR.roteiro_padrao == ("musica", "chamada_ouvinte", "musica", "comentario", "musica", "retomada")
    assert VARIEDADES.roteiro_padrao == ("musica", "comentario", "musica", "chamada_ouvinte", "musica", "retomada")
    assert POPULAR.blocos_relogio == {}
    assert VARIEDADES.blocos_relogio == {"quadro": "@quadro"}
    assert "@quadro" == r.BLOCOS_POR_TIPO["quadro"].bloco_padrao  # o quadro do relógio C vira o quadro fixo


def test_u1_temas_e_participacao_dos_novos():
    assert POPULAR.temas_revisao == ("luto em recado", "saúde e medicamento", "dívida, empréstimo e aposta",
                                     "política", "religião")
    assert VARIEDADES.temas_revisao == ("saúde", "finanças e investimento", "orientação jurídica e de consumo",
                                        "alimentação com promessa de saúde", "política", "religião")
    assert "recados e pedidos reais" in POPULAR.participacao.lower()
    assert "convite genérico" in POPULAR.participacao
    assert "pergunta do dia" in VARIEDADES.participacao.lower() and "respostas reais" in VARIEDADES.participacao


def test_u1_aliases_unicos_e_sem_colisao_com_ids():
    vistos: list[str] = []
    for formato in f.FORMATOS.values():
        vistos.extend(formato.aliases)
    assert len(vistos) == len(set(vistos))
    assert not set(vistos) & set(f.FORMATOS)
    assert f.FORMATOS["musical_adulto"].aliases == ("musical_companhia",)
    assert f.FORMATOS["padrao"].aliases == ()


def test_u1_roteiro_do_catalogo_e_classificado_por_prefixo_sem_llm(monkeypatch):
    """Nenhum bloco de roteiro do catálogo vai ao LLM de classificação nem ao hash de categoria (item 9)."""
    from app.config.redis_client import redis_client
    from app.live.router import _CACHE_CATEGORIA_CUSTOMIZADA, _categoria_bloco

    chamadas = []
    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", lambda tipo: chamadas.append(tipo) or "")
    for formato in f.FORMATOS.values():
        for bloco in formato.roteiro_padrao:
            assert _categoria_bloco(bloco)
    assert chamadas == []
    assert redis_client.hlen(_CACHE_CATEGORIA_CUSTOMIZADA) == 0


def test_u1_relogio_padrao_e_string_conferida_contra_os_presets():
    # O catálogo não importa app.live.relogio (grafo sem ciclo): o id do preset é string, conferido aqui.
    assert {formato.relogio_padrao for formato in f.FORMATOS.values()} - {None} <= set(r.PRESETS)
    assert MUSICAL.relogio_padrao == "A"


# ---------------------------------------------------------------------------------------------------------
# U2: resolvedor
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("valor, esperado", [
    ("musical_companhia", "musical_adulto"),
    ("musical_adulto", "musical_adulto"),
    (" Musical_Companhia ", "musical_adulto"),
    ("MUSICAL_ADULTO", "musical_adulto"),
    ("padrao", "padrao"),
    ("", "padrao"),
    ("   ", "padrao"),
    (None, "padrao"),
    ("inexistente", "padrao"),
    ("hits", "padrao"),
    ("jornalistico", "padrao"),
])
def test_u2_resolvedor(valor, esperado):
    assert f.resolver_formato(valor).id == esperado


def test_u2_nao_implementado_e_desconhecido_caem_no_padrao_com_log(caplog):
    with caplog.at_level(logging.INFO, logger="radialista.live.formatos"):
        assert f.resolver_formato("religioso") is PADRAO
        assert f.resolver_formato("formato_inventado") is PADRAO
    assert "formato_nao_implementado formato=religioso" in caplog.text
    assert "formato_desconhecido" in caplog.text


def test_u2_formato_do_programa():
    assert f.formato_do_programa(SimpleNamespace(perfil_programacao="musical_companhia")) is MUSICAL
    assert f.formato_do_programa(SimpleNamespace(perfil_programacao="musical_adulto")) is MUSICAL
    assert f.formato_do_programa(SimpleNamespace(perfil_programacao="padrao")) is PADRAO
    assert f.formato_do_programa(SimpleNamespace()) is PADRAO
    assert f.resolver_formato(MUSICAL) is MUSICAL


def test_u2_compatibilidade_de_formato_py():
    from app.live.formato import musical_companhia

    assert musical_companhia(SimpleNamespace(perfil_programacao="musical_companhia"))
    assert musical_companhia(SimpleNamespace(perfil_programacao="musical_adulto"))
    assert not musical_companhia(SimpleNamespace(perfil_programacao="padrao"))
    assert not musical_companhia(SimpleNamespace())


# ---------------------------------------------------------------------------------------------------------
# U3: flags = comportamento de hoje, item a item (auditoria §2, fato 2)
# ---------------------------------------------------------------------------------------------------------

# (onde no código, atributo do formato, valor no padrao, valor no musical)
FLAGS = [
    ("_tipo_proximo_bloco / tipo_na_posicao", "comportamento.ciclo", "padrao", "musical"),
    ("contexto.py:594, vinhetas/estrutura.py", "roteiro_padrao", ROTEIRO_PADRAO, ROTEIRO_MUSICAL),
    ("contexto.py:346 (multivoz)", "comportamento.multivoz", True, False),
    ("contexto.py:401 (música sem fala)", "comportamento.musica_sem_fala", False, True),
    ("contexto.py:610-617 (expressão, mudança de ideia, imperfeição)", "comportamento.naturalidade_encenada",
     True, False),
    ("contexto.py:628-631 (hora certa, marco)", "comportamento.hora_e_marco", True, False),
    ("contexto.py:642 (convite)", "comportamento.convite", "qualquer_bloco", "so_chamada"),
    ("contexto.py:692, geracao.py:258, router.py:2093 (uma faixa)", "comportamento.uma_faixa_por_bloco",
     False, True),
    ("router.py:2170 (tom do TTS por programa/bloco)", "comportamento.tom_tts", None, None),
    ("prompt_builder.py:400, router.py:745 (blocos extras)", "comportamento.ia_pode_adicionar_blocos", True, False),
    ("relogio.py:835, :868 (preenchimento)", "comportamento.preenchimento_relogio", True, False),
    ("router.py:748-753 (abertura depois do intervalo, D17)", "comportamento.abertura_apos_intervalo",
     False, False),
    ("orcamento.py:41, prompt_emissao.py:108, :576, router.py:2502", "aplica_orcamento", False, True),
    ("relogio.py:715-719 (blocos do relógio)", "blocos_relogio", {}, {
        "link": "retomada", "curadoria": "retomada", "conversa": "retomada", "quadro": "retomada",
        "entrevista": "retomada", "resumo": "retomada"}),
]


def _atributo(formato, caminho):
    valor = formato
    for parte in caminho.split("."):
        valor = getattr(valor, parte)
    return valor


@pytest.mark.parametrize("onde, caminho, no_padrao, no_musical", FLAGS, ids=[c[1] for c in FLAGS])
def test_u3_flags_reproduzem_o_comportamento_de_hoje(onde, caminho, no_padrao, no_musical):
    assert _atributo(PADRAO, caminho) == no_padrao, onde
    assert _atributo(MUSICAL, caminho) == no_musical, onde


def test_u3_flags_cobrem_todo_o_comportamento():
    cobertos = {c[1].split(".", 1)[1] for c in FLAGS if c[1].startswith("comportamento.")}
    assert cobertos == {campo.name for campo in dataclasses.fields(f.Comportamento)}


# Tabela do §6.4: comportamento dos formatos novos (popular, variedades).
FLAGS_NOVOS = {
    "ciclo": ("padrao", "padrao"),
    "musica_sem_fala": (False, False),
    "uma_faixa_por_bloco": (False, False),
    "multivoz": (True, True),
    "naturalidade_encenada": (True, True),
    "hora_e_marco": (True, True),
    "convite": ("qualquer_bloco", "so_chamada"),
    "tom_tts": (None, None),
    "ia_pode_adicionar_blocos": (True, True),
    "preenchimento_relogio": (True, True),
    "abertura_apos_intervalo": (True, True),
}


@pytest.mark.parametrize("campo", list(FLAGS_NOVOS))
def test_u3_flags_dos_formatos_novos(campo):
    assert (getattr(POPULAR.comportamento, campo), getattr(VARIEDADES.comportamento, campo)) == FLAGS_NOVOS[campo]
    assert set(FLAGS_NOVOS) == {campo.name for campo in dataclasses.fields(f.Comportamento)}


# RegraBloco.bloco_musical antes da F6 (relogio.py:289-312 em 5987eda), tipo de evento -> bloco.
_BLOCO_MUSICAL_ANTES = {
    "abertura": "abertura", "retomada": "retomada", "manchetes": "escalada", "musica": "musica",
    "link": "retomada", "curadoria": "retomada", "retorno": "chamada_ouvinte", "participacao": "chamada_ouvinte",
    "conversa": "retomada", "quadro": "retomada", "servico": "servico", "noticia": "noticia",
    "reportagem": "noticia", "atualizacao": "escalada", "entrevista": "retomada", "intervalo": "patrocinador",
    "identificacao": "identificacao", "encerramento": "encerramento", "resumo": "retomada",
}


def test_u3_blocos_do_relogio_sao_os_de_antes():
    assert set(r.BLOCOS_POR_TIPO) == set(_BLOCO_MUSICAL_ANTES)
    for tipo, regra in r.BLOCOS_POR_TIPO.items():
        assert MUSICAL.blocos_relogio.get(tipo, regra.bloco_padrao) == _BLOCO_MUSICAL_ANTES[tipo], tipo
        assert PADRAO.blocos_relogio.get(tipo, regra.bloco_padrao) == regra.bloco_padrao


# ---------------------------------------------------------------------------------------------------------
# U4: unidade e orcamento_para (musical, padrão, alias)
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("papel", [*ORCAMENTOS, "comentario", "noticia", "bloco desconhecido"])
@pytest.mark.parametrize("primeira", [False, True])
def test_u4_unidade_do_musical_igual_a_orcamentos(papel, primeira):
    minimo, maximo, palavras = orcamento_fala(papel, primeira)
    unidade = f.unidade(MUSICAL, papel, primeira)
    assert (unidade.min_s, unidade.max_s, unidade.max_palavras) == (minimo, maximo, palavras)
    assert unidade.alvo_s == (minimo + maximo) / 2
    assert type(unidade.min_s) is int and type(unidade.max_s) is int  # "20 a 30 segundos" no prompt, não 20.0
    assert f.unidade("musical_companhia", papel, primeira) == unidade


def test_u4_padrao_observa_15_a_30():
    assert f.unidade(PADRAO, "comentario", False) == f.Unidade(15, 22.5, 30, None)
    assert f.unidade(PADRAO, "abertura", True) == f.Unidade(15, 22.5, 30, None)


def test_u4_quadro_so_com_quadro_true():
    com_quadro = dataclasses.replace(MUSICAL, unidades={**MUSICAL.unidades, "quadro": f.Unidade(60, 120, 180)})
    # Quadro fixo com rótulo livre: o papel vem do programa (quadros_fixos), não do nome.
    assert f.unidade(com_quadro, "Receita da Vó", False, quadro=True) == f.Unidade(60, 120, 180)
    assert f.unidade(com_quadro, "Receita da Vó", False) == MUSICAL.unidades["*"]
    # Sem unidade de quadro no formato, quadro=True não muda nada (é o caso do musical).
    assert f.unidade(MUSICAL, "Receita da Vó", False, quadro=True) == MUSICAL.unidades["*"]


def test_u4_orcamento_para_alias_e_canonico_iguais_em_toda_a_tabela():
    from test_live_formatos_caracterizacao import tabela_de_orcamento

    gravado = json.loads((GOLDEN / "orcamento_para.json").read_text(encoding="utf-8"))
    canonico = tabela_de_orcamento(("musical_adulto",))
    assert canonico == {chave.replace("musical_companhia|", "musical_adulto|"): valor
                        for chave, valor in gravado.items() if chave.startswith("musical_companhia|")}


def test_u4_orcamento_para_com_teto_e_quadro():
    from app.live.orcamento import orcamento_para

    musical = orcamento_para("musical_adulto", "encerramento", False, teto_relogio_s=14)
    assert (musical.min_s, musical.max_s, musical.fonte) == (10, 14, "relogio")
    assert orcamento_para(MUSICAL, "retomada", False) == orcamento_para("musical_companhia", "retomada", False)
    assert orcamento_para("musical_adulto", "Quadro da Receita", False, quadro=True) == \
        orcamento_para("musical_adulto", "Quadro da Receita", False)


def test_u4_tabelas_de_orcamento_derivadas_do_catalogo():
    from app.live import orcamento

    assert orcamento.FORMATOS_APLICADOS == frozenset({"musical_adulto", "musical_companhia", "popular_sertanejo",
                                                      "variedades_leves", "flashback"})
    assert set(orcamento.ORCAMENTOS_POR_FORMATO) == {"padrao", "musical_adulto", "musical_companhia",
                                                     "popular_sertanejo", "variedades_leves", "flashback"}
    assert orcamento.ORCAMENTOS_POR_FORMATO["musical_companhia"] == {**ORCAMENTOS, "*": orcamento_fala("*")}
    assert orcamento.ORCAMENTOS_POR_FORMATO["musical_adulto"] == orcamento.ORCAMENTOS_POR_FORMATO["musical_companhia"]
    assert orcamento.ORCAMENTOS_POR_FORMATO["padrao"] == {"*": (15, 30, None)}
    assert orcamento.formato_do_programa(SimpleNamespace(perfil_programacao="musical_companhia")) == "musical_adulto"
    assert orcamento.formato_do_programa(SimpleNamespace(perfil_programacao="padrao")) == "padrao"


@pytest.mark.parametrize("formato", NOVOS, ids=[n.id for n in NOVOS])
@pytest.mark.parametrize("tipo, primeira", [("comentario", False), ("chamada_ouvinte", False), ("abertura", True),
                                            ("abertura", False), ("musica", False), ("encerramento", False),
                                            ("bloco livre", False)])
def test_u4_novos_aplicados_sem_relogio_pela_unidade_do_papel(formato, tipo, primeira):
    from app.live.orcamento import orcamento_para

    orcamento = orcamento_para(formato.id, tipo, primeira)
    papel = f.papel_do_bloco(formato, tipo, primeira)
    u = UNIDADES_NOVOS[formato.id][papel]
    assert (orcamento.min_s, orcamento.alvo_s, orcamento.max_s) == u
    assert (orcamento.fonte, orcamento.aplicar, orcamento.max_palavras) == ("formato", True, None)


def test_u4_quadro_do_variedades_so_com_quadro_fixo():
    from app.live.orcamento import orcamento_para

    quadro = orcamento_para("variedades_leves", "Cantinho da Casa", False, quadro=True)
    assert (quadro.min_s, quadro.max_s, quadro.fonte) == (60, 180, "formato")
    # Nome de bloco com "Quadro" sem ser quadro fixo do programa não é quadro (§6.3).
    assert f.papel_do_bloco(VARIEDADES, "Quadro da Receita", False) == "*"
    assert f.papel_do_bloco(VARIEDADES, "Quadro da Receita", False, quadro=True) == "quadro"
    assert orcamento_para("variedades_leves", "Quadro da Receita", False).max_s == 60
    # O popular não declara quadro: o quadro fixo segue o papel do nome (ou "*").
    assert orcamento_para("popular_sertanejo", "Cantinho da Casa", False, quadro=True).max_s == 60
    # Com o teto do relógio, o quadro fica limitado pela etapa.
    apertado = orcamento_para("variedades_leves", "Cantinho da Casa", False, teto_relogio_s=90, minimo_relogio_s=60,
                              quadro=True)
    assert (apertado.min_s, apertado.max_s, apertado.fonte) == (60, 90, "relogio")


def test_u4_fonte_e_eh_quadro_fixo():
    programa = SimpleNamespace(quadros_fixos={"Cantinho da Casa": ["gavetas"], "Vazio": []})
    assert f.eh_quadro_fixo(programa, "Cantinho da Casa")
    assert not f.eh_quadro_fixo(programa, "Vazio") and not f.eh_quadro_fixo(programa, "comentario")
    assert not f.eh_quadro_fixo(SimpleNamespace(), "Cantinho da Casa")


# ---------------------------------------------------------------------------------------------------------
# U5: direcao_formato
# ---------------------------------------------------------------------------------------------------------

_PREFIXO_MUSICAL = "FORMATO MUSICAL DE COMPANHIA: a música ocupa o centro do programa. "
_SUFIXO_MUSICAL = (
    " Esta duração substitui a orientação genérica de quatro a seis frases. "
    "Fale com proximidade e energia moderada; use português coloquial, sem linguagem de publicidade "
    "genérica, adjetivos em série, hesitações encenadas ou risadas obrigatórias. "
    "Não acrescente assunto, hora, clima, pergunta, convite ao WhatsApp ou gancho só para preencher. "
    "Não anuncie cada música da sequência, não peça [BLOCO_MUSICAS:N] e não invente vinhetas. "
    "Não prometa intervalo, retorno ou conteúdo futuro sem programação confirmada. "
    "Mantenha as regras factuais e de atendimento dos pedidos reais."
)
_RETOMADA = "Faça uma retomada breve; o programa já está em andamento."


@pytest.mark.parametrize("tipo, primeira, funcao, meta", [
    ("abertura", True, "Receba o ouvinte e apresente o programa uma única vez, com a companhia que a música faz. "
     "Não prometa retorno nem intervalo ('daqui a pouco', 'meia hora', 'depois do intervalo'): a "
     "abertura chega ao tamanho da unidade só com apresentação e o que o ouvinte vai ouvir agora.", (20, 30, 65)),
    ("Abertura", False, _RETOMADA, (6, 12, 25)),
    ("retomada", False, _RETOMADA, (6, 12, 25)),
    ("identificação", False, "Diga apenas o nome da rádio ou do programa e uma assinatura curta.", (3, 7, 14)),
    ("musica", False, "Anuncie brevemente a faixa confirmada e o pedido real, quando fornecido.", (4, 8, 18)),
    ("encerramento", False, "Despeça-se do programa. Não prometa retorno após intervalo.", (10, 18, 38)),
    ("comentario", False, "Cumpra somente a função deste bloco, de forma breve.", (10, 20, 45)),
    ("chamada_ouvinte", True, "Cumpra somente a função deste bloco, de forma breve.", (10, 20, 45)),
])
def test_u5_direcao_do_musical_byte_a_byte(tipo, primeira, funcao, meta):
    minimo, maximo, palavras = meta
    esperado = (f"{_PREFIXO_MUSICAL}{funcao} Meta de locução: {minimo} a {maximo} segundos, "
                f"no máximo {palavras} palavras.{_SUFIXO_MUSICAL}")
    for formato in (MUSICAL, "musical_adulto", "musical_companhia"):
        assert f.direcao_formato(formato, tipo, primeira) == esperado
    assert direcao_musical(tipo, primeira) == esperado
    apertado = esperado.replace(f"{minimo} a {maximo} segundos, no máximo {palavras} palavras",
                                "5 a 9 segundos, no máximo 21 palavras")
    assert f.direcao_formato(MUSICAL, tipo, primeira, orcamento=(5, 9, 21)) == apertado
    assert direcao_musical(tipo, primeira, orcamento=(5, 9, 21)) == apertado


def test_u5_padrao_sem_direcao_e_meta_legivel_pelo_duble():
    from scripts.simulacao.dubles import META_BLOCO_RE

    assert f.direcao_formato(PADRAO, "comentario", False) == ""
    assert f.direcao_formato("padrao", "abertura", True) == ""
    assert META_BLOCO_RE.search(f.direcao_formato(MUSICAL, "retomada", False))


_PALAVRAS_EM_MAIUSCULA_PERMITIDAS = {"POPULAR/SERTANEJO", "VARIEDADES", "LEVES", "WhatsApp"}


@pytest.mark.parametrize("formato", NOVOS, ids=[n.id for n in NOVOS])
@pytest.mark.parametrize("tipo, primeira, quadro", [
    ("abertura", True, False), ("retomada", False, False), ("identificacao", False, False), ("musica", False, False),
    ("chamada_ouvinte", False, False), ("comentario", False, False), ("Cantinho da Casa", False, True),
    ("encerramento", False, False),
])
def test_u5_direcao_dos_novos(formato, tipo, primeira, quadro):
    from scripts.simulacao.dubles import META_BLOCO_RE

    direcao = f.direcao_formato(formato, tipo, primeira, orcamento=(20, 60, 150), quadro=quadro)
    assert direcao.startswith(formato.direcao_cabecalho)
    assert META_BLOCO_RE.search(direcao).groups() == ("20", "60", "150")
    assert formato.conducao.rstrip(".").lower() in direcao.lower()
    assert f.REGRA_PROMESSA in direcao and f.REGRA_FACTUAL in direcao
    papel = f.papel_do_bloco(formato, tipo, primeira, quadro)
    assert formato.funcoes[papel] in direcao
    for proibido in ("4 a 6 frases", "quatro a seis frases", "MUSICAL", "Caio", "Zeca", "Ze do Radio"):
        assert proibido not in direcao, proibido
    # Nenhum nome próprio (de apresentador, emissora ou ouvinte) além do cabeçalho do formato e do canal.
    maiusculas = {palavra.strip(",.;:()") for frase in re.split(r"[.:;]\s+", direcao)
                  for palavra in frase.split()[1:] if palavra[:1].isupper()}
    assert maiusculas <= _PALAVRAS_EM_MAIUSCULA_PERMITIDAS, maiusculas


def test_u5_sem_orcamento_a_meta_dos_novos_vem_da_unidade():
    direcao = f.direcao_formato(POPULAR, "comentario")
    assert "Meta de locução: 20 a 60 segundos." in direcao and "no máximo" not in direcao
    quadro = f.direcao_formato(VARIEDADES, "Cantinho da Casa", quadro=True)
    assert "Meta de locução: 60 a 180 segundos." in quadro and VARIEDADES.funcoes["quadro"] in quadro


def test_u5_mesmo_papel_dirige_diferente_em_cada_formato():
    for tipo, primeira in (("abertura", True), ("retomada", False), ("identificacao", False), ("musica", False),
                           ("chamada_ouvinte", False), ("comentario", False), ("encerramento", False)):
        textos = {formato.id: f.direcao_formato(formato, tipo, primeira, orcamento=(10, 20, 40))
                  for formato in (MUSICAL, POPULAR, VARIEDADES)}
        assert len(set(textos.values())) == 3, tipo


def test_u5_texto_do_catalogo_nao_cita_emissora_nem_apresentador_real():
    texto = json.dumps([dataclasses.asdict(formato) for formato in f.FORMATOS.values()], ensure_ascii=False,
                       default=str).lower()
    for nome in ("cbn", "alpha fm", "antena 1", "pretinho", "hora do ronco", "nativa", "itatiaia", "capital",
                 "heart", "canção nova"):
        assert nome not in texto, nome


# ---------------------------------------------------------------------------------------------------------
# U7: relógio
# ---------------------------------------------------------------------------------------------------------

def _programa_relogio():
    return SimpleNamespace(id=1, horario_inicio=datetime.time(14, 0), horario_fim=datetime.time(15, 0),
                           dias_semana=[], data_especifica=None, feriados_municipais=[], relogio_hora=None)


def test_u7_planejar_com_formato_igual_ao_booleano_na_grade_inteira():
    from test_live_formatos_caracterizacao import EXECUTADAS, PECAS, grade_do_relogio

    def por_formato(preset, musical, pecas, executadas, segundo):
        instante = datetime.datetime(2026, 11, 10, 14, 0, tzinfo=SP) + datetime.timedelta(seconds=segundo)
        return r.planejar(_programa_relogio(), r.PRESETS[preset], "America/Sao_Paulo", instante,
                          formato=MUSICAL if musical else PADRAO, ultima_categoria="musica", ja_encerrou=False,
                          executadas=set(EXECUTADAS[executadas]), pecas=PECAS[pecas])

    gravado = json.loads((GOLDEN / "relogio_planos.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(grade_do_relogio(por_formato))) == gravado


def _planejar(instante, formato=None, executadas=(), **extra):
    pecas = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0), r.Peca(6, 20.0)), vinheta_encerramento_s=3.0)
    if formato is not None:
        extra["formato"] = formato
    return r.planejar(_programa_relogio(), r.PRESETS["A"], "America/Sao_Paulo", instante, ultima_categoria="musica",
                      ja_encerrou=False, executadas=set(executadas), pecas=pecas, **extra)


def test_u7_sem_formato_e_sem_booleano_e_o_padrao():
    instante = datetime.datetime(2026, 11, 10, 14, 12, tzinfo=SP)
    feito = ("0:0:fala:abertura",)
    assert _planejar(instante, executadas=feito) == _planejar(instante, PADRAO, feito)
    assert _planejar(instante, executadas=feito, formato_musical=True) == _planejar(instante, MUSICAL, feito)
    assert _planejar(instante, MUSICAL, feito).tipo_bloco == "retomada"


def test_u7_preenchimento_pela_flag():
    instante = datetime.datetime(2026, 11, 10, 14, 20, tzinfo=SP)  # 240 s antes do intervalo de 14:24
    feito = ("0:0:fala:abertura", "0:720", "0:755:reserva")
    assert (_planejar(instante, PADRAO, feito).alternativa.acao,
            _planejar(instante, PADRAO, feito).alternativa.tipo_bloco) == ("reserva", "comentario")
    sem = dataclasses.replace(PADRAO, comportamento=dataclasses.replace(PADRAO.comportamento,
                                                                         preenchimento_relogio=False))
    assert _planejar(instante, sem, feito).alternativa.acao == "adiantamento"


def test_u7_unidade_do_formato_vence_a_do_relogio_d8():
    """Com aplica_orcamento, a unidade é a do formato (limitada pela etapa e pelo espaço), não o menor dos dois."""
    instante = datetime.datetime(2026, 11, 10, 14, 12, tzinfo=SP)  # link de 12:00 do relógio A (35 s)
    feito = ("0:0:fala:abertura",)
    largo = dataclasses.replace(MUSICAL, unidades={**MUSICAL.unidades, "retomada": f.Unidade(20, 30, 40, 90)})
    plano = _planejar(instante, largo, feito)
    assert (plano.tipo_bloco, plano.orcamento_s) == ("retomada", (20, 35))  # etapa de 35 s limita o máximo
    assert plano.palavras_max <= 90


def test_u7_popular_no_link_de_a_e_comentario_de_20_a_35():
    instante = datetime.datetime(2026, 11, 10, 14, 12, tzinfo=SP)  # link de 12:00 do relógio A (35 s)
    feito = ("0:0:fala:abertura",)
    popular = _planejar(instante, POPULAR, feito)
    # A etapa de 35 s limita a unidade de comentário do popular (20 a 60 s): fala reduzida pela etapa (D8).
    assert (popular.tipo_bloco, popular.acao, popular.orcamento_s) == ("comentario", "fala_reduzida", (20, 35))
    assert popular.palavras_max == math.floor(35 * r.CONFIG_PADRAO.wpm / 60)
    assert (_planejar(instante, MUSICAL, feito).tipo_bloco, _planejar(instante, MUSICAL, feito).orcamento_s) == \
        ("retomada", (6, 12))
    assert _planejar(instante, PADRAO, feito).orcamento_s == (10, 35)
    retorno = _planejar(datetime.datetime(2026, 11, 10, 14, 27, tzinfo=SP), POPULAR,
                        (*feito, "0:720", "0:1440:patrocinador:5", "0:1440:patrocinador:6"))
    assert (retorno.tipo_bloco, retorno.orcamento_s) == ("chamada_ouvinte", (20, 60))


def _planejar_c(instante, formato, executadas=(), quadros=("Cantinho da Casa",)):
    pecas = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),), quadros=quadros, tem_fonte_noticia=False)
    return r.planejar(_programa_relogio(), r.PRESETS["C"], "America/Sao_Paulo", instante, formato=formato,
                      ultima_categoria="musica", ja_encerrou=False, executadas=set(executadas), pecas=pecas)


def test_u7_variedades_no_quadro_de_c():
    instante = datetime.datetime(2026, 11, 10, 14, 44, tzinfo=SP)  # quadro de 44:00 do relógio C (360 s)
    feito = ("0:0:fala:abertura", "0:600", "0:1140", "0:2040", "0:960:patrocinador:5", "0:2460:patrocinador:5")
    plano = _planejar_c(instante, VARIEDADES, feito)
    assert (plano.etapa.tipo_efetivo, plano.tipo_bloco, plano.orcamento_s) == ("quadro", "Cantinho da Casa", (60, 180))
    sem_quadro = _planejar_c(instante, VARIEDADES, feito, quadros=())
    assert (sem_quadro.tipo_bloco, sem_quadro.orcamento_s) == ("comentario", (20, 60))
    padrao = _planejar_c(instante, PADRAO, feito)
    assert (padrao.tipo_bloco, padrao.orcamento_s) == ("Cantinho da Casa", (60, 180))  # UNIDADES_PADRAO do quadro
    assert _planejar_c(instante, MUSICAL, feito).tipo_bloco == "retomada"


def relogio_efetivo(formato, preset: str) -> tuple:
    """Sequência de (etapa, tipo_bloco, orcamento_s) numa hora, amostrada a cada 7 s, sem repetição seguida."""
    pecas = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),), quadros=("Cantinho da Casa",),
                               tem_fonte_noticia=True)
    sequencia: list[tuple] = []
    for segundo in range(0, 3600, 7):
        instante = datetime.datetime(2026, 11, 10, 14, 0, tzinfo=SP) + datetime.timedelta(seconds=segundo)
        plano = r.planejar(_programa_relogio(), r.PRESETS[preset], "America/Sao_Paulo", instante, formato=formato,
                           ultima_categoria="musica", ja_encerrou=False, executadas=set(), pecas=pecas)
        item = (plano.etapa.chave, plano.tipo_bloco, plano.orcamento_s)
        if not sequencia or sequencia[-1] != item:
            sequencia.append(item)
    return tuple(sequencia)


def test_u7_relogio_efetivo_distinto_dois_a_dois_com_o_relogio_padrao_de_cada_formato():
    efetivos = {formato.id: relogio_efetivo(formato, formato.relogio_padrao) for formato in (MUSICAL, *NOVOS)}
    assert (MUSICAL.relogio_padrao, POPULAR.relogio_padrao, VARIEDADES.relogio_padrao) == ("A", "A", "C")
    ids = list(efetivos)
    for i, primeiro in enumerate(ids):
        for segundo in ids[i + 1:]:
            assert efetivos[primeiro] != efetivos[segundo], (primeiro, segundo)
    # Mesmo preset (A), relógio efetivo diferente: o link do popular é comentário, o do musical é retomada.
    assert {b for _, b, _ in efetivos["musical_adulto"]} != {b for _, b, _ in efetivos["popular_sertanejo"]}


@pytest.mark.parametrize("preset", ["A", "B", "C"])
@pytest.mark.parametrize("chave", [chave for chave, formato in f.FORMATOS.items() if formato.implementado])
def test_u7_nenhum_plano_abaixo_do_minimo_em_cada_formato(preset, chave):
    pecas = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),), tem_fonte_noticia=True)
    for segundo in range(0, 3620, 7):
        instante = datetime.datetime(2026, 11, 10, 14, 0, tzinfo=SP) + datetime.timedelta(seconds=segundo)
        plano = r.planejar(_programa_relogio(), r.PRESETS[preset], "America/Sao_Paulo", instante,
                           formato=f.FORMATOS[chave], ultima_categoria="musica", ja_encerrou=False, executadas=set(),
                           pecas=pecas)
        for candidato in (plano, plano.alternativa):
            if candidato is not None and candidato.orcamento_s is not None:
                assert candidato.orcamento_s[1] >= candidato.orcamento_s[0], (segundo, candidato.tipo_bloco)


# ---------------------------------------------------------------------------------------------------------
# U8: roteiro (padrão e musical; os formatos novos entram na leva 2)
# ---------------------------------------------------------------------------------------------------------

def _programa(**extra):
    campos = dict(id=1, estrutura_blocos=[], perfil_programacao="padrao", ia_pode_adicionar_blocos=False,
                  quadros_fixos={})
    campos.update(extra)
    return SimpleNamespace(**campos)


def _categoria(tipo):
    from app.live.relogio import _categoria_simples
    return _categoria_simples(tipo)


@pytest.mark.parametrize("perfil", ["padrao", "musical_adulto", "musical_companhia", "popular_sertanejo",
                                    "variedades_leves"])
def test_u8_roteiro_vazio_e_o_do_formato(perfil):
    from app.live.roteiro import tipo_na_posicao
    from app.live.router import _tipo_proximo_bloco
    from app.vinhetas.estrutura import roteiro_base

    programa = _programa(perfil_programacao=perfil)
    roteiro = f.resolver_formato(perfil).roteiro_padrao
    assert roteiro_base(programa) == list(roteiro)
    esperado = [roteiro[(p - 1) % len(roteiro)] for p in range(1, 13)]
    assert [tipo_na_posicao(programa, p, _categoria) for p in range(1, 13)] == esperado
    assert [_tipo_proximo_bloco(programa, p, "musica") for p in range(1, 13)] == esperado
    assert _tipo_proximo_bloco(programa, 0, None) == "abertura"


def test_u8_alias_e_canonico_dao_o_mesmo_roteiro_na_tabela_c2(monkeypatch):
    from test_live_formatos_caracterizacao import ESTRUTURAS, ULTIMAS
    from app.live.roteiro import tipo_na_posicao
    from app.live.router import _categoria_bloco, _tipo_proximo_bloco

    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", lambda tipo: "comentario")
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.5)
    for estrutura in ESTRUTURAS.values():
        for ia in (False, True):
            alias = _programa(estrutura_blocos=estrutura, perfil_programacao="musical_companhia",
                              ia_pode_adicionar_blocos=ia)
            canonico = _programa(estrutura_blocos=estrutura, perfil_programacao="musical_adulto",
                                 ia_pode_adicionar_blocos=ia)
            for posicao in range(21):
                assert tipo_na_posicao(alias, posicao, _categoria_bloco) == \
                    tipo_na_posicao(canonico, posicao, _categoria_bloco)
                for ultima in ULTIMAS:
                    assert _tipo_proximo_bloco(alias, posicao, ultima) == _tipo_proximo_bloco(canonico, posicao, ultima)


def test_u8_abertura_depois_do_intervalo_pela_flag(monkeypatch):
    """D17: o padrão continua trocando a abertura fora de lugar por comentário depois do patrocinador; um formato
    com `abertura_apos_intervalo` a aceita (os formatos novos da leva 2)."""
    from app.live.router import _tipo_proximo_bloco

    programa = _programa(estrutura_blocos=["musica", "patrocinador:7", "abertura", "comentario"])
    assert _tipo_proximo_bloco(programa, 2, "patrocinador") == "comentario"
    assert _tipo_proximo_bloco(programa, 2, "comentario") == "comentario"
    assert _tipo_proximo_bloco(programa, 2, "musica") == "abertura"
    com_flag = dataclasses.replace(PADRAO, comportamento=dataclasses.replace(PADRAO.comportamento,
                                                                              abertura_apos_intervalo=True))
    monkeypatch.setattr("app.live.router.formato_do_programa", lambda programa: com_flag)
    assert _tipo_proximo_bloco(programa, 2, "patrocinador") == "abertura"
    assert _tipo_proximo_bloco(programa, 2, "comentario") == "comentario"


@pytest.mark.parametrize("perfil", ["popular_sertanejo", "variedades_leves"])
def test_u8_abertura_depois_do_intervalo_permitida_nos_novos(perfil):
    """D17 (pendência da F0): no popular e no variedades a abertura da volta sobrevive ao patrocinador; o padrão
    continua igual (troca por comentário)."""
    from app.live.roteiro import tipo_na_posicao
    from app.live.router import _tipo_proximo_bloco

    estrutura = ["musica", "patrocinador:7", "abertura", "comentario"]
    novo, padrao = _programa(estrutura_blocos=estrutura, perfil_programacao=perfil), _programa(estrutura_blocos=estrutura)
    assert _tipo_proximo_bloco(novo, 2, "patrocinador") == "abertura"
    assert _tipo_proximo_bloco(padrao, 2, "patrocinador") == "comentario"
    for ultima in ("musica", "vinheta", None):
        assert _tipo_proximo_bloco(novo, 2, ultima) == _tipo_proximo_bloco(padrao, 2, ultima) == "abertura"
    assert _tipo_proximo_bloco(novo, 2, "comentario") == "comentario"
    assert [tipo_na_posicao(novo, p, _categoria) for p in range(9)] == \
        [tipo_na_posicao(padrao, p, _categoria) for p in range(9)]


@pytest.mark.parametrize("perfil", ["popular_sertanejo", "variedades_leves"])
def test_u8_novos_respeitam_a_flag_de_blocos_extras_do_programa(perfil, monkeypatch):
    """D23: só o musical ignora `ia_pode_adicionar_blocos`; os novos sorteiam o comentário extra como o padrão."""
    from app.live.router import _tipo_proximo_bloco

    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)
    estrutura = ["musica", "noticia"]
    assert _tipo_proximo_bloco(_programa(estrutura_blocos=estrutura, perfil_programacao=perfil,
                                         ia_pode_adicionar_blocos=True), 1, "musica") == "comentario"
    assert _tipo_proximo_bloco(_programa(estrutura_blocos=estrutura, perfil_programacao=perfil), 1, "musica") == \
        "noticia"


def test_u8_blocos_extras_pela_flag_do_formato(monkeypatch):
    """D23: só o formato que não aceita blocos extras ignora `ia_pode_adicionar_blocos` (sem sortear)."""
    from app.live.router import _tipo_proximo_bloco

    sorteios = []
    monkeypatch.setattr("app.live.router.random.random", lambda: sorteios.append(1) or 0.0)
    programa = _programa(estrutura_blocos=["musica", "noticia"], ia_pode_adicionar_blocos=True)
    assert _tipo_proximo_bloco(programa, 1, "musica") == "comentario" and sorteios == [1]
    sem = dataclasses.replace(PADRAO, comportamento=dataclasses.replace(PADRAO.comportamento,
                                                                         ia_pode_adicionar_blocos=False))
    monkeypatch.setattr("app.live.router.formato_do_programa", lambda programa: sem)
    assert _tipo_proximo_bloco(programa, 1, "musica") == "noticia" and sorteios == [1]


# ---------------------------------------------------------------------------------------------------------
# Contexto e entrada: o formato entra no fim, o booleano fica derivado (D12)
# ---------------------------------------------------------------------------------------------------------

def test_entrada_e_contexto_derivam_o_booleano_do_formato():
    from app.live.contexto import ContextoEmissao
    from app.live.roteiro import EntradaEmissao

    for classe in (EntradaEmissao, ContextoEmissao):
        nomes = [campo.name for campo in dataclasses.fields(classe)]
        assert nomes[-1] == "formato" and "formato_musical" in nomes
    base = dict(request_id="t", db=None, account=None, radialista=None, programa=None, dados=None, total_falas=0,
                voz_programa=None, ritmos_voz=None, cfg_relogio=r.CONFIG_PADRAO)
    assert EntradaEmissao(**base, formato_musical=False).formato is PADRAO
    assert EntradaEmissao(**base, formato_musical=True).formato is MUSICAL
    derivada = EntradaEmissao(**base, formato_musical=False, formato=MUSICAL)
    assert derivada.formato_musical is True and derivada.formato is MUSICAL


# ---------------------------------------------------------------------------------------------------------
# U9 e risco 1 do §10: pureza e nenhuma comparação de string crua
# ---------------------------------------------------------------------------------------------------------

def test_u9_formatos_e_puro():
    arvore = ast.parse((BACKEND / "app" / "live" / "formatos.py").read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
        elif isinstance(no, ast.Import):
            importados.update(a.name for a in no.names)
    proibidos = ("app.live.router", "app.live.relogio", "app.live.orcamento", "app.models", "app.db", "sqlalchemy",
                 "redis", "app.config.redis_client", "app.config.settings", "app.llm", "fastapi")
    assert not [nome for nome in importados if nome.startswith(proibidos)], importados


_STRING_CRUA_PERMITIDA = {"app/live/formatos.py", "app/live/formato.py"}


def test_risco_1_nenhuma_comparacao_de_string_crua_do_musical():
    achados = []
    for pasta in ("app", "scripts"):
        for arquivo in sorted((BACKEND / pasta).rglob("*.py")):
            relativo = arquivo.relative_to(BACKEND).as_posix()
            if relativo in _STRING_CRUA_PERMITIDA:
                continue
            for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(r"""["']musical_companhia["']""", linha):
                    achados.append(f"{relativo}:{numero}")
    assert achados == []
