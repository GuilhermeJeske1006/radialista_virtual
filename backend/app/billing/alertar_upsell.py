"""Avisa o admin da conta (notificacao in-app e, se o sinal for de estouro de verdade, e-mail)
quando o uso se aproxima ou passa do limite do plano -- empurra upgrade/compra antes que o
bloqueio (402 em app/config/router.py e app/tts/router.py) pegue o atendimento no meio.

So' avalia conta com marca consolidada (ver app/billing/consolidacao.py); onboarding
incompleto e' outro problema, empurrar upsell nela e' ruido.

Uso: python -m app.billing.alertar_upsell

Pensado pra rodar num cron do SO, ex. a cada 6 horas:
    0 */6 * * * cd /caminho/backend && .venv/bin/python -m app.billing.alertar_upsell
"""

import logging

from app.billing.limites import mes_referencia_atual
from app.billing.upsell import calcular_sinal_upsell
from app.db.database import SessionLocal
from app.models.account import Account
from app.notificacoes.service import notificar_admins

logger = logging.getLogger("radialista.billing.alertar_upsell")


def verificar_gatilhos_upsell() -> int:
    """Calcula o sinal de upsell pra toda conta com plano ativo. Reavisa quando o tipo de
    sinal muda (ex.: "quase estourando" virou "estourou") ou quando o mes de referencia vira,
    mesmo sem o sinal ter "destravado" -- a cota de mensagens reseta todo mes, entao o mesmo
    aperto pode voltar. Devolve quantos avisos foram disparados nesta execucao."""
    db = SessionLocal()
    try:
        contas = db.query(Account).filter(Account.plano_status == "ativo").all()
        mes_atual = mes_referencia_atual()

        avisos_enviados = 0
        for account in contas:
            sinal = calcular_sinal_upsell(db, account)

            if sinal is None:
                if account.upsell_alerta_tipo is not None:
                    account.upsell_alerta_tipo = None
                    account.upsell_alerta_mes = None
                    db.commit()
                continue

            if account.upsell_alerta_tipo == sinal.tipo and account.upsell_alerta_mes == mes_atual:
                continue  # mesmo aviso desse mes, ja mandado -- nao repete a cada execucao do cron

            notificar_admins(
                db,
                account,
                "upsell",
                sinal.titulo,
                sinal.mensagem,
                link="/billing",
                enviar_email=sinal.enviar_email,
            )
            account.upsell_alerta_tipo = sinal.tipo
            account.upsell_alerta_mes = mes_atual
            db.commit()
            avisos_enviados += 1
            logger.info("Aviso de upsell enviado: account_id=%s tipo=%s", account.id, sinal.tipo)

        return avisos_enviados
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    total = verificar_gatilhos_upsell()
    logger.info("Verificacao de gatilhos de upsell concluida: %s aviso(s) enviado(s)", total)
