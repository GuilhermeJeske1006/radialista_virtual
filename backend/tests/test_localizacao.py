"""Bairro da sede x outros bairros (app.localizacao), o prompt e o validador da fala que usam essas regras, e o
horário que vale para a hora certa quando o bloco é gerado antes de ir ao ar."""

import datetime
from types import SimpleNamespace

import pytest
from freezegun import freeze_time

from app.live.contexto import instante_no_ar
from app.live.relogio import CONFIG_PADRAO
from app.live.validacao_fala import checar_bairro
from app.llm.prompt_builder import montar_system_prompt
from app.localizacao import aqui_em_outro_bairro, bairro_da_sede, outros_bairros
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

BAIRROS = ["Centro", "São Pedro", "Pomerânia", "Lajeado Alto"]


def _conta(bairro_sede="", endereco="", cidade="Guabiruba", bairros=BAIRROS):
    return SimpleNamespace(
        conhecimento_local={"bairro_sede": bairro_sede, "bairros": list(bairros)},
        endereco=endereco, cidade=cidade,
    )


def test_sede_informada_vale_sobre_o_endereco():
    assert bairro_da_sede(_conta(bairro_sede="Pomerânia", endereco="Rua Brusque, 10 - Centro")) == "Pomerânia"


@pytest.mark.parametrize("endereco", [
    "Rua Brusque, 100 - Centro", "Rua Brusque, 100, Centro, Guabiruba - SC", "Av. Principal 9 | Bairro Centro",
])
def test_sede_vazia_sai_do_endereco(endereco):
    assert bairro_da_sede(_conta(endereco=endereco)) == "Centro"


def test_sede_do_endereco_pelo_bairro_cadastrado_sem_acento():
    assert bairro_da_sede(_conta(endereco="Rua das Flores, 5 - Bairro Sao Pedro")) == "São Pedro"


def test_sede_desconhecida_sem_endereco_util():
    assert bairro_da_sede(_conta(endereco="Rua Brusque, 100")) == ""
    assert bairro_da_sede(SimpleNamespace(conhecimento_local=None, endereco=None, cidade=None)) == ""


def test_centro_no_meio_do_nome_da_rua_nao_vira_sede():
    assert bairro_da_sede(_conta(endereco="Rua Centro Comercial, 5")) == ""


def test_outros_bairros_tira_a_sede_e_o_nome_da_cidade():
    conta = _conta(bairro_sede="Centro", bairros=[*BAIRROS, "Guabiruba"])
    assert outros_bairros(conta) == ["São Pedro", "Pomerânia", "Lajeado Alto"]


@pytest.mark.parametrize("frase, bairro", [
    ("Bom dia, aqui na Pomerânia o sol já apareceu!", "Pomerânia"),
    ("Aqui no São Pedro tá um calorão.", "São Pedro"),
    ("Um abraço pro pessoal daqui do Lajeado Alto.", "Lajeado Alto"),
    ("Aqui, no bairro São Pedro, a gente acorda cedo.", "São Pedro"),
    ("Aqui mesmo em Pomerania tem festa.", "Pomerânia"),
])
def test_aqui_em_outro_bairro_e_detectado(frase, bairro):
    assert aqui_em_outro_bairro(frase, _conta(bairro_sede="Centro")) == bairro


@pytest.mark.parametrize("frase", [
    "Bom dia, aqui no Centro o sol já apareceu!",
    "Um abraço pro pessoal lá do São Pedro.",
    "A Maria, da Pomerânia, mandou mensagem.",
    "Aqui em Guabiruba o dia tá bonito.",
])
def test_frases_certas_passam(frase):
    assert aqui_em_outro_bairro(frase, _conta(bairro_sede="Centro")) is None


def test_sem_sede_conhecida_nenhum_bairro_e_aqui():
    assert aqui_em_outro_bairro("Aqui no Centro tá frio.", _conta()) == "Centro"


def test_validador_aponta_a_frase_com_o_bairro_errado():
    ctx = SimpleNamespace(account=_conta(bairro_sede="Centro"))
    violacoes = checar_bairro("Bom dia! Aqui na Pomerânia o sol já saiu. Vem música boa.", ctx)
    assert [(v.regra, v.trecho, v.ref_id) for v in violacoes] == [
        ("bairro_errado", "Aqui na Pomerânia o sol já saiu.", "Pomerânia")]
    assert "A rádio fica no bairro Centro" in violacoes[0].instrucao_retry
    assert violacoes[0].remediacao == "remover_frase"


def test_validador_sem_bairro_cadastrado_nao_aponta_nada():
    ctx = SimpleNamespace(account=SimpleNamespace(conhecimento_local={}, endereco="", cidade=""))
    assert checar_bairro("Aqui no Centro tá frio.", ctx) == []


# --- prompt -------------------------------------------------------------------------------------------------

@pytest.fixture
def _sem_clima_nem_redis(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)
    monkeypatch.setattr("app.llm.prompt_builder._proxima_variacao", lambda _id, _chave, opcoes: opcoes[0])


def _programa():
    return Programa(id=1, nome="Manhã", tom="animado", topicos_permitidos=[], topicos_proibidos=[],
                    generos_musicais=[], musicas_permitidas=[], musicas_bloqueadas=[], criterios_busca_musicas="",
                    assuntos_ao_vivo=[], tipos_noticias=[], fontes_noticias=[], pode_pesquisar=False,
                    fontes_pesquisa=[], instrucoes_pesquisa="", estrutura_blocos=[], ia_pode_adicionar_blocos=True,
                    descricao="")


def _prompt(**conta):
    account = Account(nome_radio="Rádio Teste", cidade="Guabiruba", **conta)
    radialista = RadioConfig(nome_locutor="Zé", personalidade="", timezone="America/Sao_Paulo")
    return montar_system_prompt(account, radialista, _programa())


@freeze_time("2026-08-10 15:00:00")
def test_prompt_diz_onde_a_radio_fica(_sem_clima_nem_redis):
    prompt = _prompt(conhecimento_local={"bairro_sede": "Centro", "bairros": ["Pomerânia"]})
    assert "Onde a rádio fica: no bairro Centro, em Guabiruba" in prompt
    assert "o lugar é sempre Centro" in prompt
    assert "nunca 'aqui no Pomerânia'" in prompt
    assert "Detalhe real do lugar onde a rádio fica" not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_tira_a_sede_do_endereco(_sem_clima_nem_redis):
    prompt = _prompt(endereco="Rua Brusque, 100 - Centro", conhecimento_local={"bairros": ["Centro"]})
    assert "Onde a rádio fica: no bairro Centro" in prompt
    assert "o bairro Centro, onde a rádio fica" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_sem_sede_nao_inventa_onde_fica(_sem_clima_nem_redis):
    prompt = _prompt(conhecimento_local={"bairros": ["São Pedro"]})
    assert "Onde a rádio fica" not in prompt
    assert "o bairro da rádio não foi informado" in prompt
    assert "nunca 'aqui no São Pedro'" in prompt


# --- hora certa: o horário em que o bloco vai ao ar ---------------------------------------------------------

AGORA = datetime.datetime(2026, 11, 25, 15, 48, tzinfo=datetime.timezone.utc)


def _entrada(inicio_previsto):
    return SimpleNamespace(dados=SimpleNamespace(inicio_previsto=inicio_previsto), cfg_relogio=CONFIG_PADRAO)


@freeze_time(AGORA)
def test_sem_relogio_a_hora_e_a_prevista_pelo_painel():
    assert instante_no_ar(_entrada("2026-11-25T15:53:10Z"), None) == AGORA.replace(minute=53, second=10)


@freeze_time(AGORA)
@pytest.mark.parametrize("valor", [None, "lixo", "2026-11-25T15:40:00Z", "2026-11-25T18:00:00Z"])
def test_sem_relogio_previsto_ausente_invalido_passado_ou_longe_vale_agora(valor):
    assert instante_no_ar(_entrada(valor), None) == AGORA


@freeze_time(AGORA)
def test_com_relogio_vale_o_instante_do_plano():
    plano = SimpleNamespace(instante=AGORA.replace(minute=55))
    assert instante_no_ar(_entrada("2026-11-25T15:53:10Z"), plano) == AGORA.replace(minute=55)
