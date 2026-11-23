from typing import Literal
import base64
import dataclasses
import datetime
from zoneinfo import ZoneInfo
from app.whatsapp.transmissao import acompanhar_geracao
import logging
import math
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import httpx
import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.redis_client import redis_sessao as redis_client  # estado de sessão e cache: falha aberta (F3)
from app.config.settings import settings
from app.billing.contexto_ia import tarefa_com_contexto, tarefa_independente
from app.db.database import SessionLocal, get_db
from app.guardrails.http_rate_limit import limite_excedido
from app.guardrails.schedule import encontrar_programa_atual, minutos_restantes
from app.live.music import (
    _DURACAO_MAX_SEGUNDOS, MusicaEncontrada, _titulo_normalizado, buscar_musica, buscar_musica_fundo,
    marcar_video_quebrado, titulo_ja_tocado,
)
from app.live.orcamento import (
    OrcamentoFala,
    avaliar_duracao,
    contar_pausas,
    encurtar_pela_medida,
    estimar_duracao_s,
    wpm_da_medida,
    palavras_faladas,
)
from app.live.ritmo_voz import (
    carregar_ritmos,
    categoria_ritmo,
    guardar_orcamento_pendente,
    ler_orcamento_pendente,
    registrar_amostra,
    voz_efetiva,
)
from app.live.relogio import (
    CONFIG_PADRAO as CONFIG_RELOGIO,
    ConfigRelogio,
    EloCadeia,
    Peca,
    PecasDisponiveis,
    Plano,
    RelogioAoVivo,
    duracao_musica_s,
    duracao_preferida_musica_s,
    duracao_prevista_bloco,
    etapas_executadas,
    gravar_elo,
    instante_previsto,
    instante_sem_painel,
    ler_cadeia,
    marcar_executada,
    musica_cabe,
    ocorrencia_em,
    planejar,
    ler_inicio_previsto,
    relogio_ao_vivo,
    relogio_do_programa,
    zerar_cadeia,
)
# Textos de prompt (F3): reexportados aqui porque testes e scripts importam do router.
from app.live.prompts import (  # noqa: F401
    INSTRUCAO_TAGS_V3,
    _CATEGORIAS_NOTICIA_LIKE,
    _DESCRICAO_BLOCO,
    _INSTRUCAO_EXTRA_CATEGORIA_NOTICIA,
    _INSTRUCAO_FECHAMENTO_CURTO,
    _INSTRUCAO_REACAO_POR_NATUREZA,
    _PROB_CALLBACK_TEMA_ANTERIOR,
    _PROB_HORA_CERTA,
    _PROB_IMPERFEICAO_GRAMATICAL,
    _PROB_MARCO_TEMPO,
    _PROB_MUDANCA_DE_IDEIA,
    _PROSODIA_BLOCO,
    _REGRAS_REDACAO_NOTICIA,
    _TIPO_PEDIDO_LEGIVEL,
    _TRANSICOES_DE_BLOCO,
    _TRANSICOES_POR_ORIGEM,
    _VARIACOES_CONVITE_OUVINTE,
    _VARIACOES_FORMATO_COMENTARIO,
    _VARIACOES_VERBO_IDENTIFICACAO,
    _instrucao_reacao_engracada,
    _instrucao_reacao_pergunta,
    _instrucao_reacao_recado_comum,
    _instrucao_reacao_reclamacao,
    _instrucao_relogio,
    _situacao_relogio_prompt,
)
from app.live.portas import PortasEmissao, ligar
from app.live.contexto import (  # noqa: F401 -- reexportados: testes importam do router
    _MAX_TEMAS_RADIO_NO_PROMPT,
    _MUSICAS_TOCADAS_HISTORICO_RE,
    ContextoEmissao,
    MusicaRef,
    ResolucaoBloco,
    _aberturas_e_fechamentos,
    _hora_certa_por_extenso,
    _primeira_frase,
    _ultima_frase,
    montar_contexto,
    resolver_musica_e_pedidos,
    teto_musica as _teto_musica,
)
from app.live.geracao import (  # noqa: F401 -- reexportados
    FalaGerada,
    FalaItem,
    _extrair_quantidade_musicas,
    _fala_semelhante_no_historico,
    _limpar_fala,
    _linhas_que_cabem,
    _termos_preservados,
    gerar_fala,
)
from app.live.prompt_emissao import montar_prompt, segundos_prompt as _segundos  # noqa: F401
from app.live.validacao_fala import (
    Violacao,
    corrigir as corrigir_fala,
    fala_reserva_neutra,
    fragmento,
    para_reescrita,
    validar,
)
from app.live import promessas_repo
from app.live.participacao import pedido_sem_mencao
from app.live.pecas_reserva import escolher_reserva
from app.live.promessas import PromessaRef, a_registrar_no_texto, dita, garantir_contingencia
from app.live.roteiro import (  # noqa: F401 -- reexportados
    _LIMIAR_ENCERRAMENTO_MIN,
    _PATROCINADOR_RE,
    _VINHETA_RE,
    DecisaoBloco,
    EntradaEmissao,
    decidir_bloco,
)
from app.live.formatos import FalaNoAr, Formato, avisos_da_fala, eh_quadro_fixo, formato_do_programa, reorienta
from app.live.direcao_voz import tom_musical
from app.live.song_service import dividir_artista_titulo, esquecer_video_catalogado, resolver_musica_catalogada
from app.live.spotify import buscar_faixas_por_categoria
from app.llm.client import (
    classificar_categoria_bloco,
    classificar_fio_condutor,
    classificar_tema_fala,
    classificar_tom_fala,
    extrair_musicas_citadas,
    gerar_dialogo_multivoz,  # noqa: F401 -- porta (app.live.portas, ligação tardia por nome)
    gerar_resposta,  # noqa: F401 -- porta
    itens_fora_do_genero,
    resumir_contexto_musica,
    escolher_faixa_do_programa,
    sugerir_musica_do_genero,
)
from app.llm.noticias import PesquisaNoticias, pesquisar_noticias  # noqa: F401 -- porta
from app.llm.prompt_builder import (  # noqa: F401 -- portas
    ParticipantePrograma,
    clima_ja_mencionado,
    montar_system_prompt,
)
from app.live.as_run import confirmar_evento, registrar_envio
from app.live.bancada import ordenar_turnos
from app.live.revisao import registrar as registrar_revisao, substituta
from app.live.roteamento_revisao import AUTOMATICO, rotear
from app.models.account import Account
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.musica_historico import MusicaHistorico
from app.models.noticia_historico import NoticiaHistorico
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.topics.pauta_conversa import (  # noqa: F401 -- pipeline, proximo_assunto e callback: portas
    pipeline_tem_estoque,
    proximo_assunto,
    registrar_assunto_usado,
    registrar_callback_musica,
    registrar_callback_noticia,
)
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.models.tema_historico import TemaHistorico
from app.news.pauta import (  # noqa: F401 -- as funções de pauta são portas (testes as trocam pelo nome aqui)
    ANGULO_CORRECAO,
    correcao_pendente,
    proxima_noticia,
    proxima_para_plantao,
    proximas_noticias,
)
from app.postprod.audio_io import duracao_mp3_s
from app.postprod.client import processar_audio
from app.vinhetas.servico import vinheta_encerramento
from pydub.exceptions import PydubException
from app.tts.client import sintetizar_audio, sintetizar_audio_stream, tts_habilitado
from app.weather.client import obter_leitura_clima  # noqa: F401 -- porta (F5): testes e simulador a trocam aqui
from app.tts.voices import validar_voz_ou_400
from app.tts.profiles import parametros_sintese
from app.util.texto import sem_acento as _sem_acento

logger = logging.getLogger("radialista.live")

router = APIRouter(prefix="/live", tags=["live"])



class LiveProgramRequest(BaseModel):
    # O painel prepara a voz em paralelo ao texto seguinte. Clientes antigos
    # continuam recebendo o áudio embutido quando não informam esta opção.
    incluir_audio: bool = True
    perfil_pos_producao: Literal["radio_fm", "alfa_fm", "jovem_pan", "classico"] | None = None
    historico: list[str] = Field(default_factory=list)
    # Contagem real de falas ja geradas nesta transmissao -- "historico" manda so
    # as ultimas 8 pra nao pesar o prompt, entao nao da pra usar len(historico)
    # pra achar a posicao no roteiro (trava sempre no mesmo bloco depois da 8a fala).
    total_falas: int | None = None
    # Texto puro da ultima fala tocada (falasProgramaRef[0]?.fala no frontend), repassado pra
    # ElevenLabs como previous_text quando este endpoint ja sintetiza o audio do bloco (ver
    # Plano B.3) -- mesmo campo que texto_anterior em LiveTtsRequest, so' com outro nome porque
    # aqui nao ha' "chamada de TTS anterior", e' a fala anterior no ar mesmo.
    ultima_fala: str | None = None
    # Horario previsto para este bloco ir ao ar (ISO 8601 com fuso), calculado pelo painel a partir
    # da fila de preparo (ver lib/relogioAoVivo.ts). So' programas com relogio da hora (F1) usam;
    # ausente, passado ou mais de 30 min a frente vale o horario atual. Clientes antigos nao mandam.
    # Texto (nao datetime) de proposito: lido por app.live.relogio.ler_inicio_previsto, que ignora
    # valor invalido em vez de recusar o bloco.
    inicio_previsto: str | None = Field(default=None, max_length=64)


class LiveTtsRequest(BaseModel):
    texto: str
    tom: Literal["calmo", "neutro", "energico"] | None = None
    tipo: str | None = None
    voz_id: str | None = None
    # Nome de um perfil em app/postprod/perfis/*.json (ex.: "alfa_fm"). Nulo = devolve o
    # mp3 cru da ElevenLabs, sem pos-producao (comportamento atual, preservado por default).
    perfil_pos_producao: Literal["radio_fm", "alfa_fm", "jovem_pan", "classico"] | None = None
    # Texto da fala anterior (mesmo locutor, bloco ou linha de dialogo imediatamente antes desta),
    # repassado pra ElevenLabs como previous_text (ver app.tts.client.sintetizar_audio) -- sem isso
    # cada fala e' sintetizada isolada, sem contexto do que veio antes, e a entonacao de
    # inicio/fim de frase sai cortada/artificial em vez de continuar o fluxo da conversa.
    texto_anterior: str | None = None
    # Programa que esta ao vivo agora (ver programaIdRef no frontend) -- usado so pra registrar o
    # tom classificado desta fala (ver classificar_tom_fala abaixo) e informar a proxima chamada de
    # gerar_proxima_fala pra manter transicao de humor coerente entre blocos (ver _ultimo_tom).
    # Nulo em chamada de TTS fora do contexto de um programa ao vivo (nenhuma hoje, mas nao trava
    # o audio se vier faltando).
    programa_id: int | None = None


class MusicaBlocoItem(BaseModel):
    video_id: str
    titulo: str
    # Canal/artista da faixa -- vai junto pro frontend poder compor o historico com
    # "Titulo - Canal" de cada musica do bloco (ver useLiveEngine.ts), dado que o locutor
    # so anuncia a 1a faixa quando emenda um [BLOCO_MUSICAS:N]: sem o canal aqui, o
    # historico enviado de volta pro LLM no proximo bloco nao tem material suficiente
    # pra comentar as faixas 2a/3a que tocaram sem nunca terem sido faladas.
    canal: str = ""
    inicio_segundos: int = 0
    fim_segundos: int | None = None
    # Duracao real do video inteiro (YouTube), None quando a API nao devolveu --
    # ver MusicaEncontrada.duracao_segundos em app.live.music. Nao confundir com
    # fim_segundos: duracao_segundos e' o video inteiro, fim_segundos e' onde corta.
    duracao_segundos: int | None = None


class OrcamentoFalaResponse(BaseModel):
    """Orçamento de duração da fala (F2, app.live.orcamento.OrcamentoFala). `aplicado` False: só medido
    e registrado (formato padrão sem relógio)."""
    min_s: float
    alvo_s: float
    max_s: float
    fonte: Literal["relogio", "formato", "observacao"]
    aplicado: bool


class ViolacaoFalaResponse(BaseModel):
    regra: str
    trecho: str
    ref_id: str = ""


class ValidacaoFalaResponse(BaseModel):
    """Validador pós-geração (F3, app.live.validacao_fala). So' vem quando ele achou algo."""
    violacoes: list[ViolacaoFalaResponse]
    acao: Literal["nenhuma", "reescrita", "mencao_removida", "fala_neutra", "fala_removida"]


class DadoFalaResponse(BaseModel):
    """Dado verificável do bloco (F5, app.dados): sem o texto, só o que o painel e o relatório precisam."""
    id: str
    tipo: str
    estado: Literal["valido", "vencido", "sem_fonte", "nao_aprovado", "futuro"]
    atualizado_em: datetime.datetime | None = None
    valido_ate: datetime.datetime | None = None
    alertas: list[str] = Field(default_factory=list)


class PromessaResponse(BaseModel):
    """Promessa registrada neste bloco (F4, app.live.promessas)."""
    id: int
    tipo: str
    trecho: str
    evento_alvo: str
    prazo: datetime.datetime | None = None
    prazo_posicao: int | None = None


class PromessaResolvidaResponse(BaseModel):
    id: int
    estado: Literal["cumprida", "cancelada", "vencida"]
    contingencia: str | None = None


class PromessasBloco(BaseModel):
    registradas: list[PromessaResponse] = Field(default_factory=list)
    resolvidas: list[PromessaResolvidaResponse] = Field(default_factory=list)


class AsRunConfirmacaoRequest(BaseModel):
    status: str  # "confirmado" | "falhou"


class AsRunConfirmacaoResponse(BaseModel):
    id: int
    status: str


class LiveProgramResponse(BaseModel):
    bloco_id: int | None = None
    bloco_token: str | None = None
    bloco_programa_id: int | None = None
    assunto_id: int | None = None
    assunto_titulo: str | None = None
    tipo: str
    fala: str
    pesquisa_noticias: PesquisaNoticias | None = None
    tom: Literal["calmo", "neutro", "energico"] | None = None
    criado_em: datetime.datetime
    video_id: str | None = None
    titulo_musica: str | None = None
    inicio_segundos: int = 0
    fim_segundos: int | None = None
    duracao_segundos: int | None = None
    musicas: list[MusicaBlocoItem] = Field(default_factory=list)
    programa_atual: str | None = None
    patrocinador_id: int | None = None
    patrocinador_audio: bool = False
    patrocinador_voz_id: str | None = None
    vinheta_id: int | None = None
    # True = /vinhetas/{id}/audio tem o arquivo final (voz + trilha mixadas). False = vinheta
    # gerada ainda sem audio (pendente/erro): o painel fala `fala` via TTS normal, sem trilha --
    # o ao vivo nunca espera a mixagem.
    vinheta_audio: bool = False
    # So' na fala de encerramento: vinheta de encerramento do programa, tocada logo depois dela
    # (encerramento nao entra em estrutura_blocos, ver app/vinhetas/estrutura.py).
    vinheta_encerramento_id: int | None = None
    vinheta_encerramento_audio: bool = False
    vinheta_encerramento_texto: str | None = None
    # Quantas posicoes do roteiro este bloco consumiu. >1 quando vinhetas desativadas/sem
    # conteudo foram puladas -- o painel soma isso em total_falas, senao o proximo /proxima
    # cairia de volta num bloco que ja saiu.
    passos_roteiro: int = 1
    # Preenchido só quando o programa tem mais de um radialista (ver ProgramaRadialista):
    # diálogo alternado, uma linha por participante, cada uma com sua própria voz.
    falas: list[FalaItem] | None = None
    # Audio (mp3, base64) de cada linha de `falas` acima, mesmo indice -- sintetizado aqui
    # dentro em paralelo (ver _sintetizar_falas_multivoz) pra poupar o frontend de abrir uma
    # chamada /tts por linha em sequencia. Item None significa que aquela linha especifica
    # falhou (ou audio nao foi pedido) -- o frontend cai pro /tts avulso so' pra essa linha,
    # nao pro bloco inteiro.
    audios_falas_base64: list[str | None] | None = None
    # Compatibilidade com painéis antigos. O painel atual usa apenas pausa_antes_ms.
    intervalo_ms: int | None = None
    # Pausa aplicada uma única vez ANTES deste bloco, quando ele já estiver preparado.
    pausa_antes_ms: int | None = None
    duracao_alvo_segundos: tuple[int, int] | None = None
    # Audio ja sintetizado (mp3, base64) do texto de `fala` acima -- preenchido so' quando o
    # bloco e' de fala unica (nao multi-voz, nao patrocinador/vinheta) e o TTS deu certo aqui
    # dentro (ver Plano B.3: funde /proxima+/tts, corta um round-trip HTTP inteiro). Quando vier
    # vazio, audio_status informa se o frontend deve buscar outra fonte ou manter a cama musical.
    audio_base64: str | None = None
    # Estado explicito da sintese embutida. Sem isso o frontend nao distingue "ainda precisa
    # buscar o audio" de "o provedor ja falhou" e repetia uma chamada cara antes de cair no
    # speechSynthesis do navegador.
    audio_status: str = "nao_aplicavel"
    audio_erro: str | None = None
    pedido_id: int | None = None
    pedido_token: str | None = None
    # F11 item 1: id da linha do as-run ('enviado'); o player devolve a confirmacao por ele (ver /as-run).
    as_run_evento_id: int | None = None
    pedido_programa_id: int | None = None
    pedido_radialista_id: int | None = None
    # Duracao estimada do bloco inteiro (fala a CONFIG_RELOGIO.wpm, musicas, vinheta/patrocinador e
    # vinheta de encerramento) -- o painel encadeia o horario previsto do bloco seguinte com ela.
    duracao_prevista_s: float | None = None
    # So' em programa com relogio da hora: etapa, proximo compromisso, backtiming e orcamento.
    relogio: RelogioAoVivo | None = None
    # Duracao real da fala (F2), so' em bloco com fala gerada. duracao_fala_s: medida no audio final
    # (pos-producao incluida) quando sintetizado aqui; no multivoz, soma das linhas mais as pausas entre
    # elas. Nulo no caminho do painel (audio_status "pendente"): o /tts mede e devolve X-Duracao-Fala-S.
    duracao_fala_s: float | None = None
    # Estimativa pelo ritmo calibrado da voz (app.live.ritmo_voz.wpm_para).
    duracao_fala_estimada_s: float | None = None
    orcamento_fala_s: OrcamentoFalaResponse | None = None
    # O que foi feito pra caber no orcamento (ver app.live.orcamento.Ajuste); nunca acelera a voz.
    fala_ajuste: Literal["nenhum", "reescrita", "encurtada", "cortada", "acima_do_teto"] | None = None
    # Validador pós-geração (F3): musica anunciada sem confirmacao ou fragmento abaixo do minimo. Nulo = nada achado.
    validacao_fala: ValidacaoFalaResponse | None = None
    # Promessas registradas e resolvidas neste bloco (F4). Nulo = nenhuma.
    promessas: PromessasBloco | None = None
    # Dados verificáveis do bloco e o estado de cada um no instante do bloco (F5). Nulo = nenhum.
    dados: list[DadoFalaResponse] | None = None


class MusicaFundoResponse(BaseModel):
    video_id: str
    titulo: str
    inicio_segundos: int = 0
    fim_segundos: int | None = None
    duracao_segundos: int | None = None


class MusicaSubstitutaRequest(BaseModel):
    video_id: str = Field(min_length=1, max_length=64)
    titulo: str = Field(default="", max_length=300)
    motivo: str | None = Field(default=None, max_length=100)


class MusicaSubstitutaResponse(MusicaFundoResponse):
    canal: str = ""


class RadialistaNoArResponse(BaseModel):
    no_ar: bool
    radialista_id: int | None = None
    radialista_nome: str | None = None
    programa_id: int | None = None
    programa_nome: str | None = None


class PedidoFilaResponse(BaseModel):
    id: int
    telefone: str
    nome: str
    tipo: str
    mensagem_usuario: str
    musica_query: str | None
    atendido: bool
    atendido_em: datetime.datetime | None
    criado_em: datetime.datetime
    programa_id: int | None = None
    transmissao: str | None = None
    estado: str = "em_fila"
    eventos: list[dict] = Field(default_factory=list)
    texto_autorizado: str = ""
    motivo: str = ""

    model_config = {"from_attributes": True}


class FilaHistoricoPaginadaResponse(BaseModel):
    pedidos: list[PedidoFilaResponse]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


def _portas() -> PortasEmissao:
    """Portas da emissão com ligação tardia nos nomes deste módulo (ver app.live.portas): os testes e o
    simulador que trocam `app.live.router.<nome>` continuam valendo para o código extraído."""
    return ligar(globals())


def _selecionar_pedido_atendimento(db: Session, radialista: RadioConfig, programa: Programa, tipos: tuple[str, ...]):
    """Seleção do fluxo novo de atendimento (importada na chamada, como antes: evita ciclo de import)."""
    from app.whatsapp.atendimento import selecionar

    return selecionar(db, radialista, programa, tipos)


def _buscar_radialista(db: Session, account: Account, radialista_id: int) -> RadioConfig:
    config = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radialista nao encontrado")
    return config


def _buscar_programa(db: Session, radialista: RadioConfig, programa_id: int) -> Programa:
    programa = db.query(Programa).filter_by(id=programa_id, radio_config_id=radialista.id).first()
    if programa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa nao encontrado")
    from app.billing.contexto_ia import selecionar_programa
    selecionar_programa(programa)
    return programa


def _buscar_roster(db: Session, account: Account, programa: Programa) -> list[ParticipantePrograma]:
    """Monta o roster do programa (dono + co-apresentadores, ver ProgramaRadialista) na
    ordem configurada. Programa sem nenhum co-apresentador cadastrado devolve so o dono --
    mesmo comportamento de sempre (locutor unico).
    """
    vinculos = (
        db.query(ProgramaRadialista)
        .filter_by(programa_id=programa.id)
        .order_by(ProgramaRadialista.ordem.asc(), ProgramaRadialista.id.asc())
        .all()
    )
    vinculo_por_radialista = {v.radio_config_id: v for v in vinculos}
    ids_radialistas = {programa.radio_config_id, *vinculo_por_radialista.keys()}
    configs_por_id = {
        c.id: c for c in db.query(RadioConfig).filter(RadioConfig.account_id == account.id, RadioConfig.id.in_(ids_radialistas)).all()
    }

    def _participante(radio_config_id: int) -> ParticipantePrograma | None:
        config = configs_por_id.get(radio_config_id)
        if config is None:
            return None
        vinculo = vinculo_por_radialista.get(radio_config_id)
        return ParticipantePrograma(
            config,
            vinculo.papel if vinculo else "Apresentador principal",
            vinculo.comportamento if vinculo else "",
            papel_bancada=vinculo.papel_bancada if vinculo else None,
        )

    dono = _participante(programa.radio_config_id)
    roster = [dono] if dono else []
    for radio_config_id in vinculo_por_radialista:
        if radio_config_id == programa.radio_config_id:
            continue
        participante = _participante(radio_config_id)
        if participante is not None:
            roster.append(participante)
    # F13: com papéis na bancada, a ordem de fala segue mediador -> comentarista -> contraponto.
    return ordenar_turnos(roster, lambda p: getattr(p, "papel_bancada", None))


_JANELA_MARCO_TEMPO_MIN = 10


# Janela pra considerar que um pedido novo "acabou de chegar" na fila enquanto o locutor ja
# estava gerando outro tipo de bloco -- curta de proposito, e' pra soar como interrupcao real,
# nao como pedido velho sendo mencionado fora de hora.
_JANELA_PEDIDO_RECENTE_SEGUNDOS = 120

# Janela (em dias) pra reconhecer o mesmo ouvinte (mesmo telefone) voltando em uma transmissao
# de outro dia -- mais larga que _JANELA_OUVINTE_RECORRENTE_HORAS (que e' "voltou nesta mesma
# transmissao"), por isso casa por telefone (mais confiavel que nome numa janela tao larga).
_DIAS_JANELA_OUVINTE_RECORRENTE = 30


def _duracao_total_minutos(programa: Programa) -> int:
    inicio = programa.horario_inicio.hour * 60 + programa.horario_inicio.minute
    fim = programa.horario_fim.hour * 60 + programa.horario_fim.minute
    if fim <= inicio:
        fim += 24 * 60
    return fim - inicio


def _marco_tempo_programa(programa: Programa, timezone: str) -> str | None:
    """Frase natural tipo "acabou de comecar"/"estamos na metade" pra reforcar a sensacao de
    tempo real acontecendo -- so aritmetica sobre horario_inicio/horario_fim (ja existentes),
    sem precisar de nenhum dado novo. None quando o programa nao esta' no ar agora ou quando nao
    da pra dizer nada natural nesse momento (fora das janelas de inicio/metade)."""
    restantes = minutos_restantes(programa, timezone)
    duracao_total = _duracao_total_minutos(programa)
    if restantes < 0 or restantes > duracao_total:
        return None
    decorridos = duracao_total - restantes
    if decorridos <= _JANELA_MARCO_TEMPO_MIN:
        return "o programa acabou de começar agora"
    metade = duracao_total / 2
    if abs(decorridos - metade) <= _JANELA_MARCO_TEMPO_MIN:
        return f"já estamos há cerca de {decorridos} minutos no ar, mais ou menos na metade do programa de hoje"
    return None


def _ajuste_energia_meio_programa(programa: Programa, timezone: str) -> str | None:
    """Locutor real nao mantem a mesma energia por horas: cansa um pouco no miolo do programa e
    recupera perto do fim -- mesma aritmetica de _marco_tempo_programa, mas cobrindo uma faixa
    larga (30% a 70% do tempo decorrido), nao um instante pontual, porque fadiga e' um estado que
    dura, nao um anuncio que se faz uma vez."""
    restantes = minutos_restantes(programa, timezone)
    duracao_total = _duracao_total_minutos(programa)
    if restantes < 0 or restantes > duracao_total or duracao_total <= 0:
        return None
    decorridos = duracao_total - restantes
    proporcao = decorridos / duracao_total
    if 0.3 <= proporcao <= 0.7:
        return (
            "Você já está no miolo do programa há um tempo: deixe a energia um pouco mais contida "
            "que na abertura, sem cair pra neutro -- ainda soa presente, só menos eufórico, como "
            "quem já pegou o ritmo do dia."
        )
    return None


# Na rota integrada /proxima, classificar o tom com outra chamada ao LLM depois de o texto
# estar pronto somava latencia sem mudar de forma confiavel a direcao editorial ja definida pelo
# bloco. A classificacao continua no endpoint avulso /tts; no caminho critico usamos uma direcao
# deterministica, estavel entre uma fala e outra.
_TOM_SINTESE_POR_CATEGORIA = {
    "abertura": "energico",
    "musica": "energico",
    "chamada_ouvinte": "energico",
    "comentario": "calmo",
    "noticia": "calmo",
    "escalada": "energico",
    "servico": "neutro",
    "plantao": "energico",
    "reporter": "calmo",
    "encerramento": "calmo",
}

# chamada_ouvinte e' o unico tipo de bloco onde a REACAO exigida do texto (ver
# _INSTRUCAO_REACAO_POR_NATUREZA acima) varia forte dentro do mesmo tipo de bloco -- reclamacao
# pede "reconheca com respeito, sem debochar", bem diferente da reacao energica default. Sem
# isso, o texto saia serio mas a prosodia/voice_settings continuavam "energico" fixo pra todo
# chamada_ouvinte, ouvinte que reclamou ouvia o locutor "animado" respondendo a reclamacao dele.
_TOM_POR_NATUREZA_CHAMADA_OUVINTE = {
    "reclamacao": "calmo",
    "pergunta": "neutro",
    "reacao_engracada": "energico",
    "participacao_sorteio": "energico",
    "pedido_musica": "energico",
    "recado_comum": "energico",
    "outro": "neutro",
}


def _tom_sintese_do_bloco(tipo_bloco: str, natureza_ouvinte: str | None = None) -> str:
    categoria = _categoria_bloco(tipo_bloco)
    if categoria == "chamada_ouvinte" and natureza_ouvinte:
        return _TOM_POR_NATUREZA_CHAMADA_OUVINTE.get(natureza_ouvinte, _TOM_SINTESE_POR_CATEGORIA[categoria])
    return _TOM_SINTESE_POR_CATEGORIA.get(categoria, "neutro")


# Timeout SEM retry pra sintese embutida em /proxima (ver chamada de sintetizar_audio abaixo) --
# essa chamada acontece dentro do MESMO request que ja gastou tempo gerando a fala via LLM, e o
# frontend aplica um timeout unico (45s, ver apiFetchComTimeout em useLiveEngine.ts) pro round-trip
# inteiro de /proxima. Medido direto na API: eleven_v3 sozinho ja leva ~11s pra um bloco de tamanho
# normal (voz de catalogo; voz clonada e' mais lenta ainda) -- o valor antigo (6s) estourava SEMPRE,
# nao so' no caso lento. 18s da margem real pro v3 sem devorar o orcamento do frontend (LLM +
# sintese + rede ainda precisam caber nos 45s). Sem retentativa aqui: se falhar (429 incluido), o
# /tts avulso chamado em seguida pelo frontend ja tem seu proprio orcamento cheio de retentativa/backoff.
_TTS_TIMEOUT_EMBUTIDO_SEGUNDOS = 18.0


def _instrucao_transicao(programa_id: int, categoria_anterior: str | None, categoria_atual: str) -> str | None:
    """Instrucao de COMO o tom se move da categoria anterior pra atual (ver _TRANSICOES_DE_BLOCO) --
    None quando nao ha bloco anterior (largada do programa) ou quando o par nao tem movimento
    especifico cadastrado nem fallback por origem (cai so no gancho generico ja existente no
    prompt)."""
    if categoria_anterior is None or categoria_anterior == categoria_atual:
        return None
    par = (categoria_anterior, categoria_atual)
    opcoes = _TRANSICOES_DE_BLOCO.get(par) or _TRANSICOES_POR_ORIGEM.get(categoria_anterior)
    if not opcoes:
        # Nenhum movimento especifico cadastrado pro par -- ainda assim rotula explicitamente o
        # tipo do bloco anterior (ver Frente K.2), pra o LLM sempre saber de onde a fala esta
        # vindo mesmo sem instrucao de movimento dedicada.
        return f"A fala anterior foi do tipo '{categoria_anterior}'."
    chave = f"transicao_{categoria_anterior}_{categoria_atual}"
    return _proxima_variacao(programa_id, chave, opcoes)


# Contrato legado para painéis antigos; o player atual usa _pausa_antes_ms.
# Faixas (ms) de silencio entre o fim do audio do bloco anterior e o inicio do proximo, por tipo
# de transicao -- ver _intervalo_transicao_ms (Frente K.5). Silencio sempre igual entre blocos e'
# outro sinal claro de "colado"/robotico: radio de verdade emenda quase sem pausa numa transicao
# animada (ex.: saindo de musica) e da um respiro maior em volta de notica (mais serio/pensativo).
_INTERVALO_TRANSICAO_PADRAO_MS = 2200
_INTERVALO_TRANSICAO_ANIMADA_MS = (900, 1400)
_INTERVALO_TRANSICAO_NOTICIA_MS = (2800, 3400)
_INTERVALO_TRANSICAO_NORMAL_MS = (1800, 2600)


def _intervalo_transicao_ms(categoria_anterior: str | None, categoria_atual: str) -> int:
    """Duracao do silencio (ms) antes do proximo bloco -- ver constantes acima. Usa random.randint
    dentro da faixa (nao um valor fixo por par) pra nem repetir o mesmo silencio toda vez que o
    mesmo par de categorias se repete, mesmo padrao de "nao decorar" ja aplicado ao texto (ver
    _proxima_variacao)."""
    if categoria_anterior is None:
        return _INTERVALO_TRANSICAO_PADRAO_MS
    if categoria_anterior in _CATEGORIAS_NOTICIA_LIKE or categoria_atual in _CATEGORIAS_NOTICIA_LIKE:
        return random.randint(*_INTERVALO_TRANSICAO_NOTICIA_MS)
    if "musica" in (categoria_anterior, categoria_atual) and categoria_anterior != categoria_atual:
        return random.randint(*_INTERVALO_TRANSICAO_ANIMADA_MS)
    return random.randint(*_INTERVALO_TRANSICAO_NORMAL_MS)


def _pausa_antes_ms(anterior: str | None, atual: str) -> int:
    """Ritmo editorial; tempo de rede e preparação não fazem parte desta pausa."""
    if anterior is None:
        return 0
    if anterior == atual == "musica":
        return 0
    if anterior in _CATEGORIAS_NOTICIA_LIKE or atual in _CATEGORIAS_NOTICIA_LIKE:
        return 800
    if "vinheta" in (anterior, atual) or "musica" in (anterior, atual):
        return 150
    return 350


def _ultima_categoria_bloco(historico: list[str]) -> str | None:
    """Categoria (ver _categoria_bloco) do ultimo bloco falado, a partir de dados.historico
    (formato "tipo: fala..." -- ver useLiveEngine.ts no frontend). None quando o programa ainda
    nao tem historico (inicio da transmissao ou dado ausente) -- usado por _tipo_proximo_bloco
    pra nunca deixar "abertura" cair logo depois de um bloco que nao seja musica."""
    if not historico:
        return None
    tipo_bruto = historico[-1].split(":", 1)[0].strip()
    return _categoria_bloco(tipo_bruto)


# Categorias do bloco anterior em que a abertura de uma volta faz sentido (None = largada). Os formatos com
# abertura_apos_intervalo (D17 da F6) aceitam também a volta do intervalo comercial.
_ANTES_DA_ABERTURA: tuple[str | None, ...] = (None, "musica", "vinheta")
_ANTES_DA_ABERTURA_APOS_INTERVALO: tuple[str, ...] = ("patrocinador",)


def _tipo_proximo_bloco(programa: Programa, total_falas: int, ultima_categoria: str | None = None) -> str:
    """Decide o tipo do proximo bloco.

    Sem estrutura customizada: mantem o comportamento padrao (abertura so pode vir logo depois de
    um bloco de musica, excecao pra abertura de largada do programa). Com estrutura customizada
    (programa.estrutura_blocos), segue a sequencia definida pelo usuario, em loop -- exceto
    "abertura" fora de lugar (usuario colocou fora de uma posicao logo apos musica, ou a injecao
    aleatoria de comentario abaixo "comeu" o bloco de musica que viria antes dela), que vira
    "comentario" em vez de quebrar a regra de que abertura so faz sentido logo apos musica ou na
    largada do programa (ultima_categoria None so' quando nao ha' historico ainda, o que so
    acontece na largada -- ver _ultima_categoria_bloco).

    "encerramento" nunca sai daqui: so e' liberado quando o programa esta' de fato terminando
    (ver perto_do_fim em gerar_proxima_fala). Se o usuario incluiu "encerramento" no meio da
    estrutura customizada, esse item e' ignorado no loop e a sequencia volta pro inicio.

    O ciclo, o roteiro com a estrutura vazia, a liberdade de inserir blocos e a abertura depois do intervalo vem do
    formato do programa (app.live.formatos, F6).
    """
    formato = formato_do_programa(programa)
    comportamento = formato.comportamento
    if comportamento.ciclo == "musical":
        if total_falas == 0:
            return "abertura"
        roteiro = [
            t.strip() for t in programa.estrutura_blocos
            if t.strip() and _sem_acento(t.strip().lower()) != "abertura"
            and _categoria_bloco(t.strip()) != "encerramento"
        ] or list(formato.roteiro_padrao)
        return roteiro[(total_falas - 1) % len(roteiro)]

    roteiro_customizado = [
        t.strip() for t in programa.estrutura_blocos if t.strip() and _categoria_bloco(t) != "encerramento"
    ]
    if not roteiro_customizado:
        if total_falas == 0:
            return "abertura"
        return formato.roteiro_padrao[(total_falas - 1) % len(formato.roteiro_padrao)]

    tipo = roteiro_customizado[total_falas % len(roteiro_customizado)]
    if programa.ia_pode_adicionar_blocos and comportamento.ia_pode_adicionar_blocos and total_falas > 0 \
            and random.random() < 0.15:
        # IA fica livre pra emendar um comentario extra fora da sequencia pre-definida de vez em quando.
        return "comentario"
    antes_da_abertura = _ANTES_DA_ABERTURA + (_ANTES_DA_ABERTURA_APOS_INTERVALO
                                              if comportamento.abertura_apos_intervalo else ())
    if (
        total_falas > 0
        and _categoria_bloco(tipo) == "abertura"
        and ultima_categoria not in antes_da_abertura
    ):
        return "comentario"
    return tipo



# TTL generico p/ estado de sessao ao vivo no Redis (historico de musica, historico de temas,
# rotacao de frases). 6h cobre uma transmissao inteira sem acumular lixo de sessoes antigas.
_TTL_SESSAO_AO_VIVO = 6 * 60 * 60


def _ultimo_tom(programa_id: int) -> str | None:
    """Tom (energico/calmo/neutro, ver classificar_tom_fala) da ultima fala deste programa que
    de fato virou audio -- classificado no momento do TTS (ver gerar_audio_fala), nao no momento
    da geracao de texto, entao so fica disponivel pra fala seguinte depois que o audio da fala
    anterior for sintetizado."""
    return redis_client.get(f"ultimo_tom:{programa_id}")


def _registrar_ultimo_tom(programa_id: int, tom: str) -> None:
    redis_client.set(f"ultimo_tom:{programa_id}", tom, ex=_TTL_SESSAO_AO_VIVO)


def _ultima_reorientacao(programa_id: int) -> datetime.datetime | None:
    """F8 (passo 3): instante (UTC) da última fala deste programa que reorientou quem chegou ("Você está no ...")."""
    valor = redis_client.get(f"ultima_reorientacao:{programa_id}")
    try:
        return datetime.datetime.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _pecas_reserva_usadas(programa_id: int, ocorrencia: str | None) -> frozenset[int]:
    """F11 (item 3): ids das peças de reserva já ditas nesta ocorrência do programa (cada peça vai ao ar uma vez)."""
    if not ocorrencia:
        return frozenset()
    return frozenset(int(i) for i in redis_client.smembers(f"pecas_reserva_usadas:{programa_id}:{ocorrencia}") or ())


def _registrar_peca_usada(programa_id: int, ocorrencia: str | None, peca_id: int) -> None:
    if not ocorrencia:
        return
    chave = f"pecas_reserva_usadas:{programa_id}:{ocorrencia}"
    redis_client.sadd(chave, str(peca_id))
    redis_client.expire(chave, _TTL_SESSAO_AO_VIVO)


def _registrar_reorientacao(programa_id: int, instante: datetime.datetime) -> None:
    redis_client.set(f"ultima_reorientacao:{programa_id}", instante.astimezone(datetime.timezone.utc).isoformat(),
                     ex=_TTL_SESSAO_AO_VIVO)


def _historico_musicas(programa_id: int) -> tuple[set[str], set[str], dict[str, int]]:
    """Musicas tocadas no programa (por sessao ao vivo), pra buscar_musica evitar repetir a
    mesma faixa (por video_id OU por titulo normalizado -- ver titulos_tocados em
    app.live.music, cobre reupload/versao diferente da mesma musica) ou saturar de um so'
    artista (ver limite_por_canal em app.live.music)."""
    ids = redis_client.smembers(f"musicas_tocadas:ids:{programa_id}")
    titulos = redis_client.smembers(f"musicas_tocadas:titulos:{programa_id}")
    canais_raw = redis_client.hgetall(f"musicas_tocadas:canais:{programa_id}")
    return set(ids), set(titulos), {canal: int(contagem) for canal, contagem in canais_raw.items()}


def _registrar_musica_tocada(programa_id: int, musica: MusicaEncontrada) -> None:
    chave_ids = f"musicas_tocadas:ids:{programa_id}"
    chave_titulos = f"musicas_tocadas:titulos:{programa_id}"
    chave_canais = f"musicas_tocadas:canais:{programa_id}"
    redis_client.sadd(chave_ids, musica.video_id)
    redis_client.expire(chave_ids, _TTL_SESSAO_AO_VIVO)
    redis_client.sadd(chave_titulos, _titulo_normalizado(musica.titulo))
    redis_client.expire(chave_titulos, _TTL_SESSAO_AO_VIVO)
    redis_client.hincrby(chave_canais, musica.canal.lower(), 1)
    redis_client.expire(chave_canais, _TTL_SESSAO_AO_VIVO)


# Quantos temas de comentario/noticia guardar no historico da sessao (ver _historico_temas).
_MAX_TEMAS_HISTORICO = 15


def _historico_temas(programa_id: int) -> list[str]:
    """Temas de comentario/noticia ja abordados nesta sessao ao vivo, do mais recente pro
    mais antigo -- cobre a transmissao inteira, ao contrario do 'historico' de falas que o
    frontend manda (so as ultimas 8), pra evitar repetir assunto depois de varios blocos."""
    return redis_client.lrange(f"temas_comentados:{programa_id}", 0, _MAX_TEMAS_HISTORICO - 1)


def _registrar_tema(programa_id: int, tema: str) -> None:
    chave = f"temas_comentados:{programa_id}"
    redis_client.lrem(chave, 0, tema)
    redis_client.lpush(chave, tema)
    redis_client.ltrim(chave, 0, _MAX_TEMAS_HISTORICO - 1)
    redis_client.expire(chave, _TTL_SESSAO_AO_VIVO)


def _fio_condutor(programa_id: int) -> str | None:
    """Pergunta/expectativa lancada na abertura do programa (ver classificar_fio_condutor em
    app.llm.client), pra ser retomada no encerramento -- da a sensacao de um arco narrativo
    atravessando o programa inteiro, nao so conexao bloco-a-bloco (ver gancho/callback abaixo)."""
    return redis_client.get(f"fio_condutor:{programa_id}")


def _registrar_fio_condutor(programa_id: int, texto: str) -> None:
    redis_client.set(f"fio_condutor:{programa_id}", texto, ex=_TTL_SESSAO_AO_VIVO)


# Quantas falas recentes guardar por categoria de bloco (ver _historico_falas) pra checagem de
# similaridade -- so entre blocos do mesmo tipo, pra abertura de hoje nao ser comparada com
# noticia de ontem (mesmo programa, blocos diferentes tendem a compartilhar vocabulario normal
# da radio sem serem repeticao de verdade).
_MAX_FALAS_HISTORICO_POR_CATEGORIA = 8

def _historico_falas(programa_id: int, categoria: str) -> list[str]:
    return redis_client.lrange(f"falas_geradas:{programa_id}:{categoria}", 0, -1)


def _registrar_fala_gerada(programa_id: int, categoria: str, texto: str) -> None:
    chave = f"falas_geradas:{programa_id}:{categoria}"
    redis_client.lpush(chave, texto)
    redis_client.ltrim(chave, 0, _MAX_FALAS_HISTORICO_POR_CATEGORIA - 1)
    redis_client.expire(chave, _TTL_SESSAO_AO_VIVO)


def _proxima_variacao(programa_id: int, chave: str, opcoes: list[str]) -> str:
    """Roda por uma lista de variacoes de frase sem repetir a mesma ate esgotar o pool --
    round-robin persistido no Redis por programa. Existe porque so pedir pro LLM 'variar' no
    prompt nao e garantia: sem estado nenhum entre chamadas, ele tende a gravitar pra mesma
    construcao de maior probabilidade sempre que o contexto se parece (ver historico_musicas
    pra o mesmo problema resolvido do lado das musicas)."""
    redis_key = f"rotacao:{chave}:{programa_id}"
    indice = redis_client.incr(redis_key)
    redis_client.expire(redis_key, _TTL_SESSAO_AO_VIVO)
    return opcoes[(indice - 1) % len(opcoes)]


# tipos de bloco com comportamento automatico (busca de musica, prosodia, fila do whatsapp).
_TIPOS_COM_COMPORTAMENTO = (
    "musica", "noticia", "escalada", "servico", "plantao", "reporter",
    "chamada_ouvinte", "abertura", "comentario", "encerramento",
)


# cache no Redis (hash, por texto normalizado de bloco) da classificacao via LLM -- so paga a
# chamada uma vez por bloco customizado distinto, mesmo que o ao vivo gere falas pra ele varias
# vezes e mesmo entre workers/instancias diferentes do backend (cache em memoria de processo nao
# seria compartilhado entre eles). TTL e teto em settings (item 9 da docs/auditoria.md): o hash e'
# global, entao sem eles cresceria pra sempre com os rotulos de todas as contas.
_CACHE_CATEGORIA_CUSTOMIZADA = "cache:categoria_bloco_customizado"


def _classificar_bloco_customizado(tipo_original: str, normalizado: str) -> str:
    categoria = redis_client.hget(_CACHE_CATEGORIA_CUSTOMIZADA, normalizado)
    if categoria is None:
        try:
            categoria = classificar_categoria_bloco(tipo_original)
        except Exception:
            logger.warning("Falha ao classificar categoria de bloco customizado: %r", tipo_original, exc_info=True)
            categoria = "outro"
        categoria = categoria if categoria in _TIPOS_COM_COMPORTAMENTO else ""
        if redis_client.hlen(_CACHE_CATEGORIA_CUSTOMIZADA) >= settings.cache_categoria_bloco_max:
            # Passou do teto: recomeca (cada rotulo paga uma classificacao de novo) em vez de crescer sem limite.
            logger.info("live_cache_categoria_recomecou max=%s", settings.cache_categoria_bloco_max)
            redis_client.delete(_CACHE_CATEGORIA_CUSTOMIZADA)
        redis_client.hset(_CACHE_CATEGORIA_CUSTOMIZADA, normalizado, categoria)
        redis_client.expire(_CACHE_CATEGORIA_CUSTOMIZADA, settings.cache_categoria_bloco_ttl_s)
    return categoria


def _categoria_bloco(tipo: str) -> str:
    """Normaliza o texto do bloco pro tipo base que rege o comportamento automatico.

    Bloco customizado tipo "Musica Vaneira" ou "Música Sertaneja" bate direto pelo prefixo
    (rapido, sem custo de LLM). Bloco customizado sem esse prefixo, tipo "chamame e xote" ou
    "forro pe de serra", nao tem como saber por texto que e um bloco de musica -- por isso cai
    numa classificacao via LLM (cacheada) antes de virar "bloco livre" sem musica nenhuma.
    """
    if _PATROCINADOR_RE.match(tipo) or _VINHETA_RE.match(tipo):
        return tipo
    tipo = tipo.strip()
    normalizado = _sem_acento(tipo.lower())
    if normalizado in ("vinheta", "patrocinador"):
        return normalizado
    if normalizado in ("retomada", "identificacao"):
        return "abertura"
    if normalizado == "giro":
        return "noticia"
    for base in _TIPOS_COM_COMPORTAMENTO:
        if normalizado == base or normalizado.startswith((f"{base} ", f"{base}_")):
            return base
    if re.match(r"^manchetes?(?:\b|_)", normalizado.replace("_", " ")):
        return "escalada"
    if re.match(
        r"^(tempo e transito|previsao (?:do )?tempo|utilidade publica|cotacoes)(?:\b|_)",
        normalizado.replace("_", " "),
    ):
        return "servico"
    if re.match(r"^(boletim|jornal|agenda cultural)(?:\b|_)", normalizado.replace("_", " ")):
        return "noticia"
    return _classificar_bloco_customizado(tipo, normalizado) or normalizado


def _buscar_patrocinador_ativo(db: Session, account: Account, tipo: str) -> Patrocinador | None:
    match = _PATROCINADOR_RE.match(tipo)
    if not match:
        return None
    return (
        db.query(Patrocinador)
        .filter_by(id=int(match.group(1)), account_id=account.id, ativo=True)
        .first()
    )


def _buscar_vinheta_ativa(db: Session, account: Account, tipo: str) -> BibliotecaAudioItem | None:
    match = _VINHETA_RE.match(tipo)
    if not match:
        return None
    return (
        db.query(BibliotecaAudioItem)
        .filter_by(id=int(match.group(1)), account_id=account.id, ativo=True)
        .first()
    )


_PREFIXO_MUSICA_RE = re.compile(r"^m[uú]sica\s+", re.IGNORECASE)


def _genero_do_rotulo(rotulo: str) -> str:
    """Extrai a parte 'genero' de um rotulo de bloco de musica customizado -- 'Musica Vaneira' vira
    'Vaneira'; 'chamame e xote', sem prefixo, e devolvido inteiro (ja e o proprio nome do estilo)."""
    return _PREFIXO_MUSICA_RE.sub("", rotulo).strip()


# Pesos relativos pra escolha ponderada da query de musica quando o bloco nao tem rotulo de
# genero proprio (ver _escolher_query_musica). Posicao na lista curada pelo admin pesa mais que
# frequencia de pedido do publico: e' curadoria deliberada, enquanto pedido do publico e' sinal
# real porem mais ruidoso (mesmo artista escrito de jeitos diferentes, pedido por brincadeira, etc.).
_PESO_POSICAO_ADMIN = 3.0
_PESO_PEDIDO_PUBLICO = 1.0

# Janela de tempo pra contar pedido do publico como sinal de preferencia (ver
# _pedidos_publico_mais_frequentes) -- pedido de meses atras nao deveria pesar pra sempre,
# o gosto do publico muda.
_DIAS_JANELA_PEDIDOS_PUBLICO = 90
_MAX_PEDIDOS_PUBLICO_NO_POOL = 5


def _pedidos_publico_mais_frequentes(db: Session, programa_id: int) -> list[tuple[str, int]]:
    """Musicas/artistas mais pedidos pelo publico via WhatsApp neste programa nos ultimos
    _DIAS_JANELA_PEDIDOS_PUBLICO dias (ver MusicaHistorico, origem="pedido_ouvinte") --
    persiste entre transmissoes, ao contrario do historico de sessao no Redis. Agrupa pela
    query normalizada (sem acento, minuscula) pra "Chitaozinho e Xororo" e "chitãozinho e
    xororó" contarem como o mesmo pedido.
    """
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=_DIAS_JANELA_PEDIDOS_PUBLICO)
    linhas = (
        db.query(MusicaHistorico.query_normalizada, func.count().label("contagem"))
        .filter(
            MusicaHistorico.programa_id == programa_id,
            MusicaHistorico.origem == "pedido_ouvinte",
            MusicaHistorico.criado_em >= limiar,
        )
        .group_by(MusicaHistorico.query_normalizada)
        .order_by(func.count().desc())
        .limit(_MAX_PEDIDOS_PUBLICO_NO_POOL)
        .all()
    )
    return list(linhas)


def _contexto_musical_programa(programa: Programa) -> str:
    """Resumo do programa no ar (nome, descricao, tom, topicos, criterios, horario) pra a escolha
    da faixa ter nexo com o programa, nao so' com o genero."""
    agora = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
    partes = [f"Programa: {programa.nome}"]
    if programa.descricao:
        partes.append(f"Descricao: {programa.descricao}")
    if programa.tom:
        partes.append(f"Tom: {programa.tom}")
    if programa.topicos_permitidos:
        partes.append("Assuntos: " + ", ".join(programa.topicos_permitidos[:8]))
    if programa.criterios_busca_musicas:
        partes.append(f"Criterios de musica: {programa.criterios_busca_musicas}")
    partes.append(f"Horario agora: {agora:%H:%M}")
    return "\n".join(partes)


def _faixas_recentes_programa(db: Session, programa_id: int, limite: int = 20) -> list[str]:
    """Titulo/canal das ultimas faixas tocadas no programa (persistente entre transmissoes), pra
    mandar de lista de 'nao repita' ao LLM."""
    linhas = (
        db.query(MusicaHistorico.titulo, MusicaHistorico.canal)
        .filter(MusicaHistorico.programa_id == programa_id)
        .order_by(MusicaHistorico.criado_em.desc())
        .limit(limite)
        .all()
    )
    return [f"{titulo} ({canal})" for titulo, canal in linhas]


def _escolher_query_musica(
    db: Session,
    programa: Programa,
    ids_tocadas: set[str] | None = None,
    titulos_tocados: set[str] | None = None,
    canais_tocados: dict[str, int] | None = None,
) -> tuple[str, str | None, MusicaEncontrada | None]:
    """Escolhe a query de busca pra um bloco de musica sem rotulo de genero proprio.

    Combina curadoria do admin (musicas_permitidas, pesada pela posicao -- primeiro item da
    lista conta mais) com o que o publico mais pediu de verdade pelo WhatsApp (ver
    _pedidos_publico_mais_frequentes), numa escolha ponderada. So cai pro genero generico da
    radio quando nenhum dos dois tem dado nenhum; e so cai pra busca generica cantada
    (QUERY_MUSICA_GENERICA) quando a radio nao configurou genero nenhum. Devolve (query, genero_pra_filtrar, musica_catalogada)
    -- genero so vem preenchido na queda pro genero generico, porque musica_permitida/pedido do
    publico ja e' uma query especifica o suficiente (nome de musica/artista), nao precisa de
    filtro extra. musica_catalogada vem preenchida quando a sugestao da LLM ja bate com uma
    Musica catalogada (ver app.live.song_service) com youtube_video_id resolvido -- caller usa
    ela direto em vez de repetir a busca no YouTube pra query que so' muda de texto.
    """
    def _via_catalogo(texto: str, origem: str) -> MusicaEncontrada | None:
        """Se `texto` vier no formato 'Artista - Titulo', tenta reaproveitar/registrar no
        catalogo persistente (ver app.live.song_service) -- vale tanto pra sugestao da LLM
        quanto pra entrada de musicas_permitidas ja escrita nesse formato pelo admin. Texto que
        nao bate o formato (nome solto, pedido de ouvinte em linguagem livre) devolve None sem
        custo extra, e o caller usa `texto` como query livre, igual antes.

        origem so' e' usada pra' gravar o campo confianca da Musica (ver
        resolver_musica_catalogada em app.live.song_service), nao influencia a busca."""
        parsed = dividir_artista_titulo(texto)
        if parsed is None:
            return None
        artista, titulo = parsed
        return resolver_musica_catalogada(
            db,
            titulo,
            artista,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            titulos_tocados=titulos_tocados,
            canais_recentes=canais_tocados,
            origem=origem,
        )

    def _ja_tocada(texto: str) -> bool:
        """True quando `texto` ('Artista - Titulo') ja tocou nesta sessao -- sem isso o sorteio
        ponderado abaixo insiste em reoferecer o item de maior peso (posicao 1 da lista do admin,
        ou pedido mais frequente) mesmo depois dele ja ter tocado; _via_catalogo/buscar_musica
        bloqueiam a repeticao em si, mas so' depois de gastar a tentativa e cair no fallback
        generico (QUERY_MUSICA_GENERICA). Texto fora do formato 'Artista - Titulo' nao da pra
        checar aqui, segue candidato (mesmo comportamento de antes)."""
        parsed = dividir_artista_titulo(texto)
        if parsed is None:
            return False
        _, titulo = parsed
        return titulo_ja_tocado(titulo, titulos_tocados or set())

    candidatos: list[str] = []
    pesos: list[float] = []
    origens: list[str] = []

    total_permitidas = len(programa.musicas_permitidas)
    for indice, item in enumerate(programa.musicas_permitidas):
        if _ja_tocada(item):
            continue
        candidatos.append(item)
        # peso so' levemente decrescente: antes (N-i)*3 fazia o 1o item da lista tocar N vezes
        # mais que o ultimo, e o programa girava sempre em torno das mesmas 2-3 faixas.
        pesos.append((1 + (total_permitidas - indice) / max(total_permitidas, 1)) * _PESO_POSICAO_ADMIN)
        origens.append("admin")

    for query_normalizada, contagem in _pedidos_publico_mais_frequentes(db, programa.id):
        if _ja_tocada(query_normalizada):
            continue
        candidatos.append(query_normalizada)
        pesos.append(contagem * _PESO_PEDIDO_PUBLICO)
        origens.append("pedido_publico")

    if candidatos:
        escolhido = random.choices(candidatos, weights=pesos, k=1)[0]
        origem = origens[candidatos.index(escolhido)]
        return escolhido, None, _via_catalogo(escolhido, origem)

    if programa.generos_musicais:
        genero = random.choice(programa.generos_musicais)
        # query generica "{genero} musica" quase so' acha playlist/coletanea no YouTube pra genero
        # (nao artista/faixa) -- precisa de uma faixa avulsa real primeiro, muito mais provavel de
        # achar video da musica em si em vez de compilacao. Sem genero_filtro aqui: sugestao ja e'
        # especifica o suficiente, igual musica_permitida.
        #
        # Spotify primeiro: lista de faixas oficiais do genero (cacheada, ver
        # buscar_faixas_por_categoria em app.live.spotify) e' mais confiavel que texto livre da
        # LLM, que as vezes "inventa" combinacao artista+musica que nao existe. So' cai pro LLM
        # quando a integracao esta' desativada (sem credenciais) ou o genero nao tem match la'.
        contexto = _contexto_musical_programa(programa)
        recentes = _faixas_recentes_programa(db, programa.id)
        faixas_spotify = buscar_faixas_por_categoria(genero, excluir_titulos=titulos_tocados)
        if faixas_spotify:
            # artista que ja tocou na sessao sai do pool (quando sobra pool): a lista cacheada
            # tem poucos artistas e o sorteio uniforme repetia sempre os mesmos.
            canais = [c.lower() for c in (canais_tocados or {})]
            variadas = [f for f in faixas_spotify if not any(f[0].lower() in c for c in canais)]
            pool = variadas if len(variadas) >= 3 else faixas_spotify
            pool = random.sample(pool, min(len(pool), 12))
            indice = escolher_faixa_do_programa(pool, contexto)
            artista, titulo = pool[indice] if indice is not None else random.choice(pool)
            sugestao = f"{artista} - {titulo}"
            return sugestao, None, _via_catalogo(sugestao, "spotify")

        sugestao = sugerir_musica_do_genero(genero, contexto=contexto, evitar=recentes)
        if sugestao:
            return sugestao, None, _via_catalogo(sugestao, "llm_texto_livre")
        return f"{genero} musica", genero, None

    return QUERY_MUSICA_GENERICA, None, None


# Ultimo recurso de busca quando nada especifico (curadoria/pedido/genero) achou faixa -- antes era
# "musica instrumental", o que botava no ar justamente faixa sem voz "so' pra soltar no ar". No
# ar so' toca musica cantada (ver exigir_cantada em app.live.music).
QUERY_MUSICA_GENERICA = "sucessos musica brasileira"


def _normalizar_query_musica(texto: str) -> str:
    return _sem_acento(texto.strip().lower())


def _registrar_historico_persistente(
    db: Session, programa_id: int, musica: MusicaEncontrada, query: str, origem: str
) -> None:
    db.add(
        MusicaHistorico(
            programa_id=programa_id,
            song_id=musica.musica_catalogada_id,
            video_id=musica.video_id,
            titulo=musica.titulo,
            canal=musica.canal,
            query=query,
            query_normalizada=_normalizar_query_musica(query),
            origem=origem,
        )
    )
    db.commit()


# Janela de historico de musica tocada considerada entre TODOS os programas de uma mesma radio
# (nao so' o programa atual -- ver _musicas_recentes_da_radio), pra radio com "Manha", "Tarde"
# etc como programas separados nao repetir a mesma faixa de um pro outro no mesmo dia. Curta de
# proposito (diferente da retencao inteira de MusicaHistorico): so' evita repeticao recente
# entre programas, nao bane a musica da radio pra sempre (catalogo pequeno de genero de nicho
# ficaria sem musica nenhuma pra tocar).
_HORAS_JANELA_MUSICAS_RADIO = 48


def _musicas_recentes_da_radio(db: Session, radio_config_id: int) -> tuple[set[str], set[str]]:
    """video_id e titulo normalizado (ver _titulo_normalizado) de toda musica tocada em
    QUALQUER programa desta radio nas ultimas _HORAS_JANELA_MUSICAS_RADIO horas -- mesclado com
    o historico de sessao do programa atual (ver _historico_musicas) antes de chamar
    buscar_musica, pra dois programas da mesma radio nao tocarem a mesma faixa (mesma versao ou
    nao) o dia inteiro."""
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_HORAS_JANELA_MUSICAS_RADIO)
    linhas = (
        db.query(MusicaHistorico.video_id, MusicaHistorico.titulo)
        .join(Programa, Programa.id == MusicaHistorico.programa_id)
        .filter(Programa.radio_config_id == radio_config_id, MusicaHistorico.criado_em >= limiar)
        .all()
    )
    video_ids = {video_id for video_id, _ in linhas}
    titulos = {_titulo_normalizado(titulo) for _, titulo in linhas}
    return video_ids, titulos


# Janela bem mais larga que a de musica (acima): assunto de comentario/noticia tem giro natural
# mais lento (nao ha' "catalogo" que esgote), entao vale segurar mais tempo pra transmissao de
# amanha ainda lembrar do que foi falado hoje em outro programa da mesma radio.
_DIAS_JANELA_TEMAS_RADIO = 7


def _temas_recentes_da_radio(db: Session, radio_config_id: int) -> list[str]:
    """Temas de comentario/noticia abordados em QUALQUER programa desta radio nos ultimos
    _DIAS_JANELA_TEMAS_RADIO dias, do mais recente pro mais antigo -- mesclado com o historico
    de sessao do programa atual (ver _historico_temas) na instrucao de "nao repita assunto" do
    prompt, pra um programa nao repetir o que outro programa da mesma radio ja comentou."""
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=_DIAS_JANELA_TEMAS_RADIO)
    linhas = (
        db.query(TemaHistorico.tema)
        .join(Programa, Programa.id == TemaHistorico.programa_id)
        .filter(Programa.radio_config_id == radio_config_id, TemaHistorico.criado_em >= limiar)
        .order_by(TemaHistorico.criado_em.desc())
        .limit(_MAX_TEMAS_RADIO_NO_PROMPT)
        .all()
    )
    return [tema for tema, in linhas]


def _registrar_tema_persistente(db: Session, programa_id: int, tema: str) -> None:
    db.add(TemaHistorico(programa_id=programa_id, tema=tema))
    db.commit()


def _registrar_tema_em_background(programa_id: int, texto: str) -> None:
    """Classificacao de tema so alimenta o historico (redis + TemaHistorico) -- nada no
    caminho de /proxima espera o resultado dela pra devolver a fala. Roda numa thread propria,
    com sua propria sessao de DB (a `db` da request e' fechada assim que a response sai)."""

    def _tarefa() -> None:
        try:
            tema = classificar_tema_fala(texto)
            if not tema:
                return
            _registrar_tema(programa_id, tema)
            db = SessionLocal()
            try:
                _registrar_tema_persistente(db, programa_id, tema)
            finally:
                db.close()
        except Exception:
            logger.warning("Falha ao registrar tema em background: programa_id=%s", programa_id, exc_info=True)

    threading.Thread(target=tarefa_independente(_tarefa), daemon=True).start()


# Contexto real de uma musica (tema/curiosidade, ver resumir_contexto_musica) nao muda depois
# de gerado -- cache bem mais longo que o de sessao, mesma logica do cache de duracao/metadados
# em app.live.music.
_TTL_CONTEXTO_MUSICA = 30 * 24 * 60 * 60


def _contexto_musica(musica: MusicaEncontrada) -> str:
    """Contexto real (tema da letra, curiosidade, ano) que o locutor pode citar ao anunciar a
    musica -- cacheado por video_id porque e' sempre a mesma resposta pra mesma faixa. So chama
    o LLM quando ha' metadado nenhum (descricao/tags/ano) pra resumir; sem isso, nem vale a
    chamada, o LLM so' devolveria 'insuficiente' mesmo.
    """
    if not (musica.descricao or musica.tags or musica.ano):
        return ""

    chave_cache = f"cache:contexto_musica:{musica.video_id}"
    em_cache = redis_client.get(chave_cache)
    if em_cache is not None:
        return em_cache

    contexto = resumir_contexto_musica(musica.titulo, musica.canal, musica.descricao, musica.tags, musica.ano)
    redis_client.set(chave_cache, contexto, ex=_TTL_CONTEXTO_MUSICA)
    return contexto


def _montar_bloco_musicas(
    db: Session,
    programa: Programa,
    primeira: MusicaEncontrada,
    quantidade: int,
    rotulo_bloco: str | None = None,
    citadas: list[MusicaEncontrada] | None = None,
) -> list[MusicaEncontrada]:
    # citadas (musicas que o locutor comentou na fala, ver _musicas_citadas_na_fala) entram
    # sempre, logo depois da anunciada -- mesmo passando da quantidade pedida pela tag
    # [BLOCO_MUSICAS:N]; so' o que faltar pra completar N e' sorteado.
    musicas = [primeira]
    usados = {primeira.video_id}
    for citada in citadas or []:
        if citada.video_id not in usados and not titulo_ja_tocado(
            citada.titulo, {_titulo_normalizado(m.titulo) for m in musicas}
        ):
            musicas.append(citada)
            usados.add(citada.video_id)
    tentativas = 0
    while len(musicas) < quantidade and tentativas < quantidade * 3:
        tentativas += 1
        extra = _buscar_musica_para_bloco(db, programa, rotulo_bloco)
        if extra is None:
            break
        if extra.video_id in usados or titulo_ja_tocado(extra.titulo, {_titulo_normalizado(m.titulo) for m in musicas}):
            continue
        musicas.append(extra)
        usados.add(extra.video_id)
    return musicas


# Linha do historico com as faixas que tocaram num bloco (ver linhaMusicasHistorico em
# useLiveEngine.ts) -- usada pra nao confundir comentario sobre o que acabou de tocar com musica
# nova que o locutor prometeu.
_MAX_MUSICAS_CITADAS = 3


def _musicas_citadas_na_fala(
    db: Session,
    programa: Programa,
    fala: str,
    historico: list[str],
    ja_no_bloco: list[MusicaEncontrada] | None = None,
) -> tuple[list[MusicaEncontrada], list[str], dict[str, str]]:
    """Musicas especificas que o locutor citou/comentou na fala e que ainda nao tocaram,
    resolvidas pra tocar logo depois dela. Sem isso o locutor comentava uma musica (ou prometia
    'daqui a pouco vem aquela do fulano'), mudava de assunto e ela nunca tocava -- a musica do
    bloco era escolhida antes da fala, sem saber o que ele ia dizer. Musica que ja tocou nesta
    sessao nao volta (e' comentario sobre o que acabou de tocar), e citada que nao existe no
    YouTube so' gera log -- nao trava o bloco. Devolve tambem as citadas que nao viraram faixa (o validador
    tira a mencao delas da fala, F3) e a consulta de cada faixa resolvida. So' resolve: quem chama registra como
    tocadas so' as que ficam no bloco (ver _registrar_citadas; antes do F3 a descartada pelo relogio ficava
    registrada sem tocar)."""
    ja_no_bloco = ja_no_bloco or []
    ignorar = [f"{m.titulo} - {m.canal}" for m in ja_no_bloco]
    for linha in historico[-6:]:
        ignorar += [t.strip() for achado in _MUSICAS_TOCADAS_HISTORICO_RE.findall(linha) for t in achado.split(",")]
    citadas = extrair_musicas_citadas(fala, ignorar)[:_MAX_MUSICAS_CITADAS]
    if not citadas:
        return [], [], {}

    ids_tocadas, titulos_tocados, canais_tocados = _historico_musicas(programa.id)
    ids_tocadas |= {m.video_id for m in ja_no_bloco}
    # titulos do bloco e do historico do painel tambem contam -- citada que e' a mesma musica
    # de uma delas (outra versao, outro "sotaque" de titulo) nao toca de novo em seguida.
    titulos_tocados |= {_titulo_normalizado(t.rsplit(" - ", 1)[0]) for t in ignorar}
    resolvidas: list[MusicaEncontrada] = []
    nao_resolvidas: list[str] = []
    consultas: dict[str, str] = {}
    for citada in citadas:
        encontrada = None
        parsed = dividir_artista_titulo(citada)
        titulo_citado = parsed[1] if parsed is not None else citada
        if titulo_ja_tocado(titulo_citado, titulos_tocados):
            logger.info("live_musica_citada_ja_tocada programa_id=%s citada=%r", programa.id, citada)
            continue
        if parsed is not None:
            artista, titulo = parsed
            encontrada = resolver_musica_catalogada(
                db,
                titulo,
                artista,
                bloqueados=programa.musicas_bloqueadas,
                evitar_video_ids=ids_tocadas,
                titulos_tocados=titulos_tocados,
                canais_recentes=canais_tocados,
                origem="citada_locutor",
            )
        if encontrada is None:
            encontrada = buscar_musica(
                citada.replace(" - ", " "),
                bloqueados=programa.musicas_bloqueadas,
                evitar_video_ids=ids_tocadas,
                titulos_tocados=titulos_tocados,
                canais_recentes=canais_tocados,
                exigir_cantada=True,
                exigir_canal_oficial=True,
            )
        if encontrada is not None and titulo_ja_tocado(encontrada.titulo, titulos_tocados):
            continue
        if encontrada is None or encontrada.video_id in ids_tocadas:
            logger.warning("live_musica_citada_sem_faixa programa_id=%s citada=%r", programa.id, citada)
            nao_resolvidas.append(citada)
            continue
        if _fora_do_genero(programa.id, encontrada, programa.generos_musicais or []):
            nao_resolvidas.append(citada)
            continue
        resolvidas.append(encontrada)
        consultas[encontrada.video_id] = citada
        ids_tocadas.add(encontrada.video_id)
        titulos_tocados.add(_titulo_normalizado(encontrada.titulo))
    return resolvidas, nao_resolvidas, consultas


def _registrar_citadas(db: Session, programa_id: int, musicas: list[MusicaEncontrada], consultas: dict[str, str]) -> None:
    """Registra como tocadas (sessao no Redis e MusicaHistorico) as citadas que ficaram no bloco."""
    for musica in musicas:
        if musica.video_id in consultas:
            _registrar_musica_tocada(programa_id, musica)
            _registrar_historico_persistente(db, programa_id, musica, consultas[musica.video_id],
                                             origem="citada_locutor")


def _pedidos_em_fila(db: Session, radialista: RadioConfig, programa: Programa) -> list[FilaAoVivo]:
    """Pedidos ainda na fila (sem consumir): fluxo novo deste programa e legado da rádio. O validador usa os
    títulos pedidos como títulos conhecidos e os nomes como ouvintes reais (nunca como confirmação)."""
    return (
        db.query(FilaAoVivo)
        .filter(
            FilaAoVivo.radio_config_id == radialista.id,
            ((FilaAoVivo.programa_id == programa.id) & (FilaAoVivo.estado == "em_fila"))
            | (FilaAoVivo.programa_id.is_(None) & FilaAoVivo.atendido.is_(False)
               & FilaAoVivo.estado.in_(_ESTADOS_LEGADO_ABERTOS)),
        )
        .order_by(FilaAoVivo.criado_em.asc())
        .limit(_MAX_PEDIDOS_FILA_VALIDACAO)
        .all()
    )


_MAX_PEDIDOS_FILA_VALIDACAO = 30


def _fora_do_genero(programa_id: int, musica: MusicaEncontrada, generos: list[str]) -> bool:
    """True quando o canal/artista da faixa encontrada e' claramente de outro genero que os do
    programa (ver itens_fora_do_genero em app.llm.client) -- busca automatica (Spotify, sugestao da
    LLM, query generica, citacao do locutor) as vezes acha cantor de outro estilo, e o filtro por
    palavra-chave de genero em buscar_musica relaxa como ultimo recurso. Sem generos pra conferir
    (programa sem genero configurado, curadoria do admin) nao checa nada."""
    if not generos:
        return False
    item = f"{musica.titulo} (canal: {musica.canal})" if musica.canal else musica.titulo
    if not itens_fora_do_genero([item], generos):
        return False
    logger.info(
        "live_musica_fora_do_genero programa_id=%s generos=%r titulo=%r canal=%r",
        programa_id, generos, musica.titulo, musica.canal,
    )
    return True


def _buscar_musica_para_bloco(
    db: Session, programa: Programa, rotulo_bloco: str | None = None, *, plano_relogio: Plano | None = None
) -> MusicaEncontrada | None:
    """Escolhe e registra a faixa do bloco. Com `plano_relogio` (programa com relogio da hora, F1),
    a faixa precisa caber no teto do plano: ate' CONFIG_RELOGIO.musica_tentativas_teto buscas, sem
    repetir a rejeitada; a que nao deixa sobra impossivel antes do hard time tem preferencia, senao
    a mais longa que cabe. Nada cabe = None, sem registrar nada (o caller usa a alternativa do plano).
    Sem plano, o comportamento de sempre (o kwarg so' e' passado com relogio)."""
    if plano_relogio is None:
        musica, query = _selecionar_musica_para_bloco(db, programa, rotulo_bloco)
    else:
        musica, query = _selecionar_musica_que_cabe(db, programa, rotulo_bloco, plano_relogio)
    if musica is not None:
        _registrar_musica_tocada(programa.id, musica)
        _registrar_historico_persistente(db, programa.id, musica, query, origem="auto")
    return musica


def _selecionar_musica_que_cabe(
    db: Session, programa: Programa, rotulo_bloco: str | None, plano: Plano
) -> tuple[MusicaEncontrada | None, str]:
    rejeitadas: set[str] = set()
    titulos_rejeitados: set[str] = set()
    melhor: tuple[MusicaEncontrada, str] | None = None
    for _ in range(CONFIG_RELOGIO.musica_tentativas_teto):
        musica, query = _selecionar_musica_para_bloco(
            db, programa, rotulo_bloco, evitar_ids=rejeitadas, evitar_titulos=titulos_rejeitados,
            duracao_max_s=duracao_preferida_musica_s(plano, CONFIG_RELOGIO),
        )
        if musica is None:
            break
        duracao = duracao_musica_s(musica, CONFIG_RELOGIO)
        if musica_cabe(duracao, plano, CONFIG_RELOGIO):
            return musica, query
        if musica_cabe(duracao, plano, CONFIG_RELOGIO, estrito=False) and (
            melhor is None or duracao > duracao_musica_s(melhor[0], CONFIG_RELOGIO)
        ):
            melhor = (musica, query)
        rejeitadas.add(musica.video_id)
        titulos_rejeitados.add(_titulo_normalizado(musica.titulo))
    if melhor is not None:
        return melhor
    logger.info("relogio_musica_sem_faixa_que_caiba programa_id=%s teto_s=%s rejeitadas=%s",
                programa.id, plano.duracao_max_musica_s, len(rejeitadas))
    return None, ""


def _selecionar_musica_para_bloco(
    db: Session,
    programa: Programa,
    rotulo_bloco: str | None = None,
    evitar_ids: set[str] | None = None,
    evitar_titulos: set[str] | None = None,
    duracao_max_s: int | None = None,
) -> tuple[MusicaEncontrada | None, str]:
    """Busca a faixa do bloco sem registrar (ver _buscar_musica_para_bloco). evitar_ids/
    evitar_titulos e duracao_max_s so' vem preenchidos pela escolha com teto do relogio."""
    genero_bloco = _genero_do_rotulo(rotulo_bloco) if rotulo_bloco else ""
    # Preferencia de duracao repassada a buscar_musica so' com teto do relogio (nao e' bloqueio).
    preferencia = {} if duracao_max_s is None else {"duracao_max_segundos": min(duracao_max_s, _DURACAO_MAX_SEGUNDOS)}

    ids_tocadas, titulos_tocados, canais_tocados = _historico_musicas(programa.id)
    ids_radio, titulos_radio = _musicas_recentes_da_radio(db, programa.radio_config_id)
    ids_tocadas |= ids_radio | set(evitar_ids or ())
    titulos_tocados |= titulos_radio | set(evitar_titulos or ())

    if genero_bloco and _sem_acento(genero_bloco.lower()) != "musica":
        # rotulo do bloco customizado carrega o proprio genero/estilo (ex.: "Vaneira", "Xote")
        # -- tem prioridade sobre a curadoria generica da radio (e' o sinal mais especifico pra
        # este bloco), e o proprio genero vira filtro de busca (ver genero= em buscar_musica)
        # pra nao deixar o YouTube derivar pra um genero vizinho (xote virando chamame).
        query, genero_filtro, musica = f"{genero_bloco} musica", genero_bloco, None
        generos_alvo = [genero_bloco]
        generos_escolha = generos_alvo
    else:
        query, genero_filtro, musica = _escolher_query_musica(db, programa, ids_tocadas, titulos_tocados, canais_tocados)
        generos_alvo = programa.generos_musicais or []
        # curadoria do admin e' escolha deliberada (pode ser fora do genero de proposito) -- so'
        # escolha automatica (Spotify, LLM, pedidos do publico, genero) passa pela checagem.
        generos_escolha = [] if query in (programa.musicas_permitidas or []) else generos_alvo

    if musica is None:
        # musica so' vem preenchida aqui quando _escolher_query_musica ja resolveu via catalogo
        # (ver app.live.song_service) -- do contrario, busca no YouTube como sempre.
        musica = buscar_musica(
            query,
            genero=genero_filtro,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            titulos_tocados=titulos_tocados,
            canais_recentes=canais_tocados,
            exigir_cantada=True,
            # genero_filtro so' vem preenchido na busca generica por genero (sem faixa
            # especifica, ver _escolher_query_musica/genero_bloco acima) -- so' exige canal
            # oficial quando a query e' uma musica especifica (curadoria do admin/pedido do
            # publico), nao trava o bloco genero-so' sem musica.
            exigir_canal_oficial=genero_filtro is None,
            **preferencia,
        )
    if musica is not None and _fora_do_genero(programa.id, musica, generos_escolha):
        musica = None
    if musica is None and query.strip().lower() != QUERY_MUSICA_GENERICA:
        # query especifica (curadoria do admin, pedido do publico ou genero/rotulo do bloco) nao
        # achou nada -- sem isso, o locutor recebia instrucao pra anunciar um genero/artista
        # "permitido" mesmo com `musica` None, e a fala saia prometendo uma faixa que nunca
        # tocava (ver ramo `else` do anuncio de musica em gerar_proxima_fala). Tenta mais uma
        # vez com a query mais generica possivel antes de desistir de vez.
        query_fallback = QUERY_MUSICA_GENERICA
        musica = buscar_musica(
            query_fallback,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            titulos_tocados=titulos_tocados,
            canais_recentes=canais_tocados,
            exigir_cantada=True,
            **preferencia,
        )
        if musica is not None and _fora_do_genero(programa.id, musica, generos_alvo):
            musica = None
        if musica is not None:
            query = query_fallback
    if musica is None:
        # Nada achou nada, nem a query especifica nem o retry generico -- ultimo recurso antes
        # de desistir do bloco de verdade (ver _fallback_curado_genero): tenta faixas da lista
        # Spotify cacheada por genero, curadoria pronta muito mais provavel de existir no
        # YouTube do que a busca generica sem genero nenhum.
        fallback = _fallback_curado_genero(db, programa, ids_tocadas, titulos_tocados, canais_tocados)
        if fallback is not None:
            musica, query = fallback
    return musica, query


# Tentativas de resolucao YouTube (via resolver_musica_catalogada, cada uma podendo custar
# alguns segundos de rede) que o fallback curado gasta antes de desistir -- teto pra' nao
# empacar o bloco de musica numa sequencia longa de tentativas sincronas quando o genero
# configurado tem YouTube ruim pra' quase tudo.
_MAX_TENTATIVAS_FALLBACK_CURADO = 6


def _fallback_curado_genero(
    db: Session,
    programa: Programa,
    ids_tocadas: set[str],
    titulos_tocados: set[str],
    canais_tocados: dict[str, int],
) -> tuple[MusicaEncontrada, str] | None:
    """Ultimo recurso antes do bloco de musica ficar vazio (ver _buscar_musica_para_bloco):
    tenta, uma a uma, faixas da lista Spotify cacheada por genero configurado na radio (ver
    buscar_faixas_por_categoria em app.live.spotify) -- mesma fonte usada na escolha normal
    (ver _escolher_query_musica), so' que aqui percorre VARIAS faixas da lista em vez de uma
    unica escolhida ao acaso, porque o ponto de ter uma lista curada e' justamente servir de
    pool de alternativas quando a 1a tentativa falha no YouTube. So' roda quando o resto do
    pipeline (query especifica + retry generico) ja' desistiu; radio sem genero configurado
    (programa.generos_musicais vazio) nao tem lista nenhuma pra' tentar, devolve None direto.
    """
    candidatos: list[tuple[str, str]] = []
    for genero in programa.generos_musicais or []:
        candidatos.extend(buscar_faixas_por_categoria(genero, excluir_titulos=titulos_tocados))
    random.shuffle(candidatos)

    for artista, titulo in candidatos[:_MAX_TENTATIVAS_FALLBACK_CURADO]:
        musica = resolver_musica_catalogada(
            db,
            titulo,
            artista,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            titulos_tocados=titulos_tocados,
            canais_recentes=canais_tocados,
            origem="spotify",
        )
        if musica is not None and not _fora_do_genero(programa.id, musica, programa.generos_musicais or []):
            return musica, f"{artista} - {titulo}"
    return None


# Janela pra considerar um pedido anterior do mesmo ouvinte como "recorrente nesta transmissao" --
# mesma ordem de grandeza da sessao ao vivo (ver _TTL_SESSAO_AO_VIVO), pra nao citar um pedido de
# dias atras como se fosse "há pouco".
_JANELA_OUVINTE_RECORRENTE_HORAS = 6


def _ouvinte_recorrente_anterior(db: Session, radio_config_id: int, pedido_atual: FilaAoVivo) -> FilaAoVivo | None:
    """Pedido anterior (ja atendido), do mesmo ouvinte (mesmo nome) do pedido que acabou de sair
    da fila, dentro da janela de sessao -- da pro locutor citar que "aquele mesmo fulano que pediu
    tal coisa ha pouco mandou outra mensagem agora", sensacao de programa vivo com gente de
    verdade interagindo. None quando o pedido atual nao tem nome preenchido ou nao ha pedido
    anterior comparavel."""
    if not pedido_atual.nome:
        return None
    limite = pedido_atual.criado_em - datetime.timedelta(hours=_JANELA_OUVINTE_RECORRENTE_HORAS)
    return (
        db.query(FilaAoVivo)
        .filter(
            FilaAoVivo.radio_config_id == radio_config_id,
            FilaAoVivo.atendido.is_(True),
            FilaAoVivo.id != pedido_atual.id,
            FilaAoVivo.telefone == pedido_atual.telefone,
            FilaAoVivo.criado_em >= limite,
            FilaAoVivo.criado_em < pedido_atual.criado_em,
        )
        .order_by(FilaAoVivo.criado_em.desc())
        .first()
    )


def _ouvinte_recorrente_dias_anteriores(db: Session, radio_config_id: int, pedido_atual: FilaAoVivo) -> FilaAoVivo | None:
    """Extensao de _ouvinte_recorrente_anterior pra fora da janela de sessao (_JANELA_OUVINTE_
    RECORRENTE_HORAS): mesmo telefone aparecendo numa transmissao de outro dia, ate
    _DIAS_JANELA_OUVINTE_RECORRENTE dias atras (ver Frente J do plano de profundidade). Casa por
    telefone, nao por nome -- numa janela tao larga o nome pode ter mudado/faltado, telefone e'
    o identificador estavel. None quando nao ha pedido atendido anterior fora da janela recente."""
    limite_recente = pedido_atual.criado_em - datetime.timedelta(hours=_JANELA_OUVINTE_RECORRENTE_HORAS)
    limite_antigo = pedido_atual.criado_em - datetime.timedelta(days=_DIAS_JANELA_OUVINTE_RECORRENTE)
    return (
        db.query(FilaAoVivo)
        .filter(
            FilaAoVivo.radio_config_id == radio_config_id,
            FilaAoVivo.atendido.is_(True),
            FilaAoVivo.id != pedido_atual.id,
            FilaAoVivo.telefone == pedido_atual.telefone,
            FilaAoVivo.criado_em < limite_recente,
            FilaAoVivo.criado_em >= limite_antigo,
        )
        .order_by(FilaAoVivo.criado_em.desc())
        .first()
    )


def _proximo_pedido_fila(db: Session, radialista: RadioConfig, tipo: str) -> FilaAoVivo | None:
    """Seleciona (com token, sem marcar atendido) o pedido legado mais antigo da fila vindo do WhatsApp."""
    return _proximo_pedido_fila_dentre(db, radialista, (tipo,))


def _proximo_pedido_fila_dentre(db: Session, radialista: RadioConfig, tipos: tuple[str, ...]) -> FilaAoVivo | None:
    """Como _proximo_pedido_fila, mas escolhe o mais antigo nao atendido dentre varios tipos --
    usado pelo bloco chamada_ouvinte, que atende tanto "abraco" quanto "sorteio" na mesma fala
    (ver Frente S): FIFO entre os tipos, so' consome o pedido escolhido, os outros tipos ficam
    intactos na fila pros proximos blocos."""
    pedido = (
        db.query(FilaAoVivo)
        .filter(
            FilaAoVivo.radio_config_id == radialista.id,
            FilaAoVivo.tipo.in_(tipos),
            FilaAoVivo.programa_id.is_(None),
            FilaAoVivo.atendido.is_(False),
            FilaAoVivo.estado.in_(_ESTADOS_LEGADO_ABERTOS),
        )
        .order_by(FilaAoVivo.criado_em.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if pedido is not None:
        # F4 (D1): selecionado com token, como no fluxo novo; "atendido" só quando o player confirma a reprodução
        # (POST /ouvintes/pedidos/{id}/reproducao). Sem moderação: o legado continua sem revisão da equipe.
        from app.whatsapp.atendimento import registrar_evento

        pedido.estado = "selecionado"
        pedido.selecao_token = uuid.uuid4().hex
        pedido.selecionado_em = datetime.datetime.now(datetime.timezone.utc)
        registrar_evento(pedido, "selecionar_legado")
        db.commit()
    return pedido


def _reprovar_pedido(db: Session, pedido: FilaAoVivo, motivo: str) -> None:
    """Pedido de música que não vai tocar (F4, D2): fica "nao_atendido" à vista da equipe, antes da geração, e o
    nome do ouvinte não vai ao ar (pesquisa §10: não anunciar; manter o status na fila)."""
    from app.whatsapp.atendimento import registrar_evento

    pedido.estado, pedido.motivo, pedido.selecao_token = "nao_atendido", motivo, None
    registrar_evento(pedido, "musica_indisponivel")
    db.commit()
    logger.info("live_pedido_musica_indisponivel pedido_id=%s", pedido.id)


# Estados de um pedido legado ainda na fila: "em_fila" (padrão do webhook) e "aguardando_revisao" (linhas de antes
# da coluna estado, migradas por app.main.garantir_colunas_fila_ao_vivo).
_ESTADOS_LEGADO_ABERTOS = ("em_fila", "aguardando_revisao")


def _pedido_recente_nao_atendido(db: Session, radialista: RadioConfig, tipo: str) -> FilaAoVivo | None:
    """Espia (sem consumir) o pedido nao atendido mais recente, pra saber se algo "acabou de
    chegar" no WhatsApp enquanto o locutor esta gerando outro tipo de bloco -- ao contrario de
    _proximo_pedido_fila, nao marca atendido nem tira da fila (ver Frente I, reacao a evento
    real: essa e' so a checagem, quem consome de verdade continua sendo _proximo_pedido_fila nos
    blocos dedicados). Janela filtrada em SQL (nao em Python) de proposito: SQLite (usado nos
    testes) devolve criado_em sem tzinfo na leitura, e subtrair isso de um datetime aware em
    Python quebra -- mesmo padrao ja usado pelas outras janelas de tempo deste arquivo
    (_temas_recentes_da_radio, _pedidos_publico_mais_frequentes etc)."""
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=_JANELA_PEDIDO_RECENTE_SEGUNDOS)
    return (
        db.query(FilaAoVivo)
        .filter(
            FilaAoVivo.radio_config_id == radialista.id,
            FilaAoVivo.tipo == tipo,
            FilaAoVivo.atendido.is_(False),
            FilaAoVivo.criado_em >= limiar,
            # F4 (D7): só o legado aberto. Pedido do fluxo novo (com programa) passa pela revisão da equipe e
            # não pode chegar ao ar pela espiada; cancelado ou não atendido também não.
            FilaAoVivo.programa_id.is_(None),
            FilaAoVivo.estado.in_(_ESTADOS_LEGADO_ABERTOS),
        )
        .order_by(FilaAoVivo.criado_em.desc())
        .first()
    )


# Janela da "transmissão" para os nomes de ouvintes que a fala pode citar (F4, app.live.participacao): a mesma
# da sessão ao vivo.
_JANELA_NOMES_TRANSMISSAO_HORAS = _JANELA_OUVINTE_RECORRENTE_HORAS
_ESTADOS_JA_ATENDIDOS = ("executado", "selecionado", "historico_legado")


def _promessas_abertas(db: Session, programa: Programa, ocorrencia: str) -> list[PromessaRef]:
    """Promessas abertas desta ocorrência (F4). Só banco: com o Redis fora continuam valendo. As que sobraram de
    outra ocorrência (transmissão que acabou sem encerramento) vencem aqui."""
    promessas_repo.vencer(db, programa.id, exceto_ocorrencia=ocorrencia)
    return [promessas_repo.para_ref(linha) for linha in promessas_repo.abertas(db, programa.id, ocorrencia)]


def _nomes_da_transmissao(db: Session, radialista: RadioConfig, programa: Programa) -> tuple[list[str], list[str]]:
    """(já atendidos, todos) os ouvintes com pedido nesta transmissão (janela da sessão), em qualquer estado.
    Citar quem está na fila ou não foi atendido é violação; lembrar quem já foi atendido, não (D8)."""
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_JANELA_NOMES_TRANSMISSAO_HORAS)
    linhas = (
        db.query(FilaAoVivo.nome, FilaAoVivo.estado, FilaAoVivo.atendido)
        .filter(FilaAoVivo.radio_config_id == radialista.id, FilaAoVivo.criado_em >= limiar)
        .order_by(FilaAoVivo.criado_em.asc())
        .limit(_MAX_PEDIDOS_FILA_VALIDACAO)
        .all()
    )
    # Pelo estado, não por `atendido`: o legado reprovado (Música indisponível) foi consumido, mas não atendido.
    ja_atendidos = [nome for nome, estado, _ in linhas if nome and estado in _ESTADOS_JA_ATENDIDOS]
    return ja_atendidos, [nome for nome, _, _ in linhas if nome]


# Teto de threads simultaneas pra sintese multi-voz embutida -- dialogo tem no maximo 4 linhas
# (ver instrucao "entre 2 e 4 linhas" em montar_system_prompt), entao isso so' limita o caso raro
# de o LLM devolver mais que isso.
_MAX_WORKERS_TTS_MULTIVOZ = 4


def _preparar_parametros_multivoz(db: Session, account_id: int, falas_bloco: list[FalaItem]) -> dict[str, dict]:
    """Resolve parametros_sintese (toca o banco, ver app.tts.profiles) uma vez por voz distinta
    do dialogo, ANTES de paralelizar -- Session do SQLAlchemy nao e' thread-safe pra uso
    concorrente, entao nenhum acesso a `db` pode acontecer dentro das threads de
    _sintetizar_falas_multivoz abaixo."""
    parametros_por_voz: dict[str, dict] = {}
    for linha in falas_bloco:
        chave = linha.voz_id or ""
        if chave not in parametros_por_voz:
            parametros_por_voz[chave] = parametros_sintese(db, account_id, linha.voz_id)
    return parametros_por_voz


def _sintetizar_falas_multivoz(
    falas_bloco: list[FalaItem],
    parametros_por_voz: dict[str, dict],
    tipo: str,
    tom: str,
    ultima_fala_anterior: str | None,
    perfil_pos_producao: str | None,
    request_id: str,
    programa_id: int,
) -> tuple[list[str | None], list[float | None]]:
    """Sintetiza em paralelo o audio de cada linha de um dialogo multi-voz, embutido aqui em
    /proxima (mesmo espirito do Plano B.3 pro locutor unico) -- sem isso o frontend abre uma
    chamada /tts por linha (ver prepararAudio em useLiveEngine.ts). So a chamada de rede pra
    ElevenLabs roda em thread; parametros de voz ja foram resolvidos fora da paralelizacao (ver
    _preparar_parametros_multivoz). Item None no resultado = aquela linha falhou -- o frontend
    pula só essa linha, sem repetir automaticamente uma chamada possivelmente cobrada. Devolve tambem a
    duracao medida de cada linha (F2; None quando o audio falhou ou nao decodifica) -- medida aqui, sem
    tocar o banco (a amostra de ritmo e' gravada pelo chamador depois das threads)."""
    resultados: list[str | None] = [None] * len(falas_bloco)
    duracoes: list[float | None] = [None] * len(falas_bloco)

    def _uma_linha(indice: int) -> None:
        linha = falas_bloco[indice]
        texto_anterior = falas_bloco[indice - 1].texto if indice > 0 else ultima_fala_anterior
        parametros_voz = parametros_por_voz.get(linha.voz_id or "", {"eh_clonada": False})
        try:
            audio_bytes = sintetizar_audio(
                linha.texto,
                linha.voz_id,
                tipo_bloco=tipo,
                tom=tom,
                **parametros_voz,
                texto_anterior=texto_anterior,
                timeout_segundos=_TTS_TIMEOUT_EMBUTIDO_SEGUNDOS,
                max_tentativas=1,
            )
            if perfil_pos_producao:
                audio_bytes = processar_audio(audio_bytes, perfil_pos_producao)
            resultados[indice] = base64.b64encode(audio_bytes).decode("ascii")
            duracoes[indice] = duracao_mp3_s(audio_bytes)
        except Exception:
            logger.warning(
                "live_audio_multivoz_falhou request_id=%s programa_id=%s indice=%s",
                request_id, programa_id, indice, exc_info=True,
            )

    with ThreadPoolExecutor(max_workers=min(len(falas_bloco), _MAX_WORKERS_TTS_MULTIVOZ)) as executor:
        tarefas = [executor.submit(tarefa_com_contexto(_uma_linha, i)) for i in range(len(falas_bloco))]
        for tarefa in tarefas:
            tarefa.result()

    return resultados, duracoes


# --- Relogio da hora (F1, ver app.live.relogio) ---------------------------------------------------
# So' entra em programa com programa.relogio_hora preenchido; sem ele nada abaixo e' chamado.


def _pecas_do_relogio(db: Session, account: Account, programa: Programa, wpm: float | None = None) -> PecasDisponiveis:
    """Vinhetas de papel abertura/passagem, patrocinadores citados na estrutura (na ordem), quadros
    e a vinheta de encerramento, com a duracao conhecida ou estimada por palavras (ritmo da voz)."""
    wpm = wpm or CONFIG_RELOGIO.wpm

    def _duracao(tem_audio: bool, duracao: int | None, texto: str | None) -> float:
        return float(duracao) if tem_audio and duracao else estimar_duracao_s(texto or "", wpm)

    vinhetas: dict[str, list[Peca]] = {"abertura": [], "passagem": []}
    for item in (
        db.query(BibliotecaAudioItem)
        .filter(BibliotecaAudioItem.account_id == account.id, BibliotecaAudioItem.programa_id == programa.id,
                BibliotecaAudioItem.ativo.is_(True), BibliotecaAudioItem.papel.in_(tuple(vinhetas)))
        .order_by(BibliotecaAudioItem.id.asc())
        .all()
    ):
        if item.audio_path or (item.texto or "").strip():
            vinhetas[item.papel].append(Peca(item.id, _duracao(bool(item.audio_path), item.duracao_segundos, item.texto)))

    ids: list[int] = []
    for bloco in programa.estrutura_blocos or []:
        achado = _PATROCINADOR_RE.match(bloco.strip())
        if achado and int(achado.group(1)) not in ids:
            ids.append(int(achado.group(1)))
    ativos = {
        p.id: p for p in db.query(Patrocinador).filter(
            Patrocinador.id.in_(ids), Patrocinador.account_id == account.id, Patrocinador.ativo.is_(True)
        ).all()
    } if ids else {}
    patrocinadores = tuple(
        Peca(pid, _duracao(ativos[pid].tipo_conteudo == "audio", ativos[pid].duracao_segundos, ativos[pid].texto))
        for pid in ids if pid in ativos
    )
    quadros = tuple(t for t in programa.estrutura_blocos or [] if (programa.quadros_fixos or {}).get(t))
    vinheta_fim = vinheta_encerramento(db, account.id, programa.id)
    return PecasDisponiveis(
        vinhetas_abertura=tuple(vinhetas["abertura"]), vinhetas_passagem=tuple(vinhetas["passagem"]),
        patrocinadores=patrocinadores, quadros=quadros,
        vinheta_encerramento_s=_duracao(bool(vinheta_fim.audio_path), vinheta_fim.duracao_segundos, vinheta_fim.texto)
        if vinheta_fim else 0.0,
        tem_fonte_noticia=getattr(programa, "dose_noticia", "jornalistica") != "nenhuma"
        and bool(programa.pode_pesquisar or programa.tipos_noticias or programa.fontes_noticias),
    )


def _transmissao_recomecou(dados: LiveProgramRequest) -> bool:
    return not dados.total_falas and not dados.historico


def _instante_do_bloco(programa: Programa, radialista: RadioConfig, dados: LiveProgramRequest,
                       agora: datetime.datetime, cfg: ConfigRelogio) -> tuple[datetime.datetime, bool, str]:
    """(instante, aceito, origem). Com `inicio_previsto`, o do painel (ou agora, se inválido). Sem o campo (painel
    antigo, F3), a estimativa pela cadeia de blocos gerados nesta ocorrência; sem ocorrência, agora."""
    if dados.inicio_previsto is not None:
        instante, aceito = instante_previsto(ler_inicio_previsto(dados.inicio_previsto), agora, cfg)
        return instante, aceito, "painel" if aceito else "agora"
    ocorrencia = ocorrencia_em(programa, radialista.timezone, agora, cfg) or ocorrencia_em(
        programa, radialista.timezone, agora + datetime.timedelta(seconds=cfg.preparo_sem_painel_max_s), cfg)
    if ocorrencia is None:
        return agora, False, "agora"
    elos = [] if _transmissao_recomecou(dados) else ler_cadeia(programa.id, ocorrencia)
    instante = instante_sem_painel(elos, agora, ocorrencia.inicio, cfg)
    logger.info("relogio_inicio_previsto_estimado programa_id=%s instante=%s elos=%s", programa.id,
                instante.isoformat(timespec="seconds"), len(elos))
    return instante, False, "estimado"


def _planejar_relogio(
    db: Session, account: Account, radialista: RadioConfig, programa: Programa, dados: LiveProgramRequest, *,
    formato: Formato, ultima_categoria: str | None, ja_encerrou: bool, cfg: ConfigRelogio = CONFIG_RELOGIO,
) -> tuple[Plano | None, bool, str | None, str]:
    """(plano, inicio_previsto_aceito, preset, origem do instante). Plano None = caminho de sempre
    (estrutura_blocos). `cfg` traz o ritmo calibrado da voz (F2) para as estimativas do backtiming."""
    relogio = relogio_do_programa(programa)
    if relogio is None:
        return None, False, None, "agora"
    agora = datetime.datetime.now(datetime.timezone.utc)
    instante, aceito, origem = _instante_do_bloco(programa, radialista, dados, agora, cfg)
    ocorrencia = ocorrencia_em(programa, radialista.timezone, instante, cfg)
    if ocorrencia is not None and _transmissao_recomecou(dados):
        zerar_cadeia(programa.id, ocorrencia)  # nova transmissão (painel, painel antigo ou prewarm)
    if ocorrencia is None or ja_encerrou:
        return None, aceito, relogio.preset, origem
    plano = planejar(
        programa, relogio, radialista.timezone, instante, formato=formato,
        ultima_categoria=ultima_categoria, ja_encerrou=ja_encerrou,
        executadas=etapas_executadas(programa.id, ocorrencia), pecas=_pecas_do_relogio(db, account, programa, cfg.wpm),
        cfg=cfg, obrigacoes=promessas_repo.obrigacoes(db, programa.id, ocorrencia.chave),  # F4: promessas abertas
    )
    if plano is not None:
        logger.info(
            "relogio_plano programa_id=%s etapa=%s acao=%s tipo=%s espaco_s=%s ate_hard_time_s=%s",
            programa.id, plano.etapa.chave, plano.acao, plano.tipo_bloco, plano.espaco_s, plano.segundos_ate_hard_time,
        )
    return plano, aceito, relogio.preset, origem


def _ha_pedido_musica_pendente(db: Session, radialista: RadioConfig, programa: Programa, novo_atendimento: bool) -> bool:
    """Espia (sem consumir) se a selecao de pedido de musica acharia algo -- mesmos filtros de
    app.whatsapp.atendimento.selecionar (fluxo novo) e de _proximo_pedido_fila (legado)."""
    consulta = db.query(FilaAoVivo.id).filter(FilaAoVivo.radio_config_id == radialista.id, FilaAoVivo.tipo == "musica")
    if novo_atendimento:
        from app.guardrails.schedule import programa_no_ar
        from app.whatsapp.atendimento import ocorrencia as ocorrencia_atendimento

        if not programa_no_ar(programa, radialista.timezone):
            return False
        consulta = consulta.filter(
            FilaAoVivo.programa_id == programa.id, FilaAoVivo.estado == "em_fila", FilaAoVivo.texto_autorizado != "",
            FilaAoVivo.transmissao == ocorrencia_atendimento(programa, radialista.timezone),
        )
    else:
        consulta = consulta.filter(FilaAoVivo.programa_id.is_(None), FilaAoVivo.atendido.is_(False),
                                   FilaAoVivo.estado.in_(_ESTADOS_LEGADO_ABERTOS))
    return consulta.first() is not None


def _resolver_musica_do_relogio(
    db: Session, radialista: RadioConfig, programa: Programa, plano: Plano, novo_atendimento: bool
) -> tuple[Plano, MusicaEncontrada | None, bool]:
    """Busca a faixa da etapa de musica antes de decidir o bloco: se nenhuma couber, o bloco passa a
    ser a alternativa do plano (reserva, link de preenchimento, etapa seguinte ou adiantamento).
    Devolve (plano, musica, buscou). Com pedido de musica pendente a busca fica pro caminho normal."""
    buscou = False
    for _ in range(3):
        if plano.acao != "musica":
            break
        if plano.aceita_pedido_musica and _ha_pedido_musica_pendente(db, radialista, programa, novo_atendimento):
            return plano, None, False
        buscou = True
        musica = _buscar_musica_para_bloco(db, programa, plano.tipo_bloco, plano_relogio=plano)
        if musica is not None:
            return plano, musica, True
        if plano.alternativa is None:
            break
        logger.info("relogio_sem_musica_que_caiba programa_id=%s etapa=%s alternativa=%s/%s", programa.id,
                    plano.etapa.chave, plano.alternativa.acao, plano.alternativa.tipo_bloco)
        plano = plano.alternativa
    return plano, None, buscou and plano.acao == "musica"


def _citadas_que_cabem(plano: Plano, fala: str, musicas: list[MusicaEncontrada], programa_id: int,
                       wpm: float | None = None) -> list[MusicaEncontrada]:
    """Musicas citadas na fala so' entram no bloco se couberem antes do proximo hard time."""
    if plano.espaco_s is None:
        return musicas
    restante = plano.espaco_s - estimar_duracao_s(fala, wpm or CONFIG_RELOGIO.wpm) + CONFIG_RELOGIO.tolerancia_hard_time_s
    cabem = []
    for musica in musicas:
        duracao = duracao_musica_s(musica, CONFIG_RELOGIO)
        if duracao <= restante:
            cabem.append(musica)
            restante -= duracao
    if len(cabem) < len(musicas):
        logger.warning("relogio_musica_citada_sem_espaco programa_id=%s descartadas=%s", programa_id,
                       [m.titulo for m in musicas if m not in cabem])
    return cabem


def _com_relogio(
    resposta: LiveProgramResponse, programa_id: int, plano: Plano | None, preset: str | None, aceito: bool, *,
    duracao_peca_s: float | None = None, duracao_vinheta_fim_s: float | None = None,
    cfg: ConfigRelogio = CONFIG_RELOGIO, origem: str | None = None,
) -> LiveProgramResponse:
    """Completa a resposta com duracao_prevista_s (todos os programas) e, com relogio, o campo
    `relogio`; so' aqui, com o bloco decidido, marca a etapa/peca como executada. A fala entra pela
    duracao medida quando houver audio, senao pela estimativa no ritmo da voz (`cfg.wpm`, F2)."""
    resposta.duracao_prevista_s = duracao_prevista_bloco(
        resposta, cfg, duracao_peca_s=duracao_peca_s, duracao_vinheta_fim_s=duracao_vinheta_fim_s,
    )
    if plano is None:
        return resposta
    resposta.relogio = relogio_ao_vivo(plano, preset, aceito, origem)
    marcar_executada(programa_id, plano.ocorrencia, plano.chave_estado, *plano.puladas, cfg=cfg)
    # Cadeia do painel antigo (F3): todo bloco decidido pelo relógio, inclusive o do prewarm.
    gravar_elo(programa_id, plano.ocorrencia, EloCadeia(
        tipo=resposta.tipo, vinheta=resposta.tipo == "vinheta",
        duracao_s=round((resposta.pausa_antes_ms or 0) / 1000 + resposta.duracao_prevista_s, 2),
        gerado_em=round(time.time(), 3),
    ), cfg)
    if plano.orcamento_s and resposta.fala.strip() and resposta.tipo not in ("vinheta", "patrocinador"):
        prevista = resposta.duracao_fala_s or resposta.duracao_fala_estimada_s or estimar_duracao_s(resposta.fala, cfg.wpm)
        if prevista > plano.orcamento_s[1] + cfg.tolerancia_hard_time_s:
            logger.warning("relogio_fala_acima_do_espaco programa_id=%s tipo=%s prevista_s=%s maximo_s=%s",
                           programa_id, resposta.tipo, round(prevista, 1), plano.orcamento_s[1])
    return resposta


# --- Duracao real da fala (F2, ver app.live.orcamento e app.live.ritmo_voz) ---------------------


def _registrar_amostra_fala(db: Session, voz, categoria: str, texto: str, duracao_s: float | None,
                            audio: bytes | None) -> None:
    if duracao_s is None or not texto.strip():
        return
    registrar_amostra(db, voz, categoria, palavras=palavras_faladas(texto), duracao_s=duracao_s,
                      pausas=contar_pausas(texto), audio=audio)


def _estimar_fala_do_bloco(fala: str, falas_bloco: list[FalaItem], wpm: float) -> float | None:
    if falas_bloco:
        return round(sum(estimar_duracao_s(f.texto, wpm) for f in falas_bloco)
                     + settings.fala_pausa_entre_linhas_s * max(0, len(falas_bloco) - 1), 2)
    return round(estimar_duracao_s(fala, wpm), 2) if fala.strip() else None


def _excesso_pct(segundos: float | None, maximo: float) -> float | None:
    return round((segundos / maximo - 1) * 100, 1) if segundos is not None and maximo > 0 else None


def _registrar_duracao_fala(request_id: str, programa_id: int, tipo: str, fala: str, falas_bloco: list[FalaItem],
                            orcamento: OrcamentoFala, wpm: float, estimada_s: float | None,
                            medida_s: float | None, ajuste: str, categoria: str) -> None:
    """Log da duracao (registro ate' o as-run da F11) e, na voz unica, o orcamento que o /tts do painel le
    pra medir o excesso do audio que ele mesmo pede."""
    if estimada_s is None:
        return
    logger.info(
        "live_fala_duracao request_id=%s programa_id=%s tipo=%s origem=proxima palavras=%s wpm_usado=%s "
        "estimada_s=%s medida_s=%s max_s=%s excesso_pct=%s ajuste=%s fonte=%s aplicado=%s",
        request_id, programa_id, tipo, palavras_faladas(fala), round(wpm), estimada_s, medida_s, orcamento.max_s,
        _excesso_pct(medida_s if medida_s is not None else estimada_s, orcamento.max_s), ajuste, orcamento.fonte,
        orcamento.aplicar,
    )
    if not falas_bloco and fala.strip():
        guardar_orcamento_pendente(programa_id, fala, {
            "tipo": tipo, "categoria": categoria, "min_s": orcamento.min_s, "alvo_s": orcamento.alvo_s,
            "max_s": orcamento.max_s, "fonte": orcamento.fonte, "aplicar": orcamento.aplicar,
            "estimada_s": estimada_s, "wpm_usado": round(wpm, 1), "request_id": request_id,
        })


# --- POST /proxima: orquestração (F3). As fases ficam em app.live.roteiro, app.live.contexto,
# app.live.prompt_emissao e app.live.geracao; aqui ficam o HTTP, as respostas prontas, o TTS (momento C da F2),
# os registros com o texto que vai ao ar e a resposta.


def _resposta_pronta(decisao: DecisaoBloco, programa: Programa, cfg: ConfigRelogio) -> LiveProgramResponse:
    """Vinheta ou patrocinador: conteúdo fixo, sem LLM (contrato comercial ou peça gravada)."""
    agora = datetime.datetime.now(datetime.timezone.utc)
    if decisao.vinheta is not None:
        vinheta = decisao.vinheta
        resposta = LiveProgramResponse(
            tipo="vinheta", fala=(vinheta.texto or "").strip(), criado_em=agora, programa_atual=programa.nome,
            vinheta_id=vinheta.id, vinheta_audio=bool(vinheta.audio_path), passos_roteiro=decisao.passos_roteiro,
            pausa_antes_ms=_pausa_antes_ms(decisao.ultima_categoria, "vinheta"),
        )
        duracao = float(vinheta.duracao_segundos) if vinheta.audio_path and vinheta.duracao_segundos else None
    else:
        patrocinador = decisao.patrocinador
        resposta = LiveProgramResponse(
            tipo="patrocinador", fala=(patrocinador.texto or "").strip(), criado_em=agora,
            programa_atual=programa.nome, patrocinador_id=patrocinador.id,
            patrocinador_audio=patrocinador.tipo_conteudo == "audio", patrocinador_voz_id=patrocinador.voz_id,
            passos_roteiro=decisao.passos_roteiro, pausa_antes_ms=_pausa_antes_ms(decisao.ultima_categoria,
                                                                                  "patrocinador"),
        )
        duracao = float(patrocinador.duracao_segundos) \
            if patrocinador.tipo_conteudo == "audio" and patrocinador.duracao_segundos else None
    return _com_relogio(resposta, programa.id, decisao.plano, decisao.preset_relogio, decisao.inicio_previsto_aceito,
                        cfg=cfg, duracao_peca_s=duracao, origem=decisao.origem_instante)


def _item_musica(m: MusicaEncontrada) -> MusicaBlocoItem:
    return MusicaBlocoItem(video_id=m.video_id, titulo=m.titulo, canal=m.canal, inicio_segundos=m.inicio_segundos,
                           fim_segundos=m.fim_segundos, duracao_segundos=m.duracao_segundos)


def _resposta_so_musica(decisao: DecisaoBloco, musica: MusicaEncontrada, programa: Programa,
                        cfg: ConfigRelogio) -> LiveProgramResponse:
    """Janela de música sem locução (formato musical, ou relógio sem pedido real): a seleção e o histórico da
    faixa já correram pelo caminho normal; só a fala é dispensada."""
    return _com_relogio(LiveProgramResponse(
        tipo=decisao.tipo, fala="", criado_em=datetime.datetime.now(datetime.timezone.utc),
        programa_atual=programa.nome, video_id=musica.video_id, titulo_musica=musica.titulo,
        inicio_segundos=musica.inicio_segundos, fim_segundos=musica.fim_segundos,
        duracao_segundos=musica.duracao_segundos, musicas=[_item_musica(musica)],
        pausa_antes_ms=_pausa_antes_ms(decisao.ultima_categoria, "musica"), audio_status="nao_aplicavel",
        passos_roteiro=decisao.passos_roteiro,
    ), programa.id, decisao.plano, decisao.preset_relogio, decisao.inicio_previsto_aceito, cfg=cfg,
        origem=decisao.origem_instante)


def _musicas_do_bloco(db: Session, ctx: ContextoEmissao, musica: MusicaEncontrada | None, fala: str,
                      quantidade: int, historico: list[str]
                      ) -> tuple[MusicaEncontrada | None, list[MusicaEncontrada], list[str]]:
    """Faixas que tocam depois da fala: a confirmada (mais as citadas que se resolvem, no formato padrão sem
    relógio) no bloco de música; nos outros blocos, as citadas na fala, com teto do relógio. Devolve também as
    citadas que não vão tocar (sem faixa, fora do gênero ou sem espaço), para o validador."""
    programa, categoria, plano = ctx.programa, ctx.categoria, ctx.tempo.plano
    musicas_bloco: list[MusicaEncontrada] = []
    nao_resolvidas: list[str] = []
    if categoria == "musica":
        if musica is not None:
            # Musica que o locutor citou alem da anunciada tambem toca no bloco -- formato musical e relogio
            # mantem uma faixa so' por bloco.
            citadas, nao_resolvidas, consultas = (
                ([], [], {}) if ctx.formato.comportamento.uma_faixa_por_bloco or plano is not None
                else _musicas_citadas_na_fala(db, programa, fala, historico, ja_no_bloco=[musica])
            )
            # Sem relogio todas as citadas resolvidas ficam no bloco: registradas antes de completar a sequencia,
            # para a busca das faixas extras ([BLOCO_MUSICAS:N]) nao repetir nenhuma delas.
            _registrar_citadas(db, programa.id, citadas, consultas)
            musicas_bloco = _montar_bloco_musicas(db, programa, musica, quantidade, ctx.tipo, citadas=citadas)
    elif fala.strip():
        # Fora do bloco de musica o locutor tambem comenta/promete musica -- se citou uma especifica, ela toca
        # logo depois da fala, em vez de ficar prometida e nunca tocar.
        musicas_bloco, nao_resolvidas, consultas = _musicas_citadas_na_fala(db, programa, fala, historico)
        if plano is not None and musicas_bloco:
            cabem = _citadas_que_cabem(plano, fala, musicas_bloco, programa.id, ctx.wpm_fala)
            nao_resolvidas += [m.titulo for m in musicas_bloco if m not in cabem]
            musicas_bloco = cabem
        _registrar_citadas(db, programa.id, musicas_bloco, consultas)
        if musicas_bloco:
            musica = musicas_bloco[0]
    return musica, musicas_bloco, nao_resolvidas


@dataclasses.dataclass
class _Sintese:
    fala: str
    falas_bloco: list[FalaItem]
    ajuste: str
    audio_base64: str | None = None
    audio_status: str = "nao_aplicavel"
    audio_erro: str | None = None
    tom: str | None = None
    duracao_fala_s: float | None = None
    audios_falas_base64: list[str | None] | None = None
    # Validador pós-geração (F3): violações achadas e o que foi feito com a fala.
    violacoes: list[Violacao] = dataclasses.field(default_factory=list)
    acao_validacao: str = "nenhuma"
    violacoes_finais: list[Violacao] = dataclasses.field(default_factory=list)   # só as da V2


def _checagem_pre(ctx: ContextoEmissao):
    """V1 do validador: as violações da fala recém-gerada entram na MESMA reescrita única, só as das regras no
    modo corrigir (modo por regra, D12 da F4)."""
    return lambda fala: para_reescrita(validar(fala, ctx, "pre"))


def _validar_fala_final(ctx: ContextoEmissao, gerada: FalaGerada, preservar: list[str], so_musica: bool) -> _Sintese:
    """V2 do validador (F3): na fala final, depois do momento B e da resolução das citadas, antes do TTS e dos
    registros. Tira a menção a música sem confirmação; fala vazia ou fragmento abaixo do mínimo vira só música
    ou a reorientação neutra."""
    resultado = corrigir_fala(
        gerada.fala, gerada.falas_bloco, ctx, preservar=preservar, modo=settings.validacao_musica_modo,
        so_musica_se_vazia=so_musica, alterada=gerada.ajuste == "encurtada", wpm=ctx.wpm_fala,
        fracao_minimo=settings.validacao_fala_minimo_fracao, violacoes_pre=gerada.violacoes_pre,
    )
    return _Sintese(fala=resultado.fala, falas_bloco=resultado.falas_bloco, ajuste=gerada.ajuste,
                    violacoes=list(resultado.violacoes), acao_validacao=resultado.acao,
                    violacoes_finais=list(resultado.finais))


def _validacao_resposta(sintese: _Sintese) -> ValidacaoFalaResponse | None:
    if not sintese.violacoes:
        return None
    return ValidacaoFalaResponse(
        violacoes=[ViolacaoFalaResponse(regra=v.regra, trecho=v.trecho, ref_id=v.ref_id) for v in sintese.violacoes],
        acao=sintese.acao_validacao,
    )


def _sintetizar_voz_unica(db: Session, entrada: EntradaEmissao, ctx: ContextoEmissao, sintese: _Sintese,
                          gerada: FalaGerada, preservar: list[str], so_musica: bool = False) -> None:
    """Sintetiza o audio aqui dentro pra cortar o round-trip HTTP separado de /tts (Plano B.3) -- so' na voz
    padrao do radialista (nao multi-voz, nao patrocinador). Qualquer falha retorna estado explicito para evitar
    repeticao do TTS. Momento C (F2): medido acima de maximo + teto, encurta por frases e sintetiza UMA vez."""
    account, radialista, dados = entrada.account, entrada.radialista, entrada.dados
    tipo, categoria, orcamento = ctx.tipo, ctx.categoria, ctx.orcamento
    request_id, programa_id = ctx.request_id, ctx.programa.id
    if sintese.falas_bloco or categoria == "patrocinador" or not sintese.fala.strip():
        return
    sintese.tom = ctx.formato.comportamento.tom_tts or tom_musical(
        ctx.programa, categoria, _tom_sintese_do_bloco(
            tipo, ctx.participacao.pedido_ouvinte.natureza if ctx.participacao.pedido_ouvinte is not None else None
        ),
    )
    _registrar_ultimo_tom(programa_id, sintese.tom)
    if not dados.incluir_audio:
        sintese.audio_status = "pendente" if tts_habilitado(radialista.voz_id) else "indisponivel"
        return
    if not tts_habilitado(radialista.voz_id):
        sintese.audio_status = "indisponivel"
        return
    try:
        inicio_tts = time.perf_counter()
        parametros_voz = parametros_sintese(db, account.id, radialista.voz_id)

        def _sintetizar(texto: str) -> bytes:
            audio = sintetizar_audio(
                texto, radialista.voz_id, tipo_bloco=tipo, tom=sintese.tom, **parametros_voz,
                texto_anterior=dados.ultima_fala, timeout_segundos=_TTS_TIMEOUT_EMBUTIDO_SEGUNDOS, max_tentativas=1,
            )
            return processar_audio(audio, dados.perfil_pos_producao) if dados.perfil_pos_producao else audio

        audio_bytes: bytes | None = _sintetizar(sintese.fala)
        sintese.duracao_fala_s = duracao_mp3_s(audio_bytes)
        _registrar_amostra_fala(db, entrada.voz_programa, ctx.categoria_voz, sintese.fala, sintese.duracao_fala_s,
                                audio_bytes)
        if sintese.duracao_fala_s is not None and orcamento.aplicar \
                and avaliar_duracao(sintese.duracao_fala_s, orcamento) == "acima_do_teto":
            curto = encurtar_pela_medida(sintese.fala, orcamento, sintese.duracao_fala_s, preservar=preservar,
                                         manter=gerada.manter_frase, manter_ultima=gerada.manter_ultima)
            cortar = gerada.pode_cortar
            wpm_medido = wpm_da_medida(sintese.fala, sintese.duracao_fala_s) or ctx.wpm_fala
            if curto is not None and fragmento(curto, ctx, wpm_medido, settings.validacao_fala_minimo_fracao,
                                               so_musica):
                # Fragmento abaixo do minimo (achado do juiz da F2: "Radio.", 0,4 s) nao vai ao ar: a musica segue,
                # ou entra a reorientacao neutra (uma ressintese so', o limite de 2 continua).
                sintese.violacoes.append(Violacao("fala_abaixo_do_minimo", curto.strip()[:120],
                                                  remediacao="fala_inteira"))
                if so_musica:
                    curto, cortar, sintese.acao_validacao = None, True, "fala_removida"
                else:
                    curto, sintese.acao_validacao = fala_reserva_neutra(ctx, wpm_medido), "fala_neutra"
            if curto is not None:
                try:
                    audio_curto = _sintetizar(curto)
                except Exception:
                    logger.warning("live_audio_ressintese_falhou request_id=%s programa_id=%s tipo=%s",
                                   request_id, programa_id, tipo, exc_info=True)
                    sintese.ajuste = "acima_do_teto"
                else:
                    sintese.fala, audio_bytes, sintese.ajuste = curto, audio_curto, "encurtada"
                    sintese.duracao_fala_s = duracao_mp3_s(audio_bytes)
                    _registrar_amostra_fala(db, entrada.voz_programa, ctx.categoria_voz, sintese.fala,
                                            sintese.duracao_fala_s, audio_bytes)
            elif cortar:
                sintese.fala, audio_bytes, sintese.ajuste, sintese.duracao_fala_s, sintese.tom = \
                    "", None, "cortada", None, None
            else:
                sintese.ajuste = "acima_do_teto"
            logger.info("live_fala_ajustada request_id=%s programa_id=%s tipo=%s ajuste=%s momento=audio",
                        request_id, programa_id, tipo, sintese.ajuste)
        if audio_bytes is not None:
            sintese.audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
            sintese.audio_status = "pronto"
        logger.info("live_audio_pronto request_id=%s programa_id=%s tipo=%s tts_ms=%s", request_id, programa_id,
                    tipo, round((time.perf_counter() - inicio_tts) * 1000))
    except Exception as exc:
        # Nao esconda o motivo nem faca o navegador repetir o mesmo request automaticamente. A cama musical
        # continua no ar enquanto o proximo bloco e preparado.
        sintese.audio_status = "falhou"
        sintese.duracao_fala_s = None
        sintese.audio_erro = (
            "orcamento_ia_esgotado" if isinstance(exc, HTTPException) and exc.status_code == 402
            else type(exc).__name__
        )
        logger.warning("live_audio_falhou request_id=%s programa_id=%s tipo=%s erro=%s", request_id, programa_id,
                       tipo, sintese.audio_erro, exc_info=True)


def _sintetizar_multivoz(db: Session, entrada: EntradaEmissao, ctx: ContextoEmissao, sintese: _Sintese,
                         preservar: list[str]) -> None:
    """Dialogo multi-voz: cada linha em paralelo aqui dentro (poupa o painel de N chamadas /tts). Nao depende de
    dados.incluir_audio (o streaming do /tts avulso e' so' do locutor unico). Momento C' (F2): pelas duracoes
    medidas, retira linhas do fim, mantendo falas e audios alinhados."""
    account, radialista, dados = entrada.account, entrada.radialista, entrada.dados
    tipo, request_id, programa_id = ctx.tipo, ctx.request_id, ctx.programa.id
    if not sintese.falas_bloco or not tts_habilitado(radialista.voz_id):
        return
    natureza = ctx.participacao.pedido_ouvinte.natureza if ctx.participacao.pedido_ouvinte is not None else None
    tom_multivoz = ctx.formato.comportamento.tom_tts or tom_musical(
        ctx.programa, ctx.categoria, _tom_sintese_do_bloco(tipo, natureza)
    )
    _registrar_ultimo_tom(programa_id, tom_multivoz)
    inicio_tts_multivoz = time.perf_counter()
    parametros_por_voz = _preparar_parametros_multivoz(db, account.id, sintese.falas_bloco)
    audios, duracoes_linhas = _sintetizar_falas_multivoz(
        sintese.falas_bloco, parametros_por_voz, tipo, tom_multivoz, dados.ultima_fala,
        dados.perfil_pos_producao, request_id, programa_id,
    )
    sintese.audios_falas_base64 = audios
    logger.info("live_audio_multivoz_pronto request_id=%s programa_id=%s tipo=%s linhas=%s tts_ms=%s",
                request_id, programa_id, tipo, len(sintese.falas_bloco),
                round((time.perf_counter() - inicio_tts_multivoz) * 1000))
    # Amostras de ritmo por voz, so' depois das threads (a sessao do banco nao e' thread-safe).
    for linha, audio_linha, duracao_linha in zip(sintese.falas_bloco, audios, duracoes_linhas):
        if audio_linha is not None:
            _registrar_amostra_fala(db, voz_efetiva(db, account.id, linha.voz_id), ctx.categoria_voz, linha.texto,
                                    duracao_linha, audio_linha.encode("ascii"))
    if None in duracoes_linhas:
        return
    ficam = _linhas_que_cabem(sintese.falas_bloco, duracoes_linhas, ctx.orcamento, preservar,
                              lambda total, orc: avaliar_duracao(total, orc) == "acima_do_teto")
    if ficam < len(sintese.falas_bloco):
        sintese.falas_bloco, sintese.audios_falas_base64 = sintese.falas_bloco[:ficam], audios[:ficam]
        duracoes_linhas = duracoes_linhas[:ficam]
        sintese.fala, sintese.ajuste = " ".join(item.texto for item in sintese.falas_bloco), "encurtada"
        logger.info("live_fala_ajustada request_id=%s programa_id=%s tipo=%s ajuste=encurtada momento=audio "
                    "linhas=%s", request_id, programa_id, tipo, ficam)
    sintese.duracao_fala_s = round(sum(duracoes_linhas) + settings.fala_pausa_entre_linhas_s
                                   * max(0, len(duracoes_linhas) - 1), 3)


def _registrar_fala_no_ar(db: Session, ctx: ContextoEmissao, fala: str) -> None:
    """Registros com o texto que vai ao ar: depois do TTS, porque o momento C pode encurtar a fala."""
    programa, categoria = ctx.programa, ctx.categoria
    if not fala.strip():
        return
    _registrar_fala_gerada(programa.id, categoria, fala)
    if categoria in ("comentario", "noticia"):
        _registrar_tema_em_background(programa.id, fala)
    assunto = ctx.variacoes.assunto
    if categoria == "comentario" and assunto is not None:
        registrar_assunto_usado(programa.id, programa.radio_config_id, assunto.assunto_id, eixo=assunto.eixo,
                                origem=assunto.origem, tag_principal=assunto.tag_principal)
    pautas, pauta = ctx.jornalismo.pautas, ctx.jornalismo.pauta
    if categoria in _CATEGORIAS_NOTICIA_LIKE and pautas:
        # Auditoria + base pro angulo/repeticao da proxima vez que cada noticia concorrer a pauta de novo --
        # escalada registra uma linha por manchete lida; os outros, so' a sua.
        for pauta_lida in pautas:
            db.add(NoticiaHistorico(programa_id=programa.id, noticia_id=pauta_lida.noticia_id,
                                    angulo=pauta_lida.angulo, fala=fala))
        db.commit()
        if pauta is not None and pauta.angulo != ANGULO_CORRECAO:
            # Fase G: noticia puxa comentario -- prioridade pro assunto derivado desta noticia.
            registrar_callback_noticia(programa.id, pauta.noticia_id)
    if categoria == "abertura" and ctx.primeira_fala:
        fio_condutor_novo = classificar_fio_condutor(fala)
        if fio_condutor_novo:
            _registrar_fio_condutor(programa.id, fio_condutor_novo)


def _devolver_pedido_sem_mencao(db: Session, ctx: ContextoEmissao, resolucao: ResolucaoBloco,
                                sintese: _Sintese) -> bool:
    """D10 da F4: chamada de ouvinte com pedido selecionado cujo nome não ficou na fala que vai ao ar (nem depois
    da reescrita). O pedido volta para a fila e a resposta sai sem pedido_id: o painel não confirma o que não foi
    dito."""
    violacao = pedido_sem_mencao(sintese.fala, ctx)
    pedido = resolucao.pedido_ouvinte
    if violacao is None or pedido is None:
        return False
    if not any(v.regra == "pedido_sem_mencao" for v in sintese.violacoes_finais):
        sintese.violacoes.append(violacao)  # o nome saiu depois da V2 (encurtamento pelo áudio)
    if settings.validacao_participacao_modo != "corrigir":
        return False
    from app.whatsapp.atendimento import registrar_evento

    if pedido.programa_id is None:
        pedido.atendido, pedido.atendido_em = False, None  # legado: a seleção tinha marcado atendido
    pedido.estado, pedido.selecao_token = "em_fila", None
    pedido.motivo = "Nome do ouvinte não foi ao ar; volta para a fila"
    registrar_evento(pedido, "devolver_sem_mencao")
    db.commit()
    logger.info("live_pedido_devolvido_sem_mencao request_id=%s programa_id=%s pedido_id=%s", ctx.request_id,
                ctx.programa.id, pedido.id)
    return True


def _registrar_promessas(db: Session, ctx: ContextoEmissao, fala: str, devolvido: bool = False
                         ) -> PromessasBloco | None:
    """Com o texto que vai ao ar (depois do TTS: o momento C pode ter tirado a frase): promessas novas casadas com
    um evento da agenda viram linha aberta; as que este bloco cumpre viram cumpridas; as contingências ditas
    cancelam as suas. No encerramento, o que sobrou vence. Sem promessa, nenhuma escrita."""
    chamadas = ctx.chamadas
    if chamadas.ocorrencia is None:
        return None
    resolvidas = []
    if fala.strip():
        cumpridas = [p.id for p in chamadas.a_cumprir if not (devolvido and p.tipo == "participacao")]
        resolvidas += promessas_repo.resolver(db, cumpridas, "cumprida", "cumprida no bloco")
        for contingencia in chamadas.contingencias:
            if dita(contingencia.texto, fala):
                if contingencia.peca_id is not None:
                    _registrar_peca_usada(ctx.programa.id, chamadas.ocorrencia, contingencia.peca_id)
                resolvidas += promessas_repo.resolver(db, [contingencia.promessa_id], "cancelada",
                                                      f"contingencia:{contingencia.motivo}",
                                                      contingencia=contingencia.texto)
    novas = promessas_repo.registrar(db, programa=ctx.programa, ocorrencia=chamadas.ocorrencia,
                                     request_id=ctx.request_id, itens=a_registrar_no_texto(fala, ctx)) \
        if fala.strip() else []
    if ctx.categoria == "encerramento":
        resolvidas += promessas_repo.vencer(db, ctx.programa.id, ocorrencia=chamadas.ocorrencia)
    if not (novas or resolvidas):
        return None
    return PromessasBloco(
        registradas=[PromessaResponse(id=linha.id, tipo=linha.tipo, trecho=linha.trecho,
                                      evento_alvo=linha.evento_alvo, prazo=linha.prazo,
                                      prazo_posicao=linha.prazo_posicao) for linha in novas],
        resolvidas=[PromessaResolvidaResponse(id=linha.id, estado=linha.estado, contingencia=linha.contingencia or None)
                    for linha in resolvidas])


def _dados_resposta(ctx: ContextoEmissao) -> list[DadoFalaResponse] | None:
    from app.dados.verificavel import estado as estado_do_dado, valido_ate_efetivo

    if not ctx.dados:
        return None
    return [DadoFalaResponse(id=d.id, tipo=d.tipo, estado=estado_do_dado(d, ctx.tempo.instante),
                             atualizado_em=d.atualizado_em, valido_ate=valido_ate_efetivo(d), alertas=list(d.alertas))
            for d in ctx.dados]


def _pedido_confirmavel(db: Session, resolucao: ResolucaoBloco, musica: MusicaEncontrada | None):
    """Pedido (fluxo novo ou legado, desde a D1 da F4) que o painel confirma depois de tocar; música indisponível
    reprova na hora."""
    pedido = resolucao.pedido_musica or resolucao.pedido_ouvinte
    if pedido and (resolucao.pedido_sem_resultado or (resolucao.pedido_musica and musica is None)):
        pedido.estado = "nao_atendido"
        pedido.motivo = "Música indisponível"
        db.commit()
        return None
    return pedido


# F12: tipos que não carregam fala revisável (conteúdo fixo ou música).
_TIPOS_SEM_FALA_REVISAVEL = ("vinheta", "patrocinador", "musica")


def _aplicar_revisao(db: Session, account: Account, radialista_id: int, programa_id: int,
                     resposta: LiveProgramResponse) -> LiveProgramResponse:
    """F12: fala que o roteamento não deixa ir ao ar sozinha (revisão ou proibida) vira substituta neutra. O
    original fica em falas_em_revisao aguardando decisão; nunca vai ao ar nesta etapa (ver app.live.revisao)."""
    if resposta.tipo in _TIPOS_SEM_FALA_REVISAVEL or not resposta.fala.strip():
        return resposta
    radialista = _buscar_radialista(db, account, radialista_id)
    programa = _buscar_programa(db, radialista, programa_id)
    rota = rotear(resposta.tipo, resposta.fala, programa.topicos_proibidos or [])
    if rota == AUTOMATICO:
        return resposta
    agora = datetime.datetime.now(datetime.timezone.utc)
    registrar_revisao(db, account.id, programa_id, resposta.tipo, resposta.fala, rota, agora)
    resposta.fala = substituta(agora.second)
    resposta.falas = None  # multi-voz traria o texto original de novo
    # Com incluir_audio (preparo antecipado), o áudio já sintetizado é do texto original: descartado, o
    # player sintetiza a substituta pelo /tts. "falhou"/"indisponivel" ficam como estão (não repetir).
    resposta.audio_base64 = None
    resposta.audios_falas_base64 = None
    resposta.duracao_fala_s = None
    if resposta.audio_status == "pronto":
        resposta.audio_status = "pendente"
    return resposta


@router.post("/{radialista_id}/programas/{programa_id}/proxima", response_model=LiveProgramResponse)
def gerar_proxima_fala(
    radialista_id: int,
    programa_id: int,
    dados: LiveProgramRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Entrega o proximo bloco e grava no as-run (F11) como "enviado"; o player confirma depois."""
    resposta = _gerar_proxima_fala(radialista_id=radialista_id, programa_id=programa_id, dados=dados,
                                   account=account, db=db)
    resposta = _aplicar_revisao(db, account, radialista_id, programa_id, resposta)
    resposta.as_run_evento_id = registrar_envio(
        db, account.id, programa_id, resposta.tipo, resposta.fala, vinheta_id=resposta.vinheta_id,
        patrocinador_id=resposta.patrocinador_id, video_id=resposta.video_id, pedido_id=resposta.pedido_id,
    )
    return resposta


@router.post("/{radialista_id}/programas/{programa_id}/as-run/{evento_id}", response_model=AsRunConfirmacaoResponse)
def confirmar_as_run(
    radialista_id: int,
    programa_id: int,
    evento_id: int,
    dados: AsRunConfirmacaoRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Relato do player: o bloco tocou ate o fim ("confirmado") ou deu erro ("falhou")."""
    radialista = _buscar_radialista(db, account, radialista_id)
    _buscar_programa(db, radialista, programa_id)
    try:
        evento = confirmar_evento(db, account.id, programa_id, evento_id, dados.status)
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))
    if evento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento do as-run nao encontrado")
    return AsRunConfirmacaoResponse(id=evento.id, status=evento.status)


@acompanhar_geracao
def _gerar_proxima_fala(
    radialista_id: int,
    programa_id: int,
    dados: LiveProgramRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    request_id = uuid.uuid4().hex[:12]
    inicio_request = time.perf_counter()
    radialista = _buscar_radialista(db, account, radialista_id)
    programa = _buscar_programa(db, radialista, programa_id)

    # Cada chamada gera fala via LLM (paga) -- sem teto, um JWT vazado (7 dias, sem revogacao, ver
    # app/auth/security.py) pode chamar sem limite. Generoso pra nao afetar uso normal (auditoria: item 4).
    if limite_excedido(f"live_proxima:{account.id}", limite=60, janela_segundos=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas requisicoes. Tente novamente em instantes.")

    # Mesmos 3 campos que identificam cada linha de log deste endpoint, como tag do Sentry.
    sentry_sdk.set_tag("radialista_id", radialista_id)
    sentry_sdk.set_tag("programa_id", programa_id)
    sentry_sdk.set_tag("request_id", request_id)

    # Ritmo da voz do programa (F2): calibracao medida no audio final, senao o padrao do modelo e o geral. Lido
    # so' do banco; vale pro backtiming do relogio e pro orcamento.
    voz_programa = voz_efetiva(db, account.id, radialista.voz_id)
    ritmos_voz = carregar_ritmos(db, voz_programa)
    cfg_relogio = replace(CONFIG_RELOGIO, wpm=ritmos_voz.wpm())
    formato = formato_do_programa(programa)
    entrada = EntradaEmissao(
        request_id=request_id, db=db, account=account, radialista=radialista, programa=programa, dados=dados,
        total_falas=dados.total_falas if dados.total_falas is not None else len(dados.historico),
        formato_musical=formato.comportamento.ciclo == "musical", voz_programa=voz_programa, ritmos_voz=ritmos_voz,
        cfg_relogio=cfg_relogio, formato=formato,
    )
    portas = _portas()

    decisao = decidir_bloco(entrada, portas)
    if decisao.vinheta is not None or decisao.patrocinador is not None:
        return _resposta_pronta(decisao, programa, cfg_relogio)
    resolucao = resolver_musica_e_pedidos(entrada, decisao, portas)
    if resolucao.so_musica:
        return _resposta_so_musica(decisao, resolucao.musica, programa, cfg_relogio)

    ctx = montar_contexto(entrada, decisao, resolucao, portas)
    gerada = _gerada_da_peca_de_estouro(ctx) or gerar_fala(ctx, montar_prompt(ctx), portas,
                                                           checar_pre=_checagem_pre(ctx))
    tipo, categoria = ctx.tipo, ctx.categoria
    musica, musicas_bloco, nao_resolvidas = _musicas_do_bloco(db, ctx, resolucao.musica, gerada.fala,
                                                              gerada.quantidade, dados.historico)
    ctx = dataclasses.replace(ctx, musica=dataclasses.replace(
        ctx.musica, bloco=tuple(MusicaRef.de(m) for m in musicas_bloco), resolvido=True,
        citadas_nao_resolvidas=tuple(nao_resolvidas)))
    # O encurtamento depois do TTS tambem nao tira a frase que anuncia uma faixa do bloco.
    preservar = gerada.preservar + [m.titulo for m in musicas_bloco if m.titulo and m.titulo not in gerada.preservar]
    so_musica = bool(musicas_bloco) and ctx.participacao.pedido_musica is None

    sintese = _validar_fala_final(ctx, gerada, preservar, so_musica)
    # Contingência garantida (F4, D5): a frase vai ao ar mesmo que o LLM a ignore, e o momento C não a tira.
    sintese.fala, sintese.falas_bloco, _ = garantir_contingencia(sintese.fala, sintese.falas_bloco,
                                                                 ctx.chamadas.contingencias)
    preservar = preservar + [c.texto for c in ctx.chamadas.contingencias]
    _sintetizar_voz_unica(db, entrada, ctx, sintese, gerada, preservar, so_musica)
    _sintetizar_multivoz(db, entrada, ctx, sintese, preservar)
    fala, falas_bloco = sintese.fala, sintese.falas_bloco
    _registrar_fala_no_ar(db, ctx, fala)
    devolvido = _devolver_pedido_sem_mencao(db, ctx, resolucao, sintese)
    promessas = _registrar_promessas(db, ctx, fala, devolvido)

    duracao_fala_estimada_s = _estimar_fala_do_bloco(fala, falas_bloco, ctx.wpm_fala)
    _registrar_duracao_fala(request_id, programa.id, tipo, fala, falas_bloco, ctx.orcamento, ctx.wpm_fala,
                            duracao_fala_estimada_s, sintese.duracao_fala_s, sintese.ajuste, ctx.categoria_voz)
    if sintese.violacoes:
        logger.info("live_validacao_fala request_id=%s programa_id=%s tipo=%s acao=%s regras=%s refs=%s", request_id,
                    programa.id, tipo, sintese.acao_validacao, [v.regra for v in sintese.violacoes],
                    [v.ref_id for v in sintese.violacoes])
    _registrar_coerencia_formato(ctx, fala, sintese.duracao_fala_s if sintese.duracao_fala_s is not None
                                 else duracao_fala_estimada_s)
    _registrar_memoria_reorientacao(ctx, fala)
    logger.info("live_proxima_pronta request_id=%s programa_id=%s tipo=%s audio_status=%s total_ms=%s", request_id,
                programa.id, tipo, sintese.audio_status, round((time.perf_counter() - inicio_request) * 1000))

    pedido = None if devolvido else _pedido_confirmavel(db, resolucao, musica)
    vinheta_fim = vinheta_encerramento(db, account.id, programa.id) if categoria == "encerramento" else None
    orcamento, plano = ctx.orcamento, ctx.tempo.plano
    return _com_relogio(LiveProgramResponse(
        pedido_id=pedido.id if pedido else None,
        pesquisa_noticias=ctx.jornalismo.pesquisa,
        pedido_token=pedido.selecao_token if pedido else None,
        pedido_programa_id=programa.id if pedido else None,
        pedido_radialista_id=radialista.id if pedido else None,
        tipo=tipo,
        fala=fala,
        criado_em=datetime.datetime.now(datetime.timezone.utc),
        video_id=musica.video_id if musica else None,
        titulo_musica=musica.titulo if musica else None,
        inicio_segundos=musica.inicio_segundos if musica else 0,
        fim_segundos=musica.fim_segundos if musica else None,
        duracao_segundos=musica.duracao_segundos if musica else None,
        musicas=[_item_musica(m) for m in musicas_bloco],
        programa_atual=programa.nome,
        assunto_id=ctx.variacoes.assunto.assunto_id if ctx.variacoes.assunto else None,
        assunto_titulo=ctx.variacoes.assunto.titulo if ctx.variacoes.assunto else None,
        falas=falas_bloco or None,
        audios_falas_base64=sintese.audios_falas_base64,
        intervalo_ms=_intervalo_transicao_ms(decisao.ultima_categoria, categoria),
        pausa_antes_ms=_pausa_antes_ms(decisao.ultima_categoria, categoria),
        duracao_alvo_segundos=plano.orcamento_s if plano is not None else (
            (orcamento.min_s, orcamento.max_s) if ctx.formato.aplica_orcamento else None
        ),
        audio_base64=sintese.audio_base64,
        audio_status=sintese.audio_status,
        audio_erro=sintese.audio_erro,
        tom=sintese.tom,
        passos_roteiro=decisao.passos_roteiro,
        duracao_fala_s=round(sintese.duracao_fala_s, 2) if sintese.duracao_fala_s is not None else None,
        duracao_fala_estimada_s=duracao_fala_estimada_s,
        orcamento_fala_s=OrcamentoFalaResponse(min_s=orcamento.min_s, alvo_s=orcamento.alvo_s, max_s=orcamento.max_s,
                                               fonte=orcamento.fonte, aplicado=orcamento.aplicar),
        fala_ajuste=sintese.ajuste,
        validacao_fala=_validacao_resposta(sintese),
        promessas=promessas,
        dados=_dados_resposta(ctx),
        vinheta_encerramento_id=vinheta_fim.id if vinheta_fim else None,
        vinheta_encerramento_audio=bool(vinheta_fim and vinheta_fim.audio_path),
        vinheta_encerramento_texto=(vinheta_fim.texto or None) if vinheta_fim else None,
    ), programa.id, plano, decisao.preset_relogio, decisao.inicio_previsto_aceito, cfg=cfg_relogio,
        origem=decisao.origem_instante, duracao_vinheta_fim_s=float(vinheta_fim.duracao_segundos)
        if vinheta_fim and vinheta_fim.audio_path and vinheta_fim.duracao_segundos else None)


def _registrar_coerencia_formato(ctx: ContextoEmissao, fala: str, duracao_s: float | None) -> None:
    """F6 (D21): a coerência da fala com o formato só é medida e registrada (ids e códigos, nunca trecho de fala);
    nada é reescrito nem removido. Pura (sem Redis nem sorteio): não muda o retrato dos goldens."""
    if not fala.strip():
        return
    plano, programa = ctx.tempo.plano, ctx.programa
    retorno = ctx.memoria.ultima_categoria == "patrocinador" or (
        plano is not None and getattr(plano.etapa, "tipo_efetivo", None) == "retorno")
    avisos = avisos_da_fala(ctx.formato, FalaNoAr(
        bloco=ctx.tipo, categoria=ctx.categoria, texto=fala, duracao_s=duracao_s or 0.0, primeira=ctx.primeira_fala,
        quadro=eh_quadro_fixo(programa, ctx.tipo), retorno=retorno,
        teto_s=plano.orcamento_s[1] if plano is not None and plano.orcamento_s else None,
        desde_reorientacao_s=ctx.memoria.desde_reorientacao_s,
    ), nomes=_nomes_reorientacao(ctx))
    if avisos:
        logger.info("live_formato_aviso request_id=%s programa_id=%s formato=%s tipo=%s avisos=%s", ctx.request_id,
                    programa.id, ctx.formato.id, ctx.categoria, sorted({a.codigo for a in avisos}))


def _gerada_da_peca_de_estouro(ctx: ContextoEmissao) -> FalaGerada | None:
    """F11 (item 3): no "debate estourou" (plano `fechamento_curto` do relógio), a peça de reserva "estouro" aprovada
    e ainda não dita nesta ocorrência fecha o assunto, sem chamar o LLM. Só quando cabe no orçamento do fechamento:
    o texto aprovado vai ao ar inteiro, nunca encurtado. Diálogo multi-voz segue com o LLM."""
    plano = ctx.tempo.plano
    if plano is None or plano.instrucao != "fechamento_curto" or ctx.multi_voz or not plano.orcamento_s:
        return None
    peca = escolher_reserva(getattr(ctx.programa, "pecas_reserva", None) or [], "estouro", ctx.chamadas.pecas_usadas)
    if peca is None or estimar_duracao_s(peca["texto"], ctx.wpm_fala) > plano.orcamento_s[1]:
        return None
    _registrar_peca_usada(ctx.programa.id, ctx.chamadas.ocorrencia, peca["id"])
    logger.info("live_peca_reserva request_id=%s programa_id=%s tipo=estouro peca_id=%s", ctx.request_id,
                ctx.programa.id, peca["id"])
    return FalaGerada(falas_bloco=[], fala=peca["texto"], quantidade=1, ajuste="nenhum", preservar=[peca["texto"]],
                      manter_frase=None, manter_ultima=False, pode_cortar=False)


def _nomes_reorientacao(ctx: ContextoEmissao) -> tuple[str, str]:
    return ctx.programa.nome, getattr(ctx.account, "nome_radio", "") or ""


def _registrar_memoria_reorientacao(ctx: ContextoEmissao, fala: str) -> None:
    """F8 (passo 3): a abertura do programa e toda fala que reorienta (nome do programa ou da rádio) viram a última
    reorientação, só nos formatos com `reorientacao_s`. O instante é o de ir ao ar (relógio), não o da geração."""
    if not ctx.formato.reorientacao_s or not fala.strip():
        return
    if ctx.primeira_fala or reorienta(fala, _nomes_reorientacao(ctx)):
        _registrar_reorientacao(ctx.programa.id, ctx.tempo.instante)


@router.get("/{radialista_id}/programas/{programa_id}/preparo")
def buscar_preparo_antecipado(
    radialista_id: int,
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Devolve a primeira fala (+ audio) pre-gerada pelo prewarm em background (ver
    app.live.prewarm), quando o horario_inicio do programa chegou dentro da janela de
    antecedencia -- permite ao painel comecar tocando na hora exata, sem esperar LLM+TTS,
    mesmo se a aba so' foi aberta agora. Uso unico: consumir_preparo_antecipado ja apaga a
    chave, entao um retry aqui sempre cai no caminho normal de /proxima."""
    # import local pra evitar ciclo: app.live.prewarm importa gerar_proxima_fala/gerar_audio_fala
    # deste modulo (reusa a logica de verdade em vez de duplicar), entao nao da pra importar
    # prewarm no topo daqui.
    from app.live.prewarm import consumir_preparo_antecipado

    radialista = _buscar_radialista(db, account, radialista_id)
    _buscar_programa(db, radialista, programa_id)
    preparo = consumir_preparo_antecipado(programa_id)
    if preparo is None:
        return {"disponivel": False}
    return {"disponivel": True, **preparo}


@router.get("/{radialista_id}/programas/{programa_id}/reserva")
def buscar_audio_reserva(radialista_id: int, programa_id: int,
                        account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    """Somente identificação já gravada deste programa; nunca gera TTS nem reutiliza notícias."""
    from app.storage import get_storage
    radialista = _buscar_radialista(db, account, radialista_id)
    _buscar_programa(db, radialista, programa_id)
    itens = (db.query(BibliotecaAudioItem).filter_by(account_id=account.id, programa_id=programa_id,
             papel="passagem", origem="auto", ativo=True, status="pronta")
             .filter(BibliotecaAudioItem.audio_path.isnot(None)).order_by(BibliotecaAudioItem.id.desc()).limit(3).all())
    for item in itens:
        audio = get_storage().read(item.audio_path)
        if audio:
            return {"disponivel": True, "audio_base64": base64.b64encode(audio).decode(), "texto": item.texto or ""}
    return {"disponivel": False}


@router.get("/{radialista_id}/programas/{programa_id}/musica-fundo", response_model=MusicaFundoResponse)
def buscar_musica_de_fundo(
    radialista_id: int,
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Faixa instrumental pra tocar baixinho em loop entre as falas, sem deixar vazio no ar."""
    radialista = _buscar_radialista(db, account, radialista_id)
    programa = _buscar_programa(db, radialista, programa_id)

    musica = buscar_musica_fundo(
        programa.generos_musicais,
        bloqueados=programa.musicas_bloqueadas,
        musica_escolhida=programa.musica_fundo_escolhida or None,
    )
    if musica is None:
        logger.warning("Nenhuma musica de fundo encontrada: programa_id=%s", programa.id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma musica de fundo encontrada")

    return MusicaFundoResponse(
        video_id=musica.video_id,
        titulo=musica.titulo,
        inicio_segundos=musica.inicio_segundos,
        fim_segundos=musica.fim_segundos,
        duracao_segundos=musica.duracao_segundos,
    )


# Erros do IFrame API do YouTube que sao do VIDEO (100 removido/privado, 101/150 dono bloqueou
# embed) -- so' esses barram o video pra sempre. "nao_iniciou"/erro 5 (HTML5) podem ser do
# navegador/rede do painel, entao so' trocam a faixa desta vez (ela ja' esta' no historico da
# sessao, nao volta nesta transmissao) sem condenar o video no catalogo.
_MOTIVOS_VIDEO_QUEBRADO = {"erro_100", "erro_101", "erro_150"}


@router.post("/{radialista_id}/programas/{programa_id}/musica-substituta", response_model=MusicaSubstitutaResponse)
def buscar_musica_substituta(
    radialista_id: int,
    programa_id: int,
    dados: MusicaSubstitutaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Chamado pelo painel quando o player do YouTube nao consegue tocar a faixa escolhida
    (video removido/privado, embed bloqueado, nunca comecou a tocar). Em erro do proprio video
    marca ele como quebrado (nunca mais volta numa busca, nem pelo catalogo) e devolve outra versao da MESMA
    musica -- o locutor ja anunciou ela -- ou, se nao houver, outra faixa do programa. Sem isso
    o bloco de musica era pulado em silencio: musica chamada e nunca tocada."""
    radialista = _buscar_radialista(db, account, radialista_id)
    programa = _buscar_programa(db, radialista, programa_id)
    if limite_excedido(f"live_musica_substituta:{account.id}", limite=20, janela_segundos=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas requisicoes. Tente novamente em instantes.")

    logger.warning(
        "Musica nao tocou no painel, buscando substituta: programa_id=%s video_id=%s titulo=%r motivo=%s",
        programa.id, dados.video_id, dados.titulo, dados.motivo,
    )
    if dados.motivo in _MOTIVOS_VIDEO_QUEBRADO:
        marcar_video_quebrado(dados.video_id)
        esquecer_video_catalogado(db, dados.video_id)

    ids_tocadas, titulos_tocados, canais_tocados = _historico_musicas(programa.id)
    ids_radio, titulos_radio = _musicas_recentes_da_radio(db, programa.radio_config_id)
    ids_tocadas |= ids_radio
    # a faixa que falhou ja' entrou no historico ao ser escolhida -- tira o titulo dela pra outra
    # versao da mesma musica poder substituir (o video quebrado segue barrado por video_id).
    titulos_tocados = (titulos_tocados | titulos_radio) - {_titulo_normalizado(dados.titulo)}

    musica = None
    if dados.titulo.strip():
        # canal oficial primeiro (mesmo criterio da escolha original); se so' o oficial existia e
        # e' ele que esta' bloqueado, aceita outra versao em vez de deixar o bloco mudo.
        for exigir_oficial in (True, False):
            musica = buscar_musica(
                dados.titulo,
                bloqueados=programa.musicas_bloqueadas,
                evitar_video_ids=ids_tocadas,
                titulos_tocados=titulos_tocados,
                canais_recentes=canais_tocados,
                exigir_cantada=True,
                exigir_canal_oficial=exigir_oficial,
            )
            if musica is not None:
                break
        if musica is not None:
            _registrar_musica_tocada(programa.id, musica)
            _registrar_historico_persistente(db, programa.id, musica, dados.titulo, origem="substituta")
    if musica is None:
        musica = _buscar_musica_para_bloco(db, programa)
    if musica is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma musica substituta encontrada")

    return MusicaSubstitutaResponse(
        video_id=musica.video_id,
        titulo=musica.titulo,
        canal=musica.canal,
        inicio_segundos=musica.inicio_segundos,
        fim_segundos=musica.fim_segundos,
        duracao_segundos=musica.duracao_segundos,
    )


@router.post("/{radialista_id}/tts")
def gerar_audio_fala(
    radialista_id: int,
    dados: LiveTtsRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    if dados.programa_id is not None:
        # Fala do programa usa a voz da combinação escolhida para ele.
        programa = db.query(Programa).filter_by(id=dados.programa_id, radio_config_id=radialista.id).first()
        if programa is not None:
            from app.billing.contexto_ia import selecionar_programa
            selecionar_programa(programa)

    # Mesmo motivo do teto em /proxima (ver auditoria: item 4) -- sintese de audio tambem e'
    # paga (ElevenLabs) e este endpoint nao tinha nenhum limite ate' aqui.
    if limite_excedido(f"live_tts:{account.id}", limite=90, janela_segundos=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas requisicoes. Tente novamente em instantes.")

    # Tag em vez de contexto de request (Sentry ja' correlaciona por request via
    # FastApiIntegration) -- so' pra' filtrar/agrupar issues por radialista/programa direto
    # na lista de issues do Sentry, sem abrir cada evento pra' ver o traceback primeiro.
    sentry_sdk.set_tag("radialista_id", radialista_id)
    if dados.programa_id is not None:
        sentry_sdk.set_tag("programa_id", dados.programa_id)

    # Patrocinador pode pedir uma voz especifica (independente da voz do locutor no ar) --
    # ver Patrocinador.voz_id em app/models/patrocinador.py.
    voz_id = validar_voz_ou_400(db, account, dados.voz_id) or radialista.voz_id

    if not tts_habilitado(voz_id):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS nao configurado")

    tom = dados.tom if dados.tom is not None else classificar_tom_fala(dados.texto, dados.tipo)
    # O tom explícito já foi registrado ao escrever o bloco. Áudios concorrentes
    # não podem sobrescrever o tom de um texto mais recente ao terminarem depois.
    if dados.programa_id is not None and dados.tom is None:
        _registrar_ultimo_tom(dados.programa_id, tom)
    parametros_voz = parametros_sintese(db, account.id, voz_id)

    if not dados.perfil_pos_producao:
        # Streaming corta a cauda de latencia em blocos de fala mais longos (ver Plano B.4): o
        # backend repassa os bytes pro frontend a medida que chegam da ElevenLabs, em vez de
        # baixar o mp3 inteiro antes de comecar a responder. So' da pra usar aqui quando NAO ha
        # perfil de pos-producao pedido -- processar_audio (abaixo) precisa do arquivo completo
        # em memoria pra rodar.
        try:
            gerador = sintetizar_audio_stream(
                dados.texto,
                voz_id,
                tipo_bloco=dados.tipo,
                tom=tom,
                **parametros_voz,
                texto_anterior=dados.texto_anterior,
            )
            # puxa o primeiro pedaco AQUI, fora da StreamingResponse -- erro de conexao/rate-limit/
            # autenticacao ainda vira HTTPException normal (ver docstring de sintetizar_audio_stream);
            # depois deste ponto os headers HTTP 200 ja foram escritos e nao da mais pra mudar o status.
            primeiro_pedaco = next(gerador)
        except (httpx.HTTPError, StopIteration):
            # sem isso a excecao (ElevenLabs fora do ar, timeout, voice_id invalido, etc.) sobe crua
            # como 500 sem contexto nenhum -- e o front, ao receber qualquer erro em /tts, cai calado
            # pra voz robotica do navegador (ver useLiveEngine.ts) sem log nenhum indicando o motivo.
            logger.exception(
                "Falha ao sintetizar audio (streaming): radialista_id=%s voz_id=%s eh_clonada=%s",
                radialista_id,
                voz_id,
                parametros_voz["eh_clonada"],
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao gerar audio da fala") from None

        def _corpo_streaming():
            yield primeiro_pedaco
            yield from gerador

        return StreamingResponse(_corpo_streaming(), media_type="audio/mpeg")

    try:
        audio = sintetizar_audio(
            dados.texto,
            voz_id,
            tipo_bloco=dados.tipo,
            tom=tom,
            **parametros_voz,
            texto_anterior=dados.texto_anterior,
        )
    except httpx.HTTPError:
        logger.exception(
            "Falha ao sintetizar audio: radialista_id=%s voz_id=%s eh_clonada=%s",
            radialista_id,
            voz_id,
            parametros_voz["eh_clonada"],
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao gerar audio da fala") from None

    try:
        audio = processar_audio(audio, dados.perfil_pos_producao)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeError, PydubException):
        # PydubException (ex.: CouldntDecodeError) cobre mp3 vazio/corrompido vindo da
        # ElevenLabs -- sem isso a excecao (subclasse direta de Exception, nao RuntimeError)
        # sobe crua como 500 sem log nenhum, em vez do 502 com contexto que RuntimeError ja tinha.
        logger.exception("Falha na pos-producao: radialista_id=%s", radialista_id)
        raise HTTPException(status_code=502, detail="Falha ao processar audio da fala") from None

    # F2: mede o audio final (so' neste caminho, que tem o mp3 inteiro), devolve a duracao num cabecalho,
    # grava a amostra de ritmo da voz e registra o excesso contra o orcamento guardado pelo /proxima. Nao
    # muda texto nem audio: no caminho do painel a fala ja' esta' no historico.
    return Response(content=audio, media_type="audio/mpeg",
                    headers=_medir_audio_tts(db, account, voz_id, dados, audio))


def _medir_audio_tts(db: Session, account: Account, voz_id: str | None, dados: LiveTtsRequest, audio: bytes) -> dict:
    duracao = duracao_mp3_s(audio)
    if duracao is None:
        return {}
    categoria = categoria_ritmo(dados.tipo)
    voz = voz_efetiva(db, account.id, voz_id)
    _registrar_amostra_fala(db, voz, categoria, dados.texto, duracao, audio)
    pendente = ler_orcamento_pendente(dados.programa_id, dados.texto) if dados.programa_id is not None else None
    maximo = float(pendente["max_s"]) if pendente and pendente.get("max_s") else None
    logger.info(
        "live_fala_duracao request_id=%s programa_id=%s tipo=%s origem=tts palavras=%s wpm_usado=%s "
        "estimada_s=%s medida_s=%s max_s=%s excesso_pct=%s ajuste=- fonte=%s aplicado=%s",
        (pendente or {}).get("request_id"), dados.programa_id, dados.tipo, palavras_faladas(dados.texto),
        (pendente or {}).get("wpm_usado"), (pendente or {}).get("estimada_s"), round(duracao, 2), maximo,
        _excesso_pct(duracao, maximo) if maximo else None, (pendente or {}).get("fonte"),
        (pendente or {}).get("aplicar"),
    )
    return {"X-Duracao-Fala-S": f"{duracao:.2f}"}


@router.get("/no-ar", response_model=RadialistaNoArResponse)
def radialista_no_ar(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    """Qual radialista (de todos os ativos da conta) esta na escala agora, se algum
    estiver -- pro indicador "no ar" do painel. Mesma logica de selecao usada pra
    decidir quem atende o WhatsApp (app/whatsapp/webhook.py::_radialista_no_ar), mas
    sem o fallback pro primeiro radialista: aqui, ninguem na escala = ninguem no ar."""
    configs = db.query(RadioConfig).filter_by(account_id=account.id, ativo=True).order_by(RadioConfig.id.asc()).all()
    programas_por_config: dict[int, list[Programa]] = {config.id: [] for config in configs}
    todos_programas = (
        db.query(Programa).filter(Programa.radio_config_id.in_(programas_por_config.keys()), Programa.ativo.is_(True)).all()
        if configs
        else []
    )
    for programa in todos_programas:
        programas_por_config[programa.radio_config_id].append(programa)

    for config in configs:
        programa_atual = encontrar_programa_atual(programas_por_config[config.id], config.timezone)
        if programa_atual is not None:
            return RadialistaNoArResponse(
                no_ar=True,
                radialista_id=config.id,
                radialista_nome=config.nome_locutor,
                programa_id=programa_atual.id,
                programa_nome=programa_atual.nome,
            )
    return RadialistaNoArResponse(no_ar=False)


@router.get("/{radialista_id}/fila/historico", response_model=FilaHistoricoPaginadaResponse)
def historico_fila(
    radialista_id: int,
    pagina: int = 1,
    tamanho_pagina: int = 20,
    atendido: bool | None = None,
    dias: int = 30,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Pedidos de ouvinte (musica/abraco) recebidos via WhatsApp pra esse radialista,
    mais recentes primeiro -- FilaAoVivo nunca e' apagada ao ser consumida (so' marcada
    atendido=True em _proximo_pedido_fila), entao o historico completo fica disponivel."""
    radialista = _buscar_radialista(db, account, radialista_id)

    pagina = max(1, pagina)
    tamanho_pagina = max(1, min(tamanho_pagina, 100))
    dias = max(1, min(dias, 365))

    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)

    base = db.query(FilaAoVivo).filter(FilaAoVivo.radio_config_id == radialista.id, FilaAoVivo.criado_em >= desde)
    if atendido is not None:
        base = base.filter(FilaAoVivo.atendido == atendido)

    total = base.count()
    pedidos = (
        base.order_by(FilaAoVivo.criado_em.desc())
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
        .all()
    )

    return FilaHistoricoPaginadaResponse(
        pedidos=pedidos,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=max(1, math.ceil(total / tamanho_pagina)),
    )
