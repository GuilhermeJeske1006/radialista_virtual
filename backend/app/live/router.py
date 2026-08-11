import datetime
import json
import logging
import random
import re
import unicodedata
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.redis_client import redis_client
from app.db.database import get_db
from app.guardrails.schedule import minutos_restantes
from app.live.music import MusicaEncontrada, buscar_musica, buscar_musica_fundo
from app.llm.client import classificar_categoria_bloco, classificar_tom_fala, gerar_configuracao, gerar_resposta
from app.llm.json_utils import extrair_json
from app.llm.prompt_builder import ParticipantePrograma, montar_system_prompt
from app.models.account import Account
from app.models.fila_ao_vivo import FilaAoVivo
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


# Historico de musicas tocadas no programa (por sessao ao vivo), pra buscar_musica evitar
# repetir a mesma faixa ou saturar de um so' artista (ver limite_por_canal em app.live.music).
# TTL de 6h cobre uma transmissao inteira sem acumular lixo de sessoes antigas no Redis.
_TTL_HISTORICO_MUSICA = 6 * 60 * 60


def _historico_musicas(programa_id: int) -> tuple[set[str], dict[str, int]]:
    ids = redis_client.smembers(f"musicas_tocadas:ids:{programa_id}")
    canais_raw = redis_client.hgetall(f"musicas_tocadas:canais:{programa_id}")
    return set(ids), {canal: int(contagem) for canal, contagem in canais_raw.items()}


def _registrar_musica_tocada(programa_id: int, musica: MusicaEncontrada) -> None:
    chave_ids = f"musicas_tocadas:ids:{programa_id}"
    chave_canais = f"musicas_tocadas:canais:{programa_id}"
    redis_client.sadd(chave_ids, musica.video_id)
    redis_client.expire(chave_ids, _TTL_HISTORICO_MUSICA)
    redis_client.hincrby(chave_canais, musica.canal.lower(), 1)
    redis_client.expire(chave_canais, _TTL_HISTORICO_MUSICA)


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


def _montar_bloco_musicas(
    programa: Programa, primeira: MusicaEncontrada, quantidade: int, rotulo_bloco: str | None = None
) -> list[MusicaEncontrada]:
    musicas = [primeira]
    usados = {primeira.video_id}
    tentativas = 0
    while len(musicas) < quantidade and tentativas < quantidade * 3:
        tentativas += 1
        extra = _buscar_musica_para_bloco(programa, rotulo_bloco)
        if extra is None:
            break
        if extra.video_id in usados:
            continue
        musicas.append(extra)
        usados.add(extra.video_id)
    return musicas


def _buscar_musica_para_bloco(programa: Programa, rotulo_bloco: str | None = None) -> MusicaEncontrada | None:
    genero_bloco = _genero_do_rotulo(rotulo_bloco) if rotulo_bloco else ""
    if programa.musicas_permitidas:
        query = random.choice(programa.musicas_permitidas)
    elif genero_bloco and _sem_acento(genero_bloco.lower()) != "musica":
        # rotulo do bloco customizado carrega o proprio genero/estilo (ex.: "Vaneira",
        # "chamame e xote") -- usa isso na busca em vez de cair no genero generico da radio.
        query = f"{genero_bloco} musica"
    elif programa.generos_musicais:
        query = f"{random.choice(programa.generos_musicais)} musica"
    else:
        query = "musica instrumental"

    ids_tocadas, canais_tocados = _historico_musicas(programa.id)
    musica = buscar_musica(
        query,
        bloqueados=programa.musicas_bloqueadas,
        evitar_video_ids=ids_tocadas,
        canais_recentes=canais_tocados,
    )
    if musica is not None:
        _registrar_musica_tocada(programa.id, musica)
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
    else:
        musica = _buscar_musica_para_bloco(programa, tipo) if categoria == "musica" else None

    pedido_abraco = _proximo_pedido_fila(db, radialista, "abraco") if categoria == "chamada_ouvinte" else None

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
        "cidade'). Varie a construção a cada vez -- troque a ordem das informações, use só parte delas, mude o "
        "verbo de chamada ('toca com a gente', 'aqui é a', 'você tá na', 'segue ligado na'), ou nem cite a "
        "identificação nessa fala. Trate isso como qualquer outro gancho: repetição literal soa de robô.",
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
    ]

    if tipo != "encerramento" and random.random() < _PROB_HORA_CERTA:
        hora_certa = _hora_certa_por_extenso(datetime.datetime.now(ZoneInfo(radialista.timezone)))
        system_prompt_linhas.append(
            f"Nesta fala, marque a hora certa: mencione naturalmente, em algum ponto, que agora são {hora_certa} "
            "-- como um locutor de verdade faz de vez em quando (ex: 'agora são catorze e trinta e cinco aqui "
            "na rádio', 'são onze horas em ponto nesse sábado quente'). Escreva a hora por extenso, exatamente "
            "como veio acima, nunca em algarismo. Encaixe sem soar forçado, não precisa ser a primeira frase."
        )

    if musica is not None and pedido_musica is not None:
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
            "Quando o bloco for música, anuncie uma música/artista permitido ou um gênero permitido "
            "(nenhuma faixa foi encontrada para tocar ao vivo agora)."
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
            "Quando o bloco for chamada_ouvinte, convide o público a mandar recado ou pedido de música "
            "no WhatsApp da rádio."
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

    falas_bloco: list[FalaItem] = []
    if multi_voz:
        resposta_llm = gerar_configuracao(system_prompt, mensagem)
        try:
            linhas_dialogo = list((extrair_json(resposta_llm) if resposta_llm else {}).get("linhas") or [])
        except (json.JSONDecodeError, TypeError, AttributeError, ValueError):
            logger.warning("Resposta de dialogo multi-voz invalida: programa_id=%s", programa.id)
            linhas_dialogo = []

        roster_por_nome = {_sem_acento(p.radialista.nome_locutor.lower()): p for p in roster}
        for linha in linhas_dialogo:
            texto_linha = _limpar_fala(str(linha.get("texto") or ""))
            if not texto_linha:
                continue
            participante = roster_por_nome.get(_sem_acento(str(linha.get("locutor") or "").lower()), roster[0])
            falas_bloco.append(
                FalaItem(
                    radio_config_id=participante.radialista.id,
                    nome_locutor=participante.radialista.nome_locutor,
                    voz_id=participante.radialista.voz_id,
                    texto=texto_linha,
                )
            )

    if falas_bloco:
        fala = " ".join(item.texto for item in falas_bloco)
    elif multi_voz:
        # LLM nao retornou dialogo em JSON valido -- nao trava o ao vivo, segue com uma fala generica.
        fala = "Seguimos no ar, ja volto com mais uma novidade."
    else:
        fala = _limpar_fala(gerar_resposta(system_prompt, mensagem))

    musicas_bloco: list[MusicaEncontrada] = []
    if categoria == "musica":
        fala, quantidade = _extrair_quantidade_musicas(fala)
        if musica is not None:
            musicas_bloco = _montar_bloco_musicas(programa, musica, quantidade, tipo)

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
