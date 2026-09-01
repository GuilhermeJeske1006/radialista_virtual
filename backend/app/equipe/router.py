import datetime
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_admin, get_current_usuario
from app.auth.email import enviar_email_convite
from app.auth.security import criar_token, definir_cookie_sessao, hash_senha
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip
from app.models.account import Account
from app.models.convite_usuario import ConviteUsuario
from app.models.usuario import Usuario
from app.notificacoes.service import notificar_admins

logger = logging.getLogger("radialista.equipe")

TOKEN_CONVITE_VALIDADE_MINUTOS = 60 * 24 * 7  # 7 dias

router = APIRouter(tags=["equipe"])


class UsuarioResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    nome: str
    email: str
    role: str
    ativo: bool
    criado_em: datetime.datetime


class ConviteRequest(BaseModel):
    email: EmailStr
    role: str = "membro"


class ConviteResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    role: str
    expira_em: datetime.datetime
    criado_em: datetime.datetime
    email_enviado: bool = True


class AceitarConviteRequest(BaseModel):
    token: str
    nome: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AlterarRoleRequest(BaseModel):
    role: str


def _contar_admins_ativos(db: Session, account_id: int) -> int:
    return db.query(Usuario).filter_by(account_id=account_id, role="admin", ativo=True).count()


@router.get("/equipe", response_model=list[UsuarioResponse])
def listar_equipe(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).filter_by(account_id=usuario.account_id).order_by(Usuario.criado_em).all()
    return usuarios


@router.get("/equipe/convites", response_model=list[ConviteResponse])
def listar_convites(usuario: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)):
    convites = (
        db.query(ConviteUsuario)
        .filter_by(account_id=usuario.account_id, aceito_em=None, revogado_em=None)
        .order_by(ConviteUsuario.criado_em.desc())
        .all()
    )
    return convites


@router.post(
    "/equipe/convites",
    response_model=ConviteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limitar_por_ip("equipe_convidar", limite=10, janela_segundos=60))],
)
def convidar(
    dados: ConviteRequest,
    usuario: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    if dados.role not in ("admin", "membro"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role invalido")

    ja_e_usuario = (
        db.query(Usuario).filter_by(account_id=usuario.account_id, email=dados.email, ativo=True).first()
    )
    if ja_e_usuario is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este e-mail ja faz parte da equipe")

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expira_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=TOKEN_CONVITE_VALIDADE_MINUTOS
    )

    convite = ConviteUsuario(
        account_id=usuario.account_id,
        email=dados.email,
        role=dados.role,
        token_hash=token_hash,
        convidado_por_usuario_id=usuario.id,
        expira_em=expira_em,
    )
    db.add(convite)
    db.commit()
    db.refresh(convite)

    email_enviado = enviar_email_convite(dados.email, token, usuario.account.nome_radio)
    logger.info("Convite criado: account_id=%s email=%s role=%s", usuario.account_id, dados.email, dados.role)

    return ConviteResponse.model_validate(convite).model_copy(update={"email_enviado": email_enviado})


@router.post(
    "/equipe/convites/{convite_id}/reenviar",
    response_model=ConviteResponse,
    dependencies=[Depends(limitar_por_ip("equipe_reenviar_convite", limite=10, janela_segundos=60))],
)
def reenviar_convite(
    convite_id: int,
    usuario: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    convite = db.query(ConviteUsuario).filter_by(id=convite_id, account_id=usuario.account_id).first()
    if convite is None or convite.aceito_em is not None or convite.revogado_em is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite nao encontrado")

    token = secrets.token_urlsafe(32)
    convite.token_hash = hashlib.sha256(token.encode()).hexdigest()
    convite.expira_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=TOKEN_CONVITE_VALIDADE_MINUTOS
    )
    db.commit()
    db.refresh(convite)

    email_enviado = enviar_email_convite(convite.email, token, usuario.account.nome_radio)
    logger.info("Convite reenviado: convite_id=%s", convite.id)

    return ConviteResponse.model_validate(convite).model_copy(update={"email_enviado": email_enviado})


@router.delete("/equipe/convites/{convite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revogar_convite(
    convite_id: int,
    usuario: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    convite = db.query(ConviteUsuario).filter_by(id=convite_id, account_id=usuario.account_id).first()
    if convite is None or convite.aceito_em is not None or convite.revogado_em is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite nao encontrado")

    convite.revogado_em = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    logger.info("Convite revogado: convite_id=%s", convite.id)


@router.post(
    "/convites/aceitar",
    response_model=TokenResponse,
    dependencies=[Depends(limitar_por_ip("equipe_aceitar_convite", limite=10, janela_segundos=60))],
)
def aceitar_convite(dados: AceitarConviteRequest, response: Response, db: Session = Depends(get_db)):
    convite_invalido = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Convite invalido, expirado ou ja utilizado"
    )
    if len(dados.senha) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A senha precisa ter pelo menos 8 caracteres"
        )

    token_hash = hashlib.sha256(dados.token.encode()).hexdigest()
    convite = db.query(ConviteUsuario).filter_by(token_hash=token_hash).first()
    agora = datetime.datetime.now(datetime.timezone.utc)
    expira_em = convite.expira_em if convite is not None else None
    if expira_em is not None and expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=datetime.timezone.utc)

    if (
        convite is None
        or convite.aceito_em is not None
        or convite.revogado_em is not None
        or expira_em < agora
    ):
        logger.warning("Tentativa de aceitar convite invalido ou expirado")
        raise convite_invalido

    if db.query(Usuario).filter_by(email=convite.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail ja cadastrado")

    usuario = Usuario(
        nome=dados.nome.strip(),
        email=convite.email,
        senha_hash=hash_senha(dados.senha),
        account_id=convite.account_id,
        role=convite.role,
    )
    db.add(usuario)
    convite.aceito_em = agora
    db.commit()
    db.refresh(usuario)

    logger.info("Convite aceito: convite_id=%s usuario_id=%s", convite.id, usuario.id)

    account = db.get(Account, convite.account_id)
    if account is not None:
        notificar_admins(
            db,
            account,
            "equipe",
            "Novo membro na equipe",
            f"{usuario.nome or usuario.email} entrou na equipe da radio.",
            link="/equipe",
        )

    token = criar_token(usuario.id)
    definir_cookie_sessao(response, token)
    return TokenResponse(access_token=token)


@router.patch("/equipe/{usuario_id}/role", response_model=UsuarioResponse)
def alterar_role(
    usuario_id: int,
    dados: AlterarRoleRequest,
    usuario: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    if dados.role not in ("admin", "membro"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role invalido")

    alvo = db.query(Usuario).filter_by(id=usuario_id, account_id=usuario.account_id).first()
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    if alvo.role == "admin" and dados.role != "admin" and _contar_admins_ativos(db, usuario.account_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Precisa haver pelo menos um administrador na equipe"
        )

    alvo.role = dados.role
    db.commit()
    db.refresh(alvo)
    logger.info("Role alterado: usuario_id=%s role=%s", alvo.id, alvo.role)
    return alvo


@router.delete("/equipe/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_usuario(
    usuario_id: int,
    usuario: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    alvo = db.query(Usuario).filter_by(id=usuario_id, account_id=usuario.account_id).first()
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    if alvo.role == "admin" and _contar_admins_ativos(db, usuario.account_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Precisa haver pelo menos um administrador na equipe"
        )

    alvo.ativo = False
    db.commit()
    logger.info("Usuario removido da equipe: usuario_id=%s", alvo.id)
