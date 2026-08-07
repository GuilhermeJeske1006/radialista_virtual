import datetime

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_senha(senha: str) -> str:
    return _pwd_context.hash(senha)


def verificar_senha(senha: str, hash_: str) -> bool:
    return _pwd_context.verify(senha, hash_)


def criar_token(account_id: int) -> str:
    expira_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {"sub": str(account_id), "exp": expira_em}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decodificar_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None

    account_id = payload.get("sub")
    if account_id is None:
        return None

    return int(account_id)
