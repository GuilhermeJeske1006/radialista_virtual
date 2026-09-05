"""Avisa por e-mail o admin da conta quando a sessao do WhatsApp cai -- sem isso a
radio para de atender ouvintes sem ninguem perceber ate reclamarem.

Uso: python -m app.onboarding.alertar_desconexao

Pensado pra rodar num cron do SO, ex. a cada 5 minutos:
    */5 * * * * cd /caminho/backend && .venv/bin/python -m app.onboarding.alertar_desconexao
"""

import logging

import httpx

from app.auth.email import enviar_email_alerta_desconexao
from app.db.database import SessionLocal
from app.models.account import Account
from app.notificacoes.service import criar_notificacao
from app.whatsapp.session_manager import obter_status_sessao

logger = logging.getLogger("radialista.onboarding.alertar_desconexao")


def verificar_desconexoes() -> int:
    """Confere a sessao do WuzAPI de toda conta com wuzapi_token e manda e-mail pro
    admin quando encontra uma caida (uma unica vez, ate reconectar). Devolve quantos
    alertas foram enviados nesta execucao."""
    db = SessionLocal()
    try:
        contas = db.query(Account).filter(Account.wuzapi_token.isnot(None)).all()

        alertas_enviados = 0
        for account in contas:
            try:
                resultado = obter_status_sessao(account.wuzapi_token)
            except httpx.HTTPStatusError:
                logger.warning("Falha ao consultar status da sessao: account_id=%s", account.id)
                continue

            logado = (resultado.get("data") or {}).get("loggedIn", False)

            if logado:
                # reconectou -- destrava o alerta pra proxima queda avisar de novo
                if account.wuzapi_desconectado_alerta_enviado:
                    account.wuzapi_desconectado_alerta_enviado = False
                    db.commit()
                continue

            if account.wuzapi_desconectado_alerta_enviado:
                continue  # ja avisado nessa queda, nao manda de novo a cada execucao

            admin = next((u for u in account.usuarios if u.role == "admin" and u.ativo), None)
            if admin is None:
                continue

            if enviar_email_alerta_desconexao(admin.email, admin.nome):
                account.wuzapi_desconectado_alerta_enviado = True
                db.commit()
                criar_notificacao(
                    db,
                    admin.id,
                    "whatsapp",
                    "WhatsApp desconectado",
                    "O WhatsApp da sua radio caiu. Reconecte escaneando o QR Code novamente.",
                    link="/conversas",
                )
                alertas_enviados += 1
                logger.info("Alerta de desconexao enviado: account_id=%s", account.id)

        return alertas_enviados
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    total = verificar_desconexoes()
    logger.info("Verificacao de desconexao concluida: %s alerta(s) enviado(s)", total)
