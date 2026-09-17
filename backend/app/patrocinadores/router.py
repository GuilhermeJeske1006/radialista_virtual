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
from app.llm.client import classificar_tom_fala
from app.models.account import Account
from app.models.categoria_vinheta import CategoriaVinheta
from app.models.patrocinador import Patrocinador
from app.models.radio_config import RadioConfig
from app.postprod.client import processar_audio
from app.storage import get_storage
from app.tts.client import sintetizar_audio, tts_habilitado
from app.tts.profiles import parametros_sintese
from app.tts.voices import voz_valida_para_conta

logger = logging.getLogger("radialista.patrocinadores")

router = APIRouter(prefix="/patrocinadores", tags=["patrocinadores"])

_TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024

# Extensao (em minusculo) -> media type usado tanto pra validar upload quanto pra servir o arquivo.
_EXTENSOES_PERMITIDAS = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}


class PatrocinadorResponse(BaseModel):
    id: int
    nome: str
    categoria_id: int | None
    tipo_conteudo: str
    texto: str | None
    audio_nome_original: str | None
    duracao_segundos: int | None
    voz_id: str | None
    ativo: bool

    model_config = {"from_attributes": True}


def _validar_voz(db: Session, account: Account, voz_id: str | None) -> str | None:
    voz_id = (voz_id or "").strip() or None
    if voz_id is not None and not voz_valida_para_conta(db, account.id, voz_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voz invalida")
    return voz_id


def _validar_categoria(db: Session, account: Account, categoria_id: int | None) -> int | None:
    if categoria_id is None:
        return None
    categoria = db.query(CategoriaVinheta).filter_by(id=categoria_id, account_id=account.id).first()
    if categoria is None or categoria.tipo != "propaganda":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoria invalida")
    return categoria_id


def _buscar_patrocinador(db: Session, account: Account, patrocinador_id: int) -> Patrocinador:
    patrocinador = db.query(Patrocinador).filter_by(id=patrocinador_id, account_id=account.id).first()
    if patrocinador is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patrocinador nao encontrado")
    return patrocinador


def _duracao_segundos(conteudo: bytes) -> int | None:
    try:
        segmento = AudioSegment.from_file(io.BytesIO(conteudo))
        return round(segmento.duration_seconds)
    except Exception:
        logger.warning("Falha ao calcular duracao do audio do patrocinador", exc_info=True)
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
    audio_path = f"patrocinadores/{account_id}/{nome_arquivo}"
    get_storage().save(audio_path, conteudo)

    duracao = _duracao_segundos(conteudo)
    return audio_path, (arquivo.filename or nome_arquivo), duracao


def _remover_audio(audio_path: str | None) -> None:
    if not audio_path:
        return
    get_storage().delete(audio_path)


def _limpar_cache_audio(patrocinador: Patrocinador) -> None:
    for caminho in (patrocinador.audio_cache or {}).values():
        get_storage().delete(caminho)
    patrocinador.audio_cache = None


@router.get("", response_model=list[PatrocinadorResponse])
def listar_patrocinadores(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return db.query(Patrocinador).filter_by(account_id=account.id).order_by(Patrocinador.nome).all()


@router.post("", response_model=PatrocinadorResponse, status_code=status.HTTP_201_CREATED)
async def criar_patrocinador(
    nome: str = Form(...),
    categoria_id: int | None = Form(None),
    tipo_conteudo: str = Form(...),
    texto: str | None = Form(None),
    voz_id: str | None = Form(None),
    arquivo: UploadFile | None = File(None),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if tipo_conteudo not in ("texto", "audio"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tipo_conteudo invalido")

    patrocinador = Patrocinador(
        account_id=account.id,
        nome=nome,
        categoria_id=_validar_categoria(db, account, categoria_id),
        tipo_conteudo=tipo_conteudo,
    )

    if tipo_conteudo == "texto":
        if not texto or not texto.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Texto obrigatorio")
        patrocinador.texto = texto.strip()
        patrocinador.voz_id = _validar_voz(db, account, voz_id)
    else:
        if arquivo is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de audio obrigatorio")
        patrocinador.audio_path, patrocinador.audio_nome_original, patrocinador.duracao_segundos = await _salvar_audio(
            arquivo, account.id
        )

    db.add(patrocinador)
    db.commit()
    db.refresh(patrocinador)
    logger.info("Patrocinador criado: id=%s account_id=%s", patrocinador.id, account.id)
    return patrocinador


@router.put("/{patrocinador_id}", response_model=PatrocinadorResponse)
async def atualizar_patrocinador(
    patrocinador_id: int,
    nome: str = Form(...),
    categoria_id: int | None = Form(None),
    tipo_conteudo: str = Form(...),
    texto: str | None = Form(None),
    voz_id: str | None = Form(None),
    ativo: bool = Form(True),
    arquivo: UploadFile | None = File(None),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if tipo_conteudo not in ("texto", "audio"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tipo_conteudo invalido")

    patrocinador = _buscar_patrocinador(db, account, patrocinador_id)

    patrocinador.nome = nome
    patrocinador.categoria_id = _validar_categoria(db, account, categoria_id)
    patrocinador.ativo = ativo
    patrocinador.tipo_conteudo = tipo_conteudo
    # Qualquer edicao pode mudar texto/voz -- limpa o cache de audio TTS pra nao servir
    # uma leitura antiga (ver audio_cache em app/models/patrocinador.py).
    _limpar_cache_audio(patrocinador)

    if tipo_conteudo == "texto":
        if not texto or not texto.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Texto obrigatorio")
        patrocinador.texto = texto.strip()
        patrocinador.voz_id = _validar_voz(db, account, voz_id)
        _remover_audio(patrocinador.audio_path)
        patrocinador.audio_path = None
        patrocinador.audio_nome_original = None
        patrocinador.duracao_segundos = None
    else:
        if arquivo is not None:
            _remover_audio(patrocinador.audio_path)
            patrocinador.audio_path, patrocinador.audio_nome_original, patrocinador.duracao_segundos = (
                await _salvar_audio(arquivo, account.id)
            )
        elif patrocinador.audio_path is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de audio obrigatorio")
        patrocinador.texto = None
        patrocinador.voz_id = None

    db.commit()
    db.refresh(patrocinador)
    logger.info("Patrocinador atualizado: id=%s account_id=%s", patrocinador.id, account.id)
    return patrocinador


@router.delete("/{patrocinador_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_patrocinador(
    patrocinador_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    patrocinador = _buscar_patrocinador(db, account, patrocinador_id)
    _remover_audio(patrocinador.audio_path)
    _limpar_cache_audio(patrocinador)
    db.delete(patrocinador)
    db.commit()
    logger.info("Patrocinador excluido: id=%s account_id=%s", patrocinador_id, account.id)


@router.get("/{patrocinador_id}/audio")
def obter_audio_patrocinador(
    patrocinador_id: int,
    radialista_id: int | None = None,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    patrocinador = _buscar_patrocinador(db, account, patrocinador_id)

    if patrocinador.tipo_conteudo == "audio":
        if not patrocinador.audio_path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patrocinador sem audio")
        conteudo = get_storage().read(patrocinador.audio_path)
        if conteudo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de audio nao encontrado")
        media_type = _EXTENSOES_PERMITIDAS.get(Path(patrocinador.audio_path).suffix.lower(), "application/octet-stream")
        return Response(content=conteudo, media_type=media_type)

    return _obter_audio_tts_cacheado(db, account, patrocinador, radialista_id)


def _obter_audio_tts_cacheado(
    db: Session, account: Account, patrocinador: Patrocinador, radialista_id: int | None,
) -> Response:
    """Sintetiza (uma unica vez) e serve o audio TTS de um patrocinador tipo_conteudo=="texto".

    Um spot de radio de verdade e' sempre a mesma gravacao -- ao contrario de uma fala qualquer
    do programa, cache aqui e' mais realista que sintese nova a cada exibicao (que varia por
    jitter, ver _aplicar_jitter em app.tts.client), alem de cortar custo/latencia de ElevenLabs
    em toda vez que o bloco toca. Chave do cache e' a voz efetiva: quando o patrocinador nao tem
    voz propria, ele usa a do radialista no ar, que pode diferir entre programas/contas.
    """
    voz_efetiva = patrocinador.voz_id
    if voz_efetiva is None and radialista_id is not None:
        radialista = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
        voz_efetiva = radialista.voz_id if radialista else None

    if not patrocinador.texto or not tts_habilitado(voz_efetiva):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patrocinador sem audio")

    chave_cache = voz_efetiva or "_padrao"
    cache = patrocinador.audio_cache or {}
    caminho_cache = cache.get(chave_cache)
    if caminho_cache:
        conteudo = get_storage().read(caminho_cache)
        if conteudo is not None:
            return Response(content=conteudo, media_type="audio/mpeg")

    parametros_voz = parametros_sintese(db, account.id, voz_efetiva)
    tom = classificar_tom_fala(patrocinador.texto, "patrocinador")
    try:
        audio = sintetizar_audio(patrocinador.texto, voz_efetiva, tipo_bloco="patrocinador", tom=tom, **parametros_voz)
        audio = processar_audio(audio, "radio_fm")
    except Exception:
        logger.exception("Falha ao gerar audio (cache) do patrocinador: id=%s", patrocinador.id)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao gerar audio do patrocinador") from None

    caminho_cache = f"patrocinadores/{account.id}/tts-cache/{patrocinador.id}-{chave_cache}.mp3"
    get_storage().save(caminho_cache, audio)
    patrocinador.audio_cache = {**cache, chave_cache: caminho_cache}
    db.commit()

    return Response(content=audio, media_type="audio/mpeg")
