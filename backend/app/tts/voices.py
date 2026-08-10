"""Catalogo de vozes pre-definidas da ElevenLabs para o usuario escolher."""

from sqlalchemy.orm import Session

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
