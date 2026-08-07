import logging
import smtplib
from email.message import EmailMessage

from app.config.settings import settings

logger = logging.getLogger(__name__)


def enviar_email_redefinicao_senha(email: str, token: str) -> None:
    link = f"{settings.frontend_url}/redefinir-senha?token={token}"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga o link em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. Link de redefinicao de senha para %s: %s", email, link)
        return

    mensagem = EmailMessage()
    mensagem["Subject"] = "Redefinir sua senha - Radialista Virtual"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        "Recebemos um pedido para redefinir sua senha.\n\n"
        f"Clique no link abaixo para criar uma nova senha (valido por 30 minutos):\n{link}\n\n"
        "Se voce nao pediu isso, pode ignorar este e-mail."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(mensagem)
