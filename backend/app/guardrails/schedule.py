import datetime
from zoneinfo import ZoneInfo

from app.models.programa import Programa


_GRACA_APOS_FIM_MIN = 20


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

    Negativo quando ja passou do horario_fim. Trata o caso de janela que cruza
    meia-noite (ex: 22:00-06:00) igual _dentro_da_janela.

    Fora da janela e fora da janela de graca pos-fim (ainda nao comecou, ou --
    pra overnight -- agora cai no intervalo morto entre o fim de uma ocorrencia
    e o inicio da proxima), devolve um valor bem alto em vez de calcular a
    diferenca com o horario_fim de "hoje": sem essa guarda, um programa
    overnight (ex: 22:00-06:00) checado a tarde bateria contra o horario_fim
    que ja passou de manha, dando um numero bem negativo -- perto do limiar de
    encerramento por acidente, mesmo com o programa ainda a horas de comecar.

    A janela de graca (_GRACA_APOS_FIM_MIN) existe porque o loop ao vivo so'
    reavalia o tipo do proximo bloco quando o bloco atual termina de tocar (ver
    app.live.router), nao num timer fixo -- um bloco de musica/fala pode
    facilmente atravessar o horario_fim. Sem graca, o instante em que o
    programa mais precisa do gatilho de encerramento e' exatamente o instante
    em que _dentro_da_janela vira False e essa funcao cairia pro fallback de
    "nao comecou ainda", nunca disparando o encerramento.
    """
    agora = datetime.datetime.now(ZoneInfo(timezone))

    if _dentro_da_janela(agora.time(), programa.horario_inicio, programa.horario_fim):
        fim = datetime.datetime.combine(agora.date(), programa.horario_fim, tzinfo=agora.tzinfo)
        if programa.horario_inicio > programa.horario_fim and agora.time() >= programa.horario_inicio:
            fim += datetime.timedelta(days=1)
        return int((fim - agora).total_seconds() // 60)

    fim_hoje = datetime.datetime.combine(agora.date(), programa.horario_fim, tzinfo=agora.tzinfo)
    candidatos_fim = (fim_hoje - datetime.timedelta(days=1), fim_hoje, fim_hoje + datetime.timedelta(days=1))
    fim_mais_recente = max((f for f in candidatos_fim if f <= agora), default=None)
    if fim_mais_recente is not None:
        atraso_min = int((agora - fim_mais_recente).total_seconds() // 60)
        if atraso_min <= _GRACA_APOS_FIM_MIN:
            return -atraso_min

    return 24 * 60
