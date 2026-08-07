from fastapi import APIRouter, Depends

from app.guardrails.http_rate_limit import limitar_por_ip
from app.tts.voices import listar_vozes

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/voices", dependencies=[Depends(limitar_por_ip("tts_voices", limite=30, janela_segundos=60))])
def vozes():
    return listar_vozes()
