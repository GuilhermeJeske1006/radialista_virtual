import datetime
import random

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


class LiveProgramResponse(BaseModel):
    tipo: str
    fala: str
    criado_em: datetime.datetime
    video_id: str | None = None
    titulo_musica: str | None = None
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


def _tipo_proximo_bloco(total_falas: int) -> str:
    roteiro = ["abertura", "musica", "comentario", "noticia", "chamada_ouvinte"]
    return roteiro[total_falas % len(roteiro)]


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
    tipo = _tipo_proximo_bloco(len(dados.historico))
    historico = "\n".join(dados.historico[-6:]) or "Programa acabou de entrar no ar."

    pedido_musica = _proximo_pedido_fila(db, radialista, "musica") if tipo == "musica" else None
    if pedido_musica is not None:
        query = pedido_musica.musica_query or pedido_musica.mensagem_usuario
        musica = buscar_musica(query, bloqueados=programa.musicas_bloqueadas)
    else:
        musica = _buscar_musica_para_bloco(programa) if tipo == "musica" else None

    pedido_abraco = _proximo_pedido_fila(db, radialista, "abraco") if tipo == "chamada_ouvinte" else None

    system_prompt_linhas = [
        montar_system_prompt(radialista, programa),
        "Voce tambem apresenta um programa de radio ao vivo dentro do painel.",
        "Gere somente a fala do locutor, sem aspas, sem markdown e sem narracao externa.",
        "A fala deve ter entre 2 e 4 frases curtas, com ritmo de radio e transicoes naturais.",
        "Fale como locutor de verdade, nao como texto escrito: use reticencias para pausas de respiracao, "
        "virgulas para dar ritmo, e de vez em quando um maneirismo natural (\"entao\", \"olha so\", \"e ai\", "
        "\"po\") no comeco da frase. Nao exagere, no maximo um por fala.",
        "Quando o bloco for noticia, comente apenas noticias dos tipos e fontes permitidas.",
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
    return LiveProgramResponse(
        tipo=tipo,
        fala=fala,
        criado_em=datetime.datetime.now(datetime.timezone.utc),
        video_id=musica.video_id if musica else None,
        titulo_musica=musica.titulo if musica else None,
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

    audio = sintetizar_audio(dados.texto, radialista.voz_id)
    return Response(content=audio, media_type="audio/mpeg")
