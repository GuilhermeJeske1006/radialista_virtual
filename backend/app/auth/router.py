import datetime
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_usuario
from app.auth.email import enviar_email_redefinicao_senha
from app.auth.security import (
    COOKIE_ADMIN_TOKEN,
    criar_token,
    definir_cookie_sessao,
    hash_senha,
    limpar_cookie_sessao,
    verificar_senha,
)
from app.biblioteca_audio.sons_padrao import criar_sons_padrao
from app.categorias_vinheta.defaults import criar_categorias_padrao
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip
from app.models.account import Account
from app.models.password_reset_token import PasswordResetToken
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.super_admin import SuperAdmin
from app.models.usuario import Usuario

logger = logging.getLogger("radialista.auth")

TOKEN_RESET_VALIDADE_MINUTOS = 30

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
    # "usuario" | "super_admin" -- login e' unico (mesmo form pra tenant e super-admin, ver
    # app/models/super_admin.py), o frontend usa esse campo pra saber pra qual tela mandar
    # depois do login (/dashboard ou /admin).
    papel: str


class ContaResponse(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    plano_status: str
    plano: str
    criado_em: datetime.datetime
    tem_radio_config: bool


class AlterarSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


class AtualizarPerfilRequest(BaseModel):
    nome: str


class EsqueciSenhaRequest(BaseModel):
    email: EmailStr


class RedefinirSenhaRequest(BaseModel):
    token: str
    senha_nova: str


@router.post(
    "/register",
    response_model=TokenResponse,
    dependencies=[Depends(limitar_por_ip("auth_register", limite=5, janela_segundos=60))],
)
def registrar(dados: RegistroRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(Usuario).filter_by(email=dados.email).first() is not None:
        logger.warning("Tentativa de registro com e-mail ja cadastrado: %s", dados.email)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail ja cadastrado")

    account = Account()
    db.add(account)
    db.flush()

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        account_id=account.id,
        role="admin",
    )
    db.add(usuario)
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

    criar_categorias_padrao(db, account.id)

    try:
        criar_sons_padrao(db, account.id)
    except Exception:
        logger.warning("Falha ao seedar sons padrao pra account_id=%s", account.id, exc_info=True)

    db.commit()

    logger.info("Conta registrada: account_id=%s usuario_id=%s email=%s", account.id, usuario.id, usuario.email)
    token = criar_token(usuario.id)
    definir_cookie_sessao(response, token)
    return TokenResponse(access_token=token, papel="usuario")


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(limitar_por_ip("auth_login", limite=10, janela_segundos=60))],
)
def login(dados: LoginRequest, response: Response, db: Session = Depends(get_db)):
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha invalidos"
    )

    usuario = db.query(Usuario).filter_by(email=dados.email).first()
    if usuario is not None and usuario.ativo and verificar_senha(dados.senha, usuario.senha_hash):
        token = criar_token(usuario.id)
        definir_cookie_sessao(response, token)
        return TokenResponse(access_token=token, papel="usuario")

    # E-mail nao bateu com nenhum Usuario (ou senha errada) -- tenta como super-admin antes
    # de desistir. Perfil isolado (app/models/super_admin.py), sem relacao com Usuario/Account,
    # mas divide o mesmo formulario de login (so' muda pra onde o frontend redireciona depois).
    admin = db.query(SuperAdmin).filter_by(email=dados.email).first()
    if admin is not None and admin.ativo and verificar_senha(dados.senha, admin.senha_hash):
        token = criar_token(admin.id, tipo="super_admin")
        definir_cookie_sessao(response, token, cookie_name=COOKIE_ADMIN_TOKEN)
        return TokenResponse(access_token=token, papel="super_admin")

    logger.warning("Login falhou para e-mail: %s", dados.email)
    raise credenciais_invalidas


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    limpar_cookie_sessao(response)


@router.post(
    "/esqueci-senha",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limitar_por_ip("auth_esqueci_senha", limite=5, janela_segundos=60))],
)
def esqueci_senha(dados: EsqueciSenhaRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter_by(email=dados.email).first()
    if usuario is not None and usuario.ativo:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expira_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=TOKEN_RESET_VALIDADE_MINUTOS
        )
        db.add(PasswordResetToken(usuario_id=usuario.id, token_hash=token_hash, expira_em=expira_em))
        db.commit()
        enviar_email_redefinicao_senha(usuario.email, token)
        logger.info("Solicitacao de redefinicao de senha enviada: usuario_id=%s", usuario.id)

    # Sempre 204, exista ou nao a conta -- evita expor quais e-mails estao cadastrados.


@router.post(
    "/redefinir-senha",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limitar_por_ip("auth_redefinir_senha", limite=10, janela_segundos=60))],
)
def redefinir_senha(dados: RedefinirSenhaRequest, db: Session = Depends(get_db)):
    link_invalido = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Link invalido ou expirado"
    )
    if len(dados.senha_nova) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha precisa ter pelo menos 8 caracteres"
        )

    token_hash = hashlib.sha256(dados.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter_by(token_hash=token_hash).first()
    agora = datetime.datetime.now(datetime.timezone.utc)
    expira_em = reset_token.expira_em if reset_token is not None else None
    # Alguns drivers/DBs (ex.: SQLite, usado nos testes) nao preservam tzinfo num
    # DateTime(timezone=True) no round-trip -- sem isso a comparacao abaixo levanta
    # TypeError (naive vs aware) em vez de simplesmente invalidar o token expirado.
    if expira_em is not None and expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=datetime.timezone.utc)
    if reset_token is None or reset_token.usado_em is not None or expira_em < agora:
        logger.warning("Tentativa de redefinicao de senha com token invalido ou expirado")
        raise link_invalido

    usuario = db.query(Usuario).filter_by(id=reset_token.usuario_id).first()
    if usuario is None:
        raise link_invalido

    usuario.senha_hash = hash_senha(dados.senha_nova)
    reset_token.usado_em = agora
    db.commit()
    logger.info("Senha redefinida via token: usuario_id=%s", usuario.id)


def _conta_response(usuario: Usuario, db: Session) -> ContaResponse:
    tem_radio_config = db.query(RadioConfig).filter_by(account_id=usuario.account_id).first() is not None
    return ContaResponse(
        id=usuario.account_id,
        nome=usuario.nome,
        email=usuario.email,
        role=usuario.role,
        plano_status=usuario.account.plano_status,
        plano=usuario.account.plano,
        criado_em=usuario.account.criado_em,
        tem_radio_config=tem_radio_config,
    )


@router.get("/me", response_model=ContaResponse)
def me(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)):
    return _conta_response(usuario, db)


@router.patch("/perfil", response_model=ContaResponse)
def atualizar_perfil(
    dados: AtualizarPerfilRequest,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    nome = dados.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um nome")

    usuario.nome = nome
    db.commit()
    db.refresh(usuario)

    return _conta_response(usuario, db)


@router.put("/senha", status_code=status.HTTP_204_NO_CONTENT)
def alterar_senha(
    dados: AlterarSenhaRequest,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        logger.warning("Tentativa de troca de senha com senha atual incorreta: usuario_id=%s", usuario.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta")
    if len(dados.senha_nova) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha precisa ter pelo menos 8 caracteres"
        )

    usuario.senha_hash = hash_senha(dados.senha_nova)
    db.commit()
    logger.info("Senha alterada: usuario_id=%s", usuario.id)
