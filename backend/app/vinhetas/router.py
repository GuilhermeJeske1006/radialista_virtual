"""Rotas das vinhetas geradas por programa e das trilhas delas (ver app/vinhetas/servico.py).

Tudo filtrado por account_id. O audio final de qualquer vinheta (gerada ou upload) tambem sai
em /biblioteca-audio/{id}/audio -- /vinhetas/{id}/audio e' o mesmo arquivo.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.account import Account
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.trilha_vinheta import TrilhaVinheta
from app.storage import get_storage
from app.tts.voices import validar_voz_ou_400
from app.vinhetas import audio
from app.vinhetas.estrutura import inserir_vinhetas_na_estrutura
from app.vinhetas.servico import (
    agendar_processamento,
    criar_vinhetas_com_seguranca,
    excluir_vinhetas,
    mixar_item,
    vinhetas_auto_do_programa,
)
from app.vinhetas.trilha import estilos_do_banco, salvar_trilha, trilha_do_banco

logger = logging.getLogger("radialista.vinhetas")

router = APIRouter(tags=["vinhetas"])

_TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024
_EXTENSOES_TRILHA = {".mp3", ".wav"}


class VinhetaResponse(BaseModel):
    id: int
    nome: str
    programa_id: int | None
    categoria_id: int | None
    papel: str | None
    texto: str | None
    voz_id: str | None
    trilha_id: int | None
    trilha_origem: str | None = None
    volume_trilha_db: float
    usar_trilha: bool
    status: str
    erro_msg: str | None
    origem: str
    ativo: bool
    tem_audio: bool = False
    duracao_segundos: int | None

    model_config = {"from_attributes": True}


class VinhetaUpdate(BaseModel):
    nome: str | None = None
    texto: str | None = Field(default=None, max_length=300)
    voz_id: str | None = None
    ativo: bool | None = None


class RemixRequest(BaseModel):
    volume_trilha_db: float | None = Field(default=None, ge=-24, le=-6)
    usar_trilha: bool | None = None
    trilha_id: int | None = None


class TrilhaBancoRequest(BaseModel):
    estilo: str | None = None


class TrilhaResponse(BaseModel):
    id: int
    programa_id: int | None
    origem: str
    estilo: str | None
    duracao_ms: int | None

    model_config = {"from_attributes": True}


def _resposta(db: Session, item: BibliotecaAudioItem) -> VinhetaResponse:
    resposta = VinhetaResponse.model_validate(item)
    resposta.tem_audio = bool(item.audio_path)
    if item.trilha_id is not None:
        trilha = db.get(TrilhaVinheta, item.trilha_id)
        resposta.trilha_origem = trilha.origem if trilha else None
    return resposta


def _buscar_vinheta(db: Session, account: Account, vinheta_id: int) -> BibliotecaAudioItem:
    item = db.query(BibliotecaAudioItem).filter_by(id=vinheta_id, account_id=account.id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vinheta nao encontrada")
    return item


def _buscar_programa(db: Session, account: Account, programa_id: int) -> Programa:
    programa = (
        db.query(Programa)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(Programa.id == programa_id, RadioConfig.account_id == account.id)
        .first()
    )
    if programa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa nao encontrado")
    return programa


def _buscar_trilha(db: Session, account: Account, trilha_id: int) -> TrilhaVinheta:
    trilha = db.query(TrilhaVinheta).filter_by(id=trilha_id, account_id=account.id).first()
    if trilha is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trilha nao encontrada")
    return trilha


def _remixar_ou_erro(db: Session, item: BibliotecaAudioItem) -> None:
    try:
        mixar_item(db, item)
    except audio.ErroAudio as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Nao foi possivel remixar: {exc}") from None


def _aplicar_trilha_no_programa(db: Session, account: Account, programa: Programa, trilha: TrilhaVinheta) -> list:
    """Troca a trilha das vinhetas automaticas do programa e remixa na hora quem ja tem voz --
    remix e' so' ffmpeg (poucos segundos), sem TTS nem Music API. Quem ainda nao tem voz fica
    com a trilha nova pro job de audio usar."""
    itens = vinhetas_auto_do_programa(db, account.id, programa.id)
    for item in itens:
        item.trilha_id = trilha.id
        item.usar_trilha = True
        if item.voz_path:
            try:
                mixar_item(db, item)
            except audio.ErroAudio:
                logger.warning("Remix com trilha nova falhou: vinheta_id=%s", item.id, exc_info=True)
    db.commit()
    return [_resposta(db, item) for item in itens]


@router.get("/vinhetas", response_model=list[VinhetaResponse])
def listar_vinhetas(
    programa_id: int | None = None,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    consulta = db.query(BibliotecaAudioItem).filter_by(account_id=account.id)
    if programa_id is not None:
        consulta = consulta.filter_by(programa_id=programa_id)
    else:
        consulta = consulta.filter(BibliotecaAudioItem.papel.isnot(None))
    return [_resposta(db, item) for item in consulta.order_by(BibliotecaAudioItem.id).all()]


@router.get("/vinhetas/{vinheta_id}", response_model=VinhetaResponse)
def obter_vinheta(vinheta_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return _resposta(db, _buscar_vinheta(db, account, vinheta_id))


@router.get("/vinhetas/{vinheta_id}/audio")
def obter_audio_vinheta(
    vinheta_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)
):
    item = _buscar_vinheta(db, account, vinheta_id)
    conteudo = get_storage().read(item.audio_path) if item.audio_path else None
    if conteudo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vinheta ainda sem audio")
    return Response(content=conteudo, media_type="audio/mpeg")


@router.put("/vinhetas/{vinheta_id}", response_model=VinhetaResponse)
def atualizar_vinheta(
    vinheta_id: int,
    dados: VinhetaUpdate,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Texto ou voz mudou: regera SO' a voz e remixa com a mesma trilha (sem Music API)."""
    item = _buscar_vinheta(db, account, vinheta_id)
    regerar_voz = False
    if dados.nome is not None and dados.nome.strip():
        item.nome = dados.nome.strip()
    if dados.ativo is not None:
        item.ativo = dados.ativo
    if dados.texto is not None and dados.texto.strip() and dados.texto.strip() != (item.texto or ""):
        item.texto = dados.texto.strip()
        regerar_voz = True
    if "voz_id" in dados.model_fields_set:
        nova_voz = validar_voz_ou_400(db, account, dados.voz_id)
        if nova_voz != item.voz_id:
            item.voz_id = nova_voz
            regerar_voz = True
    if regerar_voz:
        item.status, item.erro_msg = "pendente", None
    db.commit()
    db.refresh(item)
    if regerar_voz:
        agendar_processamento(background_tasks, [item.id], regerar_voz=True)
    return _resposta(db, item)


@router.post("/vinhetas/{vinheta_id}/remixar", response_model=VinhetaResponse)
def remixar_vinheta(
    vinheta_id: int,
    dados: RemixRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """So' remixa a voz seca guardada com a trilha -- nunca chama TTS nem Music API."""
    item = _buscar_vinheta(db, account, vinheta_id)
    if not item.voz_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vinheta ainda nao tem voz gerada")
    if dados.trilha_id is not None:
        item.trilha_id = _buscar_trilha(db, account, dados.trilha_id).id
    if dados.volume_trilha_db is not None:
        item.volume_trilha_db = dados.volume_trilha_db
    if dados.usar_trilha is not None:
        item.usar_trilha = dados.usar_trilha
    _remixar_ou_erro(db, item)
    db.commit()
    db.refresh(item)
    return _resposta(db, item)


@router.delete("/vinhetas/{vinheta_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_vinheta(vinheta_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    item = _buscar_vinheta(db, account, vinheta_id)
    excluir_vinhetas(db, account.id, [item])
    db.commit()
    logger.info("Vinheta excluida: id=%s account_id=%s", vinheta_id, account.id)


@router.post("/programas/{programa_id}/vinhetas/regerar", response_model=list[VinhetaResponse])
def regerar_vinhetas_programa(
    programa_id: int,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Apaga as vinhetas automaticas do programa, gera texto novo e reinsere na estrutura
    (util ao renomear o programa). A trilha atual do programa e' reaproveitada."""
    programa = _buscar_programa(db, account, programa_id)
    radialista = db.get(RadioConfig, programa.radio_config_id)
    itens = criar_vinhetas_com_seguranca(db, account, radialista, programa, background_tasks, substituir=True)
    if not itens:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Nao foi possivel gerar as vinhetas agora")
    return [_resposta(db, item) for item in itens]


@router.post("/programas/{programa_id}/vinhetas/inserir", response_model=list[str])
def inserir_vinhetas_programa(
    programa_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)
):
    """Recoloca as vinhetas automaticas do programa na estrutura (se o usuario tirou)."""
    programa = _buscar_programa(db, account, programa_id)
    estrutura = inserir_vinhetas_na_estrutura(programa, vinhetas_auto_do_programa(db, account.id, programa.id))
    db.commit()
    return estrutura


@router.post("/programas/{programa_id}/trilha/gerar", response_model=list[VinhetaResponse])
def gerar_trilha_programa(
    programa_id: int,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Nova trilha por IA (cai pro banco se a IA estiver desligada/falhar) e remix das vinhetas."""
    programa = _buscar_programa(db, account, programa_id)
    itens = vinhetas_auto_do_programa(db, account.id, programa.id)
    if not itens:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa sem vinhetas")
    for item in itens:
        item.status, item.erro_msg, item.usar_trilha = "pendente", None, True
    db.commit()
    agendar_processamento(background_tasks, [i.id for i in itens], regerar_voz=False, forcar_nova_trilha=True)
    return [_resposta(db, item) for item in itens]


@router.post("/programas/{programa_id}/trilha/banco", response_model=list[VinhetaResponse])
def escolher_trilha_banco(
    programa_id: int,
    dados: TrilhaBancoRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    trilha = trilha_do_banco(db, account.id, programa, dados.estilo)
    if trilha is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banco de trilhas vazio pra esse estilo")
    return _aplicar_trilha_no_programa(db, account, programa, trilha)


@router.post("/programas/{programa_id}/trilha/upload", response_model=list[VinhetaResponse])
async def enviar_trilha_programa(
    programa_id: int,
    arquivo: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Trilha propria (mp3/wav, ate' 15 MB). Quem envia e' responsavel pelo direito de uso --
    o painel avisa isso antes do upload."""
    programa = _buscar_programa(db, account, programa_id)
    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in _EXTENSOES_TRILHA:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato nao suportado. Use: .mp3, .wav")
    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de audio vazio")
    if len(conteudo) > _TAMANHO_MAXIMO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo de audio maior que 15MB")
    try:
        normalizado, duracao_ms = audio.preparar_trilha(conteudo, extensao)
    except audio.ErroAudio:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de audio invalido") from None

    trilha = salvar_trilha(
        db, account.id, programa.id, "upload", normalizado,
        estilo=Path(arquivo.filename or "").stem[:80] or None, duracao_ms=duracao_ms,
    )
    logger.info("Trilha propria enviada: trilha_id=%s programa_id=%s", trilha.id, programa.id)
    return _aplicar_trilha_no_programa(db, account, programa, trilha)


@router.get("/programas/{programa_id}/trilhas", response_model=list[TrilhaResponse])
def listar_trilhas_programa(
    programa_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)
):
    programa = _buscar_programa(db, account, programa_id)
    return (
        db.query(TrilhaVinheta)
        .filter_by(account_id=account.id, programa_id=programa.id)
        .order_by(TrilhaVinheta.id.desc())
        .all()
    )


@router.get("/trilhas/estilos", response_model=dict[str, int])
def listar_estilos_banco(account: Account = Depends(get_current_account)):
    """Estilo do banco local -> quantas trilhas tem nele (0 = botao desabilitado no painel)."""
    return estilos_do_banco()


@router.get("/trilhas/{trilha_id}/audio")
def obter_audio_trilha(trilha_id: int, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    trilha = _buscar_trilha(db, account, trilha_id)
    conteudo = get_storage().read(trilha.audio_path)
    if conteudo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo da trilha nao encontrado")
    return Response(content=conteudo, media_type="audio/mpeg")
