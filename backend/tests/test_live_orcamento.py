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
    ("abertura", True, "Receba o ouvinte e apresente o programa uma única vez, com a companhia que a música faz. "
     "Não prometa retorno nem intervalo ('daqui a pouco', 'meia hora', 'depois do intervalo'): a "
     "abertura chega ao tamanho da unidade só com apresentação e o que o ouvinte vai ouvir agora.", (20, 30, 65)),
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


# ---------------------------------------------------------------------------------------------
# app.live.orcamento: estimativa, ritmo, orçamento e encurtamento (funções puras)
# ---------------------------------------------------------------------------------------------

@pytest.fixture()
def cfg_fala(monkeypatch):
    """Parâmetros da F2 fixados no teste (os padrões de settings são hipóteses e podem mudar)."""
    from app.config.settings import settings

    valores = {
        "fala_wpm_padrao": 150.0,
        "fala_wpm_padrao_por_modelo": {"eleven_v3": 162.0, "eleven_flash_v2_5": 171.0},
        "fala_tolerancia_orcamento": 0.15,
        "fala_teto_orcamento": 0.30,
        "fala_pausa_explicita_s": 1.2,
        "fala_pausa_entre_linhas_s": 0.28,
    }
    for chave, valor in valores.items():
        monkeypatch.setattr(settings, chave, valor)
    return settings


def test_estimar_duracao(cfg_fala):
    from app.live.orcamento import estimar_duracao_s, palavras_faladas

    assert estimar_duracao_s("um dois três quatro cinco", 150) == pytest.approx(2.0)
    assert estimar_duracao_s("[calm] um dois três [laughs] quatro cinco", 150) == pytest.approx(2.0)
    # Cada pausa explícita ("......" ou [pause]) soma a pausa configurada e separa as palavras.
    assert estimar_duracao_s("um dois......três quatro cinco", 150) == pytest.approx(2.0 + 1.2)
    assert estimar_duracao_s("um dois [pause] três quatro cinco [pause]", 150) == pytest.approx(2.0 + 2.4)
    # Números saem por extenso antes de contar, como o TTS recebe (app.numeros.normalizar_texto_fala).
    assert palavras_faladas("Em 2026") == 7  # "Em dois mil e vinte e seis"
    assert estimar_duracao_s("Em 2026", 60) == pytest.approx(7.0)
    assert palavras_faladas("R$ 19,90") == 5
    assert estimar_duracao_s("", 150) == 0.0
    with pytest.raises(ValueError):
        estimar_duracao_s("um", 0)


def test_estimar_duracao_usa_a_pausa_da_configuracao(cfg_fala, monkeypatch):
    from app.live.orcamento import estimar_duracao_s

    monkeypatch.setattr(cfg_fala, "fala_pausa_explicita_s", 2.0)
    assert estimar_duracao_s("um dois......três", 60) == pytest.approx(3.0 + 2.0)


def test_wpm_observado_filtra_amostras_ruins():
    from app.live.orcamento import wpm_observado

    assert wpm_observado(30, 12.0) == pytest.approx(150.0)
    # As pausas explícitas saem da duração antes de calcular o ritmo.
    assert wpm_observado(30, 13.2, pausas=1, pausa_s=1.2) == pytest.approx(150.0)
    assert wpm_observado(7, 3.0) is None            # menos de 8 palavras
    assert wpm_observado(10, 1.9) is None           # menos de 2 s
    assert wpm_observado(10, 10.0) is None          # 60 palavras/min: abaixo de 80
    assert wpm_observado(60, 10.0) is None          # 360 palavras/min: acima de 320
    assert wpm_observado(30, 0.0) is None
    assert wpm_observado(30, 2.5, pausas=1, pausa_s=1.2) is None  # sobra menos de 2 s de fala


def test_wpm_padrao_por_modelo_e_geral(cfg_fala):
    from app.live.orcamento import wpm_padrao

    assert wpm_padrao("eleven_v3") == 162.0
    assert wpm_padrao("eleven_flash_v2_5") == 171.0
    assert wpm_padrao("eleven_multilingual_v2") == 150.0
    assert wpm_padrao(None) == 150.0


def test_relogio_le_o_ritmo_padrao_da_mesma_origem():
    """Um só valor padrão: o relógio da F1 não tem mais o seu próprio (145 palavras/min)."""
    from app.config.settings import settings
    from app.live.orcamento import wpm_padrao
    from app.live.relogio import ConfigRelogio

    assert ConfigRelogio().wpm == wpm_padrao() == settings.fala_wpm_padrao


def test_orcamento_para_sem_relogio(cfg_fala):
    from app.live.orcamento import orcamento_para

    retomada = orcamento_para("musical_companhia", "abertura", primeira=False)
    assert (retomada.min_s, retomada.alvo_s, retomada.max_s, retomada.max_palavras) == (6, 9, 12, 25)
    assert (retomada.fonte, retomada.aplicar, retomada.cabe) == ("formato", True, True)
    assert orcamento_para("musical_companhia", "abertura", primeira=True).max_s == 30
    assert orcamento_para("musical_companhia", "comentario", primeira=False).max_palavras == 45

    padrao = orcamento_para("padrao", "comentario", primeira=False)
    assert (padrao.fonte, padrao.aplicar) == ("observacao", False)
    assert (padrao.min_s, padrao.max_s, padrao.max_palavras) == (15, 30, None)


def test_orcamento_para_com_teto_do_relogio(cfg_fala):
    from app.live.orcamento import orcamento_para

    # Musical: o teto do relógio abaixo do máximo do formato vira o máximo; o alvo não passa dele.
    musical = orcamento_para("musical_companhia", "encerramento", primeira=False, teto_relogio_s=14)
    assert (musical.min_s, musical.max_s, musical.fonte, musical.aplicar) == (10, 14, "relogio", True)
    assert musical.alvo_s <= 14
    assert musical.max_palavras == 38
    # Padrão com relógio: o orçamento é o do relógio (mínimo e máximo do backtiming da F1) e passa a valer.
    padrao = orcamento_para("padrao", "comentario", primeira=False, teto_relogio_s=35, minimo_relogio_s=10)
    assert (padrao.min_s, padrao.alvo_s, padrao.max_s) == (10, 22.5, 35)
    assert (padrao.fonte, padrao.aplicar, padrao.max_palavras) == ("relogio", True, None)
    # Teto abaixo do mínimo: devolve o orçamento e marca que não cabe (a decisão de não falar é da F1).
    apertado = orcamento_para("musical_companhia", "abertura", primeira=False, teto_relogio_s=4)
    assert (apertado.max_s, apertado.cabe) == (4, False)


def test_palavras_max_pelo_ritmo(cfg_fala):
    from app.live.orcamento import orcamento_para, palavras_max

    retomada = orcamento_para("musical_companhia", "retomada", primeira=False)
    assert palavras_max(retomada, 162) == 25          # o teto do formato vale quando o ritmo permite mais
    assert palavras_max(retomada, 100) == 20          # voz lenta: 12 s a 100 palavras/min
    assert palavras_max(retomada, 100, pausas=1) == 18  # uma pausa de 1,2 s sai do tempo de fala
    padrao = orcamento_para("padrao", "comentario", primeira=False, teto_relogio_s=35, minimo_relogio_s=10)
    assert palavras_max(padrao, 145) == 84


def test_avaliar_duracao_limites(cfg_fala, monkeypatch):
    from app.live.orcamento import OrcamentoFala, avaliar_duracao

    orc = OrcamentoFala(min_s=6, alvo_s=9, max_s=10, max_palavras=25, fonte="formato", aplicar=True)
    assert avaliar_duracao(10.0, orc) == "dentro"
    assert avaliar_duracao(11.5, orc) == "tolerancia"      # exatamente 115%: ainda tolerado
    assert avaliar_duracao(11.51, orc) == "fora"
    assert avaliar_duracao(13.0, orc) == "fora"            # exatamente 130%
    assert avaliar_duracao(13.01, orc) == "acima_do_teto"
    monkeypatch.setattr(cfg_fala, "fala_tolerancia_orcamento", 0.05)
    monkeypatch.setattr(cfg_fala, "fala_teto_orcamento", 0.10)
    assert avaliar_duracao(10.6, orc) == "fora"
    assert avaliar_duracao(11.2, orc) == "acima_do_teto"


def test_encurtar_por_frases():
    from app.live.orcamento import encurtar_por_frases

    texto = "Boa tarde, Marina! Que bom ter você aqui. O sol apareceu de vez. Agora toca Rio Manso."
    # Corta do fim, sem cortar frase pela metade, mas mantém as frases com termos preservados e a ordem.
    assert encurtar_por_frases(texto, 12, preservar=["Marina", "Rio Manso"]) == (
        "Boa tarde, Marina! Que bom ter você aqui. Agora toca Rio Manso.")
    assert encurtar_por_frases(texto, 11, preservar=["Marina", "Rio Manso"]) == (
        "Boa tarde, Marina! Agora toca Rio Manso.")
    assert encurtar_por_frases(texto, 10, preservar=["Marina"]) == "Boa tarde, Marina! Que bom ter você aqui."
    assert encurtar_por_frases(texto, 100) == texto
    # Não cabe nem com as frases obrigatórias: None.
    assert encurtar_por_frases(texto, 4, preservar=["Rio Manso", "Marina"]) is None
    assert encurtar_por_frases("Uma frase só, longa demais para caber aqui.", 3) is None
    # Trata ! ? e reticências como fronteira; a comparação ignora acento e caixa.
    assert encurtar_por_frases("Sabia? Hoje faz frio… Mas a música esquenta! Fica com a gente.", 5,
                               preservar=["musica"]) == "Sabia? Mas a música esquenta!"
    # manter_ultima: o encerramento nunca perde a despedida.
    assert encurtar_por_frases("Obrigado pela tarde. Foi ótimo. Até amanhã!", 5, manter_ultima=True) == (
        "Obrigado pela tarde. Até amanhã!")


def test_encurtar_por_frases_preserva_a_atribuicao_da_noticia():
    from app.live.orcamento import encurtar_por_frases
    from app.news.validacao import tem_atribuicao

    texto = ("A ponte do centro fica fechada até as seis. O desvio passa pela avenida do Lago. "
             "Quem puder, saia mais cedo. Segundo a Defesa Civil, a água baixou durante a manhã.")
    assert tem_atribuicao("Segundo a Defesa Civil, a água baixou durante a manhã.")
    assert encurtar_por_frases(texto, 22, manter=tem_atribuicao) == (
        "A ponte do centro fica fechada até as seis. Segundo a Defesa Civil, a água baixou durante a manhã.")


def test_cortar_linhas_dialogo():
    from app.live.orcamento import cortar_linhas_dialogo

    linhas = ["Boa tarde!", "Chegou recado da Marina.", "Ela manda um abraço.", "E o tempo vira amanhã.",
              "Vamos de música."]
    duracoes = [2.0, 3.0, 3.0, 3.0, 2.0]
    # 5 linhas + 4 pausas de 0,28 s = 14,12 s; para caber em 9 s saem as duas últimas.
    assert cortar_linhas_dialogo(linhas, duracoes, max_s=9.0, pausa_s=0.28) == 3
    # Nunca menos de 2 linhas.
    assert cortar_linhas_dialogo(linhas, duracoes, max_s=1.0, pausa_s=0.28) == 2
    # A linha com o pedido (termo preservado) não sai: o corte para antes dela.
    assert cortar_linhas_dialogo(linhas, duracoes, max_s=9.0, pausa_s=0.28, preservar=["tempo"]) == 4
    assert cortar_linhas_dialogo(linhas, duracoes, max_s=60.0, pausa_s=0.28) == 5
