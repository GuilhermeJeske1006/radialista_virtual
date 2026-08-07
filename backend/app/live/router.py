import datetime
import random
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.live.music import MusicaEncontrada, buscar_musica, buscar_musica_fundo
from app.llm.client import gerar_resposta
from app.llm.prompt_builder import montar_system_prompt
from app.models.account import Account
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.tts.client import sintetizar_audio, tts_habilitado
from app.tts.voices import voz_valida

router = APIRouter(prefix="/live", tags=["live"])


class LiveProgramRequest(BaseModel):
    historico: list[str] = Field(default_factory=list)


class LiveTtsRequest(BaseModel):
    texto: str
    tipo: str | None = None
    voz_id: str | None = None


class MusicaBlocoItem(BaseModel):
    video_id: str
    titulo: str


class LiveProgramResponse(BaseModel):
    tipo: str
    fala: str
    criado_em: datetime.datetime
    video_id: str | None = None
    titulo_musica: str | None = None
    musicas: list[MusicaBlocoItem] = Field(default_factory=list)
    programa_atual: str | None = None
    patrocinador_id: int | None = None
    patrocinador_audio: bool = False
    patrocinador_voz_id: str | None = None


class MusicaFundoResponse(BaseModel):
    video_id: str
    titulo: str


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


_ROTEIRO_PADRAO = ["musica", "abertura", "comentario", "noticia", "chamada_ouvinte"]

_DESCRICAO_BLOCO = {
    "abertura": "abertura do bloco: recebe o ouvinte, marca o início de um novo momento do programa",
    "musica": "chamada de música: anuncia a faixa que vai tocar em seguida",
    "comentario": "comentário: fala mais pausada e reflexiva sobre um assunto permitido",
    "noticia": "notícia: fala mais serena e informativa sobre um fato permitido",
    "chamada_ouvinte": "chamada ao ouvinte: convite ou recado, tom próximo e caloroso",
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
}


def _tipo_proximo_bloco(programa: Programa, total_falas: int) -> str:
    """Decide o tipo do proximo bloco.

    Sem estrutura customizada: mantem o comportamento padrao (abertura so pode vir logo depois de
    um bloco de musica, excecao pra abertura de largada do programa). Com estrutura customizada
    (programa.estrutura_blocos), segue exatamente a sequencia definida pelo usuario, em loop.
    """
    roteiro_customizado = [t.strip() for t in programa.estrutura_blocos if t.strip()]
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


_PATROCINADOR_RE = re.compile(r"^patrocinador:(\d+)$")


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


def _montar_bloco_musicas(programa: Programa, primeira: MusicaEncontrada, quantidade: int) -> list[MusicaEncontrada]:
    musicas = [primeira]
    usados = {primeira.video_id}
    tentativas = 0
    while len(musicas) < quantidade and tentativas < quantidade * 3:
        tentativas += 1
        extra = _buscar_musica_para_bloco(programa)
        if extra is None:
            break
        if extra.video_id in usados:
            continue
        musicas.append(extra)
        usados.add(extra.video_id)
    return musicas


def _buscar_musica_para_bloco(programa: Programa) -> MusicaEncontrada | None:
    if programa.musicas_permitidas:
        query = random.choice(programa.musicas_permitidas)
    elif programa.generos_musicais:
        query = f"{random.choice(programa.generos_musicais)} musica"
    else:
        query = "musica instrumental"

    return buscar_musica(query, bloqueados=programa.musicas_bloqueadas)


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
    tipo = _tipo_proximo_bloco(programa, len(dados.historico))

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

    if tipo == "noticia" and not (programa.pode_pesquisar or programa.tipos_noticias or programa.fontes_noticias):
        # Sem fonte de noticia configurada: nao arrisca fala vaga/incerta, toca musica direto.
        tipo = "musica"
    historico = "\n".join(dados.historico[-6:]) or "Programa acabou de entrar no ar."

    pedido_musica = _proximo_pedido_fila(db, radialista, "musica") if tipo == "musica" else None
    if pedido_musica is not None:
        query = pedido_musica.musica_query or pedido_musica.mensagem_usuario
        musica = buscar_musica(query, bloqueados=programa.musicas_bloqueadas)
    else:
        musica = _buscar_musica_para_bloco(programa) if tipo == "musica" else None

    pedido_abraco = _proximo_pedido_fila(db, radialista, "abraco") if tipo == "chamada_ouvinte" else None

    roteiro_ativo = [t.strip() for t in programa.estrutura_blocos if t.strip()] or _ROTEIRO_PADRAO

    def _descricao(t: str) -> str:
        return _DESCRICAO_BLOCO.get(t, f"bloco livre '{t}'")

    posicao_roteiro = ", ".join(
        f"{i + 1}) {_descricao(t)}" + (" <- bloco atual" if t == tipo else "")
        for i, t in enumerate(roteiro_ativo)
    )

    system_prompt_linhas = [
        montar_system_prompt(account, radialista, programa),
        "Você também apresenta um programa de rádio ao vivo dentro do painel.",
        "Gere somente a fala do locutor, sem aspas, sem markdown e sem narração externa.",
        "A fala deve ter entre 4 e 6 frases curtas, com ritmo de rádio e transições naturais.",
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
            tipo,
            f"Este bloco é '{tipo}': ajuste tom e ritmo conforme o conteúdo, mantendo a identidade do programa.",
        ),
        "Além do tipo do bloco, varie intensidade dentro da própria fala conforme o conteúdo: acelere e encurte "
        "frases em partes animadas ou de efeito, desacelere com vírgulas e reticências em partes que pedem mais "
        "reflexão ou peso -- não mantenha o mesmo ritmo do início ao fim da fala.",
        "Quando o bloco for notícia, comente apenas notícias dos tipos e fontes permitidas.",
        "Nunca use tom de incerteza ou promessa vaga tipo 'quando pintar novidade confirmada eu aviso' ou "
        "'se tiver algo eu passo aqui depois' -- fale com convicção sobre o que souber, e se não tiver "
        "conteúdo sólido pro bloco, mantenha a fala curta e direta em vez de enrolar.",
        "Quando o bloco for comentário, escolha um assunto diferente do último comentado no histórico.",
        "Se pesquisa externa estiver desabilitada, não invente fatos recentes: faça chamadas gerais e atemporais.",
    ]
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

    if tipo == "musica" and musica is not None:
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

    system_prompt = "\n".join(system_prompt_linhas)

    mensagem = "\n".join(
        [
            f"Tipo do próximo bloco: {tipo}.",
            "Histórico recente do programa:",
            historico,
            "Crie a próxima fala agora de acordo com a configuração da rádio.",
        ]
    )

    fala = _limpar_fala(gerar_resposta(system_prompt, mensagem))

    musicas_bloco: list[MusicaEncontrada] = []
    if tipo == "musica":
        fala, quantidade = _extrair_quantidade_musicas(fala)
        if musica is not None:
            musicas_bloco = _montar_bloco_musicas(programa, musica, quantidade)

    return LiveProgramResponse(
        tipo=tipo,
        fala=fala,
        criado_em=datetime.datetime.now(datetime.timezone.utc),
        video_id=musica.video_id if musica else None,
        titulo_musica=musica.titulo if musica else None,
        musicas=[MusicaBlocoItem(video_id=m.video_id, titulo=m.titulo) for m in musicas_bloco],
        programa_atual=programa.nome,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma musica de fundo encontrada")

    return MusicaFundoResponse(video_id=musica.video_id, titulo=musica.titulo)


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
    if dados.voz_id and not voz_valida(dados.voz_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voz invalida")
    voz_id = dados.voz_id or radialista.voz_id

    if not tts_habilitado(voz_id):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS nao configurado")

    audio = sintetizar_audio(dados.texto, voz_id, tipo_bloco=dados.tipo)
    return Response(content=audio, media_type="audio/mpeg")
