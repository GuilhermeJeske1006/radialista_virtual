import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import COOKIE_ADMIN_TOKEN, decodificar_token
from app.db.database import get_db
from app.models.super_admin import SuperAdmin

logger = logging.getLogger("radialista.admin_sistema")

# auto_error=False -- mesmo motivo do OAuth2PasswordBearer em app/auth/dependencies.py: sem
# Authorization header nao e' erro na hora, o cookie httpOnly e' tentado depois.
_oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="/admin/auth/login", auto_error=False)

_credenciais_invalidas = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais invalidas ou expiradas",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_super_admin(
    request: Request,
    token_header: str | None = Depends(_oauth2_scheme_admin),
    db: Session = Depends(get_db),
) -> SuperAdmin:
    token = token_header or request.cookies.get(COOKIE_ADMIN_TOKEN)
    if token is None:
        raise _credenciais_invalidas

    admin_id = decodificar_token(token, tipo_esperado="super_admin")
    if admin_id is None:
        logger.warning("Token de admin invalido ou expirado")
        raise _credenciais_invalidas

    admin = db.get(SuperAdmin, admin_id)
    if admin is None or not admin.ativo:
        logger.warning("Token valido pra super_admin_id inexistente ou inativo: %s", admin_id)
        raise _credenciais_invalidas

    return admin
