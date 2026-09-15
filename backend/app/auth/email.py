import html
import logging
import smtplib
from email.message import EmailMessage

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Paleta do manual da marca (rebrand-locufy.sh) -- fundo e superfícies do Azul
# Estúdio Profissional, acento no meio do gradiente do logo, laranja para
# alerta/destrutivo. Fontes ficam no stack padrão do sistema: cliente de
# e-mail não carrega a Sama Latin/Gotham Rounded licenciadas do painel.
_BG = "#131c2e"
_SURFACE = "#1b263b"
_SURFACE_2 = "#24334f"
_BORDER = "rgba(255,255,255,0.14)"
_TEXT = "#ffffff"
_TEXT_MUTED = "rgba(255,255,255,0.72)"
_TEXT_FAINT = "rgba(255,255,255,0.45)"
_ACENTO = "#3167e7"
_LARANJA = "#ff8c00"
_GRAFITE = "#18181a"
_FONTE = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# Logotipo horizontal branco oficial (frontend-painel/public/Logos) -- o mesmo
# arquivo usado na landing page sobre fundo escuro/gradiente. Proporção
# original 4213x1908; e-mail não carrega SVG/currentColor do painel, então
# usamos o PNG publicado pelo próprio frontend em vez de redesenhar a marca.
_LOGO_LARGURA = 148
_LOGO_ALTURA = 67


def _botao_html(label: str, href: str, tom: str = "acento") -> str:
    cor_bg, cor_texto = (_LARANJA, _GRAFITE) if tom == "laranja" else (_ACENTO, "#ffffff")
    return f"""\
<table role="presentation" cellpadding="0" cellspacing="0">
  <tr>
    <td style="border-radius:999px;background-color:{cor_bg};">
      <a href="{href}" style="display:inline-block;padding:13px 28px;font-size:14px;font-weight:600;color:{cor_texto};text-decoration:none;">
        {html.escape(label)}
      </a>
    </td>
  </tr>
</table>"""


def _caixa_destaque_html(titulo: str, itens: list[str]) -> str:
    linhas = "<br>".join(f"&bull; {html.escape(item)}" for item in itens)
    return f"""\
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;width:100%;background-color:{_SURFACE_2};border-radius:14px;">
  <tr>
    <td style="padding:18px 22px;font-size:14px;line-height:1.8;color:{_TEXT_MUTED};">
      <strong style="color:{_TEXT};">{html.escape(titulo)}</strong><br>
      {linhas}
    </td>
  </tr>
</table>"""


def _email_shell(corpo_html: str, preheader: str = "") -> str:
    """Moldura compartilhada por todo e-mail transacional: banda com o
    gradiente do logo no topo (único lugar do e-mail onde o roxo puro entra,
    igual à regra da sidebar) e cartão escuro do Azul Estúdio por baixo."""
    preheader_html = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(preheader)}</div>'
        if preheader
        else ""
    )
    return f"""\
<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:0;background-color:{_BG};font-family:{_FONTE};">
    {preheader_html}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BG};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background-color:{_SURFACE};border-radius:24px;overflow:hidden;border:1px solid {_BORDER};">
            <tr>
              <td style="background-color:{_ACENTO};background-image:linear-gradient(110deg,#631bf6 0%,#3167e7 52%,#00b4d8 100%);padding:26px 32px;">
                <img src="{settings.frontend_url}/Logos/Logo_Locufy_Logotipo_Horizontal_01.png" width="{_LOGO_LARGURA}" height="{_LOGO_ALTURA}" alt="Locufy" style="display:block;border:0;outline:none;">
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                {corpo_html}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _paragrafo(texto: str) -> str:
    return f'<p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:{_TEXT_MUTED};">{texto}</p>'


def _titulo(texto: str) -> str:
    return f'<h1 style="margin:0 0 16px;font-size:20px;font-weight:600;color:{_TEXT};">{texto}</h1>'


def _rodape(texto: str) -> str:
    return f'<p style="margin:24px 0 0;font-size:12px;line-height:1.6;color:{_TEXT_FAINT};">{html.escape(texto)}</p>'


def enviar_email_redefinicao_senha(email: str, token: str) -> bool:
    link = f"{settings.frontend_url}/redefinir-senha?token={token}"

    if not settings.smtp_host:
        if settings.sentry_environment == "production":
            # Nunca loga o token em producao -- se SMTP cair aqui, o log nao pode virar
            # uma forma de assumir a conta de qualquer usuario que pediu redefinicao.
            logger.warning("SMTP nao configurado. Redefinicao de senha para %s nao pode ser enviada.", email)
            return False
        # Dev local -- loga o link (com token) em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. Link de redefinicao de senha para %s: %s", email, link)
        return True

    mensagem = EmailMessage()
    mensagem["Subject"] = "Redefinir sua senha - Locufy"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        "Recebemos um pedido para redefinir sua senha.\n\n"
        f"Clique no link abaixo para criar uma nova senha (valido por 30 minutos):\n{link}\n\n"
        "Se voce nao pediu isso, pode ignorar este e-mail."
    )
    corpo = (
        _titulo("Redefinir sua senha")
        + _paragrafo("Recebemos um pedido para redefinir sua senha.")
        + _paragrafo("Clique no botão abaixo para criar uma nova senha. O link vale por 30 minutos.")
        + _botao_html("Criar nova senha", link)
        + _rodape("Se você não pediu isso, pode ignorar este e-mail.")
    )
    mensagem.add_alternative(_email_shell(corpo, preheader="Crie uma nova senha em até 30 minutos."), subtype="html")

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


def enviar_email_boas_vindas(email: str, nome: str) -> bool:
    link = f"{settings.frontend_url}/painel"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. E-mail de boas-vindas para %s (nome=%s)", email, nome)
        return True

    nome_seguro = html.escape(nome or "")

    mensagem = EmailMessage()
    mensagem["Subject"] = "Bem-vindo ao Locufy"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        f"Ola, {nome}!\n\n"
        "Sua conta no Locufy foi criada com sucesso.\n\n"
        "O Locufy e o seu radialista digital: ele monta a programacao, "
        "narra as chamadas ao vivo com voz sintetizada e escolhe as musicas de acordo "
        "com o estilo e o horario configurados para sua radio.\n\n"
        "Proximos passos:\n"
        "- Configure sua radio (nome, estilo musical e horarios de programas)\n"
        "- Cadastre os programas e defina os horarios de cada um\n"
        "- Convide sua equipe, se precisar de mais de um usuario\n\n"
        f"Acesse o painel para comecar:\n{link}\n\n"
        "Qualquer duvida, e so responder este e-mail."
    )
    corpo = (
        _titulo(f"Olá, {nome_seguro}!")
        + _paragrafo("Sua conta no Locufy foi criada com sucesso.")
        + _paragrafo(
            "O Locufy é o seu radialista digital: ele monta a programação, narra as "
            "chamadas ao vivo com voz sintetizada e escolhe as músicas de acordo com o "
            "estilo e o horário configurados para sua rádio."
        )
        + _caixa_destaque_html(
            "Próximos passos",
            [
                "Configure sua rádio (nome, estilo musical e horários)",
                "Cadastre os programas e defina os horários de cada um",
                "Convide sua equipe, se precisar de mais de um usuário",
            ],
        )
        + _botao_html("Acessar o painel", link)
        + _rodape("Qualquer dúvida, é só responder este e-mail.")
    )
    mensagem.add_alternative(_email_shell(corpo, preheader="Sua conta foi criada. Vamos configurar sua rádio."), subtype="html")

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
    link = f"{settings.frontend_url}/conversas"

    if not settings.smtp_host:
        # Sem SMTP configurado (dev local) -- loga em vez de falhar o job.
        logger.info("SMTP nao configurado. Alerta de desconexao do WhatsApp para %s", email)
        return True

    nome_seguro = html.escape(nome or "")

    mensagem = EmailMessage()
    mensagem["Subject"] = "WhatsApp desconectado - Locufy"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        f"Ola, {nome}!\n\n"
        "O WhatsApp da sua radio caiu e o Locufy parou de atender os ouvintes ate a "
        "sessao voltar.\n\n"
        f"Acesse o painel e reconecte escaneando o QR Code novamente:\n{link}\n\n"
        "Assim que a sessao voltar, o atendimento volta a funcionar sozinho."
    )
    corpo = (
        _titulo(f"Olá, {nome_seguro}!")
        + _paragrafo(
            "O WhatsApp da sua rádio caiu e o Locufy parou de atender os ouvintes até a "
            "sessão voltar."
        )
        + _paragrafo("Acesse o painel e reconecte escaneando o QR Code novamente.")
        + _botao_html("Reconectar WhatsApp", link, tom="laranja")
        + _rodape("Assim que a sessão voltar, o atendimento volta a funcionar sozinho.")
    )
    mensagem.add_alternative(
        _email_shell(corpo, preheader="O WhatsApp da sua rádio caiu. Reconecte pelo painel."), subtype="html"
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

    nome_seguro = html.escape(nome or "")
    titulo_seguro = html.escape(titulo or "")
    mensagem_segura = html.escape(mensagem or "")

    email_msg = EmailMessage()
    email_msg["Subject"] = f"{titulo} - Locufy"
    email_msg["From"] = settings.smtp_from
    email_msg["To"] = email
    email_msg.set_content(f"Ola, {nome}!\n\n{mensagem}\n\nAcesse o painel para mais detalhes:\n{settings.frontend_url}")
    corpo = (
        _titulo(f"Olá, {nome_seguro}!")
        + _paragrafo(f"<strong style=\"color:{_TEXT};\">{titulo_seguro}</strong>")
        + _paragrafo(mensagem_segura)
        + _botao_html("Acessar o painel", settings.frontend_url)
    )
    email_msg.add_alternative(_email_shell(corpo, preheader=titulo_seguro), subtype="html")

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
        if settings.sentry_environment == "production":
            # Nunca loga o token em producao -- mesma razao do link de redefinicao de senha.
            logger.warning("SMTP nao configurado. Convite para %s nao pode ser enviado.", email)
            return False
        # Dev local -- loga o link (com token) em vez de falhar o fluxo.
        logger.info("SMTP nao configurado. Link de convite para %s: %s", email, link)
        return True

    nome_radio_seguro = html.escape(nome_radio or "uma rádio")

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Convite para {nome_radio or 'a radio'} - Locufy"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = email
    mensagem.set_content(
        f"Voce foi convidado para fazer parte da equipe de {nome_radio or 'uma radio'} no Locufy.\n\n"
        f"Clique no link abaixo para criar sua senha e ativar sua conta:\n{link}\n\n"
        "Se voce nao esperava este convite, pode ignorar este e-mail."
    )
    corpo = (
        _titulo("Você foi convidado")
        + _paragrafo(f"Você foi convidado para fazer parte da equipe de <strong style=\"color:{_TEXT};\">{nome_radio_seguro}</strong> no Locufy.")
        + _paragrafo("Clique no botão abaixo para criar sua senha e ativar sua conta.")
        + _botao_html("Ativar minha conta", link)
        + _rodape("Se você não esperava este convite, pode ignorar este e-mail.")
    )
    mensagem.add_alternative(
        _email_shell(corpo, preheader=f"Você foi convidado para {nome_radio_seguro} no Locufy."), subtype="html"
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
