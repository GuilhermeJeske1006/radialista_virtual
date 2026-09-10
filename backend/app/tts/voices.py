"""Catalogo de vozes em portugues brasileiro da ElevenLabs."""

from sqlalchemy.orm import Session

from app.tts.client import obter_preview_url

# IDs e perfis conferidos em https://elevenlabs.io/text-to-speech/portuguese
# em 2026-09-08. Will e' o perfil brasileiro, nao a voz homonima em ingles.
VOZES_DISPONIVEIS = [
    {"voz_id": "Qrdut83w0Cr152Yb4Xn3", "nome": "Paulo", "genero": "masculina", "descricao": "Português brasileiro · Expressiva e confiante"},
    {"voz_id": "CstacWqMhJQlnfLPxRG4", "nome": "Will", "genero": "masculina", "descricao": "Português brasileiro · Grave, suave e afetuosa"},
    {"voz_id": "lWq4KDY8znfkV0DrK8Vb", "nome": "Yasmin Alves", "genero": "feminina", "descricao": "Português brasileiro · Leve, clara e musical"},
    {"voz_id": "cyD08lEy76q03ER1jZ7y", "nome": "Scheila", "genero": "feminina", "descricao": "Português brasileiro · Séria e direta"},
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


def descricao_voz(voz_id: str | None) -> str | None:
    """Descricao curta (genero + timbre) da voz do catalogo fixo, pra dar contexto ao LLM na
    hora de gerar personalidade/programa coerente com a voz ja escolhida. Voz clonada (fora do
    catalogo fixo) nao tem descricao aqui -- retorna None.
    """
    voz = _VOZES_POR_ID.get(voz_id or "")
    return f"{voz['nome']}, voz {voz['genero']}, {voz['descricao']}" if voz else None


def voz_valida_para_conta(db: Session, account_id: int, voz_id: str, incluir_pendente: bool = False) -> bool:
    """Valida um voz_id do catalogo fixo, uma voz clonada (app/models/voz_clonada.py)
    pertencente a essa conta, ou uma voz clonada marcada como compartilhada (disponivel
    pra qualquer conta escolher, embora so a conta que criou possa renomear/excluir).
    """
    from app.models.perfil_voz import MetadadosVoz
    meta = db.get(MetadadosVoz, voz_id)
    if not incluir_pendente and meta and meta.requer_verificacao:
        return False
    if voz_valida(voz_id):
        return True

    from sqlalchemy import or_

    from app.models.voz_clonada import VozClonada

    return (
        db.query(VozClonada)
        .filter(VozClonada.voz_id == voz_id)
        .filter(or_(VozClonada.account_id == account_id, VozClonada.compartilhada.is_(True)))
        .first()
        is not None
    )
