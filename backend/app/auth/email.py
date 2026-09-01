import html
import logging
import smtplib
from email.message import EmailMessage

from app.config.settings import settings

logger = logging.getLogger(__name__)


def enviar_email_redefinicao_senha(email: str, token: str) -> bool:
    link = f"{settings.frontend_url}/redefinir-senha?token={token}"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga o link em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. Link de redefinicao de senha para %s: %s", email, link)
        return True

    mensagem = EmailMessage()
    mensagem["Subject"] = "Redefinir sua senha - Radialista Virtual"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        "Recebemos um pedido para redefinir sua senha.\n\n"
        f"Clique no link abaixo para criar uma nova senha (valido por 30 minutos):\n{link}\n\n"
        "Se voce nao pediu isso, pode ignorar este e-mail."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
        return True
    except (smtplib.SMTPException, OSError):
        # Falha no envio nao deve derrubar o request (ex.: 500 sem header CORS,
        # pois a excecao nao tratada escapa do CORSMiddleware). Loga e segue.
        logger.exception("Falha ao enviar e-mail de redefinicao de senha para %s", email)
        return False


def _layout_boas_vindas(nome: str, link: str) -> str:
    nome_seguro = html.escape(nome or "")
    return f"""\
<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:0;background-color:#f3ede0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3ede0;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background-color:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e8ddc6;">
            <tr>
              <td style="background-color:#e8a33d;padding:28px 32px;">
                <span style="font-size:18px;font-weight:700;color:#15130f;letter-spacing:.2px;">Radialista Virtual</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h1 style="margin:0 0 16px;font-size:20px;color:#15130f;">Ola, {nome_seguro}!</h1>
                <p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:#3a3628;">
                  Sua conta no Radialista Virtual foi criada com sucesso.
                </p>
                <p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:#3a3628;">
                  O Radialista Virtual e o seu radialista digital: ele monta a programacao, narra
                  as chamadas ao vivo com voz sintetizada e escolhe as musicas de acordo com o
                  estilo e o horario configurados para sua radio.
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;width:100%;background-color:#f8f3e6;border-radius:10px;">
                  <tr>
                    <td style="padding:16px 20px;font-size:14px;line-height:1.8;color:#3a3628;">
                      <strong style="color:#15130f;">Proximos passos</strong><br>
                      &bull; Configure sua radio (nome, estilo musical e horarios)<br>
                      &bull; Cadastre os programas e defina os horarios de cada um<br>
                      &bull; Convide sua equipe, se precisar de mais de um usuario
                    </td>
                  </tr>
                </table>
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="border-radius:10px;background-color:#e8a33d;">
                      <a href="{link}" style="display:inline-block;padding:12px 24px;font-size:14px;font-weight:600;color:#15130f;text-decoration:none;">
                        Acessar o painel
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="margin:24px 0 0;font-size:12px;line-height:1.6;color:#8a8471;">
                  Qualquer duvida, e so responder este e-mail.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def enviar_email_boas_vindas(email: str, nome: str) -> bool:
    link = f"{settings.frontend_url}/painel"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. E-mail de boas-vindas para %s (nome=%s)", email, nome)
        return True

    mensagem = EmailMessage()
    mensagem["Subject"] = "Bem-vindo ao Radialista Virtual"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        f"Ola, {nome}!\n\n"
        "Sua conta no Radialista Virtual foi criada com sucesso.\n\n"
        "O Radialista Virtual e o seu radialista digital: ele monta a programacao, "
        "narra as chamadas ao vivo com voz sintetizada e escolhe as musicas de acordo "
        "com o estilo e o horario configurados para sua radio.\n\n"
        "Proximos passos:\n"
        "- Configure sua radio (nome, estilo musical e horarios de programas)\n"
        "- Cadastre os programas e defina os horarios de cada um\n"
        "- Convide sua equipe, se precisar de mais de um usuario\n\n"
        f"Acesse o painel para comecar:\n{link}\n\n"
        "Qualquer duvida, e so responder este e-mail."
    )
    mensagem.add_alternative(_layout_boas_vindas(nome, link), subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar e-mail de boas-vindas para %s", email)
        return False


def enviar_email_alerta_desconexao(email: str, nome: str) -> bool:
    link = f"{settings.frontend_url}/onboarding"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga em vez de falhar o job.
        logger.info("SMTP nao configurado. Alerta de desconexao do WhatsApp para %s", email)
        return True

    mensagem = EmailMessage()
    mensagem["Subject"] = "WhatsApp desconectado - Radialista Virtual"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        f"Ola, {nome}!\n\n"
        "O WhatsApp da sua radio caiu e o Radialista Virtual parou de atender os ouvintes ate a "
        "sessao voltar.\n\n"
        f"Acesse o painel e reconecte escaneando o QR Code novamente:\n{link}\n\n"
        "Assim que a sessao voltar, o atendimento volta a funcionar sozinho."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar e-mail de alerta de desconexao para %s", email)
        return False


def enviar_email_notificacao(email: str, nome: str, titulo: str, mensagem: str) -> bool:
    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga em vez de falhar o fluxo que disparou a notificacao.
        logger.info("SMTP nao configurado. Notificacao '%s' para %s: %s", titulo, email, mensagem)
        return True

    email_msg = EmailMessage()
    email_msg["Subject"] = f"{titulo} - Radialista Virtual"
    email_msg["From"] = settings.smtp_from
    email_msg["To"] = email
    email_msg.set_content(f"Ola, {nome}!\n\n{mensagem}\n\nAcesse o painel para mais detalhes:\n{settings.frontend_url}")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(email_msg)
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar e-mail de notificacao '%s' para %s", titulo, email)
        return False


def enviar_email_convite(email: str, token: str, nome_radio: str) -> bool:
    link = f"{settings.frontend_url}/convite?token={token}"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga o link em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. Link de convite para %s: %s", email, link)
        return True

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Convite para {nome_radio or 'a radio'} - Radialista Virtual"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        f"Voce foi convidado para fazer parte da equipe de {nome_radio or 'uma radio'} no Radialista Virtual.\n\n"
        f"Clique no link abaixo para criar sua senha e ativar sua conta:\n{link}\n\n"
        "Se voce nao esperava este convite, pode ignorar este e-mail."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar e-mail de convite para %s", email)
        return False
