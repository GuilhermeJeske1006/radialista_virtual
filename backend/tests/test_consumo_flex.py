from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.billing.flex import autorizar, calcular, finalizar, entregar_operacao
from app.billing.fechamento import fechar, registrar_pagamento
from app.models.consumo_flex import ContaConsumo, TarifaIA, UsoIA, FaturaConsumo


@pytest.fixture
def flex(db_session, account_factory):
    a = account_factory(plano='flex', plano_status='ativo', stripe_customer_id='cus_flex', stripe_subscription_id='sub_flex')
    t = TarifaIA(id='tarifa-1', tipo='llm', provedor='teste', modelo='texto', versao='v1',
        unidades={'entrada': {'preco': '5', 'divisor': '1000000'}, 'saida': {'preco': '25', 'divisor': '1000000'}, 'cache_write': {'preco':'6.25','divisor':'1000000'}, 'cache_read': {'preco':'0.5','divisor':'1000000'}, 'buscas': {'preco':'0.01','divisor':'1'}},
        moeda='USD', cambio='5', acrescimo='100', vigente_desde=datetime.now(timezone.utc) - timedelta(days=1))
    db_session.add_all([t, ContaConsumo(account_id=a.id, limite=100000000, exposicao=0)])
    db_session.commit()
    return a


def invoice(a, **kwargs):
    now = datetime.now(timezone.utc)
    return {'id': 'in_flex', 'status': 'draft', 'customer': a.stripe_customer_id,
        'period_start': int((now - timedelta(days=30)).timestamp()),
        'period_end': int((now + timedelta(seconds=1)).timestamp()), **kwargs}


def uso(db, a, **kwargs):
    return autorizar(db, a.id, 'llm', 'texto', {'entrada': 100000, 'saida': 100000}, **kwargs)


def test_precificacao_unidades_cambio_reserva_separada(db_session, flex):
    uid = uso(db_session, flex)
    finalizar(db_session, uid, {'entrada': 1000, 'saida': 100})
    u = db_session.get(UsoIA, uid)
    assert u.custo_bruto == 37500
    assert u.preco == 75000
    assert u.reserva_interna == 5625
    assert db_session.get(ContaConsumo, flex.id).exposicao == 75000


def test_tarifa_modelo_congelados_na_autorizacao(db_session, flex):
    uid = uso(db_session, flex)
    db_session.add(TarifaIA(id='nova', tipo='llm', provedor='teste', modelo='texto', versao='v2', unidades={'entrada': {'preco':'100','divisor':'1000000'}}, cambio='9', acrescimo='500'))
    db_session.flush()
    finalizar(db_session, uid, {'entrada':1000})
    assert db_session.get(UsoIA, uid).preco == 50000


def test_reconciliacao_idempotente_e_falha_sem_debito(db_session, flex):
    uid = uso(db_session, flex)
    finalizar(db_session, uid, {'entrada':1000}, entregue=False)
    finalizar(db_session, uid, {'entrada':1000})
    u = db_session.get(UsoIA, uid)
    assert u.estado == 'falha' and u.preco == 0 and u.custo_bruto == 25000
    assert db_session.get(ContaConsumo, flex.id).exposicao == 0


def test_resultado_nao_entregue_nao_faturavel(db_session, flex):
    uid = uso(db_session, flex, operacao='op')
    finalizar(db_session, uid, {'entrada':1000}, entregue=None)
    assert db_session.get(UsoIA, uid).estado == 'medido'
    entregar_operacao(db_session, flex.id, 'op', False)
    assert db_session.get(UsoIA, uid).preco == 0
    assert db_session.get(ContaConsumo, flex.id).exposicao == 0


def test_entrega_e_conclusao_repetidas(db_session, flex):
    uid = uso(db_session, flex, operacao='op')
    finalizar(db_session, uid, {'entrada':1000}, entregue=None)
    entregar_operacao(db_session, flex.id, 'op', True)
    entregar_operacao(db_session, flex.id, 'op', False)
    assert db_session.get(UsoIA, uid).estado == 'concluido'
    assert db_session.get(ContaConsumo, flex.id).exposicao == 50000


def test_dedupe_antes_do_provedor(db_session, flex):
    uso(db_session, flex, chave='evento-etapa')
    with pytest.raises(HTTPException) as exc:
        uso(db_session, flex, chave='evento-etapa')
    assert exc.value.status_code == 409
    assert len(db_session.scalars(select(UsoIA)).all()) == 1


def test_orcamento_nao_reseta_no_mes_novo(db_session, flex):
    conta = db_session.get(ContaConsumo, flex.id)
    conta.limite = 30000000
    db_session.flush()
    uid = uso(db_session, flex)
    db_session.get(UsoIA, uid).iniciado_em -= timedelta(days=35)
    db_session.flush()
    with pytest.raises(HTTPException) as exc:
        uso(db_session, flex)
    assert exc.value.status_code == 402


def test_sem_tarifa_nao_autoriza(db_session, flex):
    with pytest.raises(HTTPException) as exc:
        autorizar(db_session, flex.id, 'tts', 'nao-aprovado', {'caracteres':100})
    assert exc.value.status_code == 503


def test_inadimplente_nao_autoriza(db_session, flex):
    flex.plano_status = 'inadimplente'
    db_session.flush()
    with pytest.raises(HTTPException) as exc:
        uso(db_session, flex)
    assert exc.value.status_code == 402


def test_fechamento_aguarda_chamada_cruzando_corte(db_session, flex):
    uso(db_session, flex)
    c = MagicMock()
    with pytest.raises(HTTPException) as exc:
        fechar(db_session, flex, invoice(flex), c)
    assert exc.value.status_code == 503
    c.v1.invoices.update.assert_called_with('in_flex', {'auto_advance':False})
    c.v1.invoice_items.create.assert_not_called()


def test_fatura_renovacao_dedupe_e_pagamento(db_session, flex):
    uid = uso(db_session, flex)
    finalizar(db_session, uid, {'entrada':1000,'saida':100})
    c = MagicMock()
    f = fechar(db_session, flex, invoice(flex), c)
    assert f.total_centavos == 8
    assert f.linhas[0]['unidades'] == {'entrada':'1000', 'saida':'100'}
    fechar(db_session, flex, invoice(flex), c)
    assert c.v1.invoice_items.create.call_count == 1
    assert db_session.get(ContaConsumo, flex.id).exposicao == 75000
    registrar_pagamento(db_session, flex, invoice(flex, status='open',total=6998))
    assert flex.plano_status == 'inadimplente'
    registrar_pagamento(db_session, flex, invoice(flex, status='paid', total=6998))
    registrar_pagamento(db_session, flex, invoice(flex, status='paid', total=6998))
    assert db_session.get(ContaConsumo, flex.id).exposicao == 0
    assert flex.plano_status == 'ativo'
    assert db_session.get(FaturaConsumo, 'in_flex').estado == 'paga'


def test_zero_uso_sem_segunda_mensalidade(db_session, flex):
    c = MagicMock()
    f = fechar(db_session, flex, invoice(flex), c)
    assert f.linhas == [] and f.total_centavos == 0
    c.v1.invoice_items.create.assert_not_called()


def test_fatura_finalizada_nao_alterada(db_session, flex):
    uid = uso(db_session, flex)
    finalizar(db_session, uid, {'entrada':100})
    c = MagicMock()
    with pytest.raises(HTTPException) as exc:
        fechar(db_session, flex, invoice(flex,status='open'), c)
    assert exc.value.status_code == 409
    c.v1.invoice_items.create.assert_not_called()


def test_isolamento_extrato_e_faturas(client, db_session, flex, account_factory, auth_headers):
    uid = uso(db_session, flex)
    finalizar(db_session, uid, {'entrada':1000})
    db_session.commit()
    outro = account_factory(email='outro@teste.com', plano_status='ativo')
    assert client.get('/billing/extrato', headers=auth_headers(outro.id)).json() == []
    assert len(client.get('/billing/extrato', headers=auth_headers(flex.id)).json()) == 1
    assert client.get('/billing/faturas', headers=auth_headers(outro.id)).json() == []


def test_extrato_paginado(client, db_session, flex, auth_headers):
    for _ in range(3):
        finalizar(db_session, uso(db_session, flex), {'entrada': 1000})
    db_session.commit()
    todos = [u['id'] for u in client.get('/billing/extrato', headers=auth_headers(flex.id)).json()]
    pagina = lambda q: [u['id'] for u in client.get(f'/billing/extrato?{q}', headers=auth_headers(flex.id)).json()]
    assert pagina('limite=2') == todos[:2]
    assert pagina('offset=2&limite=2') == todos[2:]
    assert client.get('/billing/extrato?limite=101', headers=auth_headers(flex.id)).status_code == 422


@pytest.mark.parametrize('unidade,divisor,quantidade,esperado', [('caracteres','1000',100,100000),('segundos','3600',60,166667),('milissegundos','60000',30000,5000000)])
def test_divisores_duracao_e_caracteres(unidade, divisor, quantidade, esperado):
    tarifa = {'unidades':{unidade:{'preco':'1','divisor':divisor}},'cambio':'5','acrescimo':'100'}
    _, preco = calcular(tarifa, {unidade:quantidade})
    # caracteres: 100 / 1000 * 5 * 2 = 1 real
    assert preco == (1000000 if unidade == 'caracteres' else esperado)


@pytest.mark.parametrize('quantidade', ['NaN','Infinity','-1'])
def test_valores_invalidos(quantidade):
    with pytest.raises(HTTPException):
        calcular({'unidades':{'entrada':{'preco':'1','divisor':'1'}},'cambio':'1','acrescimo':'100'}, {'entrada':quantidade})


def test_orcamento_atomico_concorrente(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.database import Base
    from app.models.account import Account
    engine = create_engine(f'sqlite:///{tmp_path / "concorrencia.db"}', connect_args={'timeout':10})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db, db.begin():
        db.add(Account(id=1, plano='flex', plano_status='ativo'))
        db.add(ContaConsumo(account_id=1, limite=10000000, exposicao=0))
        db.add(TarifaIA(id='tts',tipo='tts',provedor='teste',modelo='teste',versao='1',
            unidades={'caracteres':{'preco':'1','divisor':'1'}},cambio='1',acrescimo='100'))
    def gastar(_):
        try:
            with factory() as db, db.begin():
                return autorizar(db,1,'tts','teste',{'caracteres':3})
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados=list(pool.map(gastar,range(2)))
    assert sum(isinstance(r,str) for r in resultados)==1
    assert 402 in resultados
    with factory() as db:
        assert db.get(ContaConsumo,1).exposicao==6000000
    engine.dispose()


def test_migracao_versionada_idempotente_sem_reprecificar(tmp_path):
    from sqlalchemy import create_engine, text, inspect
    from app.db.migrations.consumo_20260925 import aplicar
    engine=create_engine(f'sqlite:///{tmp_path / "migracao.db"}')
    aplicar(engine)
    aplicar(engine)
    assert {'usos_ia','contas_consumo','tarifas_ia','faturas_consumo','eventos_cobranca'}.issubset(inspect(engine).get_table_names())
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM migracoes_consumo')).scalar()==1
        assert c.execute(text('SELECT count(*) FROM usos_ia')).scalar()==0
    engine.dispose()


def test_amostra_estimada_nao_gasta_e_exige_autorizacao_da_conta(client, db_session, flex, auth_headers, account_factory):
    r=client.post('/billing/amostras/estimar',json={'tipo':'llm','modelo':'texto','texto':'Olá'},headers=auth_headers(flex.id))
    assert r.status_code==200
    assert r.json()['limite_brl']>0
    assert db_session.query(UsoIA).count()==0
    outro=account_factory(email='amostra@teste.com',plano_status='ativo')
    r=client.post('/billing/amostras/executar',json={'autorizacao':r.json()['autorizacao']},headers=auth_headers(outro.id))
    assert r.status_code==400


def test_escolha_modelos_nao_acessa_programa_outra_conta(client, db_session, flex, auth_headers):
    r=client.put('/billing/modelos',json={'texto':'texto','programa_id':999},headers=auth_headers(flex.id))
    assert r.status_code==404


def test_credito_vinculado_nao_edita_uso_original(db_session, flex):
    from app.billing.consumo_router import creditar, CreditoRequest
    uid=uso(db_session,flex)
    finalizar(db_session,uid,{'entrada':100000})
    db_session.commit()
    original=db_session.get(UsoIA,uid)
    antes=original.preco
    req=CreditoRequest(uso_id=uid,credito_brl=Decimal('1'),motivo='Correção de processamento',chave='credito-teste')
    ajuste=creditar(req,db_session)
    assert ajuste['preco_brl']==-1 and ajuste['original_id']==uid
    assert db_session.get(UsoIA,uid).preco==antes
    assert creditar(req,db_session)['id']==ajuste['id']
    assert db_session.get(ContaConsumo,flex.id).exposicao==antes-1000000


def test_concilia_linha_remota_apos_interrupcao(db_session,flex):
    from hashlib import sha256
    uid=uso(db_session,flex,funcionalidade='roteiro')
    finalizar(db_session,uid,{'entrada':1000})
    digest=sha256('roteiro|texto|tarifa-1|'.encode()).hexdigest()[:32]
    c=MagicMock()
    c.v1.invoices.line_items.list.return_value.auto_paging_iter.return_value=iter([{'amount':5,'metadata':{'grupo_consumo':digest}}])
    f=fechar(db_session,flex,invoice(flex),c)
    assert f.total_centavos==5
    c.v1.invoice_items.create.assert_not_called()


def test_pagamento_fatura_antiga_nao_libera_outra_pendente(db_session,flex):
    db_session.add(FaturaConsumo(id='outra',account_id=flex.id,assinatura='sub_flex',inicio=datetime(2025,1,1),fim=datetime(2025,2,1),estado='pendente'))
    db_session.commit()
    registrar_pagamento(db_session,flex,invoice(flex,status='paid'))
    assert flex.plano_status=='inadimplente'


def test_consumo_real_de_cinquenta_centavos_cobra_um_real(db_session, flex):
    uid = uso(db_session, flex)
    finalizar(db_session, uid, {'entrada': 20000}, entregue=None)
    entregar_operacao(db_session, flex.id, db_session.get(UsoIA, uid).operacao, True)
    medido = db_session.get(UsoIA, uid)
    assert medido.custo_bruto == 500000
    assert medido.preco == 1000000
    assert medido.preco < medido.reservado
    assert db_session.get(ContaConsumo, flex.id).exposicao == 1000000
