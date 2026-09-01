import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SuperAdmin(Base):
    """Administrador do sistema (dono da plataforma) -- sem relacao nenhuma com Account/Usuario.
    Login e sessao proprios (ver app/admin_sistema/), so existe pra operar o painel /admin/*.
    Sem tela de cadastro: criado via app/admin_sistema/criar_super_admin.py, papel de operador.
    """

    __tablename__ = "super_admins"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String)
    nome: Mapped[str] = mapped_column(String, default="")

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    criado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
