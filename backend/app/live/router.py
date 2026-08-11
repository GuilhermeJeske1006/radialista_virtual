import datetime
import json
import logging
import random
import re
import unicodedata
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.redis_client import redis_client
from app.db.database import get_db
from app.guardrails.schedule import minutos_restantes
from app.live.music import MusicaEncontrada, buscar_musica, buscar_musica_fundo
from app.llm.client import (
    classificar_categoria_bloco,
    classificar_tema_fala,
    classificar_tom_fala,
    gerar_configuracao,
    gerar_resposta,
    resumir_contexto_musica,
)
from app.llm.json_utils import extrair_json
from app.llm.prompt_builder import ParticipantePrograma, montar_system_prompt
from app.models.account import Account
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.musica_historico import MusicaHistorico
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.tts.client import sintetizar_audio, tts_habilitado
from app.tts.voices import voz_valida_para_conta

logger = logging.getLogger("radialista.live")

router = APIRouter(prefix="/live", tags=["live"])


class LiveProgramRequest(BaseModel):
    historico: list[str] = Field(default_factory=list)
    # Contagem real de falas ja geradas nesta transmissao -- "historico" manda so
    # as ultimas 8 pra nao pesar o prompt, entao nao da pra usar len(historico)
    # pra achar a posicao no roteiro (trava sempre no mesmo bloco depois da 8a fala).
    total_falas: int | None = None


class LiveTtsRequest(BaseModel):
    texto: str
    tipo: str | None = None
    voz_id: str | None = None


class MusicaBlocoItem(BaseModel):
    video_id: str
    titulo: str
    inicio_segundos: int = 0
    fim_segundos: int | None = None


class FalaItem(BaseModel):
    radio_config_id: int
    nome_locutor: str
    voz_id: str | None
    texto: str


class LiveProgramResponse(BaseModel):
    tipo: str
    fala: str
    criado_em: datetime.datetime
    video_id: str | None = None
    titulo_musica: str | None = None
    inicio_segundos: int = 0
    fim_segundos: int | None = None
    musicas: list[MusicaBlocoItem] = Field(default_factory=list)
    programa_atual: str | None = None
    patrocinador_id: int | None = None
    patrocinador_audio: bool = False
    patrocinador_voz_id: str | None = None
    # Preenchido só quando o programa tem mais de um radialista (ver ProgramaRadialista):
    # diálogo alternado, uma linha por participante, cada uma com sua própria voz.
    falas: list[FalaItem] | None = None


class MusicaFundoResponse(BaseModel):
    video_id: str
    titulo: str
    inicio_segundos: int = 0
    fim_segundos: int | None = None


def _buscar_radialista(db: Session, account: Account, radialista_id: int) -> RadioConfig:
    config = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radialista nao encontrado")
    return config


def _buscar_programa(db: Session, radialista: RadioConfig, programa_id: int) -> Programa:
    programa = db.query(Programa).filter_by(id=programa_id, radio_config_id=radialista.id).first()
    if programa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa nao encontrado")
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
        )

    dono = _participante(programa.radio_config_id)
    roster = [dono] if dono else []
    for radio_config_id in vinculo_por_radialista:
        if radio_config_id == programa.radio_config_id:
            continue
        participante = _participante(radio_config_id)
        if participante is not None:
            roster.append(participante)
    return roster


_ROTEIRO_PADRAO = ["musica", "abertura", "comentario", "noticia", "chamada_ouvinte"]

# Quantos minutos antes do horario_fim do programa a fala vira encerramento
# em vez de seguir o roteiro normal.
_LIMIAR_ENCERRAMENTO_MIN = 3

# Chance de, numa fala qualquer, o locutor mencionar a hora certa.
_PROB_HORA_CERTA = 0.2

_DESCRICAO_BLOCO = {
    "abertura": "abertura do bloco: recebe o ouvinte, marca o início de um novo momento do programa",
    "musica": "chamada de música: anuncia a faixa que vai tocar em seguida",
    "comentario": "comentário: fala mais pausada e reflexiva sobre um assunto permitido",
    "noticia": "notícia: fala mais serena e informativa sobre um fato permitido",
    "chamada_ouvinte": "chamada ao ouvinte: convite ou recado, tom próximo e caloroso",
    "encerramento": "encerramento do programa: despedida final, agradece o ouvinte e fecha a transmissão",
}

_PROSODIA_BLOCO = {
    "abertura": (
        "Este bloco é a ABERTURA: acentue mais essa fala. Frases curtas e animadas, uma leve exclamação "
        "no cumprimento inicial pra marcar energia, ritmo mais rápido que o normal."
    ),
    "musica": (
        "Este bloco é a CHAMADA DE MÚSICA: acentue o anúncio da faixa, com empolgação genuína, "
        "ritmo um pouco mais rápido bem na hora de chamar a música."
    ),
    "comentario": (
        "Este bloco é um COMENTÁRIO: fale mais devagar e pausado, como quem está pensando alto. "
        "Use reticências e vírgulas pra marcar respiração entre as ideias, sem pressa."
    ),
    "noticia": (
        "Este bloco é uma NOTÍCIA: tom mais sério e sereno, ritmo mais lento que o normal, "
        "pausas claras (reticências/vírgulas) entre fato e comentário."
    ),
    "chamada_ouvinte": (
        "Este bloco é a CHAMADA AO OUVINTE: tom caloroso e próximo, ritmo normal a levemente mais rápido, "
        "acentue o nome do ouvinte quando houver."
    ),
    "encerramento": (
        "Este bloco é o ENCERRAMENTO do programa: tom caloroso e grato, ritmo mais calmo que o normal, "
        "feche com uma despedida clara, sem deixar no ar."
    ),
}


def _tipo_proximo_bloco(programa: Programa, total_falas: int) -> str:
    """Decide o tipo do proximo bloco.

    Sem estrutura customizada: mantem o comportamento padrao (abertura so pode vir logo depois de
    um bloco de musica, excecao pra abertura de largada do programa). Com estrutura customizada
    (programa.estrutura_blocos), segue exatamente a sequencia definida pelo usuario, em loop.

    "encerramento" nunca sai daqui: so e' liberado quando o programa esta' de fato terminando
    (ver perto_do_fim em gerar_proxima_fala). Se o usuario incluiu "encerramento" no meio da
    estrutura customizada, esse item e' ignorado no loop e a sequencia volta pro inicio.
    """
    roteiro_customizado = [
        t.strip() for t in programa.estrutura_blocos if t.strip() and _categoria_bloco(t) != "encerramento"
    ]
    if not roteiro_customizado:
        if total_falas == 0:
            return "abertura"
        return _ROTEIRO_PADRAO[(total_falas - 1) % len(_ROTEIRO_PADRAO)]

    tipo = roteiro_customizado[total_falas % len(roteiro_customizado)]
    if programa.ia_pode_adicionar_blocos and total_falas > 0 and random.random() < 0.15:
        # IA fica livre pra emendar um comentario extra fora da sequencia pre-definida de vez em quando.
        return "comentario"
    return tipo


_MARKDOWN_ENFASE = re.compile(r"(\*\*|\*|__|_|`)")
_ESPACO_ANTES_PONTUACAO = re.compile(r"\s+([,.;:!?])")
_ESPACOS_REPETIDOS = re.compile(r"[ \t]{2,}")


def _limpar_fala(fala: str) -> str:
    """Remove artefatos que o LLM às vezes deixa escapar (aspas envolvendo a fala
    inteira, ênfase em markdown, espaço solto antes de pontuação) antes de mandar
    pro TTS -- o prompt pede pra não usar essas coisas, mas nada garantia isso.
    """
    texto = fala.strip()
    if len(texto) >= 2 and texto[0] in "\"'" and texto[-1] == texto[0]:
        texto = texto[1:-1].strip()
    texto = _MARKDOWN_ENFASE.sub("", texto)
    texto = _ESPACO_ANTES_PONTUACAO.sub(r"\1", texto)
    texto = _ESPACOS_REPETIDOS.sub(" ", texto)
    return texto.strip()


_NUMERO_POR_EXTENSO = (
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
    "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove",
)
_DEZENA_POR_EXTENSO = {2: "vinte", 3: "trinta", 4: "quarenta", 5: "cinquenta"}


def _numero_0_59_por_extenso(numero: int) -> str:
    if numero < 20:
        return _NUMERO_POR_EXTENSO[numero]
    dezena, resto = divmod(numero, 10)
    palavra = _DEZENA_POR_EXTENSO[dezena]
    return f"{palavra} e {_NUMERO_POR_EXTENSO[resto]}" if resto else palavra


def _hora_certa_por_extenso(agora: datetime.datetime) -> str:
    """Hora atual por extenso (ex.: 'catorze e trinta e cinco') pra injetar no prompt --
    nunca em algarismo, porque o texto vai direto pro TTS e algarismo lido em portugues
    e' onde o sintetizador mais erra (ver _LANGUAGE_CODE em app.tts.client).
    """
    hora_extenso = _numero_0_59_por_extenso(agora.hour)
    if agora.hour == 1:
        hora_extenso = "uma"  # "horas" e' feminino: "uma hora", nao "um hora"
    if agora.minute == 0:
        return f"{hora_extenso} horas em ponto"
    return f"{hora_extenso} e {_numero_0_59_por_extenso(agora.minute)}"


# TTL generico p/ estado de sessao ao vivo no Redis (historico de musica, historico de temas,
# rotacao de frases). 6h cobre uma transmissao inteira sem acumular lixo de sessoes antigas.
_TTL_SESSAO_AO_VIVO = 6 * 60 * 60


def _historico_musicas(programa_id: int) -> tuple[set[str], dict[str, int]]:
    """Musicas tocadas no programa (por sessao ao vivo), pra buscar_musica evitar repetir a
    mesma faixa ou saturar de um so' artista (ver limite_por_canal em app.live.music)."""
    ids = redis_client.smembers(f"musicas_tocadas:ids:{programa_id}")
    canais_raw = redis_client.hgetall(f"musicas_tocadas:canais:{programa_id}")
    return set(ids), {canal: int(contagem) for canal, contagem in canais_raw.items()}


def _registrar_musica_tocada(programa_id: int, musica: MusicaEncontrada) -> None:
    chave_ids = f"musicas_tocadas:ids:{programa_id}"
    chave_canais = f"musicas_tocadas:canais:{programa_id}"
    redis_client.sadd(chave_ids, musica.video_id)
    redis_client.expire(chave_ids, _TTL_SESSAO_AO_VIVO)
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


# Quantas falas recentes guardar por categoria de bloco (ver _historico_falas) pra checagem de
# similaridade -- so entre blocos do mesmo tipo, pra abertura de hoje nao ser comparada com
# noticia de ontem (mesmo programa, blocos diferentes tendem a compartilhar vocabulario normal
# da radio sem serem repeticao de verdade).
_MAX_FALAS_HISTORICO_POR_CATEGORIA = 8

# Sobreposicao de palavras (Jaccard) a partir da qual duas falas do mesmo tipo de bloco sao
# tratadas como repeticao. Falas muito curtas (menos que isso de palavras) nao entram na
# checagem -- sobreposicao alta em frase curta e normal, nao indica repeticao.
_LIMIAR_SIMILARIDADE_REPETICAO = 0.6
_MIN_PALAVRAS_SIMILARIDADE = 5

_PONTUACAO_RE = re.compile(r"[^\w\s]")


def _historico_falas(programa_id: int, categoria: str) -> list[str]:
    return redis_client.lrange(f"falas_geradas:{programa_id}:{categoria}", 0, -1)


def _registrar_fala_gerada(programa_id: int, categoria: str, texto: str) -> None:
    chave = f"falas_geradas:{programa_id}:{categoria}"
    redis_client.lpush(chave, texto)
    redis_client.ltrim(chave, 0, _MAX_FALAS_HISTORICO_POR_CATEGORIA - 1)
    redis_client.expire(chave, _TTL_SESSAO_AO_VIVO)


def _palavras_normalizadas(texto: str) -> set[str]:
    sem_acento = _sem_acento(texto.lower())
    sem_pontuacao = _PONTUACAO_RE.sub(" ", sem_acento)
    return {p for p in sem_pontuacao.split() if p}


def _fala_semelhante_no_historico(fala: str, historico_falas: list[str]) -> str | None:
    """Rede de seguranca em runtime: mesmo com as instrucoes de variacao no prompt, o LLM as
    vezes ainda produz uma fala quase igual a uma de varios blocos atras (janela enviada ao
    prompt so cobre as ultimas falas). Compara por sobreposicao de palavras contra o historico
    da sessao pro mesmo tipo de bloco; devolve a fala anterior que colidiu (pra citar no retry),
    ou None se nao achou repeticao.
    """
    palavras_fala = _palavras_normalizadas(fala)
    if len(palavras_fala) < _MIN_PALAVRAS_SIMILARIDADE:
        return None
    for anterior in historico_falas:
        palavras_anterior = _palavras_normalizadas(anterior)
        if len(palavras_anterior) < _MIN_PALAVRAS_SIMILARIDADE:
            continue
        uniao = palavras_fala | palavras_anterior
        if not uniao:
            continue
        similaridade = len(palavras_fala & palavras_anterior) / len(uniao)
        if similaridade >= _LIMIAR_SIMILARIDADE_REPETICAO:
            return anterior
    return None


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


_VARIACOES_CONVITE_OUVINTE = [
    "Quando o bloco for chamada_ouvinte, convide o público a mandar recado pelo WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, convide o público a pedir uma música pelo WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, convide o público a mandar um áudio de voz com recado pelo "
    "WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, pergunte de onde o ouvinte está sintonizando e convide a "
    "responder pelo WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, convide o público a mandar uma dedicatória ou saudação pelo "
    "WhatsApp da rádio.",
]

_VARIACOES_VERBO_IDENTIFICACAO = [
    "toca com a gente",
    "aqui é a",
    "você tá na",
    "segue ligado na",
    "não sai da",
    "cola aqui na",
    "permanece com a gente na",
]


_PATROCINADOR_RE = re.compile(r"^patrocinador:(\d+)$")

# tipos de bloco com comportamento automatico (busca de musica, prosodia, fila do whatsapp).
_TIPOS_COM_COMPORTAMENTO = ("musica", "noticia", "chamada_ouvinte", "abertura", "comentario", "encerramento")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


# cache no Redis (hash, por texto normalizado de bloco) da classificacao via LLM -- so paga a
# chamada uma vez por bloco customizado distinto, mesmo que o ao vivo gere falas pra ele varias
# vezes e mesmo entre workers/instancias diferentes do backend (cache em memoria de processo nao
# seria compartilhado entre eles).
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
        redis_client.hset(_CACHE_CATEGORIA_CUSTOMIZADA, normalizado, categoria)
    return categoria


def _categoria_bloco(tipo: str) -> str:
    """Normaliza o texto do bloco pro tipo base que rege o comportamento automatico.

    Bloco customizado tipo "Musica Vaneira" ou "Música Sertaneja" bate direto pelo prefixo
    (rapido, sem custo de LLM). Bloco customizado sem esse prefixo, tipo "chamame e xote" ou
    "forro pe de serra", nao tem como saber por texto que e um bloco de musica -- por isso cai
    numa classificacao via LLM (cacheada) antes de virar "bloco livre" sem musica nenhuma.
    """
    if _PATROCINADOR_RE.match(tipo):
        return tipo
    tipo = tipo.strip()
    normalizado = _sem_acento(tipo.lower())
    for base in _TIPOS_COM_COMPORTAMENTO:
        if normalizado == base or normalizado.startswith(f"{base} "):
            return base
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


_TAG_BLOCO_MUSICAS = re.compile(r"\[BLOCO_MUSICAS:\s*(\d)\]\s*$")


def _extrair_quantidade_musicas(fala: str) -> tuple[str, int]:
    """Le a tag opcional que o LLM deixa no fim da fala pra emendar mais musicas seguidas."""
    match = _TAG_BLOCO_MUSICAS.search(fala)
    if not match:
        return fala, 1
    quantidade = max(1, min(3, int(match.group(1))))
    return _TAG_BLOCO_MUSICAS.sub("", fala).rstrip(), quantidade


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


def _escolher_query_musica(db: Session, programa: Programa) -> tuple[str, str | None]:
    """Escolhe a query de busca pra um bloco de musica sem rotulo de genero proprio.

    Combina curadoria do admin (musicas_permitidas, pesada pela posicao -- primeiro item da
    lista conta mais) com o que o publico mais pediu de verdade pelo WhatsApp (ver
    _pedidos_publico_mais_frequentes), numa escolha ponderada. So cai pro genero generico da
    radio quando nenhum dos dois tem dado nenhum; e so cai pra instrumental generico quando a
    radio nao configurou genero nenhum. Devolve (query, genero_pra_filtrar) -- genero so vem
    preenchido na queda pro genero generico, porque musica_permitida/pedido do publico ja e'
    uma query especifica o suficiente (nome de musica/artista), nao precisa de filtro extra.
    """
    candidatos: list[str] = []
    pesos: list[float] = []

    total_permitidas = len(programa.musicas_permitidas)
    for indice, item in enumerate(programa.musicas_permitidas):
        candidatos.append(item)
        pesos.append((total_permitidas - indice) * _PESO_POSICAO_ADMIN)

    for query_normalizada, contagem in _pedidos_publico_mais_frequentes(db, programa.id):
        candidatos.append(query_normalizada)
        pesos.append(contagem * _PESO_PEDIDO_PUBLICO)

    if candidatos:
        return random.choices(candidatos, weights=pesos, k=1)[0], None

    if programa.generos_musicais:
        genero = random.choice(programa.generos_musicais)
        return f"{genero} musica", genero

    return "musica instrumental", None


def _normalizar_query_musica(texto: str) -> str:
    return _sem_acento(texto.strip().lower())


def _registrar_historico_persistente(
    db: Session, programa_id: int, musica: MusicaEncontrada, query: str, origem: str
) -> None:
    db.add(
        MusicaHistorico(
            programa_id=programa_id,
            video_id=musica.video_id,
            titulo=musica.titulo,
            canal=musica.canal,
            query=query,
            query_normalizada=_normalizar_query_musica(query),
            origem=origem,
        )
    )
    db.commit()


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
    db: Session, programa: Programa, primeira: MusicaEncontrada, quantidade: int, rotulo_bloco: str | None = None
) -> list[MusicaEncontrada]:
    musicas = [primeira]
    usados = {primeira.video_id}
    tentativas = 0
    while len(musicas) < quantidade and tentativas < quantidade * 3:
        tentativas += 1
        extra = _buscar_musica_para_bloco(db, programa, rotulo_bloco)
        if extra is None:
            break
        if extra.video_id in usados:
            continue
        musicas.append(extra)
        usados.add(extra.video_id)
    return musicas


def _buscar_musica_para_bloco(
    db: Session, programa: Programa, rotulo_bloco: str | None = None
) -> MusicaEncontrada | None:
    genero_bloco = _genero_do_rotulo(rotulo_bloco) if rotulo_bloco else ""
    if genero_bloco and _sem_acento(genero_bloco.lower()) != "musica":
        # rotulo do bloco customizado carrega o proprio genero/estilo (ex.: "Vaneira", "Xote")
        # -- tem prioridade sobre a curadoria generica da radio (e' o sinal mais especifico pra
        # este bloco), e o proprio genero vira filtro de busca (ver genero= em buscar_musica)
        # pra nao deixar o YouTube derivar pra um genero vizinho (xote virando chamame).
        query, genero_filtro = f"{genero_bloco} musica", genero_bloco
    else:
        query, genero_filtro = _escolher_query_musica(db, programa)

    ids_tocadas, canais_tocados = _historico_musicas(programa.id)
    musica = buscar_musica(
        query,
        genero=genero_filtro,
        bloqueados=programa.musicas_bloqueadas,
        evitar_video_ids=ids_tocadas,
        canais_recentes=canais_tocados,
    )
    if musica is None and query.strip().lower() != "musica instrumental":
        # query especifica (curadoria do admin, pedido do publico ou genero/rotulo do bloco) nao
        # achou nada -- sem isso, o locutor recebia instrucao pra anunciar um genero/artista
        # "permitido" mesmo com `musica` None, e a fala saia prometendo uma faixa que nunca
        # tocava (ver ramo `else` do anuncio de musica em gerar_proxima_fala). Tenta mais uma
        # vez com a query mais generica possivel antes de desistir de vez.
        query_fallback = "musica instrumental"
        musica = buscar_musica(
            query_fallback,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            canais_recentes=canais_tocados,
        )
        if musica is not None:
            query = query_fallback
    if musica is not None:
        _registrar_musica_tocada(programa.id, musica)
        _registrar_historico_persistente(db, programa.id, musica, query, origem="auto")
    return musica


def _proximo_pedido_fila(db: Session, radialista: RadioConfig, tipo: str) -> FilaAoVivo | None:
    """Pega (e marca como atendido) o pedido mais antigo da fila vindo do WhatsApp."""
    pedido = (
        db.query(FilaAoVivo)
        .filter_by(radio_config_id=radialista.id, tipo=tipo, atendido=False)
        .order_by(FilaAoVivo.criado_em.asc())
        .first()
    )
    if pedido is not None:
        pedido.atendido = True
        pedido.atendido_em = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    return pedido


@router.post("/{radialista_id}/programas/{programa_id}/proxima", response_model=LiveProgramResponse)
def gerar_proxima_fala(
    radialista_id: int,
    programa_id: int,
    dados: LiveProgramRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    programa = _buscar_programa(db, radialista, programa_id)

    total_falas = dados.total_falas if dados.total_falas is not None else len(dados.historico)

    ja_encerrou = any(linha.startswith("encerramento:") for linha in dados.historico)
    perto_do_fim = minutos_restantes(programa, radialista.timezone) <= _LIMIAR_ENCERRAMENTO_MIN
    if perto_do_fim and not ja_encerrou:
        # Estrutura do programa roda em loop ate' chegar perto do horario_fim --
        # daqui em diante, para o loop e gera a fala de encerramento.
        tipo = "encerramento"
    else:
        tipo = _tipo_proximo_bloco(programa, total_falas)

    if _PATROCINADOR_RE.match(tipo):
        patrocinador = _buscar_patrocinador_ativo(db, account, tipo)
        if patrocinador is not None:
            # Conteudo de patrocinador e fixo (contrato comercial) -- nunca passa pelo LLM.
            return LiveProgramResponse(
                tipo="patrocinador",
                fala=(patrocinador.texto or "").strip(),
                criado_em=datetime.datetime.now(datetime.timezone.utc),
                programa_atual=programa.nome,
                patrocinador_id=patrocinador.id,
                patrocinador_audio=patrocinador.tipo_conteudo == "audio",
                patrocinador_voz_id=patrocinador.voz_id,
            )
        tipo = "comentario"  # patrocinador excluido/desativado -- nao trava o ao vivo

    categoria = _categoria_bloco(tipo)
    if categoria == "noticia" and not (programa.pode_pesquisar or programa.tipos_noticias or programa.fontes_noticias):
        # Sem fonte de noticia configurada: nao arrisca fala vaga/incerta, toca musica direto.
        tipo = "musica"
        categoria = "musica"
    historico = "\n".join(dados.historico[-6:]) or "Programa acabou de entrar no ar."

    # Dialogo multi-voz so pros blocos de fala -- musica e patrocinador (ja retornado acima)
    # continuam single-voice, sempre na voz do dono.
    roster = _buscar_roster(db, account, programa)
    multi_voz = len(roster) > 1 and categoria != "musica"

    pedido_musica = _proximo_pedido_fila(db, radialista, "musica") if categoria == "musica" else None
    pedido_sem_resultado = False
    if pedido_musica is not None:
        query = pedido_musica.musica_query or pedido_musica.mensagem_usuario
        ids_tocadas, canais_tocados = _historico_musicas(programa.id)
        musica = buscar_musica(
            query,
            bloqueados=programa.musicas_bloqueadas,
            evitar_video_ids=ids_tocadas,
            canais_recentes=canais_tocados,
        )
        if musica is not None:
            _registrar_musica_tocada(programa.id, musica)
            # pedido real do ouvinte via WhatsApp -- alimenta o sinal de preferencia do
            # publico (ver _pedidos_publico_mais_frequentes) usado em blocos futuros sem
            # pedido pendente.
            _registrar_historico_persistente(db, programa.id, musica, query, origem="pedido_ouvinte")
        else:
            # _proximo_pedido_fila ja marcou o pedido como atendido antes da busca rodar --
            # sem esse fallback, a musica pedida simplesmente sumia (nada tocava, nada
            # anunciado, ouvinte nunca sabe que o pedido dele nao foi encontrado) porque
            # `musica` ficava None e o bloco caia direto no anuncio generico "nao encontrei
            # nada". Cai pra escolha automatica pra sempre tocar algo neste bloco.
            pedido_sem_resultado = True
            logger.warning(
                "Pedido de musica sem resultado na busca, caindo pra escolha automatica: "
                "programa_id=%s query=%r",
                programa.id,
                query,
            )
            musica = _buscar_musica_para_bloco(db, programa, tipo)
    else:
        musica = _buscar_musica_para_bloco(db, programa, tipo) if categoria == "musica" else None

    pedido_abraco = _proximo_pedido_fila(db, radialista, "abraco") if categoria == "chamada_ouvinte" else None

    temas_usados = _historico_temas(programa.id) if categoria in ("comentario", "noticia") else []
    variacao_verbo_identificacao = _proxima_variacao(
        programa.id, "verbo_identificacao", _VARIACOES_VERBO_IDENTIFICACAO
    )

    roteiro_ativo = [t.strip() for t in programa.estrutura_blocos if t.strip()] or _ROTEIRO_PADRAO

    def _descricao(t: str) -> str:
        return _DESCRICAO_BLOCO.get(_categoria_bloco(t), f"bloco livre '{t}'")

    posicao_roteiro = ", ".join(
        f"{i + 1}) {_descricao(t)}" + (" <- bloco atual" if t == tipo else "")
        for i, t in enumerate(roteiro_ativo)
    )

    introducao_ao_vivo = (
        [
            "Vocês também apresentam este programa de rádio ao vivo dentro do painel.",
            "Gere apenas as falas dos apresentadores, no formato JSON pedido acima -- sem aspas fora do JSON, "
            "sem markdown e sem narração externa.",
            "Cada linha do diálogo deve ter uma ou duas frases curtas, como uma conversa real de rádio entre "
            "os apresentadores, não um monólogo de cada um.",
        ]
        if multi_voz
        else [
            "Você também apresenta um programa de rádio ao vivo dentro do painel.",
            "Gere somente a fala do locutor, sem aspas, sem markdown e sem narração externa.",
            "A fala deve ter entre 4 e 6 frases curtas, com ritmo de rádio e transições naturais.",
        ]
    )

    system_prompt_linhas = [
        montar_system_prompt(account, radialista, programa, roster=roster if multi_voz else None),
        *introducao_ao_vivo,
        "Fale como locutor de verdade, não como texto escrito: use reticências para pausas de respiração, "
        "vírgulas para dar ritmo, e de vez em quando um maneirismo natural (\"então\", \"olha só\", \"e aí\", "
        "\"pô\") no começo da frase. Não exagere, no máximo um por fala.",
        f"O programa segue esta sequência lógica de blocos, em loop: {posicao_roteiro}. "
        "Tenha consciência de qual momento do programa você está vivendo agora e conecte a fala com o que "
        "vem antes e depois dela, mantendo transição natural (não repita a mesma abertura ou o mesmo gancho "
        "toda vez).",
        f"Esta é aproximadamente a fala número {total_falas + 1} desde que o programa entrou no ar, na volta "
        f"{total_falas // len(roteiro_ativo) + 1} da estrutura de blocos acima. Quanto mais alto esse número, "
        "maior a chance de você já ter usado uma piada, gancho ou frase parecida antes -- redobre o cuidado "
        "pra trazer algo com cara nova em vez de cair no automático.",
        "Antes de escrever, releia a última fala do histórico (a mais recente na lista) e identifique um "
        "detalhe concreto nela -- um assunto, um nome, uma palavra, um clima que ficou no ar. Abra ou emende "
        "a fala atual com um gancho real (callback) nesse detalhe, em vez de uma transição genérica tipo "
        "'e agora' ou 'mudando de assunto'. Exemplos: se a última fala foi um comentário sobre trânsito, a "
        "chamada de música seguinte pode puxar 'depois desse papo de trânsito, bora resolver o humor com "
        "essa aqui'; se foi uma notícia sobre o tempo, a próxima abertura pode citar o clima que acabou de "
        "ser mencionado; se foi um pedido de ouvinte, o comentário seguinte pode retomar o nome ou o clima "
        "que ele trouxe. Só deixe de fazer esse gancho quando a última fala não render nada natural pra "
        "puxar (início do programa, ou virada de bloco que exige assunto totalmente novo).",
        "Ao citar a identificação da rádio (nome, frequência, slogan) pra fechar ou emendar uma fala, nunca "
        "repita a mesma frase pronta do bloco anterior (ex: sempre 'Fica comigo na 87,5 FM, a Rádio da sua "
        f"cidade'). Se for citar a identificação nessa fala, prefira o verbo de chamada "
        f"'{variacao_verbo_identificacao}' -- troque a ordem das outras informações, use só parte delas, ou nem "
        "cite a identificação nessa fala. Trate isso como qualquer outro gancho: repetição literal soa de robô.",
        "Ao mudar de tópico dentro da fala ou encerrar o bloco pra entrar no próximo, marque uma pausa mais "
        "longa que o normal: use reticências duplas (\"......\") ou um respiro curto antes de virar o assunto, "
        "em vez de emendar direto.",
        _PROSODIA_BLOCO.get(
            categoria,
            f"Este bloco é '{tipo}': ajuste tom e ritmo conforme o conteúdo, mantendo a identidade do programa.",
        ),
        "Além do tipo do bloco, varie intensidade dentro da própria fala conforme o conteúdo: acelere e encurte "
        "frases em partes animadas ou de efeito, desacelere com vírgulas e reticências em partes que pedem mais "
        "reflexão ou peso -- não mantenha o mesmo ritmo do início ao fim da fala.",
        "Use a pontuação como interpretação, não só como gramática: coloque exclamação (!) exatamente nos "
        "pontos de real empolgação ou efeito, no máximo uma ou duas por fala -- nunca em toda frase. Nas "
        "partes que pedem tom mais ameno, use vírgulas e reticências (...) pra marcar pausa e respiração, "
        "e ponto final simples no resto. A pontuação deve nascer do que a frase está sentindo naquele "
        "momento, não de um padrão fixo repetido em toda fala.",
        "Escreva todo número por extenso em português (ex.: 'catorze e trinta e cinco', 'oitenta e sete "
        "e cinco', 'dois mil e vinte e quatro', 'dezenove reais e noventa'), nunca em algarismo -- isso "
        "vale pra hora, frequência, preço, quantidade, data, telefone ou qualquer outro número que "
        "aparecer na fala. O sintetizador de voz não lê algarismo direito em português.",
        "Quando o bloco for notícia, comente apenas notícias dos tipos e fontes permitidas.",
        "Nunca use tom de incerteza ou promessa vaga tipo 'quando pintar novidade confirmada eu aviso' ou "
        "'se tiver algo eu passo aqui depois' -- fale com convicção sobre o que souber, e se não tiver "
        "conteúdo sólido pro bloco, mantenha a fala curta e direta em vez de enrolar.",
        "Quando o bloco for comentário, escolha um assunto diferente do último comentado no histórico.",
        "Se pesquisa externa estiver desabilitada, não invente fatos recentes: faça chamadas gerais e atemporais.",
        "Nunca soe como se o programa estivesse terminando ou se despedindo (frases tipo 'por hoje é só', "
        "'foi um prazer ficar com vocês', 'até a próxima', 'foi isso por agora') a não ser que o bloco atual "
        "seja o de encerramento -- despedida só é permitida na fala do bloco 'encerramento', em nenhum outro.",
    ]

    if temas_usados:
        system_prompt_linhas.append(
            "Temas de comentário/notícia já abordados nesta transmissão, do mais recente pro mais antigo -- "
            f"não repita nenhum deles agora, escolha um assunto novo: {', '.join(temas_usados)}."
        )

    if tipo != "encerramento" and random.random() < _PROB_HORA_CERTA:
        hora_certa = _hora_certa_por_extenso(datetime.datetime.now(ZoneInfo(radialista.timezone)))
        system_prompt_linhas.append(
            f"Nesta fala, marque a hora certa: mencione naturalmente, em algum ponto, que agora são {hora_certa} "
            "-- como um locutor de verdade faz de vez em quando (ex: 'agora são catorze e trinta e cinco aqui "
            "na rádio', 'são onze horas em ponto nesse sábado quente'). Escreva a hora por extenso, exatamente "
            "como veio acima, nunca em algarismo. Encaixe sem soar forçado, não precisa ser a primeira frase."
        )

    if musica is not None and pedido_musica is not None and pedido_sem_resultado:
        nome_pedido = pedido_musica.nome or "um ouvinte"
        system_prompt_linhas.append(
            f"{nome_pedido} pediu uma música pelo WhatsApp, mas ela não foi encontrada. Quando o bloco for "
            f"música, avise rapidamente que não achou a música pedida e anuncie que vai tocar "
            f"'{musica.titulo}' de '{musica.canal}' no lugar dela. Não anuncie outra música nem prometa "
            "achar a música pedida depois."
        )
    elif musica is not None and pedido_musica is not None:
        nome_pedido = pedido_musica.nome or "um ouvinte"
        system_prompt_linhas.append(
            f"Quando o bloco for música, anuncie que {nome_pedido} pediu pelo WhatsApp a música "
            f"'{musica.titulo}' de '{musica.canal}', que será tocada ao vivo em seguida. Não anuncie outra música."
        )
    elif musica is not None:
        system_prompt_linhas.append(
            f"Quando o bloco for música, anuncie exatamente a música '{musica.titulo}' de '{musica.canal}', "
            "que será tocada ao vivo em seguida. Não anuncie outra música."
        )
    else:
        system_prompt_linhas.append(
            "Nenhuma faixa foi encontrada pra tocar ao vivo agora. Quando o bloco for música, NÃO anuncie "
            "nenhuma música, artista ou gênero específico -- nada vai tocar de verdade nesse bloco, e "
            "anunciar uma faixa que não toca soa quebrado pro ouvinte. Em vez disso, faça uma transição "
            "curta e natural (comentário rápido, chamada pro próximo momento do programa) sem prometer "
            "nenhuma música."
        )

    if musica is not None:
        contexto_musica = _contexto_musica(musica)
        if contexto_musica:
            system_prompt_linhas.append(
                f"Contexto real sobre essa música, pra você citar naturalmente ao anunciar se fizer sentido "
                f"(não force, não é obrigatório usar tudo): {contexto_musica}"
            )

    if categoria == "musica" and musica is not None:
        system_prompt_linhas.append(
            "Se sentir que o momento pede embalar o programa sem interrupção, você pode emendar mais músicas "
            "em seguida, sem falar entre uma e outra (tipo um bloco de duas ou três). Só faça isso de vez em "
            "quando, quando fizer sentido pro clima (não sempre). Se decidir emendar, termine sua fala, em uma "
            "linha separada e sozinha, com a tag [BLOCO_MUSICAS:2] ou [BLOCO_MUSICAS:3] conforme a quantidade "
            "total de músicas do bloco (incluindo a que você já anunciou). Se for tocar só uma música dessa vez, "
            "não inclua nenhuma tag."
        )

    if pedido_abraco is not None:
        nome_ouvinte = pedido_abraco.nome or "um ouvinte"
        system_prompt_linhas.append(
            f"Quando o bloco for chamada_ouvinte, mande um alô pra {nome_ouvinte}: cumprimente pelo nome e "
            f"comente em poucas palavras o que ele mandou pelo WhatsApp: \"{pedido_abraco.mensagem_usuario}\"."
        )
    else:
        system_prompt_linhas.append(
            _proxima_variacao(programa.id, "convite_chamada_ouvinte", _VARIACOES_CONVITE_OUVINTE)
        )

    if categoria == "encerramento":
        system_prompt_linhas.append(
            "Este é o ÚLTIMO bloco do programa de hoje, o programa está terminando agora. Agradeça o "
            "ouvinte pela companhia, resuma em uma frase o clima do programa e se despeça claramente, "
            "sinalizando que a transmissão está encerrando. Não convide a mandar mensagem no WhatsApp, "
            "pedir música ou interagir mais, porque não há mais tempo de ar. Se souber quando o programa "
            "volta (mesmo horário, próximo dia de exibição), convide a voltar; senão, feche sem inventar "
            "data ou horário."
        )

    system_prompt = "\n".join(system_prompt_linhas)

    mensagem = "\n".join(
        [
            f"Tipo do próximo bloco: {tipo}.",
            "Histórico recente do programa:",
            historico,
            "Crie a próxima fala agora de acordo com a configuração da rádio.",
        ]
    )

    def _gerar_falas_bloco(prompt: str) -> tuple[list[FalaItem], str]:
        if not multi_voz:
            return [], _limpar_fala(gerar_resposta(prompt, mensagem))

        resposta_llm = gerar_configuracao(prompt, mensagem)
        try:
            linhas_dialogo = list((extrair_json(resposta_llm) if resposta_llm else {}).get("linhas") or [])
        except (json.JSONDecodeError, TypeError, AttributeError, ValueError):
            logger.warning("Resposta de dialogo multi-voz invalida: programa_id=%s", programa.id)
            linhas_dialogo = []

        roster_por_nome = {_sem_acento(p.radialista.nome_locutor.lower()): p for p in roster}
        falas: list[FalaItem] = []
        for linha in linhas_dialogo:
            texto_linha = _limpar_fala(str(linha.get("texto") or ""))
            if not texto_linha:
                continue
            participante = roster_por_nome.get(_sem_acento(str(linha.get("locutor") or "").lower()), roster[0])
            falas.append(
                FalaItem(
                    radio_config_id=participante.radialista.id,
                    nome_locutor=participante.radialista.nome_locutor,
                    voz_id=participante.radialista.voz_id,
                    texto=texto_linha,
                )
            )
        if falas:
            return falas, " ".join(item.texto for item in falas)
        # LLM nao retornou dialogo em JSON valido -- nao trava o ao vivo, segue com uma fala generica.
        return [], "Seguimos no ar, ja volto com mais uma novidade."

    falas_bloco, fala = _gerar_falas_bloco(system_prompt)

    # Rede de seguranca: se a fala saiu parecida com uma fala recente do mesmo tipo de bloco
    # nesta sessao, tenta gerar de novo uma unica vez com a colisao apontada explicitamente --
    # nao entra em loop pra nao multiplicar custo/latencia por fala.
    historico_falas_categoria = _historico_falas(programa.id, categoria)
    fala_parecida = _fala_semelhante_no_historico(fala, historico_falas_categoria)
    if fala_parecida:
        logger.info(
            "Fala repetitiva detectada, regenerando uma vez: programa_id=%s tipo=%s", programa.id, tipo
        )
        prompt_retry = system_prompt + (
            "\n\nATENÇÃO: a fala que você ia gerar agora ficou muito parecida com esta fala anterior sua, "
            f'já usada nesta transmissão: "{fala_parecida}". Reescreva com conteúdo, palavras e construção '
            "diferentes, mantendo o mesmo tipo de bloco e as regras acima."
        )
        falas_bloco, fala = _gerar_falas_bloco(prompt_retry)

    musicas_bloco: list[MusicaEncontrada] = []
    if categoria == "musica":
        fala, quantidade = _extrair_quantidade_musicas(fala)
        if musica is not None:
            musicas_bloco = _montar_bloco_musicas(db, programa, musica, quantidade, tipo)

    if fala.strip():
        _registrar_fala_gerada(programa.id, categoria, fala)

    if categoria in ("comentario", "noticia") and fala.strip():
        tema = classificar_tema_fala(fala)
        if tema:
            _registrar_tema(programa.id, tema)

    return LiveProgramResponse(
        tipo=tipo,
        fala=fala,
        criado_em=datetime.datetime.now(datetime.timezone.utc),
        video_id=musica.video_id if musica else None,
        titulo_musica=musica.titulo if musica else None,
        inicio_segundos=musica.inicio_segundos if musica else 0,
        fim_segundos=musica.fim_segundos if musica else None,
        musicas=[
            MusicaBlocoItem(
                video_id=m.video_id, titulo=m.titulo, inicio_segundos=m.inicio_segundos, fim_segundos=m.fim_segundos
            )
            for m in musicas_bloco
        ],
        programa_atual=programa.nome,
        falas=falas_bloco or None,
    )


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

    musica = buscar_musica_fundo(programa.generos_musicais, bloqueados=programa.musicas_bloqueadas)
    if musica is None:
        logger.warning("Nenhuma musica de fundo encontrada: programa_id=%s", programa.id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma musica de fundo encontrada")

    return MusicaFundoResponse(
        video_id=musica.video_id,
        titulo=musica.titulo,
        inicio_segundos=musica.inicio_segundos,
        fim_segundos=musica.fim_segundos,
    )


@router.post("/{radialista_id}/tts")
def gerar_audio_fala(
    radialista_id: int,
    dados: LiveTtsRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)

    # Patrocinador pode pedir uma voz especifica (independente da voz do locutor no ar) --
    # ver Patrocinador.voz_id em app/models/patrocinador.py.
    if dados.voz_id and not voz_valida_para_conta(db, account.id, dados.voz_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voz invalida")
    voz_id = dados.voz_id or radialista.voz_id

    if not tts_habilitado(voz_id):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS nao configurado")

    tom = classificar_tom_fala(dados.texto, dados.tipo)
    audio = sintetizar_audio(dados.texto, voz_id, tipo_bloco=dados.tipo, tom=tom)
    return Response(content=audio, media_type="audio/mpeg")
