"""Relógio da hora, espelho e hard time (F1 do plano de melhoria de rádio).

Vocabulário (skill referencia-radio): o *relógio* é o modelo de uma hora (eventos com início,
duração, natureza e hard time); o *espelho* é a ordem concreta da edição, montada do relógio para
cada hora da ocorrência do programa; *hard time* é o início que não pode atrasar; *backtiming* é o
espaço livre calculado de trás para frente até o próximo hard time.

O núcleo é puro: recebe o instante explícito, não chama `now()` nem lê o banco. Só o adaptador de
estado (`etapas_executadas` / `marcar_executada`) usa Redis, e falha aberto. Este módulo não importa
`app.live.router`.

Os números (unidades de fala, ritmo, tolerâncias) são hipóteses de projeto da skill referencia-radio
e da pesquisa (§5, §7, §9). Ficam em `ConfigRelogio`: o ritmo vem da calibração por voz da F2
(`app.live.ritmo_voz.wpm_para`). Nos formatos que aplicam orçamento, a unidade de fala e o bloco de cada tipo de
evento vêm do catálogo de formatos (`app.live.formatos`, F6, D8). Desenho completo em
docs/melhoria-radio/f1/auditoria.md (§5) e docs/melhoria-radio/f6/auditoria.md (§6.7).
"""

import datetime
import json
import logging
import math
import pathlib
from dataclasses import asdict, dataclass, field, replace
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.feriados import feriado_do_dia
from app.live.formatos import Formato, formato_pelo_booleano, unidade as unidade_do_formato
from app.live.orcamento import estimar_duracao_s, wpm_padrao

logger = logging.getLogger("radialista.live.relogio")

TipoEvento = Literal[
    "abertura", "musica", "link", "curadoria", "retorno", "participacao", "conversa", "quadro", "servico",
    "noticia", "manchetes", "atualizacao", "entrevista", "reportagem", "intervalo", "passagem", "fechamento",
]
Natureza = Literal["obrigatorio", "ajustavel", "reserva"]
Acao = Literal[
    "fala", "fala_reduzida", "fechamento_curto", "musica", "peca", "reserva", "adiantamento", "intervalo",
    "encerramento",
]

TIPOS_EVENTO: tuple[str, ...] = get_args(TipoEvento)
NATUREZAS: tuple[str, ...] = get_args(Natureza)
DURACAO_HORA_S = 3600
MAX_EVENTOS = 40
MAX_ROTULO = 80


def formatar_min_seg(segundos: float) -> str:
    total = int(round(segundos))
    return f"{total // 60:02d}:{total % 60:02d}"


def _erro(mensagem: str) -> PydanticCustomError:
    return PydanticCustomError("relogio_invalido", mensagem)


# ------------------------------------------------------------------------------------------------
# Modelo (JSON validado, coluna programas.relogio_hora)
# ------------------------------------------------------------------------------------------------

class EventoRelogio(BaseModel):
    # extra="ignore": aceita os campos de medição das fixtures da F0 (grupo, corresponde_a).
    model_config = ConfigDict(extra="ignore")

    inicio_s: int
    duracao_s: int
    tipo: TipoEvento
    rotulo: str = ""
    natureza: Natureza
    hard_time: bool = False

    @field_validator("tipo", mode="before")
    @classmethod
    def _tipo_conhecido(cls, valor):
        if valor not in TIPOS_EVENTO:
            raise _erro(f"Tipo de evento desconhecido: {valor!r}. Use um de: {', '.join(TIPOS_EVENTO)}.")
        return valor

    @field_validator("natureza", mode="before")
    @classmethod
    def _natureza_conhecida(cls, valor):
        if valor not in NATUREZAS:
            raise _erro(f"Natureza desconhecida: {valor!r}. Use obrigatorio, ajustavel ou reserva.")
        return valor

    @field_validator("inicio_s")
    @classmethod
    def _inicio_na_hora(cls, valor: int) -> int:
        if not 0 <= valor < DURACAO_HORA_S:
            raise _erro("O início do evento deve ficar entre 00:00 e 59:59 (0 a 3599 segundos).")
        return valor

    @field_validator("duracao_s")
    @classmethod
    def _duracao_positiva(cls, valor: int) -> int:
        if valor <= 0:
            raise _erro("A duração de cada evento deve ser maior que zero.")
        if valor > DURACAO_HORA_S:
            raise _erro("A duração de um evento não pode passar de 60:00.")
        return valor

    @field_validator("rotulo")
    @classmethod
    def _rotulo_curto(cls, valor: str) -> str:
        valor = (valor or "").strip()
        if len(valor) > MAX_ROTULO:
            raise _erro(f"O rótulo do evento tem no máximo {MAX_ROTULO} caracteres.")
        return valor


class RelogioHora(BaseModel):
    model_config = ConfigDict(extra="ignore")

    versao: Literal[1] = 1
    # Origem do relógio; None = personalizado.
    preset: Literal["A", "B", "C"] | None = None
    eventos: list[EventoRelogio]
    em_feriado: Literal["mesmo", "sem_intervalos", "sem_relogio"] = "mesmo"

    @field_validator("eventos")
    @classmethod
    def _quantidade(cls, eventos: list[EventoRelogio]) -> list[EventoRelogio]:
        if not 1 <= len(eventos) <= MAX_EVENTOS:
            raise _erro(f"O relógio precisa ter de 1 a {MAX_EVENTOS} eventos (recebidos: {len(eventos)}).")
        return eventos

    @model_validator(mode="after")
    def _continuo_e_soma_uma_hora(self) -> "RelogioHora":
        if self.eventos[0].inicio_s != 0:
            raise _erro("O primeiro evento do relógio deve começar em 00:00.")
        for anterior, seguinte in zip(self.eventos, self.eventos[1:]):
            fim = anterior.inicio_s + anterior.duracao_s
            if seguinte.inicio_s > fim:
                raise _erro(f"Há um buraco entre '{anterior.rotulo or anterior.tipo}' (termina em "
                            f"{formatar_min_seg(fim)}) e '{seguinte.rotulo or seguinte.tipo}' (começa em "
                            f"{formatar_min_seg(seguinte.inicio_s)}).")
            if seguinte.inicio_s < fim:
                raise _erro(f"Há sobreposição entre '{anterior.rotulo or anterior.tipo}' (termina em "
                            f"{formatar_min_seg(fim)}) e '{seguinte.rotulo or seguinte.tipo}' (começa em "
                            f"{formatar_min_seg(seguinte.inicio_s)}).")
        total = sum(e.duracao_s for e in self.eventos)
        if total != DURACAO_HORA_S:
            raise _erro(f"Os eventos somam {formatar_min_seg(total)}; o relógio precisa somar exatamente 60:00.")
        return self


def mensagens_de_erro(erro: ValidationError) -> list[str]:
    """Mensagens em português de uma validação de relógio, para a API e o painel."""
    return [item["msg"] for item in erro.errors()]


class TotaisRelogio(BaseModel):
    musica_s: int
    fala_s: int
    intervalo_s: int


def totais(relogio: RelogioHora) -> TotaisRelogio:
    soma = {"musica": 0, "fala": 0, "intervalo": 0}
    for evento in relogio.eventos:
        grupo = evento.tipo if evento.tipo in ("musica", "intervalo") else "fala"
        soma[grupo] += evento.duracao_s
    return TotaisRelogio(musica_s=soma["musica"], fala_s=soma["fala"], intervalo_s=soma["intervalo"])


class PresetRelogio(BaseModel):
    id: Literal["A", "B", "C"]
    nome: str
    descricao: str
    fonte: str
    hipotese: bool = True
    nota: str = ""
    relogio: RelogioHora


DIR_PRESETS = pathlib.Path(__file__).resolve().parent / "relogios"


def _carregar_presets() -> dict[str, PresetRelogio]:
    presets: dict[str, PresetRelogio] = {}
    for arquivo in sorted(DIR_PRESETS.glob("*.json")):
        preset = PresetRelogio.model_validate(json.loads(arquivo.read_text(encoding="utf-8")))
        presets[preset.id] = preset
    return presets


# Fonte de verdade dos relógios A/B/C. As fixtures da F0 (tests/fixtures/programas/relogios) só
# medem; um teste de paridade garante que os tempos são os mesmos.
PRESETS_INFO: dict[str, PresetRelogio] = _carregar_presets()
PRESETS: dict[str, RelogioHora] = {chave: preset.relogio for chave, preset in PRESETS_INFO.items()}


# ------------------------------------------------------------------------------------------------
# Configuração (hipóteses de projeto)
# ------------------------------------------------------------------------------------------------

UNIDADES_PADRAO: dict[str, tuple[int, int]] = {
    # Unidade de fala por tipo de evento, em segundos (mínimo, máximo). Origem: tabela "Unidades de
    # fala iniciais por formato" da skill referencia-radio e pesquisa §9. Vale no formato `padrao`; nos
    # formatos que aplicam orçamento vale a unidade do catálogo (F6, D8), limitada pela etapa e pelo espaço.
    "abertura": (20, 40),
    "retomada": (6, 20),
    "manchetes": (20, 60),
    "link": (10, 35),
    "curadoria": (15, 60),
    "retorno": (15, 60),
    "participacao": (20, 90),
    "conversa": (60, 180),
    "quadro": (60, 180),
    "entrevista": (60, 180),
    "reportagem": (60, 180),
    "servico": (20, 60),
    "noticia": (20, 60),
    "atualizacao": (20, 60),
    "passagem": (3, 15),
    "encerramento": (15, 45),
    "fechamento_curto": (6, 15),
    # Parte de um fechamento longo (B, C: 2 min) que vem antes do encerramento propriamente dito.
    "resumo": (20, 90),
    # Link de preenchimento (formato padrão) quando nenhuma faixa cabe antes do hard time.
    "preenchimento": (10, 60),
    # Anúncio de pedido real numa etapa de música.
    "musica": (4, 20),
}


@dataclass(frozen=True)
class ConfigRelogio:
    # Ritmo (palavras/min) das estimativas. Padrão: app.config.settings.fala_wpm_padrao, a mesma origem do
    # orçamento e do simulador; /proxima troca pelo ritmo calibrado da voz (app.live.ritmo_voz.wpm_para).
    wpm: float = field(default_factory=wpm_padrao)
    tolerancia_hard_time_s: int = 5        # critério de aceite da F1
    adiantamento_max_s: int = 90           # quanto um compromisso pode começar mais cedo (D3)
    # No fim do programa, começar cedo vira buraco no ar: a sobra antes do encerramento é menor.
    adiantamento_final_max_s: int = 45
    # Faixa ou peça pode terminar até este tanto depois do hard time: a pausa entre blocos (até 0,8 s no
    # ritmo editorial) ainda cabe na tolerância de 5 s do início do compromisso.
    folga_teto_s: int = 3
    # O encerramento usa a parte de cima do espaço que tem: mínimo = máximo − esta janela.
    janela_encerramento_s: int = 10
    graca_pos_fim_s: int = 1200            # igual a schedule._GRACA_APOS_FIM_MIN
    inicio_previsto_max_s: int = 1800      # horário previsto acima disso é ignorado
    musica_duracao_padrao_s: int = 210     # faixa de duração desconhecida
    # Menor faixa que se espera achar: uma sobra menor que isto antes do hard time não cabe outra
    # música. Usada para não escolher uma faixa que deixe uma sobra impossível de preencher.
    musica_duracao_min_s: int = 200
    # Abaixo disso nem se busca música (a busca rejeita faixas mais curtas, ver app.live.music).
    musica_busca_min_s: int = 120
    # Quanto uma faixa pode avançar sobre a etapa ajustável seguinte (que então se desloca).
    musica_invasao_max_s: int = 60
    musica_tentativas_teto: int = 3        # buscas por faixa que caiba antes de usar a alternativa
    espaco_min_pedido_s: int = 330         # espaço para anúncio + música pedida antes do hard time
    max_etapas_puladas: int = 4
    ttl_estado_s: int = 6 * 60 * 60        # igual a _TTL_SESSAO_AO_VIVO; renovado a cada marcação
    # Painel antigo sem inicio_previsto (F3): o servidor estima o horário pela cadeia de blocos gerados.
    # Quanto antes do início a primeira geração ainda acha a ocorrência (a mesma conta do prewarm, 90 s + folga).
    preparo_sem_painel_max_s: int = 120
    # Blocos sem vinheta que o painel gera à frente (frontend-painel/lib/filaPreparo.ts): o bloco k é gerado
    # quando o bloco k - antecedência começa a tocar.
    antecedencia_painel_antigo: int = 2
    max_elos_cadeia: int = 50
    unidades: dict[str, tuple[int, int]] = field(default_factory=lambda: dict(UNIDADES_PADRAO))


CONFIG_PADRAO = ConfigRelogio()


# ------------------------------------------------------------------------------------------------
# Tabela declarativa: como cada tipo de evento vira bloco do ao vivo
# ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RegraBloco:
    # "fala": um bloco de fala; "musica": faixa sem fala; "intervalo": patrocinadores;
    # "pecas": sequência de peças (vinhetas e falas) na ordem. O formato pode trocar o bloco de um tipo de
    # evento (Formato.blocos_relogio; o musical troca as falas longas por retomada).
    modo: Literal["fala", "musica", "intervalo", "pecas"]
    bloco_padrao: str
    repete: bool
    unidade: str | None


BLOCOS_POR_TIPO: dict[str, RegraBloco] = {
    "abertura": RegraBloco("pecas", "abertura", False, "abertura"),
    "retomada": RegraBloco("pecas", "retomada", False, "retomada"),
    "manchetes": RegraBloco("pecas", "escalada", False, "manchetes"),
    "musica": RegraBloco("musica", "musica", True, "musica"),
    "link": RegraBloco("fala", "comentario", False, "link"),
    "curadoria": RegraBloco("fala", "comentario", False, "curadoria"),
    "retorno": RegraBloco("fala", "chamada_ouvinte", False, "retorno"),
    "participacao": RegraBloco("fala", "chamada_ouvinte", False, "participacao"),
    "conversa": RegraBloco("fala", "comentario", True, "conversa"),
    # "@quadro": primeiro rótulo de quadros_fixos presente na estrutura; senão comentário.
    "quadro": RegraBloco("fala", "@quadro", True, "quadro"),
    "servico": RegraBloco("fala", "servico", True, "servico"),
    "noticia": RegraBloco("fala", "noticia", True, "noticia"),
    "reportagem": RegraBloco("fala", "noticia", True, "reportagem"),
    "atualizacao": RegraBloco("fala", "escalada", False, "atualizacao"),
    # Sem convidado real (F12/F13): contingência "convidado não entrou → conteúdo aprovado".
    "entrevista": RegraBloco("fala", "comentario", True, "entrevista"),
    "intervalo": RegraBloco("intervalo", "patrocinador", True, None),
    "identificacao": RegraBloco("pecas", "identificacao", False, "passagem"),
    "encerramento": RegraBloco("fala", "encerramento", False, "encerramento"),
    "resumo": RegraBloco("fala", "comentario", False, "resumo"),
}
# Tipos de evento cujo bloco é jornalístico: sem fonte de notícia configurada viram música, como a
# regra atual do ao vivo ("sem fonte vira música").
TIPOS_NOTICIOSOS = ("noticia", "servico", "reportagem", "atualizacao")


# ------------------------------------------------------------------------------------------------
# Estruturas do serviço
# ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Peca:
    id: int
    duracao_s: float


@dataclass(frozen=True)
class PecasDisponiveis:
    """Peças reais do programa, montadas pela rota só quando há relógio."""

    vinhetas_abertura: tuple[Peca, ...] = ()
    vinhetas_passagem: tuple[Peca, ...] = ()
    patrocinadores: tuple[Peca, ...] = ()
    quadros: tuple[str, ...] = ()
    vinheta_encerramento_s: float = 0.0
    tem_fonte_noticia: bool = False


@dataclass(frozen=True)
class Ocorrencia:
    inicio: datetime.datetime    # UTC
    fim: datetime.datetime       # UTC
    data: datetime.date          # dia (no fuso da rádio) em que a ocorrência começou

    @property
    def chave(self) -> str:
        return self.inicio.strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class Etapa:
    evento: EventoRelogio
    hora: int
    inicio: datetime.datetime    # UTC
    fim: datetime.datetime       # UTC
    tipo_efetivo: str
    hard_time: bool
    natureza: str

    @property
    def chave(self) -> str:
        return f"{self.hora}:{self.evento.inicio_s}"

    @property
    def duracao_s(self) -> float:
        return (self.fim - self.inicio).total_seconds()

    @property
    def regra(self) -> RegraBloco:
        return BLOCOS_POR_TIPO[self.tipo_efetivo]


@dataclass(frozen=True)
class Plano:
    instante: datetime.datetime
    ocorrencia: Ocorrencia
    etapa: Etapa
    proximo_compromisso: Etapa | None
    segundos_ate_hard_time: float | None
    espaco_s: float | None
    acao: Acao
    tipo_bloco: str
    primeira: bool = False
    orcamento_s: tuple[int, int] | None = None
    palavras_max: int | None = None
    duracao_max_musica_s: int | None = None
    # Sobra (segundos antes do hard time) que nenhuma faixa ou peça preenche: a música escolhida
    # não pode deixar o espaço dentro deste intervalo.
    sobra_proibida_s: tuple[int, int] | None = None
    musica_sem_fala: bool = True
    aceita_pedido_musica: bool = False
    alternativa: "Plano | None" = None
    chave_estado: str | None = None
    puladas: tuple[str, ...] = ()
    instrucao: str | None = None
    # Adiantamento acima de adiantamento_max_s: nada coube e o compromisso começa mais cedo.
    forcado: bool = False
    # F4: etapas depois desta, ainda não concluídas, até o fim da ocorrência (a agenda das promessas).
    seguintes: tuple[Etapa, ...] = ()
    # F4: etapas com promessa aberta (chaves "h:inicio_s"); o backtiming reserva o tempo da fala delas.
    obrigacoes: frozenset[str] = frozenset()


# ------------------------------------------------------------------------------------------------
# Funções puras
# ------------------------------------------------------------------------------------------------

def relogio_do_programa(programa, data: datetime.date | None = None) -> RelogioHora | None:
    """Relógio gravado no programa. JSON inválido no banco → None (caminho atual) e log.
    Com `data` de feriado e em_feriado="sem_relogio", também None."""
    bruto = getattr(programa, "relogio_hora", None)
    if not bruto:
        return None
    try:
        relogio = RelogioHora.model_validate(bruto)
    except ValidationError as erro:
        logger.warning("relogio_invalido_no_banco programa_id=%s erros=%s", getattr(programa, "id", None),
                       mensagens_de_erro(erro))
        return None
    if data is not None and relogio.em_feriado == "sem_relogio" and eh_feriado(data, programa):
        return None
    return relogio


def eh_feriado(data: datetime.date, programa) -> bool:
    return feriado_do_dia(data, getattr(programa, "feriados_municipais", None) or []) is not None


def _utc(valor: datetime.datetime) -> datetime.datetime:
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=datetime.timezone.utc)
    return valor.astimezone(datetime.timezone.utc)


def ler_inicio_previsto(texto: str | None) -> datetime.datetime | None:
    """ISO 8601 do painel. Inválido → None (vale o horário atual), com log."""
    if not texto:
        return None
    try:
        return datetime.datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    except ValueError:
        logger.info("relogio_inicio_previsto_invalido valor=%r", texto[:64])
        return None


def instante_previsto(valor: datetime.datetime | None, agora: datetime.datetime,
                      cfg: ConfigRelogio = CONFIG_PADRAO) -> tuple[datetime.datetime, bool]:
    """Instante em que o bloco vai ao ar. None ou passado → agora; sem fuso → UTC; mais de
    `inicio_previsto_max_s` à frente → agora, com aceito=False."""
    agora = _utc(agora)
    if valor is None:
        return agora, False
    valor = _utc(valor)
    if valor <= agora:
        return agora, True
    if (valor - agora).total_seconds() > cfg.inicio_previsto_max_s:
        logger.info("relogio_inicio_previsto_ignorado adiante_s=%s", round((valor - agora).total_seconds()))
        return agora, False
    return valor, True


def _duracao_programa_min(programa) -> int:
    inicio = programa.horario_inicio.hour * 60 + programa.horario_inicio.minute
    fim = programa.horario_fim.hour * 60 + programa.horario_fim.minute
    if fim <= inicio:
        fim += 24 * 60
    return fim - inicio


def ocorrencia_em(programa, timezone: str, instante: datetime.datetime,
                  cfg: ConfigRelogio = CONFIG_PADRAO) -> Ocorrencia | None:
    """Ocorrência do programa que contém `instante` (de início até fim + graça), ou None.

    Na madrugada, a data é o dia em que o programa começou (como schedule.programa_no_ar). O fim é
    o horário de parede do fim: com horário de verão a ocorrência pode ter 23 h ou 25 h.
    """
    fuso = ZoneInfo(timezone)
    instante = _utc(instante)
    local = instante.astimezone(fuso)
    duracao = datetime.timedelta(minutes=_duracao_programa_min(programa))
    for dias_atras in (0, 1):
        data = local.date() - datetime.timedelta(days=dias_atras)
        if programa.data_especifica is not None:
            if data != programa.data_especifica:
                continue
        elif programa.dias_semana and data.weekday() not in programa.dias_semana:
            continue
        inicio_local = datetime.datetime.combine(data, programa.horario_inicio, tzinfo=fuso)
        fim_local = (inicio_local.replace(tzinfo=None) + duracao).replace(tzinfo=fuso)
        inicio, fim = _utc(inicio_local), _utc(fim_local)
        if inicio <= instante <= fim + datetime.timedelta(seconds=cfg.graca_pos_fim_s):
            return Ocorrencia(inicio=inicio, fim=fim, data=data)
    return None


def _transformar(evento: EventoRelogio, hora: int, *, eh_feriado: bool, relogio: RelogioHora,
                 pecas: PecasDisponiveis) -> tuple[str, bool, str]:
    """(tipo_efetivo, hard_time, natureza) de um evento numa hora concreta."""
    tipo, hard, natureza = evento.tipo, evento.hard_time, evento.natureza
    if tipo == "intervalo" and ((eh_feriado and relogio.em_feriado == "sem_intervalos") or not pecas.patrocinadores):
        # Feriado sem intervalos, ou programa sem patrocinador na sequência: a janela vira música.
        return "musica", False, "ajustavel"
    if tipo == "abertura" and hora > 0:
        return "retomada", hard, natureza
    if tipo == "manchetes":
        if hora == 0:
            return "manchetes", hard, natureza
        return ("atualizacao" if pecas.tem_fonte_noticia else "musica"), hard, natureza
    if tipo in TIPOS_NOTICIOSOS and not pecas.tem_fonte_noticia:
        return "musica", hard, natureza
    if tipo in ("passagem", "fechamento"):
        return "identificacao", hard, natureza
    return tipo, hard, natureza


def montar_espelho(relogio: RelogioHora, ocorrencia: Ocorrencia, cfg: ConfigRelogio = CONFIG_PADRAO, *,
                   eh_feriado: bool = False, pecas: PecasDisponiveis = PecasDisponiveis()) -> list[Etapa]:
    """Espelho da ocorrência inteira: o relógio repetido a cada hora a partir do início (D1),
    truncado no fim, terminando sempre num encerramento obrigatório com hard time."""
    total_s = (ocorrencia.fim - ocorrencia.inicio).total_seconds()
    etapas: list[Etapa] = []
    for hora in range(max(1, math.ceil(total_s / DURACAO_HORA_S))):
        base = ocorrencia.inicio + datetime.timedelta(seconds=hora * DURACAO_HORA_S)
        for evento in relogio.eventos:
            inicio = base + datetime.timedelta(seconds=evento.inicio_s)
            if inicio >= ocorrencia.fim:
                break
            fim = min(inicio + datetime.timedelta(seconds=evento.duracao_s), ocorrencia.fim)
            tipo, hard, natureza = _transformar(evento, hora, eh_feriado=eh_feriado, relogio=relogio, pecas=pecas)
            etapas.append(Etapa(evento, hora, inicio, fim, tipo, hard, natureza))

    ultima = etapas[-1]
    duracao_enc = min(cfg.unidades["encerramento"][1], int(total_s))
    if ultima.evento.tipo in ("passagem", "fechamento") and ultima.fim == ocorrencia.fim \
            and ultima.duracao_s == ultima.evento.duracao_s:
        if ultima.duracao_s <= duracao_enc:
            etapas[-1] = replace(ultima, tipo_efetivo="encerramento", hard_time=True, natureza="obrigatorio")
            return etapas
        # Fechamento mais longo que a unidade de encerramento: primeiro um resumo (mantém o hard time
        # do relógio), depois a despedida nos últimos segundos.
        etapas[-1] = replace(ultima, tipo_efetivo="resumo")

    # Fim que não cai no fim do relógio (ou fechamento longo): encerramento sintético no fim.
    inicio_enc = ocorrencia.fim - datetime.timedelta(seconds=duracao_enc)
    truncadas = []
    for etapa in etapas:
        if etapa.inicio >= inicio_enc:
            continue
        truncadas.append(replace(etapa, fim=min(etapa.fim, inicio_enc)))
    hora_enc = int((inicio_enc - ocorrencia.inicio).total_seconds() // DURACAO_HORA_S)
    posicao = int((inicio_enc - ocorrencia.inicio).total_seconds() - hora_enc * DURACAO_HORA_S)
    sintetico = EventoRelogio(inicio_s=posicao, duracao_s=duracao_enc, tipo="fechamento", rotulo="Encerramento",
                              natureza="obrigatorio", hard_time=True)
    truncadas.append(Etapa(sintetico, hora_enc, inicio_enc, ocorrencia.fim, "encerramento", True, "obrigatorio"))
    return truncadas


def etapas_da_hora(relogio: RelogioHora, ocorrencia: Ocorrencia, hora: int, cfg: ConfigRelogio = CONFIG_PADRAO, *,
                   eh_feriado: bool = False, pecas: PecasDisponiveis = PecasDisponiveis()) -> list[Etapa]:
    return [e for e in montar_espelho(relogio, ocorrencia, cfg, eh_feriado=eh_feriado, pecas=pecas) if e.hora == hora]


def _indice_contendo(espelho: list[Etapa], instante: datetime.datetime) -> int:
    for indice, etapa in enumerate(espelho):
        if etapa.inicio <= instante < etapa.fim:
            return indice
    return 0 if instante < espelho[0].inicio else len(espelho) - 1


def etapa_em(relogio: RelogioHora, ocorrencia: Ocorrencia, instante: datetime.datetime,
             cfg: ConfigRelogio = CONFIG_PADRAO, **kwargs) -> Etapa:
    espelho = montar_espelho(relogio, ocorrencia, cfg, **kwargs)
    return espelho[_indice_contendo(espelho, _utc(instante))]


def proximo_compromisso(relogio: RelogioHora, ocorrencia: Ocorrencia, instante: datetime.datetime,
                        cfg: ConfigRelogio = CONFIG_PADRAO, **kwargs) -> Etapa | None:
    instante = _utc(instante)
    return next((e for e in montar_espelho(relogio, ocorrencia, cfg, **kwargs) if e.hard_time and e.inicio > instante),
                None)


def segundos_ate_hard_time(relogio: RelogioHora, ocorrencia: Ocorrencia, instante: datetime.datetime,
                           cfg: ConfigRelogio = CONFIG_PADRAO, **kwargs) -> float | None:
    compromisso = proximo_compromisso(relogio, ocorrencia, instante, cfg, **kwargs)
    return None if compromisso is None else (compromisso.inicio - _utc(instante)).total_seconds()


def espaco_livre(relogio: RelogioHora, ocorrencia: Ocorrencia, instante: datetime.datetime, executadas: set[str],
                 cfg: ConfigRelogio = CONFIG_PADRAO, **kwargs) -> float:
    """Backtiming: segundos até o próximo hard time menos os obrigatórios (sem hard time) que ainda
    precisam acontecer antes dele."""
    instante = _utc(instante)
    espelho = montar_espelho(relogio, ocorrencia, cfg, **kwargs)
    decisao = _Decisao(espelho, ocorrencia, instante, formato_pelo_booleano(False), None, executadas,
                       kwargs.get("pecas") or PecasDisponiveis(), cfg)
    indice = _indice_contendo(espelho, instante)
    compromisso = decisao.compromisso_apos(indice)
    return decisao.espaco(indice, compromisso)


def _categoria_simples(tipo: str) -> str:
    """Categoria do bloco pelas regras de prefixo do ao vivo, sem classificação por LLM."""
    bruto = (tipo or "").strip().lower()
    if bruto in ("retomada", "identificacao"):
        return "abertura"
    for base in ("musica", "noticia", "escalada", "servico", "chamada_ouvinte", "abertura", "comentario",
                 "encerramento"):
        if bruto == base or bruto.startswith((f"{base} ", f"{base}_")):
            return base
    return bruto


class _Decisao:
    """Decide o próximo bloco num espelho já montado (auditoria F1 §5.5, "Decisão")."""

    def __init__(self, espelho, ocorrencia, instante, formato, ultima_categoria, executadas, pecas, cfg,
                 obrigacoes: frozenset[str] = frozenset()):
        self.espelho: list[Etapa] = espelho
        self.ocorrencia: Ocorrencia = ocorrencia
        self.instante: datetime.datetime = instante
        self.formato: Formato = formato
        self.ultima_categoria: str | None = ultima_categoria
        self.executadas: set[str] = set(executadas)
        self.pecas: PecasDisponiveis = pecas
        self.cfg: ConfigRelogio = cfg
        self.obrigacoes: frozenset[str] = frozenset(obrigacoes)

    # --- tempo ----------------------------------------------------------------------------------

    def _ate(self, momento: datetime.datetime) -> float:
        return (momento - self.instante).total_seconds()

    def compromisso_apos(self, indice: int) -> int | None:
        return next((j for j in range(indice + 1, len(self.espelho)) if self.espelho[j].hard_time), None)

    def espaco(self, indice: int, compromisso: int | None) -> float:
        if compromisso is None:
            return self._ate(self.ocorrencia.fim)
        espaco = self._ate(self.espelho[compromisso].inicio)
        for j in range(indice + 1, compromisso):
            etapa = self.espelho[j]
            if etapa.natureza == "obrigatorio" and not etapa.hard_time and not self.concluida(etapa):
                espaco -= etapa.duracao_s
            elif etapa.chave in self.obrigacoes and not etapa.hard_time and not self.concluida(etapa):
                espaco -= self.reserva_obrigacao(etapa)
        return espaco

    def reserva_obrigacao(self, etapa: Etapa) -> float:
        """Etapa com promessa aberta (F4): reserva o máximo da unidade de fala dela, não a duração da etapa
        ("Participação ou jogo" do C tem 7 min de etapa e 20-90 s de fala), limitado à duração."""
        unidade = etapa.regra.unidade
        maximo = self.cfg.unidades[unidade][1] if unidade in self.cfg.unidades else etapa.duracao_s
        return min(float(maximo), etapa.duracao_s)

    # --- estado ---------------------------------------------------------------------------------

    def _pecas_da_etapa(self, etapa: Etapa) -> list[tuple[str, str, object]]:
        """(chave, tipo, valor) das peças de uma etapa de peças, na ordem."""
        pecas: list[tuple[str, str, object]] = []
        tipo = etapa.tipo_efetivo
        if tipo == "abertura" or (tipo == "manchetes" and etapa.hora == 0):
            pecas += [(f"{etapa.chave}:vinheta:{v.id}", "vinheta", v) for v in self.pecas.vinhetas_abertura]
            pecas.append((f"{etapa.chave}:fala:abertura", "fala", ("abertura", "abertura", True)))
            if tipo == "manchetes" and self.pecas.tem_fonte_noticia:
                pecas.append((f"{etapa.chave}:fala:escalada", "fala", ("escalada", "manchetes", False)))
        elif tipo == "retomada":
            pecas.append((f"{etapa.chave}:fala:retomada", "fala", ("retomada", "retomada", False)))
        elif tipo == "identificacao":
            if self.pecas.vinhetas_passagem:
                pecas.append((f"{etapa.chave}:vinheta:{self.pecas.vinhetas_passagem[0].id}", "vinheta",
                              self.pecas.vinhetas_passagem[0]))
            else:
                pecas.append((f"{etapa.chave}:fala:identificacao", "fala", ("identificacao", "passagem", False)))
        elif tipo == "manchetes":
            pecas.append((f"{etapa.chave}:fala:escalada", "fala", ("escalada", "manchetes", False)))
        return pecas

    def concluida(self, etapa: Etapa) -> bool:
        if etapa.chave in self.executadas:
            return True
        modo = etapa.regra.modo
        if modo == "pecas":
            return all(chave in self.executadas for chave, _, _ in self._pecas_da_etapa(etapa))
        if modo == "intervalo":
            return all(f"{etapa.chave}:patrocinador:{p.id}" in self.executadas for p in self.pecas.patrocinadores)
        return False

    def _deslocavel(self, etapa: Etapa) -> bool:
        return etapa.regra.modo in ("pecas", "intervalo") or not etapa.regra.repete

    def vigente(self) -> int:
        contem = _indice_contendo(self.espelho, self.instante)
        ultimo_hard = max((j for j in range(contem + 1)
                           if self.espelho[j].hard_time and self.espelho[j].inicio <= self.instante), default=0)
        for j in range(ultimo_hard, contem):
            etapa = self.espelho[j]
            if self._deslocavel(etapa) and not self.concluida(etapa):
                logger.info("relogio_etapa_deslocada chave=%s atraso_s=%s", etapa.chave,
                            round(-self._ate(etapa.inicio)))
                return j
        return contem

    # --- orçamento ------------------------------------------------------------------------------

    def unidade(self, unidade: str, tipo_bloco: str, primeira: bool) -> tuple[int, int, int | None]:
        """(mínimo, máximo, teto de palavras). Sem orçamento aplicado (`padrao`), a unidade do tipo de evento em
        `cfg.unidades`; com orçamento, a unidade do formato para o papel do bloco (D8: o formato vence, e a etapa e
        o espaço limitam depois, em `_fala`). No musical é o mesmo que o menor dos dois de antes (§2, fato 5)."""
        if not self.formato.aplica_orcamento:
            minimo, maximo = self.cfg.unidades[unidade]
            return minimo, maximo, None
        u = unidade_do_formato(self.formato, tipo_bloco, primeira, quadro=tipo_bloco in self.pecas.quadros)
        return u.min_s, u.max_s, u.max_palavras

    def _palavras(self, maximo: int, teto_formato: int | None) -> int:
        palavras = math.floor(maximo * self.cfg.wpm / 60)
        return min(palavras, teto_formato) if teto_formato is not None else palavras

    def _bloco(self, tipo_evento: str, regra: RegraBloco) -> str:
        bloco = self.formato.blocos_relogio.get(tipo_evento, regra.bloco_padrao)
        if bloco == "@quadro":
            return self.pecas.quadros[0] if self.pecas.quadros else "comentario"
        return bloco

    # --- planos ---------------------------------------------------------------------------------

    def _plano(self, indice: int, acao: Acao, tipo_bloco: str, **campos) -> Plano:
        etapa = self.espelho[indice]
        compromisso = self.compromisso_apos(indice)
        espaco = self.espaco(indice, compromisso)
        alvo = self.espelho[compromisso] if compromisso is not None else None
        if etapa.hard_time and self._ate(etapa.inicio) > self.cfg.tolerancia_hard_time_s \
                and acao not in ("encerramento", "reserva"):
            # O compromisso começa antes da hora marcada: nunca atrasado, no máximo adiantado.
            campos.setdefault("forcado", self._ate(etapa.inicio) > self.cfg.adiantamento_max_s)
            acao = "adiantamento"
        if campos.get("forcado"):
            logger.warning("relogio_adiantamento_acima_do_maximo chave=%s adiantado_s=%s", etapa.chave,
                           round(self._ate(etapa.inicio)))
        return Plano(
            instante=self.instante, ocorrencia=self.ocorrencia, etapa=etapa, proximo_compromisso=alvo,
            segundos_ate_hard_time=round(self._ate(alvo.inicio), 2) if alvo is not None else None,
            espaco_s=round(espaco, 2), acao=acao, tipo_bloco=tipo_bloco,
            seguintes=tuple(e for e in self.espelho[indice + 1:] if not self.concluida(e)),
            obrigacoes=self.obrigacoes, **campos,
        )

    def _fala(self, indice: int, unidade: str, tipo_bloco: str, *, disponivel: float, primeira: bool = False,
              chave: str | None, repete: bool) -> Plano | None:
        espaco = self.espaco(indice, self.compromisso_apos(indice))
        minimo, maximo_unidade, teto_palavras = self.unidade(unidade, tipo_bloco, primeira)
        maximo = min(maximo_unidade, disponivel, espaco)
        if maximo >= minimo:
            maximo = math.floor(maximo)
            return self._plano(indice, "fala" if maximo >= maximo_unidade else "fala_reduzida", tipo_bloco,
                               primeira=primeira, orcamento_s=(minimo, maximo),
                               palavras_max=self._palavras(maximo, teto_palavras), chave_estado=chave)
        etapa = self.espelho[indice]
        chave_fc = f"{etapa.chave}:fechamento_curto"
        fc_min, fc_max = self.cfg.unidades["fechamento_curto"]
        if repete and self.ultima_categoria == _categoria_simples(tipo_bloco) and chave_fc not in self.executadas \
                and espaco >= fc_min:
            # "Debate estourou": fecha o assunto em andamento em vez de abrir outro.
            limite = math.floor(min(fc_max, espaco))
            return self._plano(indice, "fechamento_curto", tipo_bloco, orcamento_s=(fc_min, limite),
                               palavras_max=self._palavras(limite, teto_palavras), chave_estado=chave_fc,
                               instrucao="fechamento_curto")
        return None

    def _etapa_fala(self, indice: int) -> Plano | None:
        etapa = self.espelho[indice]
        regra = etapa.regra
        disponivel = self._ate(etapa.fim) if regra.repete else etapa.duracao_s
        return self._fala(indice, regra.unidade, self._bloco(etapa.tipo_efetivo, regra), disponivel=disponivel,
                          chave=None if regra.repete else etapa.chave, repete=regra.repete)

    def _etapa_pecas(self, indice: int) -> Plano | None:
        etapa = self.espelho[indice]
        pecas = self._pecas_da_etapa(etapa)
        disponivel = etapa.duracao_s - sum(v.duracao_s for _, tipo, v in pecas if tipo == "vinheta")
        espaco = self.espaco(indice, self.compromisso_apos(indice))
        for chave, tipo, valor in pecas:
            if chave in self.executadas:
                continue
            if tipo == "vinheta":
                if valor.duracao_s > espaco + self.cfg.folga_teto_s:
                    continue
                return self._plano(indice, "peca", f"vinheta:{valor.id}", chave_estado=chave)
            bloco, unidade, primeira = valor
            plano = self._fala(indice, unidade, bloco, disponivel=disponivel, primeira=primeira and etapa.hora == 0,
                               chave=chave, repete=False)
            if plano is not None:
                return plano
        return None

    def _etapa_intervalo(self, indice: int) -> Plano | None:
        etapa = self.espelho[indice]
        espaco = self.espaco(indice, self.compromisso_apos(indice))
        for peca in self.pecas.patrocinadores:
            chave = f"{etapa.chave}:patrocinador:{peca.id}"
            if chave in self.executadas or peca.duracao_s > espaco + self.cfg.folga_teto_s:
                continue
            return self._plano(indice, "intervalo", f"patrocinador:{peca.id}", chave_estado=chave)
        return None

    def _etapa_musica(self, indice: int, puladas: list[str]) -> Plano | None:
        compromisso = self.compromisso_apos(indice)
        # Etapas de música seguidas formam uma janela só; ela termina na primeira etapa que não é música.
        seguinte = next((j for j in range(indice + 1, len(self.espelho)) if self.espelho[j].regra.modo != "musica"),
                        len(self.espelho) - 1)
        if seguinte == compromisso:
            return self._janela(indice, compromisso, puladas)
        espaco = self.espaco(indice, compromisso)
        teto = min(espaco + self.cfg.folga_teto_s,
                   max(0.0, self._ate(self.espelho[seguinte].inicio)) + self.cfg.musica_invasao_max_s)
        # Nenhuma faixa cabe: a etapa ajustável seguinte começa mais cedo (desloca para antes).
        alternativa = self._a_partir(seguinte, puladas)
        if teto < self.cfg.musica_busca_min_s:
            return alternativa
        return self._plano_musica(indice, teto, None, alternativa, puladas)

    def _plano_musica(self, indice: int, teto: float, sobra: tuple[int, int] | None, alternativa: Plano,
                      puladas: list[str]) -> Plano:
        minimo, maximo, teto_palavras = self.unidade("musica", "musica", False)
        return self._plano(
            indice, "musica", "musica", duracao_max_musica_s=math.floor(teto), sobra_proibida_s=sobra,
            aceita_pedido_musica=teto >= self.cfg.espaco_min_pedido_s, orcamento_s=(minimo, maximo),
            palavras_max=self._palavras(maximo, teto_palavras), alternativa=alternativa, puladas=tuple(puladas),
        )

    def _janela(self, base: int, compromisso: int, puladas: list[str]) -> Plano:
        """Espaço até o hard time `compromisso`, contado a partir da etapa `base`: música que caiba (sem
        deixar sobra impossível), senão reserva, link de preenchimento e, por último, adiantamento."""
        espaco = self.espaco(base, compromisso)
        alternativa = self._alternativa_antes_do_compromisso(base, compromisso, espaco, puladas)
        teto = espaco + self.cfg.folga_teto_s
        if teto < self.cfg.musica_busca_min_s:
            return alternativa
        preenchimento = self.cfg.unidades["preenchimento"][1] if self.formato.comportamento.preenchimento_relogio \
            else 0
        final = self.espelho[compromisso].tipo_efetivo == "encerramento"
        adiantamento = self.cfg.adiantamento_final_max_s if final else self.cfg.adiantamento_max_s
        piso, topo = adiantamento + preenchimento, self.cfg.musica_duracao_min_s
        return self._plano_musica(base, teto, (piso, topo) if topo > piso else None, alternativa, puladas)

    def _alternativa_antes_do_compromisso(self, indice: int, compromisso: int, espaco: float,
                                          puladas: list[str]) -> Plano:
        """Nenhuma faixa cabe antes do hard time: reserva, link de preenchimento, adiantamento. Reserva e
        link usam o mínimo que deixa o resto dentro do adiantamento permitido, quando a unidade deixa."""
        etapa = self.espelho[indice]
        final = self.espelho[compromisso].tipo_efetivo == "encerramento"
        permitido = self.cfg.adiantamento_final_max_s if final else self.cfg.adiantamento_max_s

        def orcamento(minimo: int, maximo: int) -> tuple[int, int]:
            limite = math.floor(min(maximo, espaco))
            return max(minimo, min(limite, math.floor(espaco - permitido))), limite

        chave_reserva = f"{etapa.chave}:reserva"
        if chave_reserva not in self.executadas:
            vinheta = next((v for v in self.pecas.vinhetas_passagem
                            if v.duracao_s <= espaco + self.cfg.folga_teto_s), None)
            if vinheta is not None:
                return self._plano(indice, "reserva", f"vinheta:{vinheta.id}", chave_estado=chave_reserva,
                                   puladas=tuple(puladas))
            p_min, p_max, teto_palavras = self.unidade("passagem", "identificacao", False)
            if espaco >= p_min:
                minimo, limite = orcamento(p_min, p_max)
                return self._plano(indice, "reserva", "identificacao", orcamento_s=(minimo, limite),
                                   palavras_max=self._palavras(limite, teto_palavras), chave_estado=chave_reserva,
                                   puladas=tuple(puladas))
        chave_link = f"{etapa.chave}:preenchimento"
        l_min, l_max = self.cfg.unidades["preenchimento"]
        if self.formato.comportamento.preenchimento_relogio and chave_link not in self.executadas \
                and espaco >= l_min:
            minimo, limite = orcamento(l_min, l_max)
            return self._plano(indice, "reserva", "comentario", orcamento_s=(minimo, limite),
                               palavras_max=self._palavras(limite, None), chave_estado=chave_link,
                               puladas=tuple(puladas))
        return self._a_partir(compromisso, puladas, adiantar=True)

    def _encerramento(self, indice: int, puladas: list[str]) -> Plano:
        minimo, maximo, teto_palavras = self.unidade("encerramento", "encerramento", False)
        disponivel = self._ate(self.ocorrencia.fim) - self.pecas.vinheta_encerramento_s
        limite = max(minimo, min(maximo, math.floor(disponivel)))
        minimo = max(minimo, limite - self.cfg.janela_encerramento_s)
        return self._plano(indice, "encerramento", "encerramento", orcamento_s=(minimo, limite),
                           palavras_max=self._palavras(limite, teto_palavras), puladas=tuple(puladas))

    def _a_partir(self, indice: int, puladas: list[str], adiantar: bool = False) -> Plano:
        """Primeira etapa, a partir de `indice`, que produz um bloco agora. Um hard time ainda distante
        não é antecipado direto: o espaço até ele vira janela (música, reserva), salvo `adiantar`."""
        puladas = list(puladas)
        while indice < len(self.espelho):
            etapa = self.espelho[indice]
            if self.concluida(etapa):
                indice += 1
                continue
            cedo = etapa.hard_time and self._ate(etapa.inicio) > self.cfg.tolerancia_hard_time_s
            if cedo and not adiantar and indice > 0:
                return self._janela(indice - 1, indice, puladas)
            adiantar = False
            if etapa.tipo_efetivo == "encerramento":
                return self._encerramento(indice, puladas)
            if len(puladas) > self.cfg.max_etapas_puladas:
                compromisso = self.compromisso_apos(indice - 1)
                if compromisso is not None and compromisso != indice:
                    indice = compromisso
                    continue
            plano = self._etapa(indice, puladas)
            if plano is not None:
                return plano if plano.puladas or not puladas else replace(plano, puladas=tuple(puladas))
            if self._deslocavel(etapa):
                logger.info("relogio_etapa_pulada chave=%s tipo=%s motivo=sem_espaco", etapa.chave, etapa.tipo_efetivo)
                if etapa.chave in self.obrigacoes:
                    # A promessa para esta etapa vence e vira contingência na próxima fala (F4).
                    logger.warning("relogio_promessa_pulada chave=%s tipo=%s", etapa.chave, etapa.tipo_efetivo)
                puladas.append(etapa.chave)
            indice += 1
        return self._encerramento(len(self.espelho) - 1, puladas)

    def _etapa(self, indice: int, puladas: list[str]) -> Plano | None:
        modo = self.espelho[indice].regra.modo
        if modo == "musica":
            return self._etapa_musica(indice, puladas)
        if modo == "intervalo":
            return self._etapa_intervalo(indice)
        if modo == "pecas":
            return self._etapa_pecas(indice)
        return self._etapa_fala(indice)

    def decidir(self) -> Plano:
        ultima = len(self.espelho) - 1
        if self.instante >= self.espelho[ultima].inicio:
            return self._encerramento(ultima, [])
        return self._a_partir(self.vigente(), [])


def planejar(programa, relogio: RelogioHora, timezone: str, instante: datetime.datetime, *,
             formato: Formato | None = None, formato_musical: bool | None = None, ultima_categoria: str | None,
             ja_encerrou: bool, executadas: set[str], pecas: PecasDisponiveis, cfg: ConfigRelogio = CONFIG_PADRAO,
             obrigacoes: frozenset[str] = frozenset()) -> Plano | None:
    """Plano do bloco que vai ao ar em `instante`. None = caminho atual (sem relógio aplicável). `obrigacoes`
    (F4): etapas com promessa aberta; sem elas o plano é o mesmo de antes. `formato` (F6) é o do catálogo; sem
    ele, o antigo booleano `formato_musical` escolhe entre o musical e o padrão."""
    if ja_encerrou:
        return None
    instante = _utc(instante)
    ocorrencia = ocorrencia_em(programa, timezone, instante, cfg)
    if ocorrencia is None:
        return None
    feriado = eh_feriado(ocorrencia.data, programa)
    if feriado and relogio.em_feriado == "sem_relogio":
        return None
    espelho = montar_espelho(relogio, ocorrencia, cfg, eh_feriado=feriado, pecas=pecas)
    formato = formato if formato is not None else formato_pelo_booleano(bool(formato_musical))
    return _Decisao(espelho, ocorrencia, instante, formato, ultima_categoria, executadas, pecas, cfg,
                    obrigacoes=obrigacoes).decidir()


def duracao_prevista_fala_s(texto: str, wpm: float) -> float:
    return estimar_duracao_s(texto, wpm)


def duracao_musica_s(musica, cfg: ConfigRelogio = CONFIG_PADRAO) -> float:
    """Mesma conta do player: (fim ou duração ou padrão) − início."""
    fim = getattr(musica, "fim_segundos", None) or getattr(musica, "duracao_segundos", None) \
        or cfg.musica_duracao_padrao_s
    return max(0.0, float(fim) - float(getattr(musica, "inicio_segundos", 0) or 0))


def duracao_prevista_bloco(resposta, cfg: ConfigRelogio = CONFIG_PADRAO, *, duracao_peca_s: float | None = None,
                           duracao_vinheta_fim_s: float | None = None) -> float:
    """Duração estimada de um bloco de /proxima: fala (medida no áudio quando sintetizada, senão
    palavras ÷ wpm), músicas, vinheta ou patrocinador (duração conhecida ou palavras ÷ wpm) e vinheta de
    encerramento."""
    if resposta.tipo in ("vinheta", "patrocinador"):
        total = duracao_peca_s if duracao_peca_s is not None else estimar_duracao_s(resposta.fala, cfg.wpm)
        return round(float(total), 2)
    falas = getattr(resposta, "falas", None)
    texto = " ".join(f.texto for f in falas) if falas else resposta.fala
    medida = getattr(resposta, "duracao_fala_s", None)
    total = float(medida) if medida is not None else estimar_duracao_s(texto, cfg.wpm)
    musicas = list(getattr(resposta, "musicas", None) or [])
    if not musicas and getattr(resposta, "video_id", None):
        musicas = [resposta]
    total += sum(duracao_musica_s(m, cfg) for m in musicas)
    if getattr(resposta, "vinheta_encerramento_id", None):
        total += duracao_vinheta_fim_s if duracao_vinheta_fim_s is not None else \
            estimar_duracao_s(getattr(resposta, "vinheta_encerramento_texto", None) or "", cfg.wpm)
    return round(total, 2)


def duracao_preferida_musica_s(plano: Plano, cfg: ConfigRelogio = CONFIG_PADRAO) -> int | None:
    """Duração máxima a preferir na busca: com sobra proibida e espaço para mais de uma faixa, uma que
    ainda deixe lugar para outra música; senão o próprio teto."""
    if plano.duracao_max_musica_s is None:
        return None
    if plano.sobra_proibida_s is not None and plano.espaco_s is not None:
        com_folga = math.floor(plano.espaco_s - plano.sobra_proibida_s[1])
        if com_folga >= cfg.musica_busca_min_s:
            return min(com_folga, plano.duracao_max_musica_s)
    return plano.duracao_max_musica_s


def musica_cabe(duracao_s: float, plano: Plano, cfg: ConfigRelogio = CONFIG_PADRAO, *, estrito: bool = True) -> bool:
    """A faixa cabe no teto do plano e (no modo estrito) não deixa uma sobra impossível."""
    if plano.duracao_max_musica_s is not None and duracao_s > plano.duracao_max_musica_s:
        return False
    if estrito and plano.sobra_proibida_s is not None and plano.espaco_s is not None:
        piso, topo = plano.sobra_proibida_s
        sobra = plano.espaco_s - duracao_s
        if piso < sobra < topo:
            return False
    return True


# ------------------------------------------------------------------------------------------------
# Resposta de /proxima (campo opcional `relogio`)
# ------------------------------------------------------------------------------------------------

class EtapaAoVivo(BaseModel):
    hora: int
    inicio_s: int
    tipo: str
    tipo_efetivo: str
    rotulo: str
    natureza: str
    hard_time: bool
    inicio: datetime.datetime
    fim: datetime.datetime


class RelogioAoVivo(BaseModel):
    preset: str | None = None
    inicio_previsto: datetime.datetime
    inicio_previsto_aceito: bool
    # F3: de onde veio o horário do bloco. "estimado" = painel antigo sem inicio_previsto, pela cadeia no servidor.
    origem_instante: Literal["painel", "estimado", "agora"] | None = None
    hora: int
    etapa: EtapaAoVivo
    proximo_compromisso: EtapaAoVivo | None = None
    segundos_ate_hard_time: float | None = None
    espaco_s: float | None = None
    acao: str
    orcamento_s: tuple[int, int] | None = None
    # Etapas puladas nesta decisão (sem espaço), marcadas como executadas.
    puladas: list[str] = []
    # F4: etapas com promessa aberta (obrigação no backtiming). Nulo sem obrigação.
    obrigacoes: list[str] | None = None


def _etapa_ao_vivo(etapa: Etapa) -> EtapaAoVivo:
    return EtapaAoVivo(hora=etapa.hora, inicio_s=etapa.evento.inicio_s, tipo=etapa.evento.tipo,
                       tipo_efetivo=etapa.tipo_efetivo, rotulo=etapa.evento.rotulo, natureza=etapa.natureza,
                       hard_time=etapa.hard_time, inicio=etapa.inicio, fim=etapa.fim)


def relogio_ao_vivo(plano: Plano, preset: str | None, aceito: bool, origem: str | None = None) -> RelogioAoVivo:
    return RelogioAoVivo(
        preset=preset, inicio_previsto=plano.instante, inicio_previsto_aceito=aceito, origem_instante=origem,
        hora=plano.etapa.hora,
        etapa=_etapa_ao_vivo(plano.etapa),
        proximo_compromisso=_etapa_ao_vivo(plano.proximo_compromisso) if plano.proximo_compromisso else None,
        segundos_ate_hard_time=plano.segundos_ate_hard_time, espaco_s=plano.espaco_s, acao=plano.acao,
        orcamento_s=plano.orcamento_s, puladas=list(plano.puladas),
        obrigacoes=sorted(plano.obrigacoes) or None,
    )


# ------------------------------------------------------------------------------------------------
# Adaptador de estado (Redis, falha aberta)
# ------------------------------------------------------------------------------------------------

def _chave_estado(programa_id: int, ocorrencia: Ocorrencia) -> str:
    return f"relogio_etapas:{programa_id}:{ocorrencia.chave}"


def etapas_executadas(programa_id: int, ocorrencia: Ocorrencia) -> set[str]:
    """Peças e etapas já decididas nesta ocorrência. Redis fora → conjunto vazio (decide só pelo tempo)."""
    try:
        from app.config.redis_client import redis_sessao as redis_client

        return set(redis_client.smembers(_chave_estado(programa_id, ocorrencia)) or ())
    except Exception:
        logger.warning("relogio_estado_indisponivel programa_id=%s", programa_id, exc_info=True)
        return set()


def marcar_executada(programa_id: int, ocorrencia: Ocorrencia, *chaves: str,
                     cfg: ConfigRelogio = CONFIG_PADRAO) -> None:
    chaves = tuple(c for c in chaves if c)
    if not chaves:
        return
    try:
        from app.config.redis_client import redis_sessao as redis_client

        chave = _chave_estado(programa_id, ocorrencia)
        redis_client.sadd(chave, *chaves)
        redis_client.expire(chave, cfg.ttl_estado_s)
    except Exception:
        logger.warning("relogio_estado_nao_gravado programa_id=%s chaves=%s", programa_id, chaves, exc_info=True)


# ------------------------------------------------------------------------------------------------
# Painel antigo sem inicio_previsto (F3): cadeia de blocos gerados, no servidor
# ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class EloCadeia:
    tipo: str
    vinheta: bool
    duracao_s: float      # pausa antes do bloco + duração prevista dele
    gerado_em: float      # epoch (s)


def instante_sem_painel(elos: list[EloCadeia], agora: datetime.datetime, inicio_ocorrencia: datetime.datetime,
                        cfg: ConfigRelogio = CONFIG_PADRAO) -> datetime.datetime:
    """Horário previsto do próximo bloco para um painel que não manda `inicio_previsto`.

    O painel gera o bloco k quando o bloco k - antecedência (sem contar vinhetas) começa a tocar. Sem elos, o
    bloco abre o programa: max(agora, início). Com menos elos que a antecedência, eles tocam a partir do início.
    Depois disso o bloco que acabou de começar é o elo k - antecedência: cada pedido se reancora em `agora` e o erro
    não acumula. Fica entre agora e agora + inicio_previsto_max_s."""
    agora, inicio = _utc(agora), _utc(inicio_ocorrencia)
    sem_vinheta = [i for i, elo in enumerate(elos) if not elo.vinheta]
    if len(sem_vinheta) < cfg.antecedencia_painel_antigo:
        instante = max(agora, inicio) + datetime.timedelta(seconds=sum(e.duracao_s for e in elos))
    else:
        desde = sem_vinheta[-cfg.antecedencia_painel_antigo]
        instante = agora + datetime.timedelta(seconds=sum(e.duracao_s for e in elos[desde:]))
    return min(max(instante, agora), agora + datetime.timedelta(seconds=cfg.inicio_previsto_max_s))


def _chave_cadeia(programa_id: int, ocorrencia: Ocorrencia) -> str:
    return f"relogio_cadeia:{programa_id}:{ocorrencia.chave}"


def ler_cadeia(programa_id: int, ocorrencia: Ocorrencia) -> list[EloCadeia]:
    """Elos desta ocorrência. Redis fora (disjuntor) ou elo ilegível: lista vazia, e o horário volta a ser agora."""
    from app.config.redis_client import redis_sessao

    elos = []
    for bruto in redis_sessao.lrange(_chave_cadeia(programa_id, ocorrencia), 0, -1) or []:
        try:
            dados = json.loads(bruto)
            elos.append(EloCadeia(str(dados["tipo"]), bool(dados["vinheta"]), float(dados["duracao_s"]),
                                  float(dados["gerado_em"])))
        except (ValueError, KeyError, TypeError):
            logger.info("relogio_cadeia_elo_invalido programa_id=%s", programa_id)
    return elos


def gravar_elo(programa_id: int, ocorrencia: Ocorrencia, elo: EloCadeia, cfg: ConfigRelogio = CONFIG_PADRAO) -> None:
    from app.config.redis_client import redis_sessao

    chave = _chave_cadeia(programa_id, ocorrencia)
    redis_sessao.rpush(chave, json.dumps(asdict(elo)))
    redis_sessao.ltrim(chave, -cfg.max_elos_cadeia, -1)
    redis_sessao.expire(chave, cfg.ttl_estado_s)


def zerar_cadeia(programa_id: int, ocorrencia: Ocorrencia) -> None:
    from app.config.redis_client import redis_sessao

    redis_sessao.delete(_chave_cadeia(programa_id, ocorrencia))
