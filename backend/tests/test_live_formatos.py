"""Catálogo de formatos (F6): integridade, resolvedor, flags, unidade, direção, relógio e roteiro.

Numeração dos casos (U1-U9) em docs/melhoria-radio/f6/auditoria.md §8. Nesta leva o catálogo tem `padrao` e
`musical_adulto` (alias `musical_companhia`) implementados e os sete formatos futuros com `implementado=False`;
nenhum comportamento muda (os retratos de tests/test_live_formatos_caracterizacao.py continuam iguais).
"""

import ast
import dataclasses
import datetime
import json
import logging
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
    assert implementados == {"padrao", "musical_adulto"}
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
    ("router.py:2170 (tom do TTS)", "comportamento.tom_tts", None, "neutro"),
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

    assert orcamento.FORMATOS_APLICADOS == frozenset({"musical_adulto", "musical_companhia"})
    assert set(orcamento.ORCAMENTOS_POR_FORMATO) == {"padrao", "musical_adulto", "musical_companhia"}
    assert orcamento.ORCAMENTOS_POR_FORMATO["musical_companhia"] == {**ORCAMENTOS, "*": orcamento_fala("*")}
    assert orcamento.ORCAMENTOS_POR_FORMATO["musical_adulto"] == orcamento.ORCAMENTOS_POR_FORMATO["musical_companhia"]
    assert orcamento.ORCAMENTOS_POR_FORMATO["padrao"] == {"*": (15, 30, None)}
    assert orcamento.formato_do_programa(SimpleNamespace(perfil_programacao="musical_companhia")) == "musical_adulto"
    assert orcamento.formato_do_programa(SimpleNamespace(perfil_programacao="padrao")) == "padrao"


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
    ("abertura", True, "Receba o ouvinte e apresente o programa uma única vez.", (20, 30, 65)),
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


@pytest.mark.parametrize("perfil", ["padrao", "musical_adulto", "musical_companhia"])
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
