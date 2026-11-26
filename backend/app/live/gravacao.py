"""Converte a gravação da aba (webm/opus do MediaRecorder) no MP3 do programa completo.

O painel grava o áudio que sai no navegador (fala, vinheta, música, fundo) e manda pra cá no
fim do programa; ffmpeg devolve MP3. Disco temporário porque gravação de 1h passa de dezenas de MB.
"""
import asyncio
import os
import subprocess
import tempfile
import datetime
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.auth.dependencies import get_current_account
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.gravacao_programa import GravacaoPrograma
from app.db.database import get_db
from app.storage import get_storage
from sqlalchemy.orm import Session

logger = logging.getLogger("radialista.gravacao")

router = APIRouter(prefix="/live", tags=["live"])

LIMITE_BYTES = 400 * 1024 * 1024  # ~6h de opus a 128 kbps, com folga
TIMEOUT_FFMPEG_S = 600


def converter_para_mp3(origem: str, destino: str) -> None:
    resultado = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", origem, "-vn", "-ac", "2", "-ar", "44100",
         "-codec:a", "libmp3lame", "-b:a", "192k", destino],
        capture_output=True, timeout=TIMEOUT_FFMPEG_S,
    )
    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.decode("utf-8", "ignore")[-500:])


def _apagar(*caminhos: str) -> None:
    for caminho in caminhos:
        try:
            os.remove(caminho)
        except OSError:
            pass


@router.post("/gravacao/mp3")
async def gravacao_para_mp3(request: Request, programa_id: int | None = None,
                           account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    if programa_id is not None:
        _programa_da_conta(db, account.id, programa_id)
    fd, origem = tempfile.mkstemp(suffix=".webm")
    destino = origem[:-5] + ".mp3"
    try:
        total = 0
        with os.fdopen(fd, "wb") as arquivo:
            async for pedaco in request.stream():
                total += len(pedaco)
                if total > LIMITE_BYTES:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Gravação grande demais.")
                arquivo.write(pedaco)
        if total == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Gravação vazia.")
        try:
            await asyncio.to_thread(converter_para_mp3, origem, destino)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Não foi possível converter a gravação: {exc}")
    except BaseException:
        _apagar(origem, destino)
        raise
    headers = {}
    if programa_id is not None:
        caminho = f"gravacoes/{account.id}/{programa_id}/{uuid.uuid4().hex}.mp3"
        try:
            await asyncio.to_thread(get_storage().save_file, caminho, destino)
            gravacao = GravacaoPrograma(account_id=account.id, programa_id=programa_id, audio_path=caminho,
                tamanho_bytes=os.path.getsize(destino), escopo="completo",
                expira_em=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7))
            db.add(gravacao)
            db.commit()
            headers["X-Gravacao-Arquivada"] = "true"
        except Exception:
            db.rollback()
            logger.exception("gravacao_arquivo_falhou programa_id=%s", programa_id)
            headers["X-Gravacao-Arquivada"] = "false"
            try:
                await asyncio.to_thread(get_storage().delete, caminho)
            except Exception:
                logger.warning("gravacao_limpeza_pendente programa_id=%s", programa_id)
    return FileResponse(destino, media_type="audio/mpeg", headers=headers,
                        background=BackgroundTask(_apagar, origem, destino))


def _programa_da_conta(db, account_id, programa_id):
    programa = db.query(Programa).join(RadioConfig).filter(
        Programa.id == programa_id, RadioConfig.account_id == account_id).first()
    if programa is None:
        raise HTTPException(404, "Programa não encontrado")
    return programa


def limpar_gravacoes_expiradas(db):
    agora = datetime.datetime.now(datetime.timezone.utc)
    for gravacao in db.query(GravacaoPrograma).filter(GravacaoPrograma.expira_em <= agora).limit(100):
        get_storage().delete(gravacao.audio_path)
        db.delete(gravacao)
    db.commit()


def excluir_gravacoes_programa(db, account_id, programa_id):
    for gravacao in db.query(GravacaoPrograma).filter_by(account_id=account_id, programa_id=programa_id):
        get_storage().delete(gravacao.audio_path)
        db.delete(gravacao)


@router.get("/programas/{programa_id}/gravacoes")
def listar_gravacoes(programa_id: int, account=Depends(get_current_account), db=Depends(get_db)):
    _programa_da_conta(db, account.id, programa_id)
    registros = db.query(GravacaoPrograma).filter(
        GravacaoPrograma.account_id == account.id, GravacaoPrograma.programa_id == programa_id,
        GravacaoPrograma.expira_em > datetime.datetime.now(datetime.timezone.utc)
    ).order_by(GravacaoPrograma.criado_em.desc()).limit(20).all()
    return [{"id": g.id, "criado_em": g.criado_em.isoformat(), "expira_em": g.expira_em.isoformat(),
             "escopo": g.escopo, "tamanho_bytes": g.tamanho_bytes} for g in registros]


@router.get("/programas/{programa_id}/gravacoes/{gravacao_id}/audio")
def baixar_gravacao(programa_id: int, gravacao_id: int, account=Depends(get_current_account), db=Depends(get_db)):
    _programa_da_conta(db, account.id, programa_id)
    gravacao = db.query(GravacaoPrograma).filter(
        GravacaoPrograma.id == gravacao_id, GravacaoPrograma.account_id == account.id,
        GravacaoPrograma.programa_id == programa_id,
        GravacaoPrograma.expira_em > datetime.datetime.now(datetime.timezone.utc)).first()
    if gravacao is None:
        raise HTTPException(404, "Gravação não encontrada ou expirada")
    return StreamingResponse(get_storage().iter_read(gravacao.audio_path), media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="programa-{programa_id}-{gravacao_id}.mp3"',
                 "Content-Length": str(gravacao.tamanho_bytes), "Cache-Control": "private, no-store"})
