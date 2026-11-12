"""Participação de verdade (F4): "toca agora" só com pedido selecionado e nenhum ouvinte inexistente
(app.live.participacao). Casos U7 e U8 da auditoria (docs/melhoria-radio/f4/auditoria.md §8). Nomes e falas
fictícios e originais.
"""

import json
import pathlib
from types import SimpleNamespace

import pytest

from app.live import participacao as pa
from app.live.contexto import MusicaRef
from app.live.validacao_fala import Violacao, remover_frases

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CASOS = RAIZ / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "programas"
EXCLUIDOS = ("Rádio Vila Ventura", "Tarde em Casa", "Marta Girassol", "Campo Alegre", "Cantinho da Casa")


def _nomes(**extra):
    campos = dict(excluidos=EXCLUIDOS)
    campos.update(extra)
    return pa.NomesParticipacao(**campos)


def _regras(texto, **extra):
    return [m.regra for m in pa.mencoes_participacao(texto, _nomes(**extra))]


# --- U7: regras ------------------------------------------------------------------------------------------

def test_u7_selecionado_passa_e_em_fila_ou_nao_atendido_e_acusado():
    conhecidos = ("Cida Morais", "Paulo Brandão")
    assert _regras("Um abraço para Cida Morais, que mandou mensagem.", selecionados=("Cida Morais",),
                   conhecidos=conhecidos) == []
    assert _regras("Paulo Brandão pediu, e toca agora Patins Amarelos.", selecionados=("Cida Morais",),
                   conhecidos=conhecidos) == ["pedido_nao_selecionado"]
    # Citar quem está na fila, mesmo sem "pediu", é anunciar antes da hora.
    assert _regras("Alô, Paulo Brandão, tudo bem por aí?", conhecidos=conhecidos) == ["pedido_nao_selecionado"]


def test_u7_nome_desconhecido_em_frase_de_participacao():
    mencoes = pa.mencoes_participacao("Um abraço também para Dona Firmina.", _nomes())
    assert [(m.regra, m.nome) for m in mencoes] == [("ouvinte_nao_autorizado", "Dona Firmina")]
    # Nome com inicial maiúscula fora de frase de participação não é ouvinte.
    assert _regras("Hoje a dica vem da Dona Firmina, avó de todo mundo.") == []


def test_u7_primeira_palavra_da_frase_nao_vira_nome():
    """Achado na simulação da F4 (popular sem relógio): "Contato de Valdo Cunha" no começo da frase não é um
    ouvinte chamado "Contato"."""
    nomes = dict(selecionados=("Valdo Cunha",), conhecidos=("Valdo Cunha",))
    assert _regras("Contato de Valdo Cunha sobre o sorteio recebido.", **nomes) == []
    assert _regras("Recado de Cida Morais na tela, e a gente agradece.", selecionados=("Cida Morais",),
                   conhecidos=("Cida Morais",)) == []
    # Título de música com conectivo, no começo da frase, coberto pela menção ("Vai X, de Y").
    assert _regras("Vai Estrada de Chão Batido, de Irmãos Taquara, no lugar da pedida.") == []
    mencoes = pa.mencoes_participacao("Dona Firmina mandou um abraço para todos.", _nomes())
    assert [(m.regra, m.nome) for m in mencoes] == [("ouvinte_nao_autorizado", "Firmina")]


def test_u7_mensagem_simulada_sem_pedido():
    for texto in ("Chegou agora uma mensagem linda de uma ouvinte.", "Acabou de chegar um recado aqui.",
                  "Recebi um pedido especial agora.", "Uma ouvinte pediu para mandar um beijo.",
                  "Muita gente pediu essa música."):
        assert _regras(texto) == ["participacao_simulada"], texto
    assert _regras("Chegou agora uma mensagem de Cida Morais.", selecionados=("Cida Morais",),
                   conhecidos=("Cida Morais",)) == []
    assert _regras("O WhatsApp da Rádio Vila Ventura está aberto para o seu recado.") == []


@pytest.mark.parametrize("texto", [
    "O WhatsApp da Rádio Vila Ventura está aberto para o seu recado.",
    "Recado para a Tarde em Casa, com Marta Girassol, pelo WhatsApp.",
    "Mande um alô para a turma de Campo Alegre.",
    "Uma dica do Cantinho da Casa para quem mandou mensagem.",
    "Alô, quem está ouvindo!",
    "Quer mandar um recado? Escreve pelo WhatsApp.",
])
def test_u7_exclusoes(texto):
    assert _regras(texto) == []


def test_u7_partes_de_mencao_de_musica_nao_sao_ouvinte():
    citaveis = (MusicaRef("Patins Amarelos", "Tati Pirilampo", origem="conhecida"),)
    texto = "Paulo Brandão pediu, e toca agora Patins Amarelos, com Tati Pirilampo."
    assert _regras(texto, selecionados=("Paulo Brandão",), conhecidos=("Paulo Brandão",), citaveis=citaveis) == []


def test_u7_d8_quem_ja_foi_atendido_pode_ser_lembrado_sem_execucao():
    nomes = dict(conhecidos=("Seu Ditinho",), ja_atendidos=("Seu Ditinho",))
    assert _regras("Lembrando o recado do Seu Ditinho, a tarde segue animada.", **nomes) == []
    assert _regras("Seu Ditinho pediu, e toca agora mais uma.", **nomes) == ["pedido_nao_selecionado"]


def test_u7_d7_nome_recente_so_com_chegou_mensagem():
    nomes = dict(conhecidos=("Rita Andrade",), recente="Rita Andrade")
    assert _regras("Opa, chegou uma mensagem da Rita Andrade aqui.", **nomes) == []
    assert _regras("Rita Andrade pediu, e já já toca a música dela.", **nomes) == ["pedido_nao_selecionado"]
    assert _regras("Rita Andrade, tudo bem?", **nomes) == ["pedido_nao_selecionado"]


def test_u7_contencao_de_nome():
    assert _regras("Alô, Ditinho, obrigado.", conhecidos=("Seu Ditinho",)) == ["pedido_nao_selecionado"]
    assert pa.cita_nome("Alô, Ditinho, obrigado.", "Seu Ditinho")
    assert pa.cita_nome("Lurdinha, obrigado pelo recado.", "Lurdinha Campos", primeiro_nome=True)
    assert not pa.cita_nome("Lurdinha, obrigado pelo recado.", "Lurdinha Campos")


# --- checagem sobre o ContextoEmissao -------------------------------------------------------------------

def _ctx(fala_categoria="chamada_ouvinte", pedido_ouvinte=None, **participacao):
    campos = dict(nomes_autorizados=(), nomes_selecionados=(), nomes_ja_atendidos=(), nomes_conhecidos=(),
                  nome_recente=None, pedido_musica=None, pedido_ouvinte=pedido_ouvinte)
    campos.update(participacao)
    return SimpleNamespace(
        categoria=fala_categoria,
        account=SimpleNamespace(nome_radio="Rádio Vila Ventura", cidade="Campo Alegre"),
        programa=SimpleNamespace(nome="Tarde em Casa", quadros_fixos={"Cantinho da Casa": ["gavetas"]}),
        radialista=SimpleNamespace(nome_locutor="Marta Girassol"), roster=(),
        musica=SimpleNamespace(citaveis=(), confirmada=None, bloco=(), tocou=()),
        participacao=SimpleNamespace(**campos),
    )


def test_checar_participacao_devolve_violacoes_com_o_nome_para_remover_so_a_oracao():
    ctx = _ctx(nomes_selecionados=("Cida Morais",), nomes_conhecidos=("Cida Morais",))
    fala = "Um abraço para Cida Morais e também para a Dona Firmina, que escreveu agora."
    violacoes = pa.checar_participacao(fala, ctx)
    assert [(v.regra, v.ref_id) for v in violacoes] == [("ouvinte_nao_autorizado", "Dona Firmina")]
    assert violacoes[0].instrucao_retry
    assert remover_frases(fala, violacoes, preservar=["Cida Morais"]) == "Um abraço para Cida Morais."


def test_pedido_sem_mencao_d10():
    pedido = SimpleNamespace(nome="Seu Valdir", tipo="abraco")
    ctx = _ctx(pedido_ouvinte=pedido, nomes_selecionados=("Seu Valdir",), nomes_conhecidos=("Seu Valdir",))
    violacao = pa.pedido_sem_mencao("Um abraço para a oficina toda!", ctx)
    assert violacao is not None and violacao.regra == "pedido_sem_mencao" and violacao.remediacao == "avisar"
    assert "Seu Valdir" in violacao.instrucao_retry
    assert pa.pedido_sem_mencao("Valdir, um abraço para a oficina toda!", ctx) is None
    assert pa.pedido_sem_mencao("Um abraço!", _ctx(fala_categoria="comentario", pedido_ouvinte=pedido)) is None
    assert pa.pedido_sem_mencao("Um abraço!", _ctx()) is None


# --- U8: remoção por oração --------------------------------------------------------------------------------

def test_u8_remover_frases_corta_e_tambem_para_e_mantem_o_selecionado():
    violacao = Violacao("ouvinte_nao_autorizado", "Um abraço para Cida Morais e para Dona Firmina.",
                        "Dona Firmina")
    assert remover_frases("Um abraço para Cida Morais e para Dona Firmina. Fica com a gente.", [violacao],
                          preservar=["Cida Morais"]) == "Um abraço para Cida Morais. Fica com a gente."
    # Sem o selecionado para manter, a frase sai inteira.
    assert remover_frases("Um abraço para Dona Firmina e para todo mundo.", [Violacao(
        "ouvinte_nao_autorizado", "Um abraço para Dona Firmina e para todo mundo.", "Dona Firmina")],
        preservar=[]) == ""


def test_u8_musica_continua_cortando_so_por_virgula():
    """A regra da F3 (música) não ganha o corte por "e para": a remoção dela fica como era."""
    frase = "Agora vem Estrada Aberta e para fechar Outra Citada."
    violacao = Violacao("musica_nao_confirmada", frase, "Outra Citada")
    assert remover_frases(frase, [violacao], preservar=["Estrada Aberta"]) == ""


# --- benchmark -------------------------------------------------------------------------------------------

def test_u7_benchmark_participacao():
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    resultado = {"pedido": [0, [], []], "inexistente": [0, [], []]}
    total = 0
    for caso in casos:
        fixture = json.loads((FIXTURES / f"{caso['formato']}.json").read_text(encoding="utf-8"))
        excluidos = (fixture["conta"]["nome_radio"], fixture["programa"]["nome"],
                     fixture["radialista"]["nome_locutor"])
        ctx = caso["contexto"]
        rotulos = [x for x in [ctx.get("proxima_confirmada"), *(ctx.get("tocou") or []),
                               *(pd.get("musica") for pd in ctx.get("pedidos") or [])] if x]
        citaveis = tuple(MusicaRef(x.rpartition(" - ")[0], x.rpartition(" - ")[2], origem="conhecida")
                         for x in rotulos)
        pedidos = ctx.get("pedidos") or []
        nomes = pa.NomesParticipacao(
            selecionados=tuple(pd["nome"] for pd in pedidos if pd["estado"] == "selecionado"),
            conhecidos=tuple(pd["nome"] for pd in pedidos), excluidos=excluidos, citaveis=citaveis)
        for fala in caso["falas_rotuladas"]:
            total += 1
            mencoes = pa.mencoes_participacao(fala["texto"], nomes)
            for chave, achou, esperado in (
                    ("pedido", bool(mencoes), bool(fala["esperado"]["pedido_indevido"])),
                    ("inexistente", any(m.regra == "ouvinte_nao_autorizado" for m in mencoes),
                     bool(fala["esperado"]["ouvinte_inexistente"]))):
                if achou and esperado:
                    resultado[chave][0] += 1
                elif achou:
                    resultado[chave][1].append((caso["id"], fala["texto"]))
                elif esperado:
                    resultado[chave][2].append((caso["id"], fala["texto"]))
    assert total == 70
    assert resultado == {"pedido": [5, [], []], "inexistente": [1, [], []]}
