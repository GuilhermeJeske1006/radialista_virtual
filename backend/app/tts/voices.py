"""Catalogo de vozes pre-definidas da ElevenLabs para o usuario escolher."""

from sqlalchemy.orm import Session

from app.tts.client import obter_preview_url

VOZES_DISPONIVEIS = [
    {"voz_id": "21m00Tcm4TlvDq8ikWAM", "nome": "Rachel", "genero": "feminina", "descricao": "Calma e clara"},
    {"voz_id": "AZnzlk1XvdvUeBnXmlld", "nome": "Domi", "genero": "feminina", "descricao": "Forte e confiante"},
    {"voz_id": "EXAVITQu4vr4xnSDxMaL", "nome": "Bella", "genero": "feminina", "descricao": "Suave e envolvente"},
    {"voz_id": "ErXwobaYiN019PkySvjV", "nome": "Antoni", "genero": "masculina", "descricao": "Bem-humorada e leve"},
    {"voz_id": "TxGEqnHWrfWFTfGW9XjX", "nome": "Josh", "genero": "masculina", "descricao": "Jovem e energetica"},
    {"voz_id": "VR6AewLTigWG4xSOukaG", "nome": "Arnold", "genero": "masculina", "descricao": "Grave e marcante"},
    {"voz_id": "pNInz6obpgDQGcFmaJgB", "nome": "Adam", "genero": "masculina", "descricao": "Profunda e seria"},
    {"voz_id": "yoZ06aMxZJJ28mfd3POQ", "nome": "Sam", "genero": "masculina", "descricao": "Neutra e versatil"},
]

_VOZES_POR_ID = {voz["voz_id"]: voz for voz in VOZES_DISPONIVEIS}


def listar_vozes() -> list[dict]:
    return VOZES_DISPONIVEIS


# so guarda preview_url resolvida com sucesso -- falha (sem api key, erro de rede) fica de
# fora do cache pra tentar de novo na proxima chamada, em vez de travar em None pra sempre.
_preview_cache: dict[str, str] = {}


def listar_vozes_com_preview() -> list[dict]:
    """Catalogo enriquecido com preview_url (amostra curta) de cada voz, pra o usuario
    ouvir antes de escolher. Voz sem preview disponivel (falha ou API nao configurada)
    entra com preview_url None -- o front so nao mostra o player pra ela.
    """
    vozes = []
    for voz in VOZES_DISPONIVEIS:
        voz_id = voz["voz_id"]
        if voz_id not in _preview_cache:
            preview_url = obter_preview_url(voz_id)
            if preview_url:
                _preview_cache[voz_id] = preview_url
        vozes.append({**voz, "preview_url": _preview_cache.get(voz_id)})
    return vozes


def voz_valida(voz_id: str) -> bool:
    return voz_id in _VOZES_POR_ID


def voz_valida_para_conta(db: Session, account_id: int, voz_id: str) -> bool:
    """Valida um voz_id do catalogo fixo OU uma voz clonada (app/models/voz_clonada.py)
    pertencente a essa conta -- clonagem de voz nao entra no catalogo global porque cada
    voz clonada e' privada de quem a criou.
    """
    if voz_valida(voz_id):
        return True

    from app.models.voz_clonada import VozClonada

    return db.query(VozClonada).filter_by(account_id=account_id, voz_id=voz_id).first() is not None
