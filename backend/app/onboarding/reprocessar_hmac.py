"""Corrige contas que ficaram sem chave HMAC configurada no WuzAPI (onboarding original
falhou -- ver app/whatsapp/webhook.py::_verificar_assinatura). Enquanto isso, o webhook
dessas contas aceita mensagem sem checar assinatura.

Uso: python -m app.onboarding.reprocessar_hmac

Pensado pra rodar num cron do SO, ex. a cada hora:
    0 * * * * cd /caminho/backend && .venv/bin/python -m app.onboarding.reprocessar_hmac
"""

import logging
import secrets

import httpx

from app.db.database import SessionLocal
from app.models.account import Account
from app.whatsapp.session_manager import configurar_hmac

logger = logging.getLogger("radialista.onboarding.reprocessar_hmac")


def reprocessar_contas_sem_hmac() -> int:
    """Tenta configurar o HMAC de novo em toda conta com wuzapi_token mas sem
    wuzapi_hmac_key. Devolve quantas contas foram corrigidas nesta execucao."""
    db = SessionLocal()
    try:
        contas = (
            db.query(Account)
            .filter(Account.wuzapi_token.isnot(None), Account.wuzapi_hmac_key.is_(None))
            .all()
        )

        corrigidas = 0
        for account in contas:
            hmac_key = secrets.token_hex(32)
            try:
                configurar_hmac(account.wuzapi_token, hmac_key)
            except httpx.HTTPStatusError:
                logger.warning("Falha ao configurar HMAC: account_id=%s", account.id)
                continue

            account.wuzapi_hmac_key = hmac_key
            db.commit()
            corrigidas += 1
            logger.info("HMAC corrigido: account_id=%s", account.id)

        return corrigidas
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    total = reprocessar_contas_sem_hmac()
    logger.info("Reprocessamento de HMAC concluido: %s conta(s) corrigida(s)", total)
