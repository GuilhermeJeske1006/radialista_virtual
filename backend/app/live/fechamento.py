"""Reta final e encerramento do programa: o que o texto do locutor sabe sobre o fim.

O tempo (backtiming até o encerramento) é do relógio (app.live.relogio: planejar, planejar_fechamento,
marcar_ultima_musica). Aqui fica o que vira instrução de fala, para todo programa, com ou sem relógio:

- a fase do bloco pelo horário em que ele vai ao ar: reta final (pode avisar que está acabando, sem se despedir) e
  zona de fechamento (não convida mais para pedido: não há tempo de tocar);
- se o aviso de reta final já foi ao ar (uma vez basta: avisar o fim cedo e repetido empurra o ouvinte para fora);
- no encerramento, só dados reais da grade: quando o programa volta e qual programa entra em seguida.

Base: pesquisa §8 ("Encerramento": agradecer, dizer quando volta e o que segue na programação), referências de
apresentação (fechar como vírgula, não ponto: deixar um motivo para voltar e para continuar ligado) e as regras
invioláveis da skill referencia-radio (não prometer sem evento agendado). Desenho em
docs/melhoria-radio/encerramento/auditoria.md. Puro: não importa o router, o banco nem o Redis.
"""

import dataclasses
import datetime
import re
from collections.abc import Iterable, Sequence
from zoneinfo import ZoneInfo

from app.live.promessas import programa_volta_em
from app.live.relogio import CONFIG_PADRAO, ConfigRelogio, Ocorrencia, reta_final_s, zona_fechamento_s
from app.numeros import cardinal_feminino, numero_por_extenso
from app.util.texto import sem_acento

# Programa seguinte "em sequência": começa até este tanto antes ou depois do fim deste.
TOLERANCIA_PROGRAMA_SEGUINTE_S = 120
# Quantos dias à frente procurar a próxima exibição (uma semana cobre qualquer dias_semana).
DIAS_PROXIMA_EXIBICAO = 7

# Aviso de reta final já dado numa fala do histórico (texto normalizado, sem acento).
_AVISO_RETA_FINAL_RE = re.compile(
    r"\breta final\b|\bultimos minutos\b|\bfinalzinho\b|\bperto do fim\b|\bchegando ao fim\b"
    r"|\bcaminhando para o fim\b|\bja ja a gente (?:encerra|fecha)\b"
)
_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


@dataclasses.dataclass(frozen=True)
class Fechamento:
    """O que a fala sabe sobre o fim do programa. None no contexto = longe do fim (fora da reta final)."""

    segundos_para_fim: float
    zona: bool                          # dentro da zona de fechamento: sem convite para pedido ou mensagem
    avisada: bool                       # o histórico já tem o aviso de reta final
    ultima_musica: bool = False         # a faixa confirmada deste bloco é a última (Plano.ultima_musica)
    volta: str | None = None            # encerramento: "amanhã, às quinze horas"; None = sem volta na grade
    proximo_programa: str | None = None  # encerramento: programa da rádio que entra em seguida


def reta_final_avisada(historico: Iterable[str]) -> bool:
    """Alguma fala do histórico do painel ("categoria: texto") já avisou que o programa está acabando."""
    for linha in historico or ():
        texto = linha.split(":", 1)[1] if ":" in linha else linha
        if _AVISO_RETA_FINAL_RE.search(sem_acento(texto.lower())):
            return True
    return False


def fase_do_bloco(ocorrencia: Ocorrencia, instante: datetime.datetime, historico: Sequence[str], *,
                  ultima_musica: bool = False, cfg: ConfigRelogio = CONFIG_PADRAO) -> Fechamento | None:
    """Fase do bloco que vai ao ar em `instante`. None fora da reta final."""
    restante = (ocorrencia.fim - instante).total_seconds()
    if restante > reta_final_s(ocorrencia, cfg):
        return None
    return Fechamento(segundos_para_fim=max(0.0, restante), zona=restante <= zona_fechamento_s(ocorrencia, cfg),
                      avisada=reta_final_avisada(historico), ultima_musica=ultima_musica)


def hora_por_extenso(momento: datetime.time) -> str:
    """'às quinze horas', 'às quinze e trinta', 'à uma hora', 'ao meio-dia', 'à meia-noite' (nunca algarismo: o
    texto vai para o TTS)."""
    if momento.minute == 0:
        if momento.hour == 0:
            return "à meia-noite"
        if momento.hour == 12:
            return "ao meio-dia"
        if momento.hour == 1:
            return "à uma hora"
        return f"às {cardinal_feminino(momento.hour)} horas"
    hora = "uma" if momento.hour == 1 else cardinal_feminino(momento.hour)
    return f"{'à' if momento.hour == 1 else 'às'} {hora} e {numero_por_extenso(momento.minute)}"


def proxima_exibicao(programa, data_atual: datetime.date) -> datetime.date | None:
    """Próximo dia, depois de `data_atual` (o dia em que esta ocorrência começou), em que a grade tem o programa."""
    for dias in range(1, DIAS_PROXIMA_EXIBICAO + 1):
        data = data_atual + datetime.timedelta(days=dias)
        if programa_volta_em(programa, data):
            return data
    return None


def descrever_volta(programa, data_atual: datetime.date, hoje_local: datetime.date) -> str | None:
    """Quando o programa volta, em palavras ('amanhã, às quinze horas', 'na segunda-feira, às nove horas',
    'no próximo sábado, às dez horas'). None sem próxima exibição na grade (programa avulso)."""
    data = proxima_exibicao(programa, data_atual)
    if data is None:
        return None
    dias = (data - hoje_local).days
    dia = _DIAS[data.weekday()]
    artigo = "no" if data.weekday() >= 5 else "na"
    if dias <= 0:
        quando = "hoje"   # madrugada: o programa que acabou de manhã volta à noite
    elif dias == 1:
        quando = "amanhã"
    elif dias < 7:
        quando = f"{artigo} {dia}"
    else:
        quando = f"{artigo} {'próximo' if artigo == 'no' else 'próxima'} {dia}"
    return f"{quando}, {hora_por_extenso(programa.horario_inicio)}"


def programa_seguinte(programas: Iterable, atual, fim: datetime.datetime, timezone: str) -> str | None:
    """Nome do programa da rádio que começa quando este termina (dentro de TOLERANCIA_PROGRAMA_SEGUINTE_S), no dia da
    grade em que ele começa. Programas sem nome, inativos ou o próprio programa ficam de fora."""
    fuso = ZoneInfo(timezone)
    fim_local = fim.astimezone(fuso)
    candidatos = []
    for programa in programas:
        nome = (getattr(programa, "nome", "") or "").strip()
        if not nome or getattr(programa, "id", None) == getattr(atual, "id", None) \
                or not getattr(programa, "ativo", True):
            continue
        for data in (fim_local.date(), fim_local.date() - datetime.timedelta(days=1)):
            if not programa_volta_em(programa, data):
                continue
            inicio = datetime.datetime.combine(data, programa.horario_inicio, tzinfo=fuso)
            distancia = abs((inicio - fim_local).total_seconds())
            if distancia <= TOLERANCIA_PROGRAMA_SEGUINTE_S:
                candidatos.append((distancia, nome))
    return min(candidatos)[1] if candidatos else None


def completar_encerramento(fase: Fechamento, programa, ocorrencia: Ocorrencia, timezone: str,
                           programas: Iterable) -> Fechamento:
    """A fase do encerramento com a volta do programa e o programa seguinte da grade."""
    hoje_local = ocorrencia.fim.astimezone(ZoneInfo(timezone)).date()
    return dataclasses.replace(
        fase, volta=descrever_volta(programa, ocorrencia.data, hoje_local),
        proximo_programa=programa_seguinte(programas, programa, ocorrencia.fim, timezone),
    )
