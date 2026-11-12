"""U1 da F5 (docs/melhoria-radio/f5/auditoria.md §8): DadoVerificavel, estado, validade efetiva, horário falado e a
configuração (os números vêm de ConfigDados, nunca de constante solta)."""

import dataclasses
import datetime
from zoneinfo import ZoneInfo

import pytest

from app.dados import verificavel as v
from app.dados.verificavel import CONFIG_DADOS, ConfigDados, DadoVerificavel

TZ = "America/Sao_Paulo"
LOCAL = ZoneInfo(TZ)
AGORA = datetime.datetime(2026, 11, 10, 14, 30, tzinfo=LOCAL)


def _dado(**campos) -> DadoVerificavel:
    base = dict(id="clima:campo-alegre", tipo="clima", valor="vinte e dois graus, céu limpo", fonte="Open-Meteo",
                atualizado_em=AGORA - datetime.timedelta(minutes=20), valido_ate=AGORA + datetime.timedelta(minutes=40))
    base.update(campos)
    return DadoVerificavel(**base)


# --- estado ------------------------------------------------------------------------------------------------

def test_estado_valido():
    assert v.estado(_dado(), AGORA) == "valido"


def test_estado_vencido_depois_do_valido_ate():
    assert v.estado(_dado(valido_ate=AGORA - datetime.timedelta(seconds=1)), AGORA) == "vencido"


def test_estado_sem_fonte_vence_tudo():
    assert v.estado(_dado(fonte=""), AGORA) == "sem_fonte"
    assert v.estado(_dado(fonte="   ", aprovado=False), AGORA) == "sem_fonte"


def test_estado_nao_aprovado():
    assert v.estado(_dado(aprovado=False), AGORA) == "nao_aprovado"


def test_estado_futuro_alem_da_tolerancia():
    tolerancia = CONFIG_DADOS.tolerancia_futuro_s
    assert v.estado(_dado(atualizado_em=AGORA + datetime.timedelta(seconds=tolerancia + 1)), AGORA) == "futuro"
    assert v.estado(_dado(atualizado_em=AGORA + datetime.timedelta(seconds=tolerancia - 1)), AGORA) == "valido"


def test_estado_atemporal_sem_valido_ate_e_valido():
    assert v.estado(_dado(tipo="assunto", valido_ate=None, atualizado_em=None), AGORA) == "valido"


def test_estados_possiveis_sao_cinco():
    assert set(v.ESTADOS) == {"valido", "vencido", "sem_fonte", "nao_aprovado", "futuro"}


# --- validade efetiva ---------------------------------------------------------------------------------------

def test_valido_ate_explicito_vale():
    dado = _dado(valido_ate=AGORA)
    assert v.valido_ate_efetivo(dado) == AGORA


def test_valido_ate_por_tipo_quando_ausente():
    observado = AGORA - datetime.timedelta(minutes=10)
    dado = _dado(valido_ate=None, atualizado_em=observado)
    assert v.valido_ate_efetivo(dado) == observado + datetime.timedelta(seconds=CONFIG_DADOS.validade_s["clima"])


def test_valido_ate_sem_regra_do_tipo_e_atemporal():
    assert v.valido_ate_efetivo(_dado(tipo="assunto", valido_ate=None)) is None


def test_valido_ate_vem_da_config_passada():
    config = dataclasses.replace(CONFIG_DADOS, validade_s={**CONFIG_DADOS.validade_s, "clima": 60})
    observado = AGORA - datetime.timedelta(minutes=2)
    dado = _dado(valido_ate=None, atualizado_em=observado)
    assert v.valido_ate_efetivo(dado, config) == observado + datetime.timedelta(seconds=60)
    assert v.estado(dado, AGORA, config) == "vencido"
    assert v.estado(dado, AGORA) == "valido"


# --- janela da notícia (a mesma da pauta antes da F5) --------------------------------------------------------

@pytest.mark.parametrize("categoria,horas", [
    ("seguranca", 24), ("transito", 24), ("clima_defesa_civil", 24), ("saude", 24), ("economia", 48),
    ("servico_publico", 48), ("geral", 48), ("agenda_cultura", 168), ("sem_regra", 48)])
def test_janela_noticia_igual_a_de_antes(categoria, horas):
    assert v.janela_noticia(categoria) == datetime.timedelta(hours=horas)


def test_janela_noticia_da_config():
    config = ConfigDados(janela_noticia_h={"transito": 3}, janela_noticia_padrao_h=5)
    assert v.janela_noticia("transito", config) == datetime.timedelta(hours=3)
    assert v.janela_noticia("geral", config) == datetime.timedelta(hours=5)


# --- idade máxima da afirmação ----------------------------------------------------------------------------

@pytest.mark.parametrize("categoria,segundos", [("temperatura", 3600), ("condicao_tempo", 3600),
                                                ("transito", 1800), ("placar", 900)])
def test_idade_maxima_por_categoria(categoria, segundos):
    assert v.idade_maxima(categoria) == datetime.timedelta(seconds=segundos)


def test_idade_maxima_sem_regra_e_none():
    assert v.idade_maxima("comercial") is None


def test_velho_demais_para_afirmar():
    dado = _dado(atualizado_em=AGORA - datetime.timedelta(minutes=61))
    assert v.velho_para_afirmar(dado, "temperatura", AGORA)
    assert not v.velho_para_afirmar(dado, "comercial", AGORA)
    assert not v.velho_para_afirmar(_dado(atualizado_em=AGORA - datetime.timedelta(minutes=59)), "temperatura",
                                    AGORA)


# --- horário falado ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("hora,minuto,esperado", [
    (12, 0, "ao meio-dia"), (12, 15, "ao meio-dia e quinze"), (0, 0, "à meia-noite"),
    (0, 30, "à meia-noite e trinta"), (1, 0, "à uma hora"), (1, 5, "à uma e cinco"), (14, 10, "às catorze e dez"),
    (14, 0, "às catorze horas"), (22, 2, "às vinte e duas e dois"), (9, 0, "às nove horas")])
def test_horario_falado(hora, minuto, esperado):
    assert v.horario_falado(datetime.datetime(2026, 11, 10, hora, minuto, tzinfo=LOCAL), TZ) == esperado


def test_horario_falado_no_fuso_da_radio():
    utc = datetime.datetime(2026, 11, 10, 15, 0, tzinfo=datetime.timezone.utc)
    assert v.horario_falado(utc, TZ) == "ao meio-dia"
    assert v.horario_falado(utc, "America/Manaus") == "às onze horas"


def test_quando_falado_hoje_ontem_e_virada_do_dia():
    agora = datetime.datetime(2026, 11, 11, 0, 20, tzinfo=LOCAL)
    assert v.quando_falado(datetime.datetime(2026, 11, 11, 0, 5, tzinfo=LOCAL), agora, TZ) == \
        "hoje, à meia-noite e cinco"
    assert v.quando_falado(datetime.datetime(2026, 11, 10, 23, 50, tzinfo=LOCAL), agora, TZ) == \
        "ontem, às vinte e três e cinquenta"
    # 02:30 UTC de 11/11 ainda é 10/11 no fuso da rádio.
    assert v.quando_falado(datetime.datetime(2026, 11, 11, 2, 30, tzinfo=datetime.timezone.utc), agora, TZ) == \
        "ontem, às vinte e três e trinta"
    assert v.quando_falado(datetime.datetime(2026, 11, 8, 9, 0, tzinfo=LOCAL), agora, TZ) == \
        "no dia oito, às nove horas"
    assert v.quando_falado(None, agora, TZ) == ""


def test_dado_e_imutavel_e_tem_os_campos_do_plano():
    dado = _dado()
    for campo in ("valor", "fonte", "atualizado_em", "valido_ate", "local", "aprovado"):
        assert hasattr(dado, campo)
    with pytest.raises(dataclasses.FrozenInstanceError):
        dado.valor = "outro"  # type: ignore[misc]


def test_numeros_vem_da_config():
    padrao = ConfigDados()
    assert padrao.validade_s["clima"] == 3600 and padrao.validade_s["pesquisa"] == 7200
    assert padrao.idade_max_vencido_s == 10800 and padrao.clima_ultima_leitura_ttl_s == 10800
    assert padrao.limite_texto == 600 and padrao.limite_nome == 40
    assert padrao.vencido_no_prompt.get("clima") == "com_horario"
    assert padrao.fonte_no_ar["clima"] == "o serviço de meteorologia"
