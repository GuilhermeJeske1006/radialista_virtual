from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decodificar_token
from app.db.database import get_db
from app.models.account import Account

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_credenciais_invalidas = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais invalidas ou expiradas",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_account(
    token: str = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> Account:
    account_id = decodificar_token(token)
    if account_id is None:
        raise _credenciais_invalidas

    account = db.get(Account, account_id)
    if account is None:
        raise _credenciais_invalidas

    return account
