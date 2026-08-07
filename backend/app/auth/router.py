import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.auth.security import criar_token, hash_senha, verificar_senha
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

router = APIRouter(prefix="/auth", tags=["auth"])


class RegistroRequest(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ContaResponse(BaseModel):
    id: int
    nome: str
    email: str
    plano_status: str
    plano: str
    criado_em: datetime.datetime
    tem_radio_config: bool


class AlterarSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


class AtualizarPerfilRequest(BaseModel):
    nome: str


@router.post(
    "/register",
    response_model=TokenResponse,
    dependencies=[Depends(limitar_por_ip("auth_register", limite=5, janela_segundos=60))],
)
def registrar(dados: RegistroRequest, db: Session = Depends(get_db)):
    if db.query(Account).filter_by(email=dados.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail ja cadastrado")

    account = Account(nome=dados.nome, email=dados.email, senha_hash=hash_senha(dados.senha))
    db.add(account)
    db.flush()

    radio_config = RadioConfig(account_id=account.id)
    db.add(radio_config)
    db.flush()

    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Principal",
        dias_semana=[],
        horario_inicio=datetime.time(0, 0),
        horario_fim=datetime.time(23, 59),
    )
    db.add(programa)
    db.commit()

    return TokenResponse(access_token=criar_token(account.id))


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(limitar_por_ip("auth_login", limite=10, janela_segundos=60))],
)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha invalidos"
    )

    account = db.query(Account).filter_by(email=dados.email).first()
    if account is None or not verificar_senha(dados.senha, account.senha_hash):
        raise credenciais_invalidas

    return TokenResponse(access_token=criar_token(account.id))


@router.get("/me", response_model=ContaResponse)
def me(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    tem_radio_config = db.query(RadioConfig).filter_by(account_id=account.id).first() is not None
    return ContaResponse(
        id=account.id,
        nome=account.nome,
        email=account.email,
        plano_status=account.plano_status,
        plano=account.plano,
        criado_em=account.criado_em,
        tem_radio_config=tem_radio_config,
    )


@router.patch("/perfil", response_model=ContaResponse)
def atualizar_perfil(
    dados: AtualizarPerfilRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    nome = dados.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um nome")

    account.nome = nome
    db.commit()
    db.refresh(account)

    tem_radio_config = db.query(RadioConfig).filter_by(account_id=account.id).first() is not None
    return ContaResponse(
        id=account.id,
        nome=account.nome,
        email=account.email,
        plano_status=account.plano_status,
        plano=account.plano,
        criado_em=account.criado_em,
        tem_radio_config=tem_radio_config,
    )


@router.put("/senha", status_code=status.HTTP_204_NO_CONTENT)
def alterar_senha(
    dados: AlterarSenhaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if not verificar_senha(dados.senha_atual, account.senha_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta")
    if len(dados.senha_nova) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha precisa ter pelo menos 8 caracteres"
        )

    account.senha_hash = hash_senha(dados.senha_nova)
    db.commit()
