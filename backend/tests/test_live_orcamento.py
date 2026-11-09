"""Orçamento de duração da fala (F2 do plano de melhoria de rádio).

Desenho em docs/melhoria-radio/f2/auditoria.md (§4.2, §4.3 e §6). A primeira parte caracteriza
`app.live.formato` (valores e texto que o router, o dublê da F0 e os testes antigos leem) antes da F2
mexer no orçamento; a segunda testa as funções puras de `app.live.orcamento`.
"""

import pytest

from app.live.formato import ORCAMENTOS, direcao_musical, orcamento_fala

# ---------------------------------------------------------------------------------------------
# Caracterização de app.live.formato (verde antes da F2; a F2 não muda nenhum destes valores)
# ---------------------------------------------------------------------------------------------


def test_orcamento_fala_valores_atuais():
    assert ORCAMENTOS == {
        "abertura": (20, 30, 65),
        "retomada": (6, 12, 25),
        "identificacao": (3, 7, 14),
        "musica": (4, 8, 18),
        "encerramento": (10, 18, 38),
    }
    assert orcamento_fala("abertura", primeira=True) == (20, 30, 65)
    assert orcamento_fala("abertura", primeira=False) == (6, 12, 25)
    assert orcamento_fala("Retomada") == (6, 12, 25)
    assert orcamento_fala("identificação") == (3, 7, 14)
    assert orcamento_fala("musica") == (4, 8, 18)
    assert orcamento_fala("encerramento") == (10, 18, 38)
    assert orcamento_fala("comentario") == (10, 20, 45)
    assert orcamento_fala("bloco desconhecido") == (10, 20, 45)


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
_FUNCAO_RETOMADA = "Faça uma retomada breve; o programa já está em andamento."


@pytest.mark.parametrize("tipo,primeira,funcao,meta", [
    ("abertura", True, "Receba o ouvinte e apresente o programa uma única vez.", (20, 30, 65)),
    ("abertura", False, _FUNCAO_RETOMADA, (6, 12, 25)),
    ("retomada", False, _FUNCAO_RETOMADA, (6, 12, 25)),
    ("identificacao", False, "Diga apenas o nome da rádio ou do programa e uma assinatura curta.", (3, 7, 14)),
    ("musica", False, "Anuncie brevemente a faixa confirmada e o pedido real, quando fornecido.", (4, 8, 18)),
    ("encerramento", False, "Despeça-se do programa. Não prometa retorno após intervalo.", (10, 18, 38)),
    ("comentario", False, "Cumpra somente a função deste bloco, de forma breve.", (10, 20, 45)),
])
def test_direcao_musical_texto_inalterado(tipo, primeira, funcao, meta):
    """Retrato do texto: a meta e o "no máximo N palavras" são lidos pelo dublê do LLM da F0."""
    minimo, maximo, palavras = meta
    esperado = (f"{_PREFIXO_MUSICAL}{funcao} Meta de locução: {minimo} a {maximo} segundos, "
                f"no máximo {palavras} palavras.{_SUFIXO_MUSICAL}")
    assert direcao_musical(tipo, primeira) == esperado
    assert direcao_musical(tipo, primeira, orcamento=(5, 9, 21)) == esperado.replace(
        f"{minimo} a {maximo} segundos, no máximo {palavras} palavras", "5 a 9 segundos, no máximo 21 palavras")
