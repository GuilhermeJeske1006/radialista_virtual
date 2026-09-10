import logging
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.config.settings import settings
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip, limite_excedido
from app.models.account import Account
from app.models.voz_clonada import VozClonada
from app.models.perfil_voz import ConfiguracaoVoz, MetadadosVoz
from app.tts.profiles import consultar_metadados
from app.tts.quality import QualidadeAudio, analisar_amostras
from app.planos import limites_do_plano
from app.tts.client import clonar_voz, excluir_voz_clonada, obter_preview_url, renomear_voz
from app.tts.voices import listar_vozes_com_preview, voz_valida_para_conta

logger = logging.getLogger("radialista.tts")

router = APIRouter(prefix="/tts", tags=["tts"])

_TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024
_EXTENSOES_PERMITIDAS = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
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
    categoria: str = "desconhecida"
    requer_verificacao: bool = False
    qualidade: QualidadeAudio | None = None

    model_config = {"from_attributes": True}


class VozClonadaRenomearRequest(BaseModel):
    nome: str


def _resposta_voz_clonada(voz_clonada: VozClonada, db: Session) -> VozClonadaResponse:
    meta = db.get(MetadadosVoz, voz_clonada.voz_id)
    return VozClonadaResponse(
        id=voz_clonada.id,
        nome=voz_clonada.nome,
        voz_id=voz_clonada.voz_id,
        preview_url=obter_preview_url(voz_clonada.voz_id) if not (meta and meta.requer_verificacao) else None,
        categoria=meta.categoria if meta else "desconhecida",
        requer_verificacao=bool(meta and meta.requer_verificacao),
    )


@router.get("/voices", dependencies=[Depends(limitar_por_ip("tts_voices", limite=30, janela_segundos=60))])
def vozes():
    return listar_vozes_com_preview()


@router.get("/vozes-clonadas", response_model=list[VozClonadaResponse])
def listar_vozes_clonadas(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    vozes_clonadas = db.query(VozClonada).filter_by(account_id=account.id).order_by(VozClonada.id.asc()).all()
    return [_resposta_voz_clonada(v, db) for v in vozes_clonadas]


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
    return [_resposta_voz_clonada(v, db) for v in vozes_clonadas]


def _exigir_clonagem(account: Account):
    if not limites_do_plano(account.plano).clonagem_voz:
        raise HTTPException(status_code=402, detail="Clonagem de voz disponível a partir do plano Growth.")


async def _ler_amostras(arquivo: UploadFile | None, arquivos: list[UploadFile] | None):
    uploads = ([arquivo] if arquivo else []) + (arquivos or [])
    if not 1 <= len(uploads) <= 5:
        raise HTTPException(status_code=400, detail="Envie de 1 a 5 arquivos do mesmo locutor.")
    amostras = []
    total = 0
    for upload in uploads:
        extensao = Path(upload.filename or "").suffix.lower()
        if extensao not in _EXTENSOES_PERMITIDAS:
            raise HTTPException(status_code=400, detail="Formato não suportado. Use MP3, WAV, M4A, MP4, OGG ou WebM.")
        conteudo = await upload.read(_TAMANHO_MAXIMO_BYTES - total + 1)
        total += len(conteudo)
        if total > _TAMANHO_MAXIMO_BYTES:
            raise HTTPException(status_code=413, detail="Os arquivos devem somar no máximo 15 MB.")
        if not conteudo:
            raise HTTPException(status_code=400, detail="Arquivo de áudio vazio.")
        amostras.append((Path(upload.filename).name, conteudo, _EXTENSOES_PERMITIDAS[extensao]))
    return amostras


async def _qualidade(amostras) -> QualidadeAudio:
    try:
        return await run_in_threadpool(analisar_amostras, [audio for _, audio, _ in amostras])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Análise de áudio indisponível. Tente novamente mais tarde.") from exc


@router.post("/analisar-voz", response_model=QualidadeAudio)
async def analisar_voz(
    arquivo: UploadFile | None = File(None), arquivos: list[UploadFile] | None = File(None),
    account: Account = Depends(get_current_account),
):
    _exigir_clonagem(account)
    if limite_excedido(f"analisar_voz:{account.id}", limite=10, janela_segundos=60):
        raise HTTPException(status_code=429, detail="Aguarde um minuto antes de analisar novamente.")
    return await _qualidade(await _ler_amostras(arquivo, arquivos))


@router.post("/vozes-clonadas", response_model=VozClonadaResponse, status_code=201)
async def criar_voz_clonada(
    nome: str = Form(...), arquivo: UploadFile | None = File(None),
    arquivos: list[UploadFile] | None = File(None),
    account: Account = Depends(get_current_account), db: Session = Depends(get_db),
):
    _exigir_clonagem(account)
    if limite_excedido(f"clonar_voz:{account.id}", limite=5, janela_segundos=3600):
        raise HTTPException(status_code=429, detail="Limite de clonagens por hora atingido.")
    if not nome.strip() or len(nome.strip()) > 100:
        raise HTTPException(status_code=400, detail="Informe um nome de até 100 caracteres.")
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=503, detail="TTS não configurado")
    amostras = await _ler_amostras(arquivo, arquivos)
    qualidade = await _qualidade(amostras)
    try:
        criada = await run_in_threadpool(clonar_voz, nome.strip(), amostras=amostras)
    except httpx.HTTPError as exc:
        logger.warning("Falha ao clonar voz: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Não foi possível clonar a voz agora. Tente novamente.") from exc
    voice_id = criada["voice_id"]
    voz_clonada = VozClonada(account_id=account.id, nome=nome.strip(), voz_id=voice_id)
    db.add(voz_clonada)
    db.add(MetadadosVoz(voz_id=voice_id, categoria="cloned", idioma="pt", requer_verificacao=criada["requires_verification"]))
    db.commit()
    db.refresh(voz_clonada)
    resposta = _resposta_voz_clonada(voz_clonada, db)
    resposta.qualidade = qualidade
    return resposta


class ConfiguracaoVozRequest(BaseModel):
    modelo: Literal["eleven_v3", "eleven_multilingual_v2", "eleven_flash_v2_5"] | None = None
    perfil: Literal["atual", "natural"] = "atual"
    formato: Literal["mp3_44100_128", "mp3_44100_192"] = "mp3_44100_128"
    pronuncias: dict[str, str] = Field(default_factory=dict, max_length=30)

    @field_validator("pronuncias")
    @classmethod
    def validar_pronuncias(cls, valores):
        normalizados = {}
        for original, pronuncia in valores.items():
            if not original.strip() or not pronuncia.strip() or max(len(original), len(pronuncia)) > 100:
                raise ValueError("Cada pronúncia deve ter texto e substituição de até 100 caracteres.")
            if any(c in original + pronuncia for c in "[]\r\n"):
                raise ValueError("Pronúncias não podem conter tags ou quebras de linha.")
            chave = original.strip()
            if chave.casefold() in {k.casefold() for k in normalizados}:
                raise ValueError("Termo de pronúncia duplicado.")
            normalizados[chave] = pronuncia.strip()
        return normalizados


def _autorizar_configuracao(db: Session, account: Account, voz_id: str) -> str:
    efetiva = settings.elevenlabs_voice_id if voz_id == "padrao" else voz_id
    if not efetiva or (voz_id != "padrao" and not voz_valida_para_conta(db, account.id, efetiva, incluir_pendente=True)):
        raise HTTPException(status_code=404, detail="Voz não encontrada")
    return efetiva


@router.get("/configuracao-voz/{voz_id}")
def obter_configuracao_voz(voz_id: str, atualizar: bool = False, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    efetiva = _autorizar_configuracao(db, account, voz_id)
    if atualizar and limite_excedido(f"atualizar_voz:{account.id}", limite=10, janela_segundos=60):
        raise HTTPException(status_code=429, detail="Aguarde antes de atualizar novamente.")
    meta = consultar_metadados(db, efetiva, atualizar)
    config = db.query(ConfiguracaoVoz).filter_by(account_id=account.id, voz_id=efetiva).first()
    dados = ConfiguracaoVozRequest(**{k: getattr(config, k) for k in ConfiguracaoVozRequest.model_fields}).model_dump() if config else ConfiguracaoVozRequest().model_dump()
    return {**dados, "categoria": meta.categoria, "idioma": meta.idioma, "sotaque": meta.sotaque,
            "requer_verificacao": meta.requer_verificacao}


@router.patch("/configuracao-voz/{voz_id}")
def salvar_configuracao_voz(voz_id: str, dados: ConfiguracaoVozRequest, account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    efetiva = _autorizar_configuracao(db, account, voz_id)
    config = db.query(ConfiguracaoVoz).filter_by(account_id=account.id, voz_id=efetiva).first()
    if config is None:
        config = ConfiguracaoVoz(account_id=account.id, voz_id=efetiva)
        db.add(config)
    for chave, valor in dados.model_dump().items():
        setattr(config, chave, valor)
    db.commit()
    return dados.model_dump()


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

    return _resposta_voz_clonada(voz_clonada, db)


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

    db.query(ConfiguracaoVoz).filter_by(voz_id=voz_clonada.voz_id).delete()
    db.query(MetadadosVoz).filter_by(voz_id=voz_clonada.voz_id).delete()
    db.delete(voz_clonada)
    db.commit()
