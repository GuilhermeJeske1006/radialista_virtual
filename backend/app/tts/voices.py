"""Catalogo de vozes pre-definidas da ElevenLabs para o usuario escolher."""

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
