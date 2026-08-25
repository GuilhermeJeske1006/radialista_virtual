import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.account import Account
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.categoria_vinheta import CategoriaVinheta
from app.models.patrocinador import Patrocinador

logger = logging.getLogger("radialista.categorias_vinheta")

router = APIRouter(prefix="/categorias-vinheta", tags=["categorias-vinheta"])


_TIPOS_VALIDOS = ("biblioteca", "propaganda")


class CategoriaVinhetaResponse(BaseModel):
    id: int
    nome: str
    tipo: str

    model_config = {"from_attributes": True}


class CategoriaVinhetaPayload(BaseModel):
    nome: str
    tipo: str = "biblioteca"


def _buscar_categoria(db: Session, account: Account, categoria_id: int) -> CategoriaVinheta:
    categoria = db.query(CategoriaVinheta).filter_by(id=categoria_id, account_id=account.id).first()
    if categoria is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria nao encontrada")
    return categoria


@router.get("", response_model=list[CategoriaVinhetaResponse])
def listar_categorias(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return db.query(CategoriaVinheta).filter_by(account_id=account.id).order_by(CategoriaVinheta.nome).all()


@router.post("", response_model=CategoriaVinhetaResponse, status_code=status.HTTP_201_CREATED)
def criar_categoria(
    payload: CategoriaVinhetaPayload,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome obrigatorio")
    if payload.tipo not in _TIPOS_VALIDOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo invalido")

    categoria = CategoriaVinheta(account_id=account.id, nome=nome, tipo=payload.tipo)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    logger.info("Categoria de vinhetagem criada: id=%s account_id=%s", categoria.id, account.id)
    return categoria


@router.put("/{categoria_id}", response_model=CategoriaVinhetaResponse)
def renomear_categoria(
    categoria_id: int,
    payload: CategoriaVinhetaPayload,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome obrigatorio")
    if payload.tipo not in _TIPOS_VALIDOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo invalido")

    categoria = _buscar_categoria(db, account, categoria_id)
    categoria.nome = nome
    categoria.tipo = payload.tipo
    db.commit()
    db.refresh(categoria)
    logger.info("Categoria de vinhetagem renomeada: id=%s account_id=%s", categoria.id, account.id)
    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_categoria(
    categoria_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    categoria = _buscar_categoria(db, account, categoria_id)

    # Vinhetas e propagandas dessa categoria nao somem, so caem em "Sem categoria".
    db.query(BibliotecaAudioItem).filter_by(account_id=account.id, categoria_id=categoria.id).update(
        {"categoria_id": None}
    )
    db.query(Patrocinador).filter_by(account_id=account.id, categoria_id=categoria.id).update(
        {"categoria_id": None}
    )

    db.delete(categoria)
    db.commit()
    logger.info("Categoria de vinhetagem excluida: id=%s account_id=%s", categoria_id, account.id)
