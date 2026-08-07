import datetime
from zoneinfo import ZoneInfo

from app.models.programa import Programa


def _dentro_da_janela(agora: datetime.time, inicio: datetime.time, fim: datetime.time) -> bool:
    if inicio <= fim:
        return inicio <= agora <= fim

    # janela cruza a meia-noite (ex: 22:00 - 06:00)
    return agora >= inicio or agora <= fim


def programa_no_ar(programa: Programa, timezone: str) -> bool:
    if not programa.ativo:
        return False

    agora = datetime.datetime.now(ZoneInfo(timezone))
    if programa.dias_semana and agora.weekday() not in programa.dias_semana:
        return False

    return _dentro_da_janela(agora.time(), programa.horario_inicio, programa.horario_fim)


def encontrar_programa_atual(programas: list[Programa], timezone: str) -> Programa | None:
    for programa in programas:
        if programa_no_ar(programa, timezone):
            return programa
    return None
