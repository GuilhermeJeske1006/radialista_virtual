import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth.dependencies import exigir_admin, get_current_account
from app.billing.limites import mensagens_respondidas_no_mes
from app.billing.stripe_client import cliente, criar_sessao_checkout, criar_portal_sessao, obter_cartao_mais_recente, dados_stripe
from app.billing.fechamento import fechar, registrar_pagamento, periodo
from app.billing.flex import conta_consumo
from app.config.settings import settings
from app.db.database import get_db
from app.models.account import Account
from app.models.consumo_flex import EventoCobranca, FaturaConsumo
from app.models.radio_config import RadioConfig

router = APIRouter(prefix='/billing', tags=['billing'])


class CheckoutRequest(BaseModel):
    plano_id: str = 'flex'
    usar_cartao_salvo: bool = False


@router.post('/checkout')
def checkout(dados: CheckoutRequest, account=Depends(get_current_account), db=Depends(get_db), _admin=Depends(exigir_admin)):
    if dados.plano_id != 'flex':
        raise HTTPException(400, 'O plano disponível é Locufy Flex')
    if account.plano_status == 'ativo':
        raise HTTPException(409, 'Assinatura já ativa')
    sub = criar_sessao_checkout(account, 'flex', db, dados.usar_cartao_salvo)
    secret = dados_stripe(sub.latest_invoice).get('confirmation_secret')
    return {'client_secret': secret.get('client_secret') if secret else None}


@router.post('/portal')
def portal(account=Depends(get_current_account), _admin=Depends(exigir_admin)):
    if not account.stripe_customer_id:
        raise HTTPException(402, 'Assine primeiro')
    return {'url': criar_portal_sessao(account).url}


@router.get('/cartao')
def cartao(account=Depends(get_current_account), _admin=Depends(exigir_admin)):
    return {'cartao': obter_cartao_mais_recente(account)}


@router.get('/status')
def status_plano(account=Depends(get_current_account), db=Depends(get_db)):
    return {'plano': 'flex', 'plano_status': account.plano_status, 'mensalidade_brl': 69.90,
        'agentes_usados': db.query(RadioConfig).filter_by(account_id=account.id).count(),
        'agentes_limite': None, 'agentes_extras': 0,
        'mensagens_usadas': mensagens_respondidas_no_mes(db, account.id),
        'mensagens_limite': None, 'mensagens_extras': 0}


@router.post('/agentes-extras/checkout')
@router.post('/excedente-mensagens/checkout')
@router.post('/trocar-plano')
def oferta_encerrada(_admin=Depends(exigir_admin)):
    raise HTTPException(410, 'Locufy Flex inclui WhatsApp completo, sem pacotes ou planos adicionais')


def assinatura_fatura(invoice):
    return ((invoice.get('parent') or {}).get('subscription_details') or {}).get('subscription') or invoice.get('subscription')


@router.post('/webhook')
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    try:
        event = dados_stripe(stripe.Webhook.construct_event(await request.body(), request.headers.get('stripe-signature', ''), settings.stripe_webhook_secret))
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, 'Assinatura inválida') from None
    if db.get(EventoCobranca, event['id']):
        return {'status': 'duplicado'}
    tipo, dados = event['type'], event['data']['object']
    account = db.scalar(select(Account).where(Account.stripe_customer_id == dados.get('customer'))) if dados.get('customer') else None
    if account:
        # Serializa inclusive dois IDs de evento diferentes referentes à mesma fatura.
        conta_consumo(db, account.id)
        if db.get(EventoCobranca, event['id']):
            return {'status': 'duplicado'}
        c = cliente()
        if tipo.startswith('invoice.'):
            # Estado atual vence webhooks atrasados (paid seguido de payment_failed antigo).
            invoice = dados_stripe(c.v1.invoices.retrieve(dados['id']))
            if (assinatura_fatura(invoice) or (invoice.get('metadata') or {}).get('assinatura_cancelada')) == account.stripe_subscription_id:
                if tipo == 'invoice.created' and invoice.get('billing_reason') != 'subscription_create':
                    fechar(db, account, invoice, c)
                elif tipo in ('invoice.paid', 'invoice.payment_failed', 'invoice.payment_action_required', 'invoice.finalized'):
                    registrar_pagamento(db, account, invoice, pendente=tipo != 'invoice.finalized')
                    for linha in invoice.get('lines', {}).get('data', []):
                        if ((linha.get('parent') or {}).get('type') == 'subscription_item_details' or linha.get('type') == 'subscription') and linha.get('period'):
                            conta = conta_consumo(db, account.id)
                            inicio, fim = periodo(linha['period']['start']), periodo(linha['period']['end'])
                            if conta.ciclo_fim is None or conta.ciclo_fim.replace(tzinfo=inicio.tzinfo) < fim:
                                conta.ciclo_inicio, conta.ciclo_fim = inicio, fim
        elif tipo in ('customer.subscription.updated', 'customer.subscription.deleted') and dados['id'] == account.stripe_subscription_id:
            sub = dados_stripe(c.v1.subscriptions.retrieve(dados['id']))
            if sub['status'] in ('canceled', 'unpaid', 'past_due'):
                account.plano_status = 'cancelado' if sub['status'] == 'canceled' else 'inadimplente'
            # Cancelamento: uma única fatura final, apenas uso, sem mensalidade futura.
            if sub['status'] == 'canceled':
                anterior = db.scalar(select(FaturaConsumo).where(FaturaConsumo.account_id == account.id, FaturaConsumo.assinatura == sub['id']).order_by(FaturaConsumo.fim.desc()).limit(1))
                if anterior and anterior.fim.timestamp() == int(sub.get('canceled_at') or event['created']):
                    invoice = c.v1.invoices.retrieve(anterior.id)
                else:
                    invoice = c.v1.invoices.create({'customer': account.stripe_customer_id, 'auto_advance': False,
                    'pending_invoice_items_behavior': 'exclude',
                    'metadata': {'assinatura_cancelada': sub['id']}},
                    options={'idempotency_key': f"cancelamento:{sub['id']}"})
                fim = int(sub.get('canceled_at') or event['created'])
                invoice = dados_stripe(invoice)
                invoice['period_start'] = int(sub.get('start_date') or fim)
                invoice['period_end'] = fim
                fechar(db, account, invoice, c)
    try:
        db.add(EventoCobranca(id=event['id'], tipo=tipo))
        db.commit()
    except IntegrityError:
        db.rollback()
        return {'status': 'duplicado'}
    return {'status': 'ok'}
