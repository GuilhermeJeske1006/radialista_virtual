from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.admin_sistema.dependencies import get_current_super_admin
from app.auth.security import COOKIE_ADMIN_TOKEN, limpar_cookie_sessao
from app.models.super_admin import SuperAdmin

# Login e' unico pra tenant e super-admin (ver app/auth/router.py::login) -- esse router so
# cuida do que e' especifico da sessao de super-admin depois de autenticado.
router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


class SuperAdminResponse(BaseModel):
    id: int
    nome: str
    email: str


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    limpar_cookie_sessao(response, cookie_name=COOKIE_ADMIN_TOKEN)


@router.get("/me", response_model=SuperAdminResponse)
def me(admin: SuperAdmin = Depends(get_current_super_admin)):
    return SuperAdminResponse(id=admin.id, nome=admin.nome, email=admin.email)
