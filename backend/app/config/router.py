import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.tts.voices import voz_valida

router = APIRouter(prefix="/config", tags=["config"])


class RadialistaRequest(BaseModel):
    nome_locutor: str
    voz_id: str | None = None
    timezone: str = "America/Sao_Paulo"


class RadialistaResponse(RadialistaRequest):
    id: int
    wuzapi_token: str | None
    ativo: bool

    model_config = {"from_attributes": True}


class ProgramaRequest(BaseModel):
    nome: str
    dias_semana: list[int] = Field(default_factory=list)
    horario_inicio: datetime.time
    horario_fim: datetime.time
    ativo: bool = True

    tom: str
    topicos_permitidos: list[str] = Field(default_factory=list)
    topicos_proibidos: list[str] = Field(default_factory=list)
    mensagem_saudacao: str = ""
    mensagem_recusa: str = ""
    limite_mensagens_hora: int = 10

    generos_musicais: list[str] = Field(default_factory=list)
    musicas_permitidas: list[str] = Field(default_factory=list)
    musicas_bloqueadas: list[str] = Field(default_factory=list)
    criterios_busca_musicas: str = ""

    assuntos_ao_vivo: list[str] = Field(default_factory=list)
    tipos_noticias: list[str] = Field(default_factory=list)
    fontes_noticias: list[str] = Field(default_factory=list)

    pode_pesquisar: bool = False
    fontes_pesquisa: list[str] = Field(default_factory=list)
    instrucoes_pesquisa: str = ""


class ProgramaResponse(ProgramaRequest):
    id: int
    radio_config_id: int

    model_config = {"from_attributes": True}


def _buscar_radialista(db: Session, account: Account, radialista_id: int) -> RadioConfig:
    radialista = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
    if radialista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radialista nao encontrado")
    return radialista


def _buscar_programa(db: Session, account: Account, programa_id: int) -> Programa:
    programa = (
        db.query(Programa)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(Programa.id == programa_id, RadioConfig.account_id == account.id)
        .first()
    )
    if programa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa nao encontrado")
    return programa


def _validar_voz(voz_id: str | None) -> None:
    if voz_id is not None and not voz_valida(voz_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voz invalida")


@router.get("/radialistas", response_model=list[RadialistaResponse])
def listar_radialistas(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return db.query(RadioConfig).filter_by(account_id=account.id).order_by(RadioConfig.id.asc()).all()


@router.post("/radialistas", response_model=RadialistaResponse, status_code=status.HTTP_201_CREATED)
def criar_radialista(
    dados: RadialistaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    _validar_voz(dados.voz_id)
    radialista = RadioConfig(account_id=account.id, **dados.model_dump())
    db.add(radialista)
    db.commit()
    db.refresh(radialista)
    return radialista


@router.get("/radialistas/{radialista_id}", response_model=RadialistaResponse)
def obter_radialista(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _buscar_radialista(db, account, radialista_id)


@router.put("/radialistas/{radialista_id}", response_model=RadialistaResponse)
def atualizar_radialista(
    radialista_id: int,
    dados: RadialistaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    _validar_voz(dados.voz_id)
    radialista = _buscar_radialista(db, account, radialista_id)
    for campo, valor in dados.model_dump().items():
        setattr(radialista, campo, valor)
    db.commit()
    db.refresh(radialista)
    return radialista


@router.delete("/radialistas/{radialista_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_radialista(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    db.query(Programa).filter_by(radio_config_id=radialista.id).delete()
    db.delete(radialista)
    db.commit()


@router.get("/radialistas/{radialista_id}/programas", response_model=list[ProgramaResponse])
def listar_programas(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    return (
        db.query(Programa)
        .filter_by(radio_config_id=radialista.id)
        .order_by(Programa.horario_inicio.asc())
        .all()
    )


@router.post(
    "/radialistas/{radialista_id}/programas",
    response_model=ProgramaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_programa(
    radialista_id: int,
    dados: ProgramaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    programa = Programa(radio_config_id=radialista.id, **dados.model_dump())
    db.add(programa)
    db.commit()
    db.refresh(programa)
    return programa


@router.get("/programas/{programa_id}", response_model=ProgramaResponse)
def obter_programa(
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _buscar_programa(db, account, programa_id)


@router.put("/programas/{programa_id}", response_model=ProgramaResponse)
def atualizar_programa(
    programa_id: int,
    dados: ProgramaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    for campo, valor in dados.model_dump().items():
        setattr(programa, campo, valor)
    db.commit()
    db.refresh(programa)
    return programa


@router.delete("/programas/{programa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_programa(
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    db.delete(programa)
    db.commit()
