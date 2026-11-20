"""Memória da fala (F8, passo 1 e 2): consolidação sem mudar comportamento e repetição por estrutura."""

import pytest

from app.live.memoria import abertura_da_fala, fechamento_da_fala, repeticao_estrutura


@pytest.mark.parametrize("texto, classe", [
    ("Você está na Rádio Serra Clara. Agora, Rua das Acácias.", "identificacao"),
    ("Bom dia, gente! Vamos lá.", "saudacao"),
    ("Quem está aí? Me conta.", "pergunta"),
    ("Hoje é dia de samba.", "chamada"),
    ("Texto sem padrão reconhecível.", "outra"),
    ("", "outra"),
    ("VOCÊ ESTÁ NO AR.", "identificacao"),  # caixa e acento não atrapalham
    ("Rádio Serra Clara. Tarde Serena.", "identificacao"),
    ("Seguimos juntos em Tarde Serena.", "retomada"),
    ("A tarde continua na Rádio Serra Clara.", "retomada"),
    ("Que bom ter você por aqui.", "agradecimento"),
])
def test_abertura_classifica_a_construcao_e_nao_o_nome(texto, classe):
    assert abertura_da_fala(texto) == classe


@pytest.mark.parametrize("texto, classe", [
    ("Vamos seguir. Fica com a gente.", "despedida"),
    ("Manda seu recado.", "convite"),
    ("Você gostou?", "pergunta"),
    ("Só isso.", "outra"),
])
def test_fechamento_classifica_a_ultima_frase(texto, classe):
    assert fechamento_da_fala(texto) == classe


def test_troca_so_do_nome_continua_a_mesma_abertura():
    textos = ["Você está na Rádio Ipê. Um.", "Você está na Rádio Serra. Dois.", "Você está no Vale. Três."]
    assert repeticao_estrutura(textos, seguidas=3) == 1


def test_janelas_contam_como_no_simulador_de_abertura():
    # Quatro iguais em sequência = duas janelas de três (sobrepostas), como abertura_repetida.
    assert repeticao_estrutura(["Bom dia."] * 4, seguidas=3) == 2


def test_outra_nao_conta_como_estrutura_repetida():
    assert repeticao_estrutura(["Texto um.", "Texto dois.", "Texto três."], seguidas=3) == 0


def test_consolidacao_mantem_os_nomes_privados_usados_pelo_router():
    from app.live.contexto import _aberturas_e_fechamentos, _primeira_frase, _ultima_frase
    from app.live.geracao import _fala_semelhante_no_historico

    assert _primeira_frase("Uma. Duas.") == "Uma."
    assert _ultima_frase("Uma. Duas.") == "Duas."
    assert _aberturas_e_fechamentos(["Uma. Duas.", "Três. Quatro."]) == (["Uma.", "Três."], ["Duas.", "Quatro."])
    assert _fala_semelhante_no_historico("um dois três quatro cinco seis", ["um dois três quatro cinco seis"]) \
        == "um dois três quatro cinco seis"
