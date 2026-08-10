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

    if programa.data_especifica is not None:
        if agora.date() != programa.data_especifica:
            return False
    elif programa.dias_semana and agora.weekday() not in programa.dias_semana:
        return False

    return _dentro_da_janela(agora.time(), programa.horario_inicio, programa.horario_fim)


def encontrar_programa_atual(programas: list[Programa], timezone: str) -> Programa | None:
    for programa in programas:
        if programa_no_ar(programa, timezone):
            return programa
    return None


def minutos_restantes(programa: Programa, timezone: str) -> int:
    """Quantos minutos faltam ate' o horario_fim do programa, a partir de agora.

    Negativo quando ja passou do horario_fim (janela ja fechou). Trata o caso de
    janela que cruza meia-noite (ex: 22:00-06:00) igual _dentro_da_janela.

    Fora da janela do programa (ainda nao comecou, ou -- pra overnight -- agora
    cai no intervalo morto entre o fim de uma ocorrencia e o inicio da proxima),
    devolve um valor bem alto em vez de calcular a diferenca com o horario_fim de
    "hoje": sem essa guarda, um programa overnight (ex: 22:00-06:00) checado a
    tarde bateria contra o horario_fim que ja passou de manha, dando um numero
    bem negativo -- perto do limiar de encerramento por acidente, mesmo com o
    programa ainda a horas de comecar.
    """
    agora = datetime.datetime.now(ZoneInfo(timezone))
    if not _dentro_da_janela(agora.time(), programa.horario_inicio, programa.horario_fim):
        return 24 * 60

    fim = datetime.datetime.combine(agora.date(), programa.horario_fim, tzinfo=agora.tzinfo)

    if programa.horario_inicio > programa.horario_fim and agora.time() >= programa.horario_inicio:
        fim += datetime.timedelta(days=1)

    return int((fim - agora).total_seconds() // 60)
