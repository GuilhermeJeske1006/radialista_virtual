import datetime

from freezegun import freeze_time

from app.guardrails.schedule import encontrar_programa_atual, minutos_restantes, programa_no_ar
from app.models.programa import Programa

TZ = "America/Sao_Paulo"

# 2026-08-10 15:00 UTC == 2026-08-10 12:00 America/Sao_Paulo (UTC-3), uma segunda-feira (weekday 0).
AGORA_UTC = "2026-08-10 15:00:00"


def _programa(**kwargs):
    padrao = dict(
        ativo=True,
        data_especifica=None,
        dias_semana=[],
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
    )
    padrao.update(kwargs)
    return Programa(**padrao)


@freeze_time(AGORA_UTC)
def test_programa_inativo_nunca_esta_no_ar():
    programa = _programa(ativo=False)
    assert programa_no_ar(programa, TZ) is False


@freeze_time(AGORA_UTC)
def test_programa_dentro_da_janela_normal_esta_no_ar():
    programa = _programa(horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0))
    assert programa_no_ar(programa, TZ) is True


@freeze_time(AGORA_UTC)
def test_programa_fora_da_janela_normal_nao_esta_no_ar():
    programa = _programa(horario_inicio=datetime.time(16, 0), horario_fim=datetime.time(18, 0))
    assert programa_no_ar(programa, TZ) is False


@freeze_time(AGORA_UTC)
def test_janela_overnight_cruzando_meia_noite():
    # agora local e' 12:00 -- fora da janela 22:00-06:00.
    programa = _programa(horario_inicio=datetime.time(22, 0), horario_fim=datetime.time(6, 0))
    assert programa_no_ar(programa, TZ) is False


@freeze_time("2026-08-10 04:00:00")  # 01:00 local
def test_janela_overnight_dentro_da_madrugada():
    programa = _programa(horario_inicio=datetime.time(22, 0), horario_fim=datetime.time(6, 0))
    assert programa_no_ar(programa, TZ) is True


@freeze_time(AGORA_UTC)
def test_dias_semana_vazio_significa_todos_os_dias():
    programa = _programa(dias_semana=[])
    assert programa_no_ar(programa, TZ) is True


@freeze_time(AGORA_UTC)
def test_dias_semana_bate_com_dia_atual():
    programa = _programa(dias_semana=[0, 2, 4])  # segunda e' 0
    assert programa_no_ar(programa, TZ) is True


@freeze_time(AGORA_UTC)
def test_dias_semana_nao_bate_com_dia_atual():
    programa = _programa(dias_semana=[1, 2, 3])  # sem segunda
    assert programa_no_ar(programa, TZ) is False


@freeze_time(AGORA_UTC)
def test_data_especifica_bate_com_hoje_ignora_dias_semana():
    programa = _programa(data_especifica=datetime.date(2026, 8, 10), dias_semana=[1, 2, 3])
    assert programa_no_ar(programa, TZ) is True


@freeze_time(AGORA_UTC)
def test_data_especifica_diferente_de_hoje_bloqueia():
    programa = _programa(data_especifica=datetime.date(2026, 8, 11))
    assert programa_no_ar(programa, TZ) is False


@freeze_time(AGORA_UTC)
def test_encontrar_programa_atual_devolve_o_primeiro_no_ar():
    fora_do_ar = _programa(horario_inicio=datetime.time(16, 0), horario_fim=datetime.time(18, 0))
    no_ar = _programa(horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0))
    assert encontrar_programa_atual([fora_do_ar, no_ar], TZ) is no_ar


@freeze_time(AGORA_UTC)
def test_encontrar_programa_atual_devolve_none_se_nenhum_no_ar():
    fora_do_ar = _programa(horario_inicio=datetime.time(16, 0), horario_fim=datetime.time(18, 0))
    assert encontrar_programa_atual([fora_do_ar], TZ) is None


@freeze_time(AGORA_UTC)
def test_minutos_restantes_dentro_da_janela():
    # agora local 12:00, fim 14:00 -> 120 minutos
    programa = _programa(horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0))
    assert minutos_restantes(programa, TZ) == 120


@freeze_time(AGORA_UTC)
def test_minutos_restantes_fora_da_janela_devolve_valor_alto():
    programa = _programa(horario_inicio=datetime.time(16, 0), horario_fim=datetime.time(18, 0))
    assert minutos_restantes(programa, TZ) == 24 * 60


@freeze_time("2026-08-10 04:00:00")  # 01:00 local
def test_minutos_restantes_overnight_apos_meia_noite():
    # fim as 06:00 do dia seguinte (data local ainda 10/08, 01:00) -> 5h = 300 min
    programa = _programa(horario_inicio=datetime.time(22, 0), horario_fim=datetime.time(6, 0))
    assert minutos_restantes(programa, TZ) == 300
