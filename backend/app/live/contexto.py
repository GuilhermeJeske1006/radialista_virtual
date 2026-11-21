"""Estado da emissão (F3): o ContextoEmissao que a geração, o prompt e o validador leem.

Montado em fases, na mesma ordem que app/live/router.py::gerar_proxima_fala seguia, porque a ordem dos
sorteios do `random`, das rotações no Redis (`_proxima_variacao`) e dos `commit` da seleção de pedidos faz parte
do comportamento (a simulação e os testes fixam a semente):

1. app.live.roteiro.decidir_bloco: tipo, plano do relógio, vinheta ou patrocinador prontos;
2. `resolver_musica_e_pedidos`: pedido de música (com `with_for_update`), faixa do bloco, pedido de ouvinte;
3. `montar_contexto`: memória, variações, jornalismo, orçamento da F2 e o `prompt_base` do prompt_builder.

Depois disso app.live.prompt_emissao.montar_prompt é pura. Os objetos ORM entram só para leitura; o que muda
depois da geração (músicas do bloco) é trocado com `dataclasses.replace`. Desenho em
docs/melhoria-radio/f3/auditoria.md §5.2. Este módulo não importa o router: o que os testes trocam por nome
chega pelas portas (app.live.portas).
"""

import dataclasses
import datetime
import logging
import math
import random
import re
from typing import Any, Literal, Mapping
from zoneinfo import ZoneInfo

from app.billing.contexto_ia import modelo_efetivo
from app.config.settings import settings
from app.dados.fontes import dados_do_bloco, no_bloco
from app.dados.texto_externo import nome_seguro
from app.dados.verificavel import DadoVerificavel
from app.live.formatos import Formato, eh_quadro_fixo, formato_pelo_booleano
from app.live.orcamento import OrcamentoFala, orcamento_para, palavras_max
from app.live.portas import PortasEmissao
from app.live.prompts import (
    _CATEGORIAS_NOTICIA_LIKE,
    _PROB_CALLBACK_TEMA_ANTERIOR,
    _PROB_HORA_CERTA,
    _PROB_IMPERFEICAO_GRAMATICAL,
    _PROB_MARCO_TEMPO,
    _PROB_MUDANCA_DE_IDEIA,
    _VARIACOES_CONVITE_OUVINTE,
    _VARIACOES_FORMATO_COMENTARIO,
    _VARIACOES_VERBO_IDENTIFICACAO,
)
from app.live.promessas import (
    CONFIG_PROMESSAS,
    Contingencia,
    EventoAgendado,
    PromessaRef,
    a_cumprir_e_contingencias,
    agenda_do_plano,
    agenda_do_roteiro,
    tem_musica_no_plano,
)
from app.live.relogio import CONFIG_PADRAO as CONFIG_RELOGIO, Plano, duracao_musica_s, ocorrencia_em
from app.live.ritmo_voz import categoria_ritmo
from app.live.roteiro import _PATROCINADOR_RE, _VINHETA_RE, DecisaoBloco, EntradaEmissao, tipo_na_posicao
from app.numeros import cardinal_feminino, numero_por_extenso
from app.tts.modelos import MODELOS_COM_TAGS

logger = logging.getLogger("radialista.live")

# Quantos temas (sessão + outros programas da rádio) entram no prompt (e o teto da consulta ao banco).
_MAX_TEMAS_RADIO_NO_PROMPT = 20

# Linha do histórico com as faixas que tocaram num bloco (linhaMusicasHistorico em useLiveEngine.ts).
_MUSICAS_TOCADAS_HISTORICO_RE = re.compile(r"\[Música\(s\) tocada\(s\) nesse bloco: (.+?)\]")


# ---------------------------------------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class MusicaRef:
    titulo: str
    artista: str = ""
    video_id: str | None = None
    origem: Literal["bloco", "citada", "pedido", "historico", "sessao", "conhecida"] = "bloco"

    @classmethod
    def de(cls, musica, origem: str = "bloco") -> "MusicaRef":
        return cls(titulo=musica.titulo, artista=musica.canal or "", video_id=musica.video_id, origem=origem)


@dataclasses.dataclass(frozen=True)
class PedidoRef:
    """Pedido aprovado: "selecionado" (fluxo novo) ou o legado consumido. `texto` é o que o prompt cita."""

    id: int
    tipo: str
    nome: str
    natureza: str | None
    texto: str                      # texto_autorizado (fluxo novo) ou mensagem_usuario (legado)
    texto_autorizado: str
    musica_query: str | None
    estado: str
    token: str | None

    @classmethod
    def de(cls, pedido, novo_atendimento: bool) -> "PedidoRef":
        # F5 (D15): o nome do WhatsApp entra saneado; o prompt e os detectores da F4 veem o mesmo nome.
        return cls(id=pedido.id, tipo=pedido.tipo, nome=nome_seguro(pedido.nome), natureza=pedido.natureza,
                   texto=pedido.texto_autorizado if novo_atendimento else pedido.mensagem_usuario,
                   texto_autorizado=pedido.texto_autorizado or "", musica_query=pedido.musica_query,
                   estado=pedido.estado, token=pedido.selecao_token)


@dataclasses.dataclass(frozen=True)
class EstadoMusical:
    tocou: tuple[MusicaRef, ...]         # "[Música(s) tocada(s) nesse bloco: …]" das linhas do painel + sessão
    confirmada: MusicaRef | None         # faixa deste bloco, que toca em seguida
    bloco: tuple[MusicaRef, ...] = ()    # depois da geração: confirmada + citadas resolvidas que cabem
    pedido_sem_resultado: bool = False
    resolve_citadas: bool = True         # False no bloco de música do formato musical ou com relógio
    citaveis: tuple[MusicaRef, ...] = ()  # títulos conhecidos (camada (a) do validador)
    contexto_faixa: str = ""
    resolvido: bool = False              # True depois da resolução das citadas (fase "final" do validador)
    citadas_nao_resolvidas: tuple[str, ...] = ()  # o extrator achou, mas não virou faixa (camada (c))


@dataclasses.dataclass(frozen=True)
class Participacao:
    novo_atendimento: bool
    pedido_musica: PedidoRef | None
    pedido_ouvinte: PedidoRef | None
    ouvinte_recorrente: str | None       # tipo do pedido anterior do mesmo ouvinte nesta transmissão
    ouvinte_recorrente_dias: str | None  # idem, numa transmissão de outro dia
    pedido_recente: PedidoRef | None     # espiado, não consumido (legado)
    nomes_autorizados: tuple[str, ...] = ()
    # F4 (app.live.participacao): quem pode ser citado e como.
    nomes_selecionados: tuple[str, ...] = ()   # pedido de música e de ouvinte deste bloco
    nomes_ja_atendidos: tuple[str, ...] = ()   # executados ou selecionados antes, nesta transmissão (D8)
    nomes_conhecidos: tuple[str, ...] = ()     # pedidos da transmissão e da fila
    nome_recente: str | None = None            # espiado do legado (D7)


@dataclasses.dataclass(frozen=True)
class Chamadas:
    """Chamadas pendentes (pesquisa §12.4). F4: promessas abertas e a agenda do que pode ser chamado adiante
    (app.live.promessas). Os campos novos têm padrão: sem promessa, nada muda."""

    fio_condutor: str | None
    pedidos_em_fila: int = 0
    promessas: tuple[PromessaRef, ...] = ()        # abertas nesta ocorrência
    agenda: tuple[EventoAgendado, ...] = ()        # o que pode ser chamado adiante
    a_cumprir: tuple[PromessaRef, ...] = ()        # alvo = este bloco, com conteúdo
    contingencias: tuple[Contingencia, ...] = ()   # alvo = este bloco sem conteúdo, ou vencidas
    ocorrencia: str | None = None                  # chave da ocorrência (registro em promessas_no_ar)
    posicao: int | None = None                     # sem relógio: posição do próximo bloco no roteiro
    tem_musica: bool = True


@dataclasses.dataclass(frozen=True)
class Tempo:
    agora_local: datetime.datetime
    instante: datetime.datetime
    origem_instante: Literal["painel", "estimado", "agora"]
    plano: Plano | None
    preset_relogio: str | None
    inicio_previsto_aceito: bool
    ajuste_energia: str | None = None
    marco_tempo: str | None = None
    hora_certa: str | None = None


@dataclasses.dataclass(frozen=True)
class Memoria:
    historico: tuple[str, ...]           # linhas do painel (as 8 últimas)
    historico_prompt: str                # as 6 últimas, ou "Programa acabou de entrar no ar."
    ultima_categoria: str | None
    falas_categoria: tuple[str, ...] = ()
    aberturas: tuple[str, ...] = ()
    fechamentos: tuple[str, ...] = ()
    tom_anterior: str | None = None
    temas_usados: tuple[str, ...] = ()
    tema_callback: str | None = None


@dataclasses.dataclass(frozen=True)
class Variacoes:
    """Já sorteadas e rotacionadas, na ordem do router antigo."""

    verbo_identificacao: str
    transicao: str | None = None
    formato_comentario: str | None = None
    convite_ouvinte: str | None = None
    expressao_regional: str | None = None
    quadro_fixo: str | None = None
    assunto_sugerido: str | None = None
    assunto: Any = None                  # AssuntoConversa
    mudanca_de_ideia: bool = False
    imperfeicao: bool = False


@dataclasses.dataclass(frozen=True)
class Jornalismo:
    pautas: tuple = ()                   # NoticiaPauta
    pauta: Any = None
    correcao: Any = None
    pesquisa: Any = None                 # PesquisaNoticias
    pesquisou: bool = False


@dataclasses.dataclass(frozen=True)
class ContextoEmissao:
    request_id: str
    account: Any
    radialista: Any
    programa: Any
    tipo: str
    categoria: str
    primeira_fala: bool
    total_falas: int
    passos_roteiro: int
    formato_musical: bool                # derivado do formato (D12 da F6); aceito na construção por compatibilidade
    multi_voz: bool
    roster: tuple
    roteiro: tuple[str, ...]
    categorias_roteiro: tuple[str | None, ...]
    tempo: Tempo
    musica: EstadoMusical
    participacao: Participacao
    chamadas: Chamadas
    memoria: Memoria
    variacoes: Variacoes
    jornalismo: Jornalismo
    orcamento: OrcamentoFala
    wpm_fala: float
    categoria_voz: str
    limite_palavras: int | None
    prompt_base: str                     # montar_system_prompt(...), chamado no montador (efeitos no Redis)
    modelo_com_tags: bool
    dados: tuple[DadoVerificavel, ...] = ()   # F5: dados verificáveis do bloco (app.dados.fontes.dados_do_bloco)
    clima_ja_mencionado: bool = False         # F5: trava de 45 min do clima (só com clima no bloco)
    extensoes: Mapping[str, Any] = dataclasses.field(default_factory=dict)  # F4/F7/F8
    # F6: formato do catálogo (app.live.formatos); as flags dele decidem o que antes era o booleano musical.
    formato: Formato | None = None

    def __post_init__(self):
        formato = self.formato if self.formato is not None else formato_pelo_booleano(self.formato_musical)
        object.__setattr__(self, "formato", formato)
        object.__setattr__(self, "formato_musical", formato.comportamento.ciclo == "musical")


@dataclasses.dataclass(frozen=True)
class ResolucaoBloco:
    """Fase 2: pedidos e faixa. Guarda os objetos ORM que o router ainda confirma ou reprova no fim."""

    historico_prompt: str
    agora_local: datetime.datetime
    roster: tuple
    multi_voz: bool
    novo_atendimento: bool
    pedido_musica: Any = None
    pedido_sem_resultado: bool = False
    musica: Any = None                   # MusicaEncontrada
    so_musica: bool = False              # bloco de música sem fala: o router responde já
    pedido_ouvinte: Any = None
    ouvinte_recorrente: Any = None
    ouvinte_recorrente_dias: Any = None
    pedido_recente: Any = None


# ---------------------------------------------------------------------------------------------------------
# Fase 2: pedidos e música
# ---------------------------------------------------------------------------------------------------------

def tocadas_no_historico(historico) -> list[MusicaRef]:
    """Faixas que o painel diz que tocaram (sufixo "[Música(s) tocada(s) nesse bloco: …]" das linhas)."""
    tocadas: list[MusicaRef] = []
    for linha in historico:
        for achado in _MUSICAS_TOCADAS_HISTORICO_RE.findall(linha):
            for rotulo in achado.split(","):
                titulo, _, artista = rotulo.strip().rpartition(" - ")
                tocadas.append(MusicaRef(titulo or artista, artista if titulo else "", origem="historico"))
    return tocadas


def chave_ocorrencia(programa, timezone: str, instante: datetime.datetime) -> str:
    """Ocorrência do programa em `instante` (com ou sem relógio). O primeiro bloco é gerado um pouco antes do
    início (prewarm, painel): vale a ocorrência que começa logo depois. Fora da grade, o dia local."""
    for adiante in (0, CONFIG_RELOGIO.preparo_sem_painel_max_s):
        ocorrencia = ocorrencia_em(programa, timezone, instante + datetime.timedelta(seconds=adiante))
        if ocorrencia is not None:
            return ocorrencia.chave
    return f"manual:{instante.astimezone(ZoneInfo(timezone)).date().isoformat()}"


def _quadros_da_estrutura(programa) -> list[str]:
    return [t for t in programa.estrutura_blocos or [] if (programa.quadros_fixos or {}).get(t)]


def _tem_fonte_noticia(programa):
    """Mesma regra de app.live.roteiro.decidir_bloco: sem fonte, o bloco noticioso vira música."""
    if getattr(programa, "dose_noticia", "jornalistica") == "nenhuma":
        return lambda _tipo: False
    configurada = bool(programa.pode_pesquisar or programa.tipos_noticias or programa.fontes_noticias)
    return lambda tipo: configurada or tipo in (programa.estrutura_blocos or [])


def _agenda(entrada: EntradaEmissao, decisao: DecisaoBloco, roteiro: tuple[str, ...],
            categorias: tuple[str | None, ...]) -> tuple[tuple[EventoAgendado, ...], int | None, bool]:
    """(agenda, posição do próximo bloco sem relógio, programa tem música adiante). Pura: sem sorteio."""
    programa, plano = entrada.programa, decisao.plano
    if plano is not None:
        return agenda_do_plano(plano.seguintes, quadros=_quadros_da_estrutura(programa)), None, \
            tem_musica_no_plano(plano.seguintes) or plano.tipo_bloco == "musica"
    por_tipo = dict(zip(roteiro, categorias))
    posicao = entrada.total_falas + decisao.passos_roteiro
    agenda = agenda_do_roteiro(
        lambda p: tipo_na_posicao(programa, p, lambda t: por_tipo.get(t.strip())),
        lambda t: por_tipo.get(t.strip()), posicao=posicao,
        posicoes=max(CONFIG_PROMESSAS.posicoes_curto, len(roteiro)),
        quadros=(programa.quadros_fixos or {}).keys(), tem_fonte_noticia=_tem_fonte_noticia(programa))
    return agenda, posicao, entrada.formato.comportamento.ciclo == "musical" or "musica" in categorias


def _estado_da_fila(entrada: EntradaEmissao, portas: PortasEmissao) -> tuple[list[MusicaRef], list[str]]:
    """Músicas pedidas (títulos conhecidos, camada (a) do validador) e nomes dos ouvintes da fila. Só leitura."""
    from app.live.song_service import dividir_artista_titulo

    pedidos = portas.pedidos_em_fila(entrada.db, entrada.radialista, entrada.programa)
    citaveis = []
    for item in [*(entrada.programa.musicas_permitidas or []), *(p.musica_query for p in pedidos if p.musica_query)]:
        partes = dividir_artista_titulo(item)
        citaveis.append(MusicaRef(partes[1], partes[0], origem="conhecida") if partes is not None
                        else MusicaRef(item, origem="conhecida"))
    return citaveis, [nome for nome in (nome_seguro(p.nome) for p in pedidos) if nome]


def teto_musica(plano: Plano) -> Plano:
    """Plano com teto de musica mesmo quando o bloco virou musica fora de uma etapa de musica."""
    if plano.duracao_max_musica_s is not None or plano.espaco_s is None:
        return plano
    return dataclasses.replace(plano, duracao_max_musica_s=math.floor(plano.espaco_s
                                                                       + CONFIG_RELOGIO.tolerancia_hard_time_s))


def resolver_musica_e_pedidos(entrada: EntradaEmissao, decisao: DecisaoBloco, portas: PortasEmissao) -> ResolucaoBloco:
    db, account, radialista, programa = entrada.db, entrada.account, entrada.radialista, entrada.programa
    tipo, categoria, plano = decisao.tipo, decisao.categoria, decisao.plano
    comportamento = entrada.formato.comportamento

    historico_prompt = "\n".join(entrada.dados.historico[-6:]) or "Programa acabou de entrar no ar."
    # Um so calculo de "agora" por requisicao (efemerides, hora certa, marco de tempo).
    agora_local = (
        plano.instante.astimezone(ZoneInfo(radialista.timezone)) if plano is not None
        else datetime.datetime.now(ZoneInfo(radialista.timezone))
    )
    # Dialogo multi-voz so pros blocos de fala -- musica continua single-voice, sempre na voz do dono.
    roster = tuple(portas.buscar_roster(db, account, programa))
    multi_voz = len(roster) > 1 and categoria != "musica" and comportamento.multivoz

    novo_atendimento = account.atendimento_ouvinte_ativo
    pedido_musica = (
        portas.selecionar_pedido(db, radialista, programa, ("musica",)) if novo_atendimento
        else portas.proximo_pedido_fila(db, radialista, "musica")
    ) if categoria == "musica" and (plano is None or plano.aceita_pedido_musica) else None
    pedido_sem_resultado = False
    if pedido_musica is not None:
        query = pedido_musica.musica_query or pedido_musica.mensagem_usuario
        ids_tocadas, titulos_tocados, canais_tocados = portas.historico_musicas(programa.id)
        musica = portas.buscar_musica(
            query,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            titulos_tocados=titulos_tocados,
            canais_recentes=canais_tocados,
            exigir_cantada=True,
            exigir_canal_oficial=True,
        )
        if musica is not None:
            if plano is not None and plano.duracao_max_musica_s is not None \
                    and duracao_musica_s(musica, CONFIG_RELOGIO) > plano.duracao_max_musica_s:
                logger.warning("relogio_pedido_acima_do_espaco programa_id=%s duracao_s=%s teto_s=%s", programa.id,
                               duracao_musica_s(musica, CONFIG_RELOGIO), plano.duracao_max_musica_s)
            portas.registrar_musica_tocada(programa.id, musica)
            # pedido real do ouvinte -- alimenta o sinal de preferencia do publico em blocos futuros.
            portas.registrar_historico_persistente(db, programa.id, musica, query, origem="pedido_ouvinte")
        else:
            # Cai pra escolha automatica pra sempre tocar algo neste bloco. O pedido fica "nao_atendido" (Música
            # indisponível) antes da geração e o nome do ouvinte não vai ao ar (F4, D2; pesquisa §10).
            pedido_sem_resultado = True
            logger.warning(
                "Pedido de musica sem resultado na busca, caindo pra escolha automatica: programa_id=%s query=%r",
                programa.id, query,
            )
            portas.reprovar_pedido(db, pedido_musica, "Música indisponível")
            pedido_musica = None
            musica = (
                portas.buscar_musica_para_bloco(db, programa, tipo) if plano is None
                else portas.buscar_musica_para_bloco(db, programa, tipo, plano_relogio=teto_musica(plano))
            )
    elif categoria != "musica":
        musica = None
    elif plano is None:
        musica = portas.buscar_musica_para_bloco(db, programa, tipo)
    elif decisao.musica_relogio is not None or decisao.buscou_musica_relogio:
        musica = decisao.musica_relogio
    else:
        musica = portas.buscar_musica_para_bloco(db, programa, tipo, plano_relogio=teto_musica(plano))

    comum = dict(historico_prompt=historico_prompt, agora_local=agora_local, roster=roster, multi_voz=multi_voz,
                 novo_atendimento=novo_atendimento, pedido_musica=pedido_musica,
                 pedido_sem_resultado=pedido_sem_resultado, musica=musica)
    # Com relogio (D2) a janela de musica nao tem fala tambem no formato padrao, exceto pedido real.
    if (comportamento.musica_sem_fala or (plano is not None and plano.musica_sem_fala)) and categoria == "musica" \
            and musica is not None and pedido_musica is None:
        return ResolucaoBloco(so_musica=True, **comum)

    pedido_ouvinte = (
        (portas.selecionar_pedido(db, radialista, programa, ("abraco", "sorteio")) if novo_atendimento
         else portas.proximo_pedido_fila_dentre(db, radialista, ("abraco", "sorteio")))
        if categoria == "chamada_ouvinte" else None
    )
    ouvinte_recorrente = (
        portas.ouvinte_recorrente_anterior(db, radialista.id, pedido_ouvinte) if pedido_ouvinte is not None else None
    )
    # So checa a janela de dias quando nao achou recorrencia dentro da sessao.
    ouvinte_recorrente_dias = (
        portas.ouvinte_recorrente_dias_anteriores(db, radialista.id, pedido_ouvinte)
        if pedido_ouvinte is not None and ouvinte_recorrente is None
        else None
    )
    # Peek (nao consome) em pedido que acabou de chegar enquanto o locutor gera outro tipo de bloco.
    pedido_recente = None
    if not novo_atendimento and categoria not in ("musica", "chamada_ouvinte"):
        pedido_recente = (
            portas.pedido_recente_nao_atendido(db, radialista, "abraco")
            or portas.pedido_recente_nao_atendido(db, radialista, "sorteio")
            or portas.pedido_recente_nao_atendido(db, radialista, "musica")
        )
    return ResolucaoBloco(pedido_ouvinte=pedido_ouvinte, ouvinte_recorrente=ouvinte_recorrente,
                          ouvinte_recorrente_dias=ouvinte_recorrente_dias, pedido_recente=pedido_recente, **comum)


# ---------------------------------------------------------------------------------------------------------
# Fase 3: memória, variações, jornalismo, orçamento
# ---------------------------------------------------------------------------------------------------------

def _hora_certa_por_extenso(agora: datetime.datetime) -> str:
    """Hora atual por extenso (ex.: 'catorze e trinta e cinco') pra injetar no prompt --
    nunca em algarismo, porque o texto vai direto pro TTS e algarismo lido em portugues
    e' onde o sintetizador mais erra (ver _LANGUAGE_CODE em app.tts.client).
    """
    hora_extenso = "uma" if agora.hour == 1 else cardinal_feminino(agora.hour)  # "horas" e' feminino
    if agora.minute == 0:
        return f"{hora_extenso} horas em ponto"
    return f"{hora_extenso} e {numero_por_extenso(agora.minute)}"


from app.live.memoria import aberturas_e_fechamentos as _aberturas_e_fechamentos  # noqa: E402
from app.live.memoria import primeira_frase as _primeira_frase  # noqa: E402,F401 -- reexportado (router e testes)
from app.live.memoria import ultima_frase as _ultima_frase  # noqa: E402,F401 -- reexportado (router e testes)


def _temas(entrada: EntradaEmissao, categoria: str, portas: PortasEmissao) -> tuple[list[str], str | None]:
    programa = entrada.programa
    temas_usados: list[str] = []
    tema_callback = None
    if categoria in ("comentario", "noticia"):
        # Sessao do proprio programa primeiro, depois o que outros programas da mesma radio ja comentaram.
        temas_sessao_atual = portas.historico_temas(programa.id)
        temas_outras_transmissoes = portas.temas_recentes_da_radio(entrada.db, programa.radio_config_id)
        vistos: set[str] = set()
        for tema in temas_sessao_atual + temas_outras_transmissoes:
            if tema not in vistos:
                vistos.add(tema)
                temas_usados.append(tema)
        temas_usados = temas_usados[:_MAX_TEMAS_RADIO_NO_PROMPT]
        # So conta como "transmissao anterior" um tema que NAO veio da sessao atual.
        so_de_outras = [t for t in temas_outras_transmissoes if t not in set(temas_sessao_atual)]
        if so_de_outras and random.random() < _PROB_CALLBACK_TEMA_ANTERIOR:
            tema_callback = portas.proxima_variacao(programa.id, "callback_tema_anterior", so_de_outras)
    return temas_usados, tema_callback


def _jornalismo(entrada: EntradaEmissao, categoria: str, tipo: str, agora_local, variacoes_assunto: dict,
                portas: PortasEmissao) -> Jornalismo:
    db, account, programa = entrada.db, entrada.account, entrada.programa
    pauta = None
    pautas: list = []
    correcao = None
    # O programa esportivo usa apuração web própria; a pauta geral de RSS da rádio
    # pode conter notícias de outras editorias e não substitui a pesquisa esportiva.
    if categoria in _CATEGORIAS_NOTICIA_LIKE and programa.perfil != "esportivo":
        # Correção tem prioridade sobre qualquer outra pauta, inclusive sobre a escalada.
        correcao = portas.correcao_pendente(db, programa)
        if correcao is not None:
            pauta = correcao
            pautas = [correcao]
        elif categoria == "escalada":
            pautas = portas.proximas_noticias(db, programa, account, limite=3)
        elif categoria == "plantao":
            pauta = portas.proxima_para_plantao(db, programa, account)
            pautas = [pauta] if pauta else []
        else:
            pauta = portas.proxima_noticia(db, programa, account)
            pautas = [pauta] if pauta else []
        if len(pautas) == 1:
            pauta = pautas[0]
    # Pauta real do worker tem prioridade sobre a pesquisa via web_search.
    pesquisa = None
    deve_pesquisar = categoria in _CATEGORIAS_NOTICIA_LIKE or (categoria == "comentario" and programa.pode_pesquisar)
    pesquisou = not pautas and deve_pesquisar
    if pesquisou:
        quadro, assunto, sugerido = (variacoes_assunto["quadro"], variacoes_assunto["assunto"],
                                     variacoes_assunto["sugerido"])
        pesquisa = portas.pesquisar_noticias(
            programa, account, agora=agora_local,
            assunto=quadro or (
                " ".join([assunto.titulo, assunto.gancho, *assunto.tags])
                if categoria == "comentario" and assunto is not None
                else sugerido if categoria == "comentario" else tipo
            ),
        )
    return Jornalismo(pautas=tuple(pautas), pauta=pauta, correcao=correcao, pesquisa=pesquisa, pesquisou=pesquisou)


def _dados(entrada: EntradaEmissao, decisao: DecisaoBloco, jornalismo: Jornalismo, quadro, portas: PortasEmissao
           ) -> tuple[DadoVerificavel, ...]:
    """Pauta (ou correção), apuração web, pauta de assunto e clima deste bloco como DadoVerificavel (F5)."""
    account, programa = entrada.account, entrada.programa
    cidade = (getattr(account, "cidade", "") or "").strip()
    leitura = portas.obter_leitura_clima(cidade) if cidade else None
    return dados_do_bloco(
        pautas=jornalismo.pautas, correcao=jornalismo.correcao,
        pesquisa=jornalismo.pesquisa if jornalismo.pesquisou else None,
        fontes_programa=programa.fontes_noticias or programa.fontes_pesquisa or [],
        assunto=decisao.assunto if quadro is None else None, leitura_clima=leitura, tz=entrada.radialista.timezone)


def montar_contexto(entrada: EntradaEmissao, decisao: DecisaoBloco, resolucao: ResolucaoBloco,
                    portas: PortasEmissao) -> ContextoEmissao:
    """Fase 3. A ordem das chamadas abaixo é a do router antigo (sorteios, rotações e leituras)."""
    account, radialista, programa = entrada.account, entrada.radialista, entrada.programa
    tipo, categoria, plano = decisao.tipo, decisao.categoria, decisao.plano
    formato, ultima_categoria = entrada.formato, decisao.ultima_categoria
    comportamento = formato.comportamento
    agora_local, multi_voz = resolucao.agora_local, resolucao.multi_voz
    novo = resolucao.novo_atendimento

    # Buscado antes do prompt (aviso de abertura/fechamento) e reaproveitado na checagem de fala repetida.
    falas_categoria = portas.historico_falas(programa.id, categoria)
    temas_usados, tema_callback = _temas(entrada, categoria, portas)
    verbo = portas.proxima_variacao(programa.id, "verbo_identificacao", _VARIACOES_VERBO_IDENTIFICACAO)
    # Quadro fixo: identificado pelo label bruto do bloco (tipo), nao pela categoria.
    quadro_pool = (programa.quadros_fixos or {}).get(tipo)
    quadro = portas.proxima_variacao(programa.id, f"quadro_{tipo}", quadro_pool) if quadro_pool else None
    # Pool rotativo de assuntos configurados -- so sem quadro fixo dando o conteudo do bloco.
    sugerido = None
    if quadro is None and categoria in ("comentario", "noticia", "chamada_ouvinte") and programa.assuntos_ao_vivo:
        sugerido = portas.proxima_variacao(programa.id, "assunto_ao_vivo", programa.assuntos_ao_vivo)

    roteiro = tuple(t.strip() for t in programa.estrutura_blocos if t.strip()) or formato.roteiro_padrao
    categorias_roteiro = tuple(
        None if _VINHETA_RE.match(t) or _PATROCINADOR_RE.match(t) or t in ("retomada", "identificacao")
        else portas.categoria_bloco(t)
        for t in roteiro
    )
    # F5: o clima sai do prompt_base do ao vivo e vai como dado verificável na mensagem (app.live.prompt_emissao).
    prompt_base = portas.montar_system_prompt(account, radialista, programa,
                                              roster=list(resolucao.roster) if multi_voz else None,
                                              agora=agora_local if plano is not None else None,
                                              incluir_clima=False)
    transicao = portas.instrucao_transicao(programa.id, ultima_categoria, categoria)
    ajuste_energia = portas.ajuste_energia_meio_programa(programa, radialista.timezone) \
        if tipo != "encerramento" else None
    expressao_regional = None
    if categoria not in _CATEGORIAS_NOTICIA_LIKE and comportamento.naturalidade_encenada:
        # Gírias/expressões regionais reais (Account.conhecimento_local), girando uma por vez.
        expressoes = (account.conhecimento_local or {}).get("expressoes_regionais") or []
        if expressoes:
            expressao_regional = portas.proxima_variacao(programa.id, "expressao_regional", expressoes)
    sorteia_estilo = comportamento.naturalidade_encenada and categoria not in _CATEGORIAS_NOTICIA_LIKE
    mudanca_de_ideia = sorteia_estilo and random.random() < _PROB_MUDANCA_DE_IDEIA
    imperfeicao = sorteia_estilo and random.random() < _PROB_IMPERFEICAO_GRAMATICAL
    modelo_com_tags = modelo_efetivo("tts", settings.elevenlabs_model) in MODELOS_COM_TAGS

    aberturas, fechamentos = _aberturas_e_fechamentos(falas_categoria)
    tom_anterior = portas.ultimo_tom(programa.id)
    formato_comentario = portas.proxima_variacao(programa.id, "formato_comentario", _VARIACOES_FORMATO_COMENTARIO) \
        if categoria == "comentario" else None
    jornalismo = _jornalismo(entrada, categoria, tipo, agora_local,
                             {"quadro": quadro, "assunto": decisao.assunto, "sugerido": sugerido}, portas)
    fio = portas.fio_condutor(programa.id) if categoria == "encerramento" else None

    sorteia_tempo = comportamento.hora_e_marco and tipo != "encerramento"
    hora_certa = _hora_certa_por_extenso(agora_local) if sorteia_tempo and random.random() < _PROB_HORA_CERTA else None
    marco = portas.marco_tempo_programa(programa, radialista.timezone) \
        if sorteia_tempo and random.random() < _PROB_MARCO_TEMPO else None

    musica = resolucao.musica
    contexto_faixa = ""
    if musica is not None:
        contexto_faixa = portas.contexto_musica(musica)
        if contexto_faixa:
            # Fase G do plano-assuntos.md: musica puxa assunto pro comentario seguinte, sem LLM extra.
            portas.registrar_callback_musica(programa.id, f"{musica.titulo} - {musica.canal}", contexto_faixa)

    convite = None
    if resolucao.pedido_ouvinte is None and (comportamento.convite == "qualquer_bloco"
                                              or categoria == "chamada_ouvinte"):
        convite = portas.proxima_variacao(programa.id, "convite_chamada_ouvinte", _VARIACOES_CONVITE_OUVINTE)

    # Orcamento de duracao da fala (F2): o do relogio quando ha', senao o do formato. As palavras do prompt e da
    # reescrita saem do ritmo da voz para esta categoria de bloco.
    orcamento = orcamento_para(
        formato, tipo, decisao.primeira_fala,
        teto_relogio_s=plano.orcamento_s[1] if plano is not None and plano.orcamento_s else None,
        minimo_relogio_s=plano.orcamento_s[0] if plano is not None and plano.orcamento_s else None,
        quadro=eh_quadro_fixo(programa, tipo),  # F6: unidade de quadro nos formatos que a declaram (variedades)
    )
    categoria_voz = categoria_ritmo(tipo)
    wpm_fala = entrada.ritmos_voz.wpm(categoria_voz)
    limite_palavras = palavras_max(orcamento, wpm_fala) if orcamento.aplicar else None

    # Estado musical para o validador (F3): só leituras, depois de todos os sorteios e rotações.
    tocou = tocadas_no_historico(entrada.dados.historico) + [
        MusicaRef(titulo, origem="sessao") for titulo in sorted(portas.historico_musicas(programa.id)[1])]
    citaveis, nomes_fila = _estado_da_fila(entrada, portas)
    pedido_musica = PedidoRef.de(resolucao.pedido_musica, novo) if resolucao.pedido_musica is not None else None
    pedido_ouvinte = PedidoRef.de(resolucao.pedido_ouvinte, novo) if resolucao.pedido_ouvinte is not None else None
    pedido_recente = PedidoRef.de(resolucao.pedido_recente, novo) if resolucao.pedido_recente is not None else None
    instante = plano.instante if plano is not None else agora_local.astimezone(datetime.timezone.utc)
    # Promessas e participação (F4): só leituras do banco, depois de todos os sorteios; nenhuma chave no Redis.
    ocorrencia = plano.ocorrencia.chave if plano is not None else chave_ocorrencia(programa, radialista.timezone,
                                                                                   instante)
    agenda, posicao, tem_musica = _agenda(entrada, decisao, roteiro, categorias_roteiro)
    abertas = tuple(portas.promessas_abertas(entrada.db, programa, ocorrencia))
    ja_atendidos, da_transmissao = portas.nomes_da_transmissao(entrada.db, radialista, programa)
    ja_atendidos, da_transmissao = [nome_seguro(n) for n in ja_atendidos], [nome_seguro(n) for n in da_transmissao]
    # Dados verificáveis (F5): só leituras, depois de todos os sorteios; o clima só com cidade configurada, e a trava
    # de 45 min só quando o clima vai ao bloco (sem leitura, nenhuma chave no Redis).
    dados = _dados(entrada, decisao, jornalismo, quadro, portas)
    instante_dados = plano.instante if plano is not None else agora_local.astimezone(datetime.timezone.utc)
    clima_no_bloco = any(d.tipo == "clima" for d, _ in no_bloco(dados, instante_dados))
    clima_ja_mencionado = portas.clima_ja_mencionado(programa.id) if clima_no_bloco else False
    selecionados = tuple(p.nome for p in (pedido_musica, pedido_ouvinte) if p is not None and p.nome)
    ctx = ContextoEmissao(
        request_id=entrada.request_id, account=account, radialista=radialista, programa=programa,
        tipo=tipo, categoria=categoria, primeira_fala=decisao.primeira_fala, total_falas=entrada.total_falas,
        passos_roteiro=decisao.passos_roteiro, formato_musical=entrada.formato_musical, multi_voz=multi_voz,
        roster=resolucao.roster, roteiro=roteiro, categorias_roteiro=categorias_roteiro,
        tempo=Tempo(agora_local=agora_local, instante=instante,
                    origem_instante=decisao.origem_instante,
                    plano=plano, preset_relogio=decisao.preset_relogio,
                    inicio_previsto_aceito=decisao.inicio_previsto_aceito, ajuste_energia=ajuste_energia,
                    marco_tempo=marco, hora_certa=hora_certa),
        musica=EstadoMusical(
            tocou=tuple(tocou), confirmada=MusicaRef.de(musica) if musica is not None else None,
            citaveis=tuple(citaveis),
            pedido_sem_resultado=resolucao.pedido_sem_resultado,
            resolve_citadas=not (categoria == "musica" and (comportamento.uma_faixa_por_bloco or plano is not None)),
            contexto_faixa=contexto_faixa,
        ),
        participacao=Participacao(
            novo_atendimento=novo, pedido_musica=pedido_musica, pedido_ouvinte=pedido_ouvinte,
            ouvinte_recorrente=resolucao.ouvinte_recorrente.tipo if resolucao.ouvinte_recorrente else None,
            ouvinte_recorrente_dias=(resolucao.ouvinte_recorrente_dias.tipo
                                     if resolucao.ouvinte_recorrente_dias else None),
            pedido_recente=pedido_recente,
            nomes_autorizados=tuple(dict.fromkeys(
                [p.nome for p in (pedido_musica, pedido_ouvinte, pedido_recente) if p is not None and p.nome]
                + nomes_fila)),
            nomes_selecionados=selecionados,
            nomes_ja_atendidos=tuple(n for n in dict.fromkeys(ja_atendidos) if n),
            nomes_conhecidos=tuple(n for n in dict.fromkeys([*nomes_fila, *da_transmissao]) if n),
            nome_recente=pedido_recente.nome if pedido_recente is not None and pedido_recente.nome else None,
        ),
        chamadas=Chamadas(fio_condutor=fio, pedidos_em_fila=len(nomes_fila), promessas=abertas, agenda=agenda,
                          ocorrencia=ocorrencia, posicao=posicao, tem_musica=tem_musica),
        memoria=Memoria(historico=tuple(entrada.dados.historico), historico_prompt=resolucao.historico_prompt,
                        ultima_categoria=ultima_categoria, falas_categoria=tuple(falas_categoria),
                        aberturas=tuple(aberturas), fechamentos=tuple(fechamentos), tom_anterior=tom_anterior,
                        temas_usados=tuple(temas_usados), tema_callback=tema_callback),
        variacoes=Variacoes(verbo_identificacao=verbo, transicao=transicao, formato_comentario=formato_comentario,
                            convite_ouvinte=convite, expressao_regional=expressao_regional, quadro_fixo=quadro,
                            assunto_sugerido=sugerido, assunto=decisao.assunto, mudanca_de_ideia=mudanca_de_ideia,
                            imperfeicao=imperfeicao),
        jornalismo=jornalismo,
        orcamento=orcamento, wpm_fala=wpm_fala, categoria_voz=categoria_voz, limite_palavras=limite_palavras,
        prompt_base=prompt_base, modelo_com_tags=modelo_com_tags, dados=dados,
        clima_ja_mencionado=clima_ja_mencionado, formato=formato,
    )
    # O que este bloco cumpre e as contingências que ele diz (F4), com o contexto completo.
    a_cumprir, contingencias = a_cumprir_e_contingencias(ctx)
    if not (a_cumprir or contingencias):
        return ctx
    return dataclasses.replace(ctx, chamadas=dataclasses.replace(ctx.chamadas, a_cumprir=a_cumprir,
                                                                 contingencias=contingencias))
