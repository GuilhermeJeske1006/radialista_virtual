import logging

from sqlalchemy.orm import Session

from app.auth.email import enviar_email_notificacao
from app.models.account import Account
from app.models.notificacao import Notificacao

logger = logging.getLogger("radialista.notificacoes")


def criar_notificacao(
    db: Session,
    usuario_id: int,
    tipo: str,
    titulo: str,
    mensagem: str,
    link: str | None = None,
) -> Notificacao:
    notificacao = Notificacao(
        usuario_id=usuario_id,
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        link=link,
    )
    db.add(notificacao)
    db.commit()
    db.refresh(notificacao)
    return notificacao


def notificar_admins(
    db: Session,
    account: Account,
    tipo: str,
    titulo: str,
    mensagem: str,
    link: str | None = None,
    enviar_email: bool = False,
) -> list[Notificacao]:
    """Cria a notificacao pra cada admin ativo da conta -- billing e equipe sao decisao de
    admin, entao membro comum nao precisa ser avisado. `enviar_email` e' pra evento urgente
    o bastante pra nao depender do admin abrir o painel (ex.: pagamento falhou)."""
    admins = [u for u in account.usuarios if u.role == "admin" and u.ativo]
    notificacoes = [criar_notificacao(db, admin.id, tipo, titulo, mensagem, link) for admin in admins]

    if enviar_email:
        for admin in admins:
            enviar_email_notificacao(admin.email, admin.nome, titulo, mensagem)

    if not admins:
        logger.warning("Notificacao sem admin ativo pra receber: account_id=%s tipo=%s", account.id, tipo)

    return notificacoes
