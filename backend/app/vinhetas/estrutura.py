"""Onde as vinhetas geradas entram em Programa.estrutura_blocos (ver app/vinhetas/servico.py).

A estrutura roda em loop no ao vivo (ver _tipo_proximo_bloco em app.live.router), entao a
vizinhanca de um bloco e' ciclica: o primeiro item encosta no ultimo.
"""
import re

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.live.formato import ROTEIRO_MUSICAL, ROTEIRO_PADRAO, musical_companhia
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.util.texto import sem_acento

_INSERCAO_RE = re.compile(r"^(vinheta|patrocinador):\d+$")


def bloco_vinheta(vinheta_id: int) -> str:
    return f"vinheta:{vinheta_id}"


def _eh_insercao(bloco: str) -> bool:
    return bool(_INSERCAO_RE.match(bloco.strip()))


def _eh_musica(bloco: str) -> bool:
    normalizado = sem_acento(bloco.strip().lower())
    return normalizado == "musica" or normalizado.startswith(("musica ", "musica_"))


def _cabe_em(estrutura: list[str], indice: int) -> bool:
    """Inserir em `indice` (empurrando o item atual pra frente) nao cola a vinheta em outra
    vinheta/patrocinador -- nem do lado de tras (item anterior, ciclico) nem da frente."""
    if not estrutura:
        return True
    anterior = estrutura[indice - 1] if indice > 0 else estrutura[-1]
    seguinte = estrutura[indice] if indice < len(estrutura) else estrutura[0]
    return not _eh_insercao(anterior) and not _eh_insercao(seguinte)


def _primeira_posicao_valida(estrutura: list[str], preferidas: list[int]) -> int | None:
    vistas = set()
    for indice in preferidas + list(range(len(estrutura) + 1)):
        if indice in vistas or not 0 <= indice <= len(estrutura):
            continue
        vistas.add(indice)
        if _cabe_em(estrutura, indice):
            return indice
    return None


def _posicao_passagem(estrutura: list[str]) -> int:
    """Logo antes do segundo bloco de musica; com menos de duas musicas, no meio da lista."""
    musicas = [i for i, bloco in enumerate(estrutura) if _eh_musica(bloco)]
    if len(musicas) >= 2:
        return musicas[1]
    return len(estrutura) // 2


def roteiro_base(programa: Programa) -> list[str]:
    """Roteiro que o ao vivo usaria com a estrutura vazia -- materializado antes de inserir as
    vinhetas, senao a estrutura ficaria so' com vinhetas e o programa perderia o roteiro padrao."""
    return list(ROTEIRO_MUSICAL) if musical_companhia(programa) else list(ROTEIRO_PADRAO)


def inserir_vinhetas_na_estrutura(programa: Programa, vinhetas: list[BibliotecaAudioItem]) -> list[str]:
    """Abertura no indice 0 (a cada volta do loop vira tambem identificacao), passagem uma vez no
    meio. Encerramento NUNCA entra: o encerramento nao faz parte do loop, o ao vivo toca essa
    vinheta logo depois da fala de encerramento (ver vinheta_encerramento_id em app.live.router).
    Nao duplica: vinheta que ja esta na estrutura fica onde esta."""
    estrutura = [b for b in (programa.estrutura_blocos or []) if b.strip()] or roteiro_base(programa)
    por_papel = {v.papel: v for v in vinhetas if v.id is not None}

    abertura = por_papel.get("abertura")
    if abertura is not None and bloco_vinheta(abertura.id) not in estrutura:
        indice = _primeira_posicao_valida(estrutura, [0])
        if indice is not None:
            estrutura.insert(indice, bloco_vinheta(abertura.id))

    passagem = por_papel.get("passagem")
    if passagem is not None and bloco_vinheta(passagem.id) not in estrutura:
        alvo = _posicao_passagem(estrutura)
        indice = _primeira_posicao_valida(estrutura, [alvo, alvo + 1, alvo - 1])
        if indice is not None:
            estrutura.insert(indice, bloco_vinheta(passagem.id))

    programa.estrutura_blocos = estrutura
    flag_modified(programa, "estrutura_blocos")
    return estrutura


def remover_vinhetas_das_estruturas(db: Session, account_id: int, vinheta_ids: list[int]) -> None:
    """Tira "vinheta:<id>" de toda estrutura_blocos da conta -- sem isso o ao vivo tentaria
    tocar uma vinheta que nao existe mais."""
    if not vinheta_ids:
        return
    blocos = {bloco_vinheta(i) for i in vinheta_ids}
    programas = (
        db.query(Programa)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account_id)
        .all()
    )
    for programa in programas:
        estrutura = programa.estrutura_blocos or []
        nova = [b for b in estrutura if b.strip() not in blocos]
        if len(nova) != len(estrutura):
            programa.estrutura_blocos = nova
            flag_modified(programa, "estrutura_blocos")
