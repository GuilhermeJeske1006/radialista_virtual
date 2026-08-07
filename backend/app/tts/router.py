from fastapi import APIRouter

from app.tts.voices import listar_vozes

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/voices")
def vozes():
    return listar_vozes()
