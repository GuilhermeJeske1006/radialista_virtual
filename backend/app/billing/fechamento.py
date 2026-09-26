"""Consolida consumo na fatura recorrente criada pelo Stripe, sem segunda cobrança."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from fastapi import HTTPException
from sqlalchemy import select, update
from app.billing.flex import absorver_abandonadas, centavos, conta_consumo
from app.billing.stripe_client import dados_stripe
from app.config.settings import settings
from app.models.consumo_flex import FaturaConsumo, UsoIA, ContaConsumo, agora


def periodo(valor):
    return datetime.fromtimestamp(valor, timezone.utc)


def fechar(db, account, invoice, stripe_client):
    inicio, fim = periodo(invoice['period_start']), periodo(invoice['period_end'])
    conta_consumo(db, account.id)
    fatura = db.get(FaturaConsumo, invoice['id'])
    if fatura and fatura.estado != 'conferindo':
        if fatura.estado == 'apurada':
            stripe_client.v1.invoices.update(invoice['id'], {'auto_advance': True})
        return fatura
    # Fatura deve ficar em rascunho até todas as operações anteriores ao corte terminarem.
    if invoice.get('status') != 'draft':
        raise HTTPException(409, 'Fatura finalizada: consumo tardio requer ajuste identificado')
    stripe_client.v1.invoices.update(invoice['id'], {'auto_advance': False})
    # Sem isso um único uso órfão manteria a fatura (e a mensalidade) em rascunho para sempre.
    abandono = agora() - timedelta(minutes=settings.ia_operacao_abandonada_minutos)
    absorver_abandonadas(db, account.id, min(fim, abandono))
    pendentes = db.scalar(select(UsoIA.id).where(UsoIA.account_id == account.id,
        UsoIA.iniciado_em < fim, UsoIA.estado.in_(['reservado', 'medido'])).limit(1))
    if pendentes:
        raise HTTPException(503, 'Fechamento aguardando operações em andamento; reentregar evento')
    if not fatura:
        fatura = FaturaConsumo(id=invoice['id'], account_id=account.id,
            assinatura=account.stripe_subscription_id or '', inicio=inicio, fim=fim)
        db.add(fatura)
        db.flush()
    usos = db.scalars(select(UsoIA).where(UsoIA.account_id == account.id,
        UsoIA.iniciado_em < fim, UsoIA.estado.in_(['concluido', 'ajuste']), UsoIA.fatura_id.is_(None))
        .order_by(UsoIA.id)).all()
    grupos = defaultdict(list)
    for uso in usos:
        # Preserva período original nos ajustes/entregas posteriores ao corte anterior.
        grupos[(uso.funcionalidade, uso.modelo, uso.tarifa['id'],
                uso.iniciado_em.isoformat()[:7] if uso.iniciado_em.replace(tzinfo=timezone.utc) < inicio else '')].append(uso)
    # Conciliação remota protege retomadas após expirar a chave de idempotência do Stripe.
    remotas = {r.get('metadata', {}).get('grupo_consumo'): r for r in map(dados_stripe,
        stripe_client.v1.invoices.line_items.list(invoice['id'], {'limit':100}).auto_paging_iter())
        if r.get('metadata', {}).get('grupo_consumo')}
    linhas = []
    for chave, itens in sorted(grupos.items()):
        total = sum(u.preco for u in itens)
        unidades = defaultdict(lambda: Decimal(0))
        for uso in itens:
            for unidade, qtd in uso.unidades.items():
                unidades[unidade] += Decimal(str(qtd))
        linha = {'funcionalidade': chave[0], 'modelo': chave[1], 'tarifa': itens[0].tarifa,
            'periodo_original': chave[3] or inicio.isoformat(),
            'unidades': {k: str(v) for k, v in unidades.items()}, 'centavos': centavos(total)}
        linhas.append(linha)
        if linha['centavos']:
            digest = sha256('|'.join(chave).encode()).hexdigest()[:32]
            existente = remotas.get(digest)
            if existente and existente['amount'] != linha['centavos']:
                raise HTTPException(409, 'Divergência de conciliação; fatura mantida em rascunho')
            if not existente:
                stripe_client.v1.invoice_items.create({
                'customer': account.stripe_customer_id, 'invoice': invoice['id'], 'currency': 'brl',
                'amount': linha['centavos'],
                'description': f"{chave[0]} · {chave[1]} · tarifa {itens[0].tarifa['versao']} · {linha['periodo_original']}",
                'period': {'start': int(inicio.timestamp()), 'end': int(fim.timestamp())},
                'metadata': {'tarifa_id': chave[2], 'demonstrativo': invoice['id'], 'grupo_consumo': digest},
            }, options={'idempotency_key': f"consumo:{invoice['id']}:{digest}"})
    for uso in usos:
        uso.fatura_id = fatura.id
    fatura.linhas = linhas
    fatura.consumo = sum(u.preco for u in usos)
    fatura.total_centavos = sum(linha['centavos'] for linha in linhas)
    fatura.estado = 'apurada'
    db.flush()
    # Persistir antes de liberar a finalização. Reentrega retoma a mesma fatura.
    db.commit()
    stripe_client.v1.invoices.update(invoice['id'], {'auto_advance': True})
    return fatura


def registrar_pagamento(db, account, invoice, *, pendente=True):
    conta_consumo(db, account.id)
    fatura = db.get(FaturaConsumo, invoice['id'])
    if fatura is None:
        fatura = FaturaConsumo(id=invoice['id'], account_id=account.id,
            assinatura=account.stripe_subscription_id or '', inicio=periodo(invoice['period_start']),
            fim=periodo(invoice['period_end']), consumo=0, linhas=[])
        db.add(fatura)
    if fatura.estado == 'paga':
        return
    if invoice.get('status') == 'paid':
        db.execute(update(ContaConsumo).where(ContaConsumo.account_id == account.id)
            .values(exposicao=ContaConsumo.exposicao - (fatura.consumo or 0)))
        fatura.estado = 'paga'
        outra_pendente = db.scalar(select(FaturaConsumo.id).where(FaturaConsumo.account_id == account.id, FaturaConsumo.id != fatura.id, FaturaConsumo.estado == 'pendente').limit(1))
        if account.plano_status != 'cancelado':
            account.plano_status = 'inadimplente' if outra_pendente else 'ativo'
        account.plano = 'flex'
    elif invoice.get('status') == 'open':
        fatura.estado = 'pendente' if pendente else 'emitida'
        if pendente:
            account.plano_status = 'inadimplente'
    fatura.total_centavos = invoice.get('total', fatura.total_centavos or 0)
    fatura.url = invoice.get('hosted_invoice_url')
