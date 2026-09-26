"""Precificação reproduzível e autorização serializada por conta.

A exposição inclui reservas e usos ainda não pagos de TODOS os ciclos.
Tarifas ausentes bloqueiam o gasto; hipóteses de simulações nunca são publicadas.
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.models.account import Account
from app.models.consumo_flex import ContaConsumo, TarifaIA, UsoIA, agora

MICRO = Decimal(1000000)


def numero(valor):
    try:
        n = Decimal(str(valor))
        if not n.is_finite() or n < 0:
            raise ValueError()
        return n
    except Exception:
        raise HTTPException(422, 'Quantidade ou tarifa inválida') from None


def calcular(tarifa, unidades):
    if set(unidades) - set(tarifa['unidades']):
        raise HTTPException(422, 'Unidade sem tarifa')
    custo = Decimal(0)
    for unidade, quantidade in unidades.items():
        regra = tarifa['unidades'][unidade]
        divisor = numero(regra['divisor'])
        if not divisor:
            raise HTTPException(422, 'Divisor deve ser positivo')
        custo += numero(quantidade) * numero(regra['preco']) / divisor
    cambio = numero(tarifa['cambio'])
    if not cambio:
        raise HTTPException(422, 'Câmbio deve ser positivo')
    custo *= cambio
    preco = custo * (1 + numero(tarifa['acrescimo']) / 100)
    return tuple(int((v * MICRO).quantize(Decimal(1), rounding=ROUND_HALF_UP)) for v in (custo, preco))


def snapshot(t):
    return {k: getattr(t, k) for k in ('id', 'tipo', 'provedor', 'modelo', 'versao', 'unidades', 'moeda', 'cambio', 'acrescimo')}


def tarifa_atual(db, tipo, modelo, instante=None):
    t = db.scalar(select(TarifaIA).where(TarifaIA.tipo == tipo, TarifaIA.modelo == modelo,
        TarifaIA.vigente_desde <= (instante or agora())).order_by(TarifaIA.vigente_desde.desc(), TarifaIA.id.desc()).limit(1))
    if not t:
        raise HTTPException(503, 'Tarifa contratada e aprovada ainda não publicada para este modelo')
    return snapshot(t)


def conta_consumo(db, account_id):
    db.flush()
    conta = db.get(ContaConsumo, account_id)
    if conta is None:
        from app.config.settings import settings
        limite = int(numero(settings.ia_limite_padrao_brl) * MICRO)
        try:
            with db.begin_nested():
                db.add(ContaConsumo(account_id=account_id, limite=limite, exposicao=0, modelos={}))
                db.flush()
        except IntegrityError:
            pass
    # UPDATE também serializa SQLite; PostgreSQL mantém row lock até commit.
    db.execute(update(ContaConsumo).where(ContaConsumo.account_id == account_id).values(exposicao=ContaConsumo.exposicao))
    return db.get(ContaConsumo, account_id, populate_existing=True)


def autorizar(db, account_id, tipo, modelo, quantidades_max, *, chave=None,
              operacao=None, funcionalidade=None, canal='painel', contexto=None, tarifa_autorizada=None):
    conta_consumo(db, account_id)  # serializa autorizações da conta
    account = db.get(Account, account_id)
    if account is None or account.plano_status != 'ativo':
        raise HTTPException(402, 'Regularize a assinatura para iniciar processamento pago')
    chave = chave or str(uuid4())
    existente = db.scalar(select(UsoIA).where(UsoIA.account_id == account_id, UsoIA.chave == chave))
    if existente:
        # Retornar um id não autoriza repetir a chamada ao provedor.
        raise HTTPException(409, {'codigo': 'uso_ja_autorizado', 'uso_id': existente.id})
    instante = agora()
    tarifa = tarifa_autorizada or tarifa_atual(db, tipo, modelo, instante)
    _, teto = calcular(tarifa, quantidades_max)
    mudou = db.execute(update(ContaConsumo).where(ContaConsumo.account_id == account_id,
        ContaConsumo.exposicao + teto <= ContaConsumo.limite).values(exposicao=ContaConsumo.exposicao + teto))
    if mudou.rowcount != 1:
        raise HTTPException(402, 'Limite financeiro insuficiente para autorizar esta operação')
    uso = UsoIA(id=str(uuid4()), account_id=account_id, chave=chave, operacao=operacao or chave,
        funcionalidade=funcionalidade or tipo, canal=canal, contexto=contexto or {}, tipo=tipo,
        modelo=modelo, tarifa=tarifa, reservado=teto, iniciado_em=instante)
    db.add(uso)
    db.flush()
    return uso.id


def finalizar(db, uso_id, unidades, *, entregue=True, request_id=None, reserva_fracao='0.15'):
    uso = db.get(UsoIA, uso_id)
    if not uso:
        return
    conta_consumo(db, uso.account_id)
    db.refresh(uso)
    if uso.estado != 'reservado':
        return
    custo, preco = calcular(uso.tarifa, unidades)
    # Se o provedor ultrapassar o teto autorizado, a diferença é custo interno.
    preco = min(preco, uso.reservado) if entregue is not False else 0
    uso.unidades = {k: str(numero(v)) for k, v in unidades.items()}
    uso.custo_bruto = custo
    uso.reserva_interna = int(Decimal(custo) * numero(reserva_fracao))
    uso.preco = preco
    uso.estado = 'medido' if entregue is None else ('concluido' if entregue else 'falha')
    uso.concluido_em = agora()
    uso.provedor_request_id = request_id
    db.execute(update(ContaConsumo).where(ContaConsumo.account_id == uso.account_id)
        .values(exposicao=ContaConsumo.exposicao + preco - uso.reservado))
    db.flush()


def centavos(micro):
    return int((Decimal(micro) / 10000).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def entregar_operacao(db, account_id, operacao, sucesso):
    """Só torna faturáveis etapas de uma operação disponibilizada ao cliente."""
    conta_consumo(db, account_id)
    usos = db.scalars(select(UsoIA).where(UsoIA.account_id == account_id, UsoIA.operacao == operacao,
        UsoIA.estado.in_(['medido', 'reservado']))).all()
    for uso in usos:
        if sucesso and uso.estado == 'medido':
            uso.estado = 'concluido'
        else:
            _descartar(db, uso)

    db.flush()


def _descartar(db, uso):
    comprometido = uso.preco if uso.estado == 'medido' else uso.reservado
    db.execute(update(ContaConsumo).where(ContaConsumo.account_id == uso.account_id)
        .values(exposicao=ContaConsumo.exposicao - comprometido))
    uso.estado, uso.preco = 'falha', 0


def absorver_abandonadas(db, account_id, iniciadas_antes_de):
    """Processo reiniciado ou thread perdida deixa uso sem conclusão. Sem entrega
    confirmada não há cobrança: vira custo interno e libera a exposição."""
    conta_consumo(db, account_id)
    usos = db.scalars(select(UsoIA).where(UsoIA.account_id == account_id,
        UsoIA.iniciado_em < iniciadas_antes_de, UsoIA.estado.in_(['medido', 'reservado']))).all()
    for uso in usos:
        _descartar(db, uso)
    db.flush()
    return len(usos)
