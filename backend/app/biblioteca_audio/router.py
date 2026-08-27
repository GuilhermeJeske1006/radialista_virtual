import io
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from pydub import AudioSegment
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.account import Account
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.categoria_vinheta import CategoriaVinheta
from app.storage import get_storage

logger = logging.getLogger("radialista.biblioteca_audio")

router = APIRouter(prefix="/biblioteca-audio", tags=["biblioteca-audio"])

_TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024

# Extensao (em minusculo) -> media type usado tanto pra validar upload quanto pra servir o arquivo.
_EXTENSOES_PERMITIDAS = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}


class BibliotecaAudioItemResponse(BaseModel):
    id: int
    nome: str
    categoria_id: int | None
    audio_nome_original: str
    duracao_segundos: int | None
    cor: str | None
    ordem: int
    ativo: bool

    model_config = {"from_attributes": True}


def _buscar_item(db: Session, account: Account, item_id: int) -> BibliotecaAudioItem:
    item = db.query(BibliotecaAudioItem).filter_by(id=item_id, account_id=account.id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item da biblioteca nao encontrado")
    return item


def _validar_categoria(db: Session, account: Account, categoria_id: int | None) -> int | None:
    if categoria_id is None:
        return None
    categoria = db.query(CategoriaVinheta).filter_by(id=categoria_id, account_id=account.id).first()
    if categoria is None or categoria.tipo != "biblioteca":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoria invalida")
    return categoria_id


def _duracao_segundos(conteudo: bytes) -> int | None:
    try:
        segmento = AudioSegment.from_file(io.BytesIO(conteudo))
        return round(segmento.duration_seconds)
    except Exception:
        logger.warning("Falha ao calcular duracao do audio da biblioteca", exc_info=True)
        return None


async def _salvar_audio(arquivo: UploadFile, account_id: int) -> tuple[str, str, int | None]:
    """Valida e grava o arquivo no disco. Devolve (audio_path relativo, nome original, duracao_segundos)."""
    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in _EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de audio nao suportado. Use: {', '.join(_EXTENSOES_PERMITIDAS)}",
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de audio vazio")
    if len(conteudo) > _TAMANHO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo de audio maior que 15MB",
        )

    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    audio_path = f"biblioteca_audio/{account_id}/{nome_arquivo}"
    get_storage().save(audio_path, conteudo)

    duracao = _duracao_segundos(conteudo)
    return audio_path, (arquivo.filename or nome_arquivo), duracao


def _remover_audio(audio_path: str | None) -> None:
    if not audio_path:
        return
    get_storage().delete(audio_path)


@router.get("", response_model=list[BibliotecaAudioItemResponse])
def listar_itens(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return (
        db.query(BibliotecaAudioItem)
        .filter_by(account_id=account.id)
        .order_by(BibliotecaAudioItem.categoria_id, BibliotecaAudioItem.ordem, BibliotecaAudioItem.nome)
        .all()
    )


@router.post("", response_model=BibliotecaAudioItemResponse, status_code=status.HTTP_201_CREATED)
async def criar_item(
    nome: str = Form(...),
    categoria_id: int | None = Form(None),
    cor: str | None = Form(None),
    arquivo: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    item = BibliotecaAudioItem(
        account_id=account.id, nome=nome, categoria_id=_validar_categoria(db, account, categoria_id), cor=cor or None
    )
    item.audio_path, item.audio_nome_original, item.duracao_segundos = await _salvar_audio(arquivo, account.id)

    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info("Item de biblioteca de audio criado: id=%s account_id=%s", item.id, account.id)
    return item


@router.put("/{item_id}", response_model=BibliotecaAudioItemResponse)
async def atualizar_item(
    item_id: int,
    nome: str = Form(...),
    categoria_id: int | None = Form(None),
    cor: str | None = Form(None),
    ordem: int = Form(0),
    ativo: bool = Form(True),
    arquivo: UploadFile | None = File(None),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    item = _buscar_item(db, account, item_id)

    item.nome = nome
    item.categoria_id = _validar_categoria(db, account, categoria_id)
    item.cor = cor or None
    item.ordem = ordem
    item.ativo = ativo

    if arquivo is not None:
        _remover_audio(item.audio_path)
        item.audio_path, item.audio_nome_original, item.duracao_segundos = await _salvar_audio(arquivo, account.id)

    db.commit()
    db.refresh(item)
    logger.info("Item de biblioteca de audio atualizado: id=%s account_id=%s", item.id, account.id)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_item(
    item_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    item = _buscar_item(db, account, item_id)
    _remover_audio(item.audio_path)
    db.delete(item)
    db.commit()
    logger.info("Item de biblioteca de audio excluido: id=%s account_id=%s", item_id, account.id)


@router.get("/{item_id}/audio")
def obter_audio_item(
    item_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    item = _buscar_item(db, account, item_id)

    conteudo = get_storage().read(item.audio_path)
    if conteudo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de audio nao encontrado")

    media_type = _EXTENSOES_PERMITIDAS.get(Path(item.audio_path).suffix.lower(), "application/octet-stream")
    return Response(content=conteudo, media_type=media_type)
