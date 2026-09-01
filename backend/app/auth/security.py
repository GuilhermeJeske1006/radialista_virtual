import datetime

from fastapi import Response
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

# Cookie httpOnly com o JWT -- alternativa ao Authorization header que o JS do painel
# nao consegue ler (mitiga roubo de token via XSS). O body ainda devolve access_token
# tambem (ver auth/router.py), pra nao quebrar clientes que ainda leem de la.
COOKIE_TOKEN = "radialista_token"

# Cookie separado pra sessao do super-admin (app/admin_sistema/) -- perfil isolado do tenant,
# sem relacao com Usuario/Account, entao usa um cookie proprio em vez de COOKIE_TOKEN. Da' pra
# estar logado como tenant e como super-admin ao mesmo tempo, no mesmo navegador, sem conflito.
COOKIE_ADMIN_TOKEN = "radialista_admin_token"


def hash_senha(senha: str) -> str:
    return _pwd_context.hash(senha)


def verificar_senha(senha: str, hash_: str) -> bool:
    return _pwd_context.verify(senha, hash_)


def criar_token(id_: int, tipo: str = "usuario") -> str:
    expira_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {"sub": str(id_), "tipo": tipo, "exp": expira_em}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def definir_cookie_sessao(response: Response, token: str, cookie_name: str = COOKIE_TOKEN) -> None:
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        # Secure exige HTTPS -- em dev local (frontend_url http://) o cookie nao sairia
        # nunca se forcado sempre True.
        secure=settings.frontend_url.startswith("https://"),
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


def limpar_cookie_sessao(response: Response, cookie_name: str = COOKIE_TOKEN) -> None:
    response.delete_cookie(key=cookie_name, path="/")


def decodificar_token(token: str, tipo_esperado: str = "usuario") -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None

    # Payload sem "tipo" e' token de tenant emitido antes dessa distincao existir --
    # trata como "usuario" pra nao derrubar sessao de quem ja tava logado.
    if payload.get("tipo", "usuario") != tipo_esperado:
        return None

    sub = payload.get("sub")
    if sub is None:
        return None

    return int(sub)
