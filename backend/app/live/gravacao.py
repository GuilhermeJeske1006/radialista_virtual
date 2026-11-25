"""Converte a gravação da aba (webm/opus do MediaRecorder) no MP3 do programa completo.

O painel grava o áudio que sai no navegador (fala, vinheta, música, fundo) e manda pra cá no
fim do programa; ffmpeg devolve MP3. Disco temporário porque gravação de 1h passa de dezenas de MB.
"""
import asyncio
import os
import subprocess
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.auth.dependencies import get_current_account
from app.models.account import Account

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
async def gravacao_para_mp3(request: Request, account: Account = Depends(get_current_account)):
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
    return FileResponse(destino, media_type="audio/mpeg", background=BackgroundTask(_apagar, origem, destino))
