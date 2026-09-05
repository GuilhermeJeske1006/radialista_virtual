import logging
from io import BytesIO
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.settings import settings
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip, limite_excedido
from app.models.account import Account
from app.models.voz_clonada import VozClonada
from app.planos import limites_do_plano
from app.tts.client import clonar_voz, excluir_voz_clonada, obter_preview_url, renomear_voz
from app.tts.voices import listar_vozes_com_preview

logger = logging.getLogger("radialista.tts")

router = APIRouter(prefix="/tts", tags=["tts"])

_TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024
# Instant Voice Cloning fica bem menos fiel a voz original com amostra curta demais -- 20s e' um
# piso pra barrar upload quase vazio/errado; a UI ainda pede 60s como recomendacao pra melhor
# qualidade (ver VozCloneModal.tsx).
_DURACAO_MINIMA_SEGUNDOS = 20
_EXTENSOES_PERMITIDAS = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}


class VozClonadaResponse(BaseModel):
    id: int
    nome: str
    voz_id: str
    # Amostra curta hospedada pela ElevenLabs pra "ouvir como ficou" -- mesmo dado de
    # app/tts/voices.py::listar_vozes_com_preview, so que sem cache (poucas vozes por conta,
    # nao justifica o _preview_cache em memoria daquele modulo, que e' pro catalogo global).
    preview_url: str | None = None

    model_config = {"from_attributes": True}


class VozClonadaRenomearRequest(BaseModel):
    nome: str


def _resposta_voz_clonada(voz_clonada: VozClonada) -> VozClonadaResponse:
    return VozClonadaResponse(
        id=voz_clonada.id,
        nome=voz_clonada.nome,
        voz_id=voz_clonada.voz_id,
        preview_url=obter_preview_url(voz_clonada.voz_id),
    )


@router.get("/voices", dependencies=[Depends(limitar_por_ip("tts_voices", limite=30, janela_segundos=60))])
def vozes():
    return listar_vozes_com_preview()


@router.get("/vozes-clonadas", response_model=list[VozClonadaResponse])
def listar_vozes_clonadas(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    vozes_clonadas = db.query(VozClonada).filter_by(account_id=account.id).order_by(VozClonada.id.asc()).all()
    return [_resposta_voz_clonada(v) for v in vozes_clonadas]


@router.get("/vozes-compartilhadas", response_model=list[VozClonadaResponse])
def listar_vozes_compartilhadas(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    """Vozes clonadas por outras contas e marcadas como compartilhadas -- selecionaveis por
    qualquer conta (ver app/tts/voices.py::voz_valida_para_conta), mas so a conta que criou
    pode renomear/excluir (por isso ficam fora da lista de /vozes-clonadas dessa conta).
    """
    vozes_clonadas = (
        db.query(VozClonada)
        .filter(VozClonada.compartilhada.is_(True), VozClonada.account_id != account.id)
        .order_by(VozClonada.id.asc())
        .all()
    )
    return [_resposta_voz_clonada(v) for v in vozes_clonadas]


@router.post("/vozes-clonadas", response_model=VozClonadaResponse, status_code=status.HTTP_201_CREATED)
async def criar_voz_clonada(
    nome: str = Form(...),
    arquivo: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if not limites_do_plano(account.plano).clonagem_voz:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Clonagem de voz disponivel a partir do plano Growth. Faca upgrade em /billing.",
        )
    if limite_excedido(f"clonar_voz:{account.id}", limite=5, janela_segundos=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de clonagens por hora atingido. Tenta de novo daqui a pouco.",
        )

    if not nome.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome obrigatorio")
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS nao configurado")

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
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo de audio maior que 15MB")

    try:
        duracao_segundos = len(AudioSegment.from_file(BytesIO(conteudo))) / 1000
    except CouldntDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nao foi possivel ler o audio enviado. Tenta outro arquivo."
        ) from exc
    if duracao_segundos < _DURACAO_MINIMA_SEGUNDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Audio muito curto ({duracao_segundos:.0f}s). Grava pelo menos "
                f"{_DURACAO_MINIMA_SEGUNDOS}s de fala limpa (o ideal e uns 60s) pra um clone fiel."
            ),
        )

    try:
        voice_id = clonar_voz(
            nome.strip(),
            conteudo,
            _EXTENSOES_PERMITIDAS[extensao],
            arquivo.filename or f"amostra{extensao}",
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("Falha ao clonar voz na ElevenLabs: %s", exc.response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel clonar a voz agora. Verifique se o audio tem qualidade suficiente e tente de novo.",
        ) from exc

    voz_clonada = VozClonada(account_id=account.id, nome=nome.strip(), voz_id=voice_id)
    db.add(voz_clonada)
    db.commit()
    db.refresh(voz_clonada)
    return _resposta_voz_clonada(voz_clonada)


@router.patch("/vozes-clonadas/{voz_clonada_id}", response_model=VozClonadaResponse)
def renomear_voz_clonada(
    voz_clonada_id: int,
    dados: VozClonadaRenomearRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if not dados.nome.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome obrigatorio")

    voz_clonada = db.query(VozClonada).filter_by(id=voz_clonada_id, account_id=account.id).first()
    if voz_clonada is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz clonada nao encontrada")

    voz_clonada.nome = dados.nome.strip()
    db.commit()
    db.refresh(voz_clonada)

    try:
        renomear_voz(voz_clonada.voz_id, voz_clonada.nome)
    except httpx.HTTPStatusError as exc:
        logger.warning("Falha ao renomear voz na ElevenLabs (%s): %s", voz_clonada.voz_id, exc.response.text)

    return _resposta_voz_clonada(voz_clonada)


@router.delete("/vozes-clonadas/{voz_clonada_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_voz_clonada_endpoint(
    voz_clonada_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    voz_clonada = db.query(VozClonada).filter_by(id=voz_clonada_id, account_id=account.id).first()
    if voz_clonada is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz clonada nao encontrada")

    try:
        excluir_voz_clonada(voz_clonada.voz_id)
    except httpx.HTTPStatusError as exc:
        logger.warning("Falha ao excluir voz na ElevenLabs (%s): %s", voz_clonada.voz_id, exc.response.text)

    db.delete(voz_clonada)
    db.commit()
