"""Promessas feitas no ar (F4): detector, agenda e casamento. Puro: sem router, sem Redis, sem banco.

Regra 4 da skill referencia-radio: não prometer conteúdo ("daqui a pouco", "depois do intervalo") sem evento
agendado. Desenho em docs/melhoria-radio/f4/auditoria.md §6.4.

- `detectar(texto)`: uma promessa por frase, com a classe de prazo do marcador (imediato, curto, intervalo, fim,
  fora da transmissão) e o tipo pelo conteúdo (participação, informação, quadro, música, continuidade...).
- `agenda_do_plano(...)`: o que o relógio da hora (F1) ainda tem pela frente nesta ocorrência e pode ser chamado.
- `agenda_do_roteiro(...)`: sem relógio, as próximas posições do roteiro, sem sorteio (não chama
  `_tipo_proximo_bloco`, que consome o `random`).
- `casar(promessa, situacao)`: evento da agenda que cumpre a promessa, "livre" (continuidade, volta do programa,
  música confirmada: não é registrada) ou violação.

Os números (prazos, teto de promessas abertas) e os textos (marcadores, contingências) ficam em
`CONFIG_PROMESSAS`: são hipóteses de projeto (decisão D11).
"""

import dataclasses
import datetime
import re
import unicodedata
from typing import TYPE_CHECKING, Callable, Iterable, Literal

from app.live.orcamento import frases

if TYPE_CHECKING:
    from app.live.contexto import ContextoEmissao
    from app.live.validacao_fala import Violacao

ClassePrazo = Literal["intervalo", "imediato", "curto", "fim", "fora"]
Situacao = Literal["evento", "livre", "violacao"]


# ---------------------------------------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ConfigPromessas:
    # Marcadores por classe de prazo, já normalizados (sem acento, minúsculas). A ordem das classes é a ordem de
    # procura: uma frase com "daqui a pouco, depois do intervalo" é de intervalo. "Toca agora", "agora vem" e
    # "agora," não são promessa: são anúncio do que vai tocar (F3).
    marcadores: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=lambda: {
        "intervalo": ("depois do intervalo", "na volta do intervalo", "depois dos comerciais",
                      "depois da pausa", "na volta da pausa"),
        "imediato": ("ja ja", "em instantes", "a seguir", "na sequencia", "em seguida", "logo em seguida",
                     "volto ja", "ja volto", "a gente volta"),
        "curto": ("daqui a pouco", "daqui a pouquinho", "logo logo", "nao sai dai"),
        "fim": ("mais tarde", "logo mais", "ainda hoje", "ainda neste programa", "ate o fim do programa",
                "antes de terminar", "no fim do programa", "no encerramento"),
        "fora": ("amanha", "na proxima edicao", "semana que vem", "proxima semana", "no proximo programa"),
    })
    # Tipo da promessa pelas palavras da frase, nesta ordem (a primeira que aparece decide).
    tipos: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=lambda: {
        "entrevista": ("entrevista", "entrevistado", "entrevistada", "convidado", "convidada", "entra na linha"),
        "participacao": ("recado", "recados", "mensagem", "mensagens", "resposta", "respostas", "pedido",
                         "pedidos", "ouvinte", "ouvintes", "alo", "abraco", "abracos", "dedicatoria",
                         "dedicatorias", "participacao"),
        "informacao": ("noticia", "noticias", "informacao", "informacoes", "boletim", "transito", "previsao",
                       "clima", "agenda", "servico", "resultado", "resultados", "placar", "atualizacao"),
        "quadro": ("quadro",),
        "musica": ("musica", "musicas", "sucesso", "sucessos", "cancao", "cancoes", "hit", "hits"),
        "continuidade": ("continua", "continuamos", "segue", "seguimos", "volta", "voltamos", "de volta",
                         "de novo", "tem mais", "esperando voce", "te espero", "a gente se encontra",
                         "nos encontramos", "a gente se ve", "estamos aqui", "esta aqui", "estou aqui"),
    })
    # Continuidade que vale sem o nome do programa ou da rádio na frase ("já já tem mais rádio").
    continuidade_livre: tuple[str, ...] = ("mais radio", "mais musica", "mais musicas", "mais sucesso",
                                           "mais sucessos", "mais som")
    # Despedidas: "até amanhã" é volta do programa, conferida pela grade (D9).
    despedidas: tuple[str, ...] = ("ate amanha", "ate a semana que vem", "ate semana que vem",
                                   "ate a proxima semana", "ate a proxima edicao", "ate o proximo programa")
    # Uma data futura em relato atribuído não é, sozinha, compromisso da emissora.
    # O recorte é conservador: tipos explícitos de chamada continuam sendo julgados.
    relatos_atribuidos: tuple[str, ...] = ("segundo", "conforme", "de acordo com")
    referencias_emissao: tuple[str, ...] = (
        "aqui", "radio", "programa", "a gente", "vamos", "teremos", "traremos",
        "mostraremos", "veremos", "falaremos", "contaremos", "voce vai", "voces vao",
    )
    # Quantos dias à frente cada marcador "fora" aponta: (de, até).
    dias_fora: dict[str, tuple[int, int]] = dataclasses.field(default_factory=lambda: {
        "amanha": (1, 1), "na proxima edicao": (1, 7), "semana que vem": (1, 7), "proxima semana": (1, 7),
        "no proximo programa": (1, 7),
    })
    # Prazos (D11): com relógio em segundos, sem relógio em posições do roteiro.
    prazo_imediato_s: int = 300
    prazo_curto_s: int = 900
    posicoes_imediato: int = 2
    posicoes_curto: int = 4
    # Promessa cujo alvo passou há mais que isto vence (vira contingência na próxima fala).
    tolerancia_vencimento_s: int = 60
    max_promessas_abertas: int = 3
    # Fora do encerramento, as frases de contingência de um bloco somam no máximo esta fração do máximo do
    # orçamento aplicado (sobra espaço para a fala); as que não cabem esperam a próxima fala. O encerramento
    # sempre resolve todas.
    fracao_orcamento_contingencia: float = 0.6
    # Palavras de conteúdo (casamento por conteúdo): pelo menos este tanto de letras, comparadas pelo prefixo.
    min_letras_conteudo: int = 5
    prefixo_conteudo: int = 6
    palavras_vazias: frozenset[str] = frozenset({
        "aqui", "agora", "programa", "radio", "gente", "voce", "voces", "hoje", "tarde", "manha", "noite",
        "daqui", "pouco", "pouquinho", "seguir", "sequencia", "depois", "intervalo", "tambem", "sobre", "com",
        "para", "pra", "mais", "tem", "vai", "vem", "ainda", "logo", "entao", "essa", "esse", "este", "esta",
    })
    # Contingência (pesquisa §10): textos originais, sem nova promessa e sem "fica para depois".
    # Rótulo dos eventos da agenda sem relógio (o bloco do roteiro é um identificador, não um nome para o ar).
    rotulos_roteiro: dict[str, str] = dataclasses.field(default_factory=lambda: {
        "participacao": "participação dos ouvintes", "informacao": "notícias", "retorno": "intervalo",
        "encerramento": "encerramento",
    })
    contingencias: dict[str, str] = dataclasses.field(default_factory=lambda: {
        "participacao": "Ainda não chegou recado para ler agora; o WhatsApp da {radio} segue aberto.",
        "quadro": "O {rotulo} não entra hoje.",
        "informacao": "Não temos atualização confirmada sobre {rotulo} agora.",
        "generico": "{Rotulo} não vai entrar hoje.",
    })
    instrucoes: dict[str, str] = dataclasses.field(default_factory=lambda: {
        "violacao": "Você prometeu '{trecho}' sem programação confirmada.",
        "com_agenda": "O que está agendado: {eventos}; se quiser chamar algo adiante, use só isso.",
        "sem_agenda": "Não prometa conteúdo futuro.",
        "cumprir": "Você prometeu '{trecho}'. Cumpra agora: {conteudo}.",
        "contingencia": "Comece a fala com esta frase, exatamente: '{texto}'",
    })
    # O que o bloco alvo traz, na instrução de cumprir.
    conteudos: dict[str, str] = dataclasses.field(default_factory=lambda: {
        "pedido_ouvinte": "o recado de {nome}",
        "pedido_musica": "o pedido de {nome}",
        "quadro": "o quadro {rotulo}",
        "informacao": "a informação sobre {rotulo}",
        "generico": "o que foi prometido",
    })


CONFIG_PROMESSAS = ConfigPromessas()


# ---------------------------------------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class EventoAgendado:
    """O que pode ser chamado adiante. `chave`: "etapa:<hora>:<inicio_s>" (relógio), "roteiro:<posição>" ou
    "encerramento"."""

    chave: str
    tipo: str                       # participacao | quadro | informacao | retorno | encerramento
    rotulo: str = ""
    inicio: datetime.datetime | None = None      # com relógio
    posicao: int | None = None                   # sem relógio (total_falas da posição)
    conteudo: str = ""
    cancelado: bool = False


@dataclasses.dataclass(frozen=True)
class PromessaDetectada:
    frase: str
    marcador: str                   # normalizado, como em CONFIG_PROMESSAS.marcadores
    classe: ClassePrazo
    tipo: str
    despedida: bool = False


@dataclasses.dataclass(frozen=True)
class PromessaRef:
    """Promessa aberta (registrada em promessas_no_ar)."""

    id: int
    tipo: str
    trecho: str
    evento_alvo: str
    rotulo: str = ""
    prazo: datetime.datetime | None = None
    prazo_posicao: int | None = None


@dataclasses.dataclass(frozen=True)
class Contingencia:
    promessa_id: int
    texto: str
    motivo: Literal["conteudo_caiu", "prazo_vencido", "fim_do_programa"]


@dataclasses.dataclass(frozen=True)
class SituacaoAgenda:
    """O que o casamento precisa saber além da promessa."""

    agenda: tuple[EventoAgendado, ...] = ()
    instante: datetime.datetime | None = None    # com relógio: horário do bloco
    posicao: int | None = None                   # sem relógio: posição do próximo bloco
    nomes_programa: tuple[str, ...] = ()         # programa, rádio, locutor
    tem_musica: bool = True
    data: datetime.date | None = None            # dia local do bloco ("amanhã" é data + 1)
    volta_em: Callable[[datetime.date], bool] | None = None   # a grade tem o programa nesse dia
    abertas: int = 0


@dataclasses.dataclass(frozen=True)
class Casamento:
    situacao: Situacao
    evento: EventoAgendado | None = None
    motivo: str = ""


# ---------------------------------------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _tem(normalizado: str, trecho: str) -> bool:
    alvo = normalizar(trecho)
    return bool(alvo) and f" {alvo} " in f" {normalizado} "


def _tipo(normalizado: str, cfg: ConfigPromessas) -> str:
    for tipo, palavras in cfg.tipos.items():
        if any(_tem(normalizado, p) for p in palavras):
            return tipo
    return "conteudo"


def detectar(texto: str, config: ConfigPromessas | None = None) -> list[PromessaDetectada]:
    """Promessas em `texto`, uma por frase, na ordem. Acento e caixa não importam."""
    cfg = config or CONFIG_PROMESSAS
    achadas: list[PromessaDetectada] = []
    for frase in frases(texto):
        n = normalizar(frase)
        for classe, marcadores in cfg.marcadores.items():
            marcador = next((m for m in marcadores if _tem(n, m)), None)
            if marcador is None:
                continue
            tipo = _tipo(n, cfg)
            relato = any(n.startswith(prefixo + " ") for prefixo in cfg.relatos_atribuidos)
            if classe == "fora" and tipo == "conteudo" and relato and not any(
                _tem(n, referencia) for referencia in cfg.referencias_emissao
            ):
                break  # Veracidade/validade do dado cabe à apuração, não ao detector de tease.
            achadas.append(PromessaDetectada(frase=frase, marcador=marcador, classe=classe, tipo=tipo,
                                             despedida=any(_tem(n, d) for d in cfg.despedidas)))
            break
    return achadas


def a_registrar(promessa: PromessaDetectada, config: ConfigPromessas | None = None) -> bool:
    """A forma da frase já diz que não há o que cumprir nesta transmissão: despedida, continuidade sem
    conteúdo ou "mais música". O simulador mede só as outras (a volta e a música são julgadas pela grade e pela
    F3)."""
    cfg = config or CONFIG_PROMESSAS
    if promessa.despedida or promessa.tipo in ("continuidade", "musica"):
        return False
    return not any(_tem(normalizar(promessa.frase), c) for c in cfg.continuidade_livre)


# ---------------------------------------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------------------------------------

# Como cada etapa do relógio entra na agenda (tipo efetivo → tipo do evento). Música, entrevista (não há
# convidado real, F12) e os blocos de fala sem conteúdo prometível ficam fora.
TIPOS_AGENDA_RELOGIO: dict[str, str] = {
    "retorno": "participacao",
    "participacao": "participacao",
    "quadro": "quadro",
    "servico": "informacao",
    "noticia": "informacao",
    "reportagem": "informacao",
    "atualizacao": "informacao",
    "intervalo": "retorno",
    "encerramento": "encerramento",
}

# Categorias de bloco (sem relógio) que entram na agenda.
TIPOS_AGENDA_ROTEIRO: dict[str, str] = {
    "chamada_ouvinte": "participacao",
    "noticia": "informacao",
    "escalada": "informacao",
    "servico": "informacao",
    "plantao": "informacao",
}

_PATROCINADOR_RE = re.compile(r"^patrocinador:")
_VINHETA_RE = re.compile(r"^vinheta:")


def agenda_do_plano(etapas: Iterable, *, quadros: Iterable[str] = ()) -> tuple[EventoAgendado, ...]:
    """Agenda pelas etapas seguintes do relógio (`Plano.seguintes`). As etapas jornalísticas sem fonte já viraram
    música no espelho, e o intervalo sem patrocinador também: nenhuma delas entra."""
    quadros = [q for q in quadros if q]
    agenda: list[EventoAgendado] = []
    for etapa in etapas:
        tipo = TIPOS_AGENDA_RELOGIO.get(etapa.tipo_efetivo)
        if tipo is None:
            continue
        rotulo, conteudo = etapa.evento.rotulo or "", ""
        if tipo == "quadro" and quadros:
            rotulo, conteudo = quadros[0], etapa.evento.rotulo or ""
        chave = "encerramento" if tipo == "encerramento" else f"etapa:{etapa.chave}"
        agenda.append(EventoAgendado(chave=chave, tipo=tipo, rotulo=rotulo, inicio=etapa.inicio, conteudo=conteudo))
    return tuple(agenda)


def tem_musica_no_plano(etapas: Iterable) -> bool:
    return any(e.tipo_efetivo == "musica" for e in etapas)


def agenda_do_roteiro(tipo_na_posicao: Callable[[int], str], categoria_de: Callable[[str], str | None], *,
                      posicao: int, posicoes: int, quadros: Iterable[str] = (),
                      tem_fonte_noticia: bool | Callable[[str], bool] = False,
                      config: ConfigPromessas | None = None) -> tuple[EventoAgendado, ...]:
    """Agenda pelas próximas `posicoes` posições do roteiro, a partir de `posicao` (a do próximo bloco).
    `tipo_na_posicao` é a versão pura da escolha do roteiro (sem o sorteio de `ia_pode_adicionar_blocos`).
    `tem_fonte_noticia` (ou a função por tipo de bloco) diz se o bloco noticioso fica notícia."""
    rotulos = (config or CONFIG_PROMESSAS).rotulos_roteiro
    quadros = set(q for q in quadros if q)
    fonte = tem_fonte_noticia if callable(tem_fonte_noticia) else (lambda _tipo: bool(tem_fonte_noticia))
    agenda: list[EventoAgendado] = []
    for p in range(posicao, posicao + max(0, posicoes)):
        tipo_bloco = tipo_na_posicao(p)
        if _VINHETA_RE.match(tipo_bloco):
            continue
        if _PATROCINADOR_RE.match(tipo_bloco):
            agenda.append(EventoAgendado(chave=f"roteiro:{p}", tipo="retorno", rotulo=rotulos["retorno"], posicao=p))
            continue
        if tipo_bloco in quadros:
            agenda.append(EventoAgendado(chave=f"roteiro:{p}", tipo="quadro", rotulo=tipo_bloco, posicao=p))
            continue
        tipo = TIPOS_AGENDA_ROTEIRO.get(categoria_de(tipo_bloco) or "")
        if tipo == "informacao" and not fonte(tipo_bloco):
            continue  # sem fonte, o bloco noticioso vira música (app.live.roteiro)
        if tipo is not None:
            agenda.append(EventoAgendado(chave=f"roteiro:{p}", tipo=tipo, rotulo=rotulos.get(tipo, tipo_bloco),
                                         posicao=p))
    # O encerramento sempre vem, mas sem posição conhecida (sai pelo horário).
    agenda.append(EventoAgendado(chave="encerramento", tipo="encerramento", rotulo=rotulos["encerramento"]))
    return tuple(agenda)


def programa_volta_em(programa, data: datetime.date) -> bool:
    """A grade tem o programa em `data` (dias_semana vazio: todo dia; data_especifica: só nela)."""
    if not getattr(programa, "ativo", True):
        return False
    especifica = getattr(programa, "data_especifica", None)
    if especifica is not None:
        return data == especifica
    dias = getattr(programa, "dias_semana", None) or []
    return not dias or data.weekday() in dias


# ---------------------------------------------------------------------------------------------------------
# Casamento
# ---------------------------------------------------------------------------------------------------------

def _palavras_conteudo(texto: str, cfg: ConfigPromessas) -> set[str]:
    return {p[:cfg.prefixo_conteudo] for p in normalizar(texto).split()
            if len(p) >= cfg.min_letras_conteudo and p not in cfg.palavras_vazias}


def _dentro_do_prazo(evento: EventoAgendado, promessa: PromessaDetectada, situacao: SituacaoAgenda,
                     cfg: ConfigPromessas) -> bool:
    if promessa.classe in ("fim", "intervalo"):
        return True  # o fim da ocorrência (a agenda já termina nele); intervalo é conferido à parte
    if evento.chave == "encerramento":
        return False  # sem posição nem horário garantidos para "já já" e "daqui a pouco"
    if evento.inicio is not None and situacao.instante is not None:
        prazo = cfg.prazo_imediato_s if promessa.classe == "imediato" else cfg.prazo_curto_s
        return (evento.inicio - situacao.instante).total_seconds() <= prazo
    if evento.posicao is not None and situacao.posicao is not None:
        posicoes = cfg.posicoes_imediato if promessa.classe == "imediato" else cfg.posicoes_curto
        return evento.posicao < situacao.posicao + posicoes
    return True  # sem horário nem posição (benchmark): só o conteúdo decide


def _mesmo_tipo(promessa: str, evento: str) -> bool:
    return promessa == evento and promessa in ("participacao", "informacao", "quadro")


def _casa(promessa: PromessaDetectada, evento: EventoAgendado, cfg: ConfigPromessas) -> bool:
    n = normalizar(promessa.frase)
    rotulo = normalizar(evento.rotulo.replace("_", " "))
    if rotulo and evento.tipo not in ("retorno",) and f" {rotulo} " in f" {n} ":
        return True
    conteudo = _palavras_conteudo(f"{evento.conteudo}", cfg)
    if conteudo and conteudo & _palavras_conteudo(promessa.frase, cfg):
        return True
    return _mesmo_tipo(promessa.tipo, evento.tipo)


def _candidatos(promessa: PromessaDetectada, situacao: SituacaoAgenda) -> list[EventoAgendado]:
    ativos = [e for e in situacao.agenda if not e.cancelado]
    if promessa.classe != "intervalo":
        return [e for e in ativos if e.tipo != "retorno"]
    indice = next((i for i, e in enumerate(ativos) if e.tipo == "retorno"), None)
    if indice is None:
        return []
    # "Depois do intervalo": só o que vem logo depois dele.
    seguinte = next((e for e in ativos[indice + 1:] if e.tipo != "retorno"), None)
    return [seguinte] if seguinte is not None else []


def _continuidade_vale(promessa: PromessaDetectada, situacao: SituacaoAgenda, cfg: ConfigPromessas) -> bool:
    n = normalizar(promessa.frase)
    nomeia = any(_tem(n, nome) for nome in situacao.nomes_programa if nome)
    if not (nomeia or any(_tem(n, c) for c in cfg.continuidade_livre)):
        return False
    if promessa.classe == "intervalo":
        return any(e.tipo == "retorno" and not e.cancelado for e in situacao.agenda)
    return True


def _volta(promessa: PromessaDetectada, situacao: SituacaoAgenda, cfg: ConfigPromessas) -> bool:
    if situacao.volta_em is None or situacao.data is None:
        return True
    de, ate = cfg.dias_fora.get(promessa.marcador, (1, 7))
    return any(situacao.volta_em(situacao.data + datetime.timedelta(days=d)) for d in range(de, ate + 1))


def casar(promessa: PromessaDetectada, situacao: SituacaoAgenda, *, musica: bool | None = None,
          config: ConfigPromessas | None = None) -> Casamento:
    """Decide o que a promessa é. `musica`: None quando a frase não cita música; True quando cita e todas as
    citadas estão confirmadas (ou ainda não dá para julgar); False quando cita uma que não vai tocar."""
    cfg = config or CONFIG_PROMESSAS
    if musica is not None:
        return Casamento("livre", motivo="musica_confirmada") if musica else \
            Casamento("violacao", motivo="musica_nao_confirmada")
    if promessa.classe == "fora":
        if promessa.tipo in ("participacao", "informacao", "quadro", "entrevista", "musica"):
            return Casamento("violacao", motivo="conteudo_em_outra_edicao")
        if not (promessa.despedida or promessa.tipo == "continuidade"):
            return Casamento("violacao", motivo="conteudo_em_outra_edicao")
        return Casamento("livre", motivo="volta_do_programa") if _volta(promessa, situacao, cfg) else \
            Casamento("violacao", motivo="programa_nao_volta")
    if promessa.tipo == "entrevista":
        return Casamento("violacao", motivo="sem_convidado")
    if promessa.tipo == "musica":
        return Casamento("livre", motivo="mais_musica") if situacao.tem_musica else \
            Casamento("violacao", motivo="sem_musica")
    if promessa.tipo in ("continuidade", "conteudo") and _continuidade_vale(promessa, situacao, cfg) and (
            promessa.tipo == "continuidade"
            or any(_tem(normalizar(promessa.frase), c) for c in cfg.continuidade_livre)):
        return Casamento("livre", motivo="continuidade")
    for evento in _candidatos(promessa, situacao):
        if _casa(promessa, evento, cfg) and _dentro_do_prazo(evento, promessa, situacao, cfg):
            if situacao.abertas >= cfg.max_promessas_abertas:
                return Casamento("violacao", evento=evento, motivo="teto_de_promessas")
            return Casamento("evento", evento=evento)
    return Casamento("violacao", motivo="sem_evento")


def avaliar(texto: str, situacao: SituacaoAgenda, musica_de: Callable[[str], bool | None] | None = None,
            config: ConfigPromessas | None = None) -> list[tuple[PromessaDetectada, Casamento]]:
    """Cada promessa do texto com o seu casamento. `musica_de(frase)` julga a música citada na frase (ver
    `casar`); sem ele, nenhuma frase cita música. As promessas casadas com evento contam para o teto na ordem."""
    resultado: list[tuple[PromessaDetectada, Casamento]] = []
    abertas = situacao.abertas
    for promessa in detectar(texto, config):
        casamento = casar(promessa, dataclasses.replace(situacao, abertas=abertas),
                          musica=musica_de(promessa.frase) if musica_de is not None else None, config=config)
        if casamento.situacao == "evento":
            abertas += 1
        resultado.append((promessa, casamento))
    return resultado


# ---------------------------------------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------------------------------------

def _minutos(evento: EventoAgendado, situacao: SituacaoAgenda) -> str:
    if evento.inicio is not None and situacao.instante is not None:
        minutos = max(1, round((evento.inicio - situacao.instante).total_seconds() / 60))
        return f"em cerca de {minutos} minutos"
    return "mais adiante neste programa"


def descrever_agenda(situacao: SituacaoAgenda, limite: int = 3) -> str:
    """"Participação em cerca de 8 minutos; Cantinho da Casa mais adiante neste programa" (sem o intervalo e o
    encerramento)."""
    itens, vistos = [], set()
    for evento in situacao.agenda:
        if evento.cancelado or evento.tipo in ("retorno", "encerramento"):
            continue
        rotulo = (evento.rotulo or evento.tipo).replace("_", " ")
        if rotulo in vistos:
            continue  # o mais próximo de cada um basta
        vistos.add(rotulo)
        itens.append(f"{rotulo} {_minutos(evento, situacao)}" + (f" ({evento.conteudo})" if evento.conteudo else ""))
        if len(itens) >= limite:
            break
    return "; ".join(itens)


def instrucao_violacao(trecho: str, situacao: SituacaoAgenda, config: ConfigPromessas | None = None) -> str:
    cfg = config or CONFIG_PROMESSAS
    agenda = descrever_agenda(situacao)
    complemento = cfg.instrucoes["com_agenda"].format(eventos=agenda) if agenda else cfg.instrucoes["sem_agenda"]
    return f"{cfg.instrucoes['violacao'].format(trecho=trecho)} {complemento}"


def texto_contingencia(tipo: str, rotulo: str, radio: str, config: ConfigPromessas | None = None) -> str:
    """Frase de contingência do tipo (pesquisa §10). Sem rótulo ou rádio, cai no texto que não precisa deles."""
    cfg = config or CONFIG_PROMESSAS
    rotulo = (rotulo or "").replace("_", " ").strip()
    modelo = cfg.contingencias.get(tipo) or cfg.contingencias["generico"]
    if tipo == "participacao" and not radio:
        return cfg.contingencias["participacao"].replace(" da {radio}", " da rádio").format(radio="")
    if "{rotulo}" in modelo.lower() and not rotulo:
        rotulo = "esse momento"
    return modelo.format(radio=radio, rotulo=rotulo, Rotulo=rotulo[:1].upper() + rotulo[1:])


# ---------------------------------------------------------------------------------------------------------
# Sobre o ContextoEmissao (checagem pós-geração, registro)
# ---------------------------------------------------------------------------------------------------------

def situacao_do_contexto(ctx: "ContextoEmissao") -> SituacaoAgenda:
    chamadas, plano, programa = ctx.chamadas, ctx.tempo.plano, ctx.programa
    nomes = (programa.nome, getattr(ctx.account, "nome_radio", ""), getattr(ctx.radialista, "nome_locutor", ""))
    return SituacaoAgenda(
        agenda=tuple(chamadas.agenda), instante=plano.instante if plano is not None else None,
        posicao=None if plano is not None else chamadas.posicao,
        nomes_programa=tuple(n for n in nomes if n), tem_musica=chamadas.tem_musica,
        data=ctx.tempo.agora_local.date(), volta_em=lambda data: programa_volta_em(programa, data),
        abertas=len(chamadas.promessas),
    )


def musica_do_contexto(ctx: "ContextoEmissao") -> Callable[[str], bool | None]:
    """Julga a música citada numa frase de promessa com as mesmas regras de app.live.validacao_fala: antes da
    resolução das citadas (fase "pre", formato padrão sem relógio) ainda não dá para julgar."""
    from app.live.validacao_fala import (
        artistas_permitidos, confirmada, mencoes_musica, nomes_nao_musica, titulos_permitidos,
    )

    def julgar(frase: str) -> bool | None:
        mencoes = mencoes_musica(frase, ctx.musica.citaveis, nomes_nao_musica(ctx))
        if not mencoes:
            return None
        if not ctx.musica.resolvido and ctx.musica.resolve_citadas:
            return True
        permitidas, artistas = titulos_permitidos(ctx), artistas_permitidos(ctx)
        return all(confirmada(m, permitidas, artistas) for m in mencoes)

    return julgar


def checar_promessas(fala: str, ctx: "ContextoEmissao", config: ConfigPromessas | None = None) -> list["Violacao"]:
    """Promessa sem evento na agenda (fases "pre" e "final"): V1 pede a reescrita com o que está agendado; V2
    tira a frase (ou só a oração do marcador, quando ela tem um termo preservado)."""
    from app.live.validacao_fala import Violacao

    situacao = situacao_do_contexto(ctx)
    return [Violacao("promessa_sem_evento", promessa.frase, promessa.marcador,
                     instrucao_violacao(promessa.frase, situacao, config))
            for promessa, casamento in avaliar(fala, situacao, musica_do_contexto(ctx), config)
            if casamento.situacao == "violacao"]


def a_registrar_no_texto(fala: str, ctx: "ContextoEmissao",
                         config: ConfigPromessas | None = None) -> list[tuple[PromessaDetectada, EventoAgendado]]:
    """Promessas do texto que vai ao ar casadas com um evento da agenda (as que viram linha aberta)."""
    return [(promessa, casamento.evento)
            for promessa, casamento in avaliar(fala, situacao_do_contexto(ctx), musica_do_contexto(ctx), config)
            if casamento.situacao == "evento" and casamento.evento is not None]


# ---------------------------------------------------------------------------------------------------------
# Cumprimento e contingência
# ---------------------------------------------------------------------------------------------------------

def _alvo(promessa: PromessaRef, ctx: "ContextoEmissao") -> tuple[bool, bool]:
    """(este bloco é o alvo, o alvo já passou)."""
    plano = ctx.tempo.plano
    alvo = promessa.evento_alvo
    if alvo == "encerramento":
        return ctx.categoria == "encerramento", False
    if alvo.startswith("etapa:"):
        if plano is None:
            return False, True
        chave = alvo[len("etapa:"):]
        if plano.etapa.chave == chave:
            return True, False
        return False, chave not in {e.chave for e in plano.seguintes}
    if alvo.startswith("roteiro:") and plano is None:
        posicao, atual = int(alvo[len("roteiro:"):]), ctx.total_falas + ctx.passos_roteiro - 1
        return posicao == atual, atual > posicao
    return False, True


def _tem_conteudo(promessa: PromessaRef, ctx: "ContextoEmissao") -> bool:
    if promessa.tipo == "participacao":
        return ctx.participacao.pedido_ouvinte is not None or ctx.participacao.pedido_musica is not None
    if promessa.tipo == "quadro":
        return ctx.variacoes.quadro_fixo is not None
    if promessa.tipo == "informacao":
        pesquisa = ctx.jornalismo.pesquisa
        return bool(ctx.jornalismo.pautas or ctx.jornalismo.pauta is not None
                    or (pesquisa is not None and getattr(pesquisa, "status", "") == "ok"))
    return True


def conteudo_do_bloco(promessa: PromessaRef, ctx: "ContextoEmissao", config: ConfigPromessas | None = None) -> str:
    cfg = config or CONFIG_PROMESSAS
    p, rotulo = ctx.participacao, (promessa.rotulo or "").replace("_", " ")
    if promessa.tipo == "participacao" and p.pedido_ouvinte is not None:
        return cfg.conteudos["pedido_ouvinte"].format(nome=p.pedido_ouvinte.nome or "um ouvinte")
    if promessa.tipo == "participacao" and p.pedido_musica is not None:
        return cfg.conteudos["pedido_musica"].format(nome=p.pedido_musica.nome or "um ouvinte")
    if promessa.tipo in ("quadro", "informacao") and rotulo:
        return cfg.conteudos[promessa.tipo].format(rotulo=rotulo)
    return cfg.conteudos["generico"]


def _contingencia(promessa: PromessaRef, ctx: "ContextoEmissao", motivo: str, cfg: ConfigPromessas) -> Contingencia:
    tipo = promessa.tipo if promessa.tipo in ("participacao", "quadro", "informacao") else "generico"
    rotulo = promessa.rotulo if tipo != "generico" or promessa.rotulo else ""
    texto = texto_contingencia(tipo, rotulo, getattr(ctx.account, "nome_radio", "") or "", cfg)
    return Contingencia(promessa_id=promessa.id, texto=texto, motivo=motivo)


def a_cumprir_e_contingencias(ctx: "ContextoEmissao", config: ConfigPromessas | None = None
                              ) -> tuple[tuple[PromessaRef, ...], tuple[Contingencia, ...]]:
    """Promessas abertas que este bloco cumpre (é o alvo e o conteúdo veio) e as contingências que ele diz: alvo
    sem conteúdo, alvo que já passou (etapa pulada, posição trocada) e, no encerramento, todas as que sobraram."""
    from app.live.orcamento import estimar_duracao_s

    cfg = config or CONFIG_PROMESSAS
    encerramento = ctx.categoria == "encerramento"
    a_cumprir: list[PromessaRef] = []
    contingencias: list[Contingencia] = []
    for promessa in ctx.chamadas.promessas:
        alvo, passou = _alvo(promessa, ctx)
        if alvo and _tem_conteudo(promessa, ctx):
            a_cumprir.append(promessa)
        elif alvo:
            contingencias.append(_contingencia(promessa, ctx, "conteudo_caiu", cfg))
        elif encerramento:
            contingencias.append(_contingencia(promessa, ctx, "fim_do_programa", cfg))
        elif passou:
            contingencias.append(_contingencia(promessa, ctx, "prazo_vencido", cfg))
    if not encerramento and ctx.orcamento.aplicar:
        cabem, total = [], 0.0
        limite = ctx.orcamento.max_s * cfg.fracao_orcamento_contingencia
        for contingencia in contingencias:
            duracao = estimar_duracao_s(contingencia.texto, ctx.wpm_fala)
            if total + duracao <= limite:
                cabem.append(contingencia)
                total += duracao
        contingencias = cabem
    return tuple(a_cumprir), tuple(contingencias)


def instrucoes_do_bloco(ctx: "ContextoEmissao", config: ConfigPromessas | None = None) -> list[str]:
    """Linhas do prompt: cumprir o que foi prometido e dizer a contingência com a frase exata."""
    cfg = config or CONFIG_PROMESSAS
    linhas = [cfg.instrucoes["cumprir"].format(trecho=p.trecho, conteudo=conteudo_do_bloco(p, ctx, cfg))
              for p in ctx.chamadas.a_cumprir]
    linhas += [cfg.instrucoes["contingencia"].format(texto=c.texto) for c in ctx.chamadas.contingencias]
    return linhas


def dita(texto: str, fala: str) -> bool:
    alvo = normalizar(texto)
    return bool(alvo) and f" {alvo} " in f" {normalizar(fala)} "


def garantir_contingencia(fala: str, falas_bloco: list, contingencias: Iterable[Contingencia]
                          ) -> tuple[str, list, list[Contingencia]]:
    """A frase de contingência vai ao ar mesmo que o LLM a ignore (D5): a que falta entra no começo (no multivoz,
    na primeira linha). Fala vazia (só música) fica vazia: a promessa espera a próxima fala."""
    contingencias = list(contingencias)
    if not fala.strip() or not contingencias:
        return fala, falas_bloco, []
    faltam = [c.texto for c in contingencias if not dita(c.texto, fala)]
    if faltam:
        prefixo = " ".join(faltam)
        if falas_bloco:
            primeira = falas_bloco[0].model_copy(update={"texto": f"{prefixo} {falas_bloco[0].texto}"})
            falas_bloco = [primeira, *falas_bloco[1:]]
            fala = " ".join(item.texto for item in falas_bloco)
        else:
            fala = f"{prefixo} {fala}"
    return fala, falas_bloco, contingencias
