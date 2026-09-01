import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_admin, get_current_account
from app.billing.limites import (
    limite_agentes_efetivo,
    limite_mensagens_efetivo,
    mensagens_extras_do_mes,
    mensagens_respondidas_no_mes,
    mes_referencia_atual,
)
from app.billing.stripe_client import (
    criar_portal_sessao,
    criar_sessao_checkout,
    criar_sessao_checkout_agente_extra,
    criar_sessao_checkout_excedente_mensagens,
    plano_por_price_id,
    trocar_plano_assinatura,
)
from app.config.settings import settings
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip
from app.models.account import Account
from app.models.compra_excedente import CompraExcedente
from app.models.radio_config import RadioConfig
from app.notificacoes.service import notificar_admins
from app.planos import PLANOS

logger = logging.getLogger("radialista.billing")
router = APIRouter(prefix="/billing", tags=["billing"])


class ExcedenteMensagensRequest(BaseModel):
    blocos: int = Field(default=1, ge=1, le=50)


class CheckoutRequest(BaseModel):
    plano_id: str = "starter"


class TrocarPlanoRequest(BaseModel):
    plano_id: str


def _exigir_plano_ativo(account: Account) -> None:
    if account.plano_status != "ativo":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Assine um plano antes de comprar itens avulsos.",
        )


def _exigir_plano_valido(plano_id: str) -> None:
    if plano_id not in PLANOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plano invalido")


def _status_plano(account: Account, db: Session) -> dict:
    agentes_usados = db.query(RadioConfig).filter_by(account_id=account.id).count()
    mensagens_usadas = mensagens_respondidas_no_mes(db, account.id)

    return {
        "plano_status": account.plano_status,
        "plano": account.plano,
        "agentes_usados": agentes_usados,
        "agentes_limite": limite_agentes_efetivo(account),
        "agentes_extras": account.agentes_extras,
        "mensagens_usadas": mensagens_usadas,
        "mensagens_limite": limite_mensagens_efetivo(db, account),
        "mensagens_extras": mensagens_extras_do_mes(db, account.id),
    }


@router.post("/checkout")
def checkout(
    dados: CheckoutRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
    _admin=Depends(exigir_admin),
):
    _exigir_plano_valido(dados.plano_id)
    if account.plano_status == "ativo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voce ja tem uma assinatura ativa -- use a troca de plano.",
        )
    assinatura = criar_sessao_checkout(account, dados.plano_id, db)
    return {"client_secret": assinatura.latest_invoice.payment_intent.client_secret}


@router.post("/trocar-plano")
def trocar_plano(
    dados: TrocarPlanoRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
    _admin=Depends(exigir_admin),
):
    _exigir_plano_valido(dados.plano_id)
    if account.plano_status != "ativo" or not account.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Nenhuma assinatura ativa pra trocar de plano.",
        )
    if dados.plano_id == account.plano:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voce ja esta nesse plano.")

    trocar_plano_assinatura(account, dados.plano_id)
    account.plano = dados.plano_id
    db.commit()
    return _status_plano(account, db)


@router.post("/portal")
def portal(account: Account = Depends(get_current_account), _admin=Depends(exigir_admin)):
    if not account.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Assine um plano primeiro.")
    sessao = criar_portal_sessao(account)
    return {"url": sessao.url}


@router.post("/agentes-extras/checkout")
def checkout_agente_extra(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
    _admin=Depends(exigir_admin),
):
    _exigir_plano_ativo(account)
    assinatura = criar_sessao_checkout_agente_extra(account, db)
    return {"client_secret": assinatura.latest_invoice.payment_intent.client_secret}


@router.post("/excedente-mensagens/checkout")
def checkout_excedente_mensagens(
    dados: ExcedenteMensagensRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
    _admin=Depends(exigir_admin),
):
    _exigir_plano_ativo(account)
    intent = criar_sessao_checkout_excedente_mensagens(account, dados.blocos, db)
    return {"client_secret": intent.client_secret}


@router.get("/status")
def status_plano(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return _status_plano(account, db)


@router.post(
    "/webhook",
    dependencies=[Depends(limitar_por_ip("billing_webhook", limite=120, janela_segundos=60))],
)
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    assinatura = request.headers.get("stripe-signature", "")

    try:
        evento = stripe.Webhook.construct_event(payload, assinatura, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning("Webhook Stripe com payload/assinatura invalidos")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload invalido")

    tipo = evento["type"]
    dados = evento["data"]["object"]
    logger.info("Webhook Stripe recebido: tipo=%s", tipo)

    if tipo == "invoice.paid":
        # Assinatura (plano ou agente extra) criada direto via API (payment_behavior=
        # default_incomplete, ver stripe_client.py) fica "incomplete" ate o pagamento da
        # primeira invoice ser confirmado -- billing_reason=="subscription_create" so'
        # acontece nessa primeira invoice, nunca em renovacao mensal (essa vem como
        # "subscription_cycle"), entao serve de sinal de ativacao sem risco de repetir todo mes.
        if dados.get("billing_reason") != "subscription_create":
            return {"status": "ignorado"}

        # A partir da API version usada nessa conta Stripe, invoice nao tem mais "subscription"/
        # "subscription_details" no nivel raiz -- o line item (sempre 1, um price por
        # assinatura) carrega o metadata da subscription e a referencia pra ela.
        linhas = dados.get("lines", {}).get("data") or []
        metadata = linhas[0].get("metadata", {}) if linhas else {}
        subscription_id = None
        if linhas:
            detalhes_item = (linhas[0].get("parent") or {}).get("subscription_item_details") or {}
            subscription_id = detalhes_item.get("subscription")

        account_id = metadata.get("account_id")
        account = db.get(Account, int(account_id)) if account_id else None
        if account is None:
            logger.warning("invoice.paid (subscription_create) sem account_id resolvivel")
            return {"status": "ok"}

        tipo_compra = metadata.get("tipo")
        if tipo_compra == "assinatura":
            account.plano_status = "ativo"
            account.plano = metadata.get("plano", "starter")
            account.stripe_subscription_id = subscription_id
            _definir_ativo(db, account, True)
            db.commit()
            logger.info("Assinatura ativada: account_id=%s plano=%s", account.id, account.plano)
            notificar_admins(
                db,
                account,
                "billing",
                "Assinatura ativada",
                f"Sua assinatura do plano {account.plano} foi ativada com sucesso.",
                link="/billing",
            )
        elif tipo_compra == "agente_extra":
            account.agentes_extras += 1
            db.commit()
            logger.info("Agente extra ativado: account_id=%s", account.id)

    elif tipo == "payment_intent.succeeded":
        metadata = dados.get("metadata", {})
        if metadata.get("tipo") != "excedente_mensagens":
            return {"status": "ignorado"}

        account_id = metadata.get("account_id")
        account = db.get(Account, int(account_id)) if account_id else None
        if account is None:
            logger.warning("payment_intent.succeeded (excedente) sem account_id resolvivel")
            return {"status": "ok"}

        blocos = int(metadata.get("blocos", "1"))
        db.add(
            CompraExcedente(
                account_id=account.id,
                quantidade=blocos * 1000,
                mes_referencia=mes_referencia_atual(),
            )
        )
        db.commit()
        logger.info("Excedente de mensagens creditado: account_id=%s blocos=%s", account.id, blocos)

    elif tipo == "customer.subscription.deleted":
        account = db.query(Account).filter_by(stripe_customer_id=dados.get("customer")).first()
        # Um customer pode ter mais de uma subscription (a do plano + uma por agente extra
        # comprado) -- so' a subscription principal (account.stripe_subscription_id) representa
        # a assinatura em si. Cancelar so' um agente extra nao pode derrubar a conta inteira.
        if account is not None and dados.get("id") == account.stripe_subscription_id:
            account.plano_status = "cancelado"
            _definir_ativo(db, account, False)
            db.commit()
            logger.info("Plano cancelado: account_id=%s", account.id)
            notificar_admins(
                db,
                account,
                "billing",
                "Assinatura cancelada",
                "Sua assinatura foi cancelada. Os agentes da radio foram desativados.",
                link="/billing",
                enviar_email=True,
            )

    elif tipo == "customer.subscription.updated":
        novo_status = dados.get("status")
        if novo_status not in ("canceled", "unpaid", "active", "trialing"):
            return {"status": "ignorado"}

        account = db.query(Account).filter_by(stripe_customer_id=dados.get("customer")).first()
        # Mesmo motivo do subscription.deleted acima: ignora updates de subscriptions que nao
        # sao a assinatura principal (ex.: subscription de agente extra mudando de status).
        if account is not None and dados.get("id") == account.stripe_subscription_id:
            if novo_status in ("canceled", "unpaid"):
                account.plano_status = "cancelado"
                _definir_ativo(db, account, False)
                logger.info("Plano cancelado: account_id=%s", account.id)
                titulo, mensagem = (
                    ("Pagamento falhou", "Nao conseguimos processar o pagamento da sua assinatura.")
                    if novo_status == "unpaid"
                    else ("Assinatura cancelada", "Sua assinatura foi cancelada.")
                )
                notificar_admins(db, account, "billing", titulo, mensagem, link="/billing", enviar_email=True)
            else:
                # Preco pode ter mudado fora do nosso endpoint de troca (ex.: portal do
                # Stripe, ou ajuste manual no dashboard) -- sincroniza o plano local com
                # o price atual da assinatura em vez de confiar so' no que a gente setou.
                itens = dados.get("items", {}).get("data") or []
                price_id = itens[0].get("price", {}).get("id") if itens else None
                plano_novo = plano_por_price_id(price_id)
                if plano_novo and plano_novo != account.plano:
                    account.plano = plano_novo
                    logger.info("Plano sincronizado via webhook: account_id=%s plano=%s", account.id, plano_novo)
            db.commit()

    return {"status": "ok"}


def _definir_ativo(db: Session, account: Account, ativo: bool) -> None:
    db.query(RadioConfig).filter_by(account_id=account.id).update({"ativo": ativo})
