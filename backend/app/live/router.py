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
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.tts.client import sintetizar_audio, tts_habilitado

router = APIRouter(prefix="/live", tags=["live"])


class LiveProgramRequest(BaseModel):
    historico: list[str] = Field(default_factory=list)


class LiveTtsRequest(BaseModel):
    texto: str
    tipo: str | None = None


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
    "abertura": "abertura do bloco: recebe o ouvinte, marca o inicio de um novo momento do programa",
    "musica": "chamada de musica: anuncia a faixa que vai tocar em seguida",
    "comentario": "comentario: fala mais pausada e reflexiva sobre um assunto permitido",
    "noticia": "noticia: fala mais serena e informativa sobre um fato permitido",
    "chamada_ouvinte": "chamada ao ouvinte: convite ou recado, tom proximo e caloroso",
}

_PROSODIA_BLOCO = {
    "abertura": (
        "Este bloco e a ABERTURA: acentue mais essa fala. Frases curtas e animadas, uma leve exclamacao "
        "no cumprimento inicial pra marcar energia, ritmo mais rapido que o normal."
    ),
    "musica": (
        "Este bloco e a CHAMADA DE MUSICA: acentue o anuncio da faixa, com empolgacao genuina, "
        "ritmo um pouco mais rapido bem na hora de chamar a musica."
    ),
    "comentario": (
        "Este bloco e um COMENTARIO: fale mais devagar e pausado, como quem esta pensando alto. "
        "Use reticencias e virgulas pra marcar respiracao entre as ideias, sem pressa."
    ),
    "noticia": (
        "Este bloco e uma NOTICIA: tom mais serio e sereno, ritmo mais lento que o normal, "
        "pausas claras (reticencias/virgulas) entre fato e comentario."
    ),
    "chamada_ouvinte": (
        "Este bloco e a CHAMADA AO OUVINTE: tom caloroso e proximo, ritmo normal a levemente mais rapido, "
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
        "Voce tambem apresenta um programa de radio ao vivo dentro do painel.",
        "Gere somente a fala do locutor, sem aspas, sem markdown e sem narracao externa.",
        "A fala deve ter entre 4 e 6 frases curtas, com ritmo de radio e transicoes naturais.",
        "Fale como locutor de verdade, nao como texto escrito: use reticencias para pausas de respiracao, "
        "virgulas para dar ritmo, e de vez em quando um maneirismo natural (\"entao\", \"olha so\", \"e ai\", "
        "\"po\") no comeco da frase. Nao exagere, no maximo um por fala.",
        f"O programa segue esta sequencia logica de blocos, em loop: {posicao_roteiro}. "
        "Tenha consciencia de qual momento do programa voce esta vivendo agora e conecte a fala com o que "
        "vem antes e depois dela, mantendo transicao natural (nao repita a mesma abertura ou o mesmo gancho "
        "toda vez).",
        "Ao citar a identificacao da radio (nome, frequencia, slogan) pra fechar ou emendar uma fala, nunca "
        "repita a mesma frase pronta do bloco anterior (ex: sempre 'Fica comigo na 87,5 FM, a Radio da sua "
        "cidade'). Varie a construcao a cada vez -- troque a ordem das informacoes, use so parte delas, mude o "
        "verbo de chamada ('toca com a gente', 'aqui e a', 'voce ta na', 'segue ligado na'), ou nem cite a "
        "identificacao nessa fala. Trate isso como qualquer outro gancho: repeticao literal soa de robo.",
        "Ao mudar de topico dentro da fala ou encerrar o bloco pra entrar no proximo, marque uma pausa mais "
        "longa que o normal: use reticencias duplas (\"......\") ou um respiro curto antes de virar o assunto, "
        "em vez de emendar direto.",
        _PROSODIA_BLOCO.get(
            tipo,
            f"Este bloco e '{tipo}': ajuste tom e ritmo conforme o conteudo, mantendo a identidade do programa.",
        ),
        "Alem do tipo do bloco, varie intensidade dentro da propria fala conforme o conteudo: acelere e encurte "
        "frases em partes animadas ou de efeito, desacelere com virgulas e reticencias em partes que pedem mais "
        "reflexao ou peso -- nao mantenha o mesmo ritmo do inicio ao fim da fala.",
        "Quando o bloco for noticia, comente apenas noticias dos tipos e fontes permitidas.",
        "Nunca use tom de incerteza ou promessa vaga tipo 'quando pintar novidade confirmada eu aviso' ou "
        "'se tiver algo eu passo aqui depois' -- fale com convicao sobre o que souber, e se nao tiver "
        "conteudo solido pro bloco, mantenha a fala curta e direta em vez de enrolar.",
        "Quando o bloco for comentario, escolha um assunto diferente do ultimo comentado no historico.",
        "Se pesquisa externa estiver desabilitada, nao invente fatos recentes: faca chamadas gerais e atemporais.",
    ]
    if musica is not None and pedido_musica is not None:
        nome_pedido = pedido_musica.nome or "um ouvinte"
        system_prompt_linhas.append(
            f"Quando o bloco for musica, anuncie que {nome_pedido} pediu pelo WhatsApp a musica "
            f"'{musica.titulo}' de '{musica.canal}', que sera tocada ao vivo em seguida. Nao anuncie outra musica."
        )
    elif musica is not None:
        system_prompt_linhas.append(
            f"Quando o bloco for musica, anuncie exatamente a musica '{musica.titulo}' de '{musica.canal}', "
            "que sera tocada ao vivo em seguida. Nao anuncie outra musica."
        )
    else:
        system_prompt_linhas.append(
            "Quando o bloco for musica, anuncie uma musica/artista permitido ou um genero permitido "
            "(nenhuma faixa foi encontrada para tocar ao vivo agora)."
        )

    if tipo == "musica" and musica is not None:
        system_prompt_linhas.append(
            "Se sentir que o momento pede embalar o programa sem interrupcao, voce pode emendar mais musicas "
            "em seguida, sem falar entre uma e outra (tipo um bloco de duas ou tres). So faca isso de vez em "
            "quando, quando fizer sentido pro clima (nao sempre). Se decidir emendar, termine sua fala, em uma "
            "linha separada e sozinha, com a tag [BLOCO_MUSICAS:2] ou [BLOCO_MUSICAS:3] conforme a quantidade "
            "total de musicas do bloco (incluindo a que voce ja anunciou). Se for tocar so uma musica dessa vez, "
            "nao inclua nenhuma tag."
        )

    if pedido_abraco is not None:
        nome_ouvinte = pedido_abraco.nome or "um ouvinte"
        system_prompt_linhas.append(
            f"Quando o bloco for chamada_ouvinte, mande um alo pra {nome_ouvinte}: cumprimente pelo nome e "
            f"comente em poucas palavras o que ele mandou pelo WhatsApp: \"{pedido_abraco.mensagem_usuario}\"."
        )
    else:
        system_prompt_linhas.append(
            "Quando o bloco for chamada_ouvinte, convide o publico a mandar recado ou pedido de musica "
            "no WhatsApp da radio."
        )

    system_prompt = "\n".join(system_prompt_linhas)

    mensagem = "\n".join(
        [
            f"Tipo do proximo bloco: {tipo}.",
            "Historico recente do programa:",
            historico,
            "Crie a proxima fala agora de acordo com a configuracao da radio.",
        ]
    )

    fala = gerar_resposta(system_prompt, mensagem).strip()

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
    if not tts_habilitado(radialista.voz_id):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS nao configurado")

    audio = sintetizar_audio(dados.texto, radialista.voz_id, tipo_bloco=dados.tipo)
    return Response(content=audio, media_type="audio/mpeg")
