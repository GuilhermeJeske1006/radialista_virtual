import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import COOKIE_TOKEN, decodificar_token
from app.db.database import get_db
from app.models.account import Account
from app.models.usuario import Usuario

logger = logging.getLogger("radialista.auth")

# auto_error=False -- sem Authorization header nao e' erro na hora, o cookie
# httpOnly (setado no login/registro, ver auth/security.py) e' tentado depois.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_credenciais_invalidas = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais invalidas ou expiradas",
    headers={"WWW-Authenticate": "Bearer"},
)

_acao_restrita_a_admin = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Acao restrita a administradores da conta",
)


def get_current_usuario(
    request: Request,
    token_header: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    token = token_header or request.cookies.get(COOKIE_TOKEN)
    if token is None:
        raise _credenciais_invalidas

    usuario_id = decodificar_token(token)
    if usuario_id is None:
        logger.warning("Token invalido ou expirado")
        raise _credenciais_invalidas

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        logger.warning("Token valido pra usuario_id inexistente ou inativo: %s", usuario_id)
        raise _credenciais_invalidas

    return usuario


def get_current_account(usuario: Usuario = Depends(get_current_usuario)) -> Account:
    return usuario.account


def exigir_admin(usuario: Usuario = Depends(get_current_usuario)) -> Usuario:
    if usuario.role != "admin":
        logger.warning("Usuario nao-admin tentou acao restrita: usuario_id=%s", usuario.id)
        raise _acao_restrita_a_admin
    return usuario
