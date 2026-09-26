"""Fluxo Locufy Flex ponta a ponta com medição e bloqueio ligados.

O conftest desliga a medição para o restante da suíte. Aqui o banco é um arquivo e as
sessões são independentes, como em produção: a rota usa get_db e a medição abre a
própria transação (app.billing.consumo_ia.SessionLocal).
"""
import hashlib
import hmac
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.auth.security import criar_token, hash_senha
from app.billing.flex import calcular, centavos
from app.config.settings import settings
from app.db.database import Base, get_db
from app.models.account import Account
from app.models.consumo_flex import ContaConsumo, EventoCobranca, FaturaConsumo, TarifaIA, UsoIA
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.super_admin import SuperAdmin
from app.models.usuario import Usuario

TARIFA_CLASSIFICACAO = {
    'tipo': 'llm', 'provedor': 'anthropic', 'modelo': 'claude-haiku-4-5', 'versao': '2026-09',
    'unidades': {
        'entrada': {'preco': '1', 'divisor': '1000000'}, 'saida': {'preco': '5', 'divisor': '1000000'},
        'cache_write': {'preco': '1.25', 'divisor': '1000000'}, 'cache_read': {'preco': '0.1', 'divisor': '1000000'},
        'buscas': {'preco': '0.01', 'divisor': '1'},
    },
    'moeda': 'USD', 'cambio': '5.5', 'acrescimo': '100', 'descricao': 'Classificação', 'limitacoes': '-',
    'contrato_e_qualidade_confirmados': True,
}
TARIFA_TEXTO = {**TARIFA_CLASSIFICACAO, 'modelo': 'claude-opus-5', 'unidades': {
    'entrada': {'preco': '5', 'divisor': '1000000'}, 'saida': {'preco': '25', 'divisor': '1000000'},
    'cache_write': {'preco': '6.25', 'divisor': '1000000'}, 'cache_read': {'preco': '0.5', 'divisor': '1000000'},
    'buscas': {'preco': '0.01', 'divisor': '1'},
}}
TARIFA_VOZ = {
    'tipo': 'tts', 'provedor': 'elevenlabs', 'modelo': 'eleven_v3', 'versao': '2026-09',
    'unidades': {'caracteres': {'preco': '0.10', 'divisor': '1000'}},
    'moeda': 'USD', 'cambio': '5.5', 'acrescimo': '100', 'descricao': 'Voz', 'limitacoes': '-',
    'contrato_e_qualidade_confirmados': True,
}
# ~1000 caracteres: R$ 1,10 de locução, valor visível em centavos na fatura.
FALA_LONGA = ('Bom dia, ouvintes! Hoje o programa começa com muita música boa e notícias da cidade. ' * 12).strip()


@pytest.fixture
def e2e(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'flex.db'}", connect_args={'check_same_thread': False, 'timeout': 10})
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr('app.billing.consumo_ia.SessionLocal', Sessao)
    monkeypatch.setattr('app.live.router.SessionLocal', Sessao)
    monkeypatch.setattr(settings, 'ia_medicao_habilitada', True)
    monkeypatch.setattr(settings, 'ia_orcamento_bloquear', True)
    monkeypatch.setattr(settings, 'elevenlabs_api_key', 'eleven-teste')
    stripe = MagicMock()
    monkeypatch.setattr('app.billing.router.cliente', lambda: stripe)

    from app.main import app

    def _db():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    with Sessao() as db, db.begin():
        account = Account(plano='flex', plano_status='trial', stripe_customer_id='cus_e2e',
                          wuzapi_token='wuzapi-e2e', wuzapi_user_id='user-e2e', wuzapi_hmac_key='hmac-e2e')
        db.add(account)
        db.flush()
        usuario = Usuario(email='e2e@teste.com', senha_hash=hash_senha('senha12345'), account_id=account.id, role='admin')
        admin = SuperAdmin(email='root@teste.com', senha_hash=hash_senha('senha12345'))
        radio = RadioConfig(account_id=account.id, ativo=True, timezone='America/Sao_Paulo', voz_id='voz-e2e')
        db.add_all([usuario, admin, radio])
        db.flush()
        ids = SimpleNamespace(account=account.id, usuario=usuario.id, admin=admin.id, radio=radio.id)
    ctx = SimpleNamespace(
        Sessao=Sessao, stripe=stripe, ids=ids, client=TestClient(app),
        user={'Authorization': f'Bearer {criar_token(ids.usuario)}'},
        root={'Authorization': f"Bearer {criar_token(ids.admin, tipo='super_admin')}"},
    )
    yield ctx
    app.dependency_overrides.clear()
    engine.dispose()


def evento(ctx, tipo, dados, ident):
    body = json.dumps({'object': 'event', 'id': ident, 'type': tipo, 'created': int(time.time()),
                       'data': {'object': dados}}).encode()
    ts = str(int(time.time()))
    sig = hmac.new(settings.stripe_webhook_secret.encode(), ts.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return ctx.client.post('/billing/webhook', content=body, headers={'stripe-signature': f't={ts},v1={sig}'})


def resposta_llm(texto, entrada, saida):
    return SimpleNamespace(
        id='msg_llm', stop_reason='end_turn', content=[SimpleNamespace(type='text', text=texto)],
        usage=SimpleNamespace(input_tokens=entrada, output_tokens=saida, cache_creation_input_tokens=0,
                              cache_read_input_tokens=0, server_tool_use=None))


def publicar_tarifas(ctx):
    for tarifa in (TARIFA_CLASSIFICACAO, TARIFA_TEXTO, TARIFA_VOZ):
        r = ctx.client.post('/billing/admin/tarifas', json=tarifa, headers=ctx.root)
        assert r.status_code == 200, r.text


def ativar(ctx, inicio, fim):
    """Adesão: primeira fatura só com a mensalidade; ativa a conta e registra o ciclo."""
    with ctx.Sessao() as db, db.begin():
        db.get(Account, ctx.ids.account).stripe_subscription_id = 'sub_e2e'
    primeira = {
        'id': 'in_adesao', 'customer': 'cus_e2e', 'status': 'paid', 'billing_reason': 'subscription_create',
        'parent': {'subscription_details': {'subscription': 'sub_e2e'}},
        'period_start': inicio, 'period_end': inicio, 'total': 6990,
        'lines': {'data': [{'parent': {'type': 'subscription_item_details'}, 'period': {'start': inicio, 'end': fim}}]},
    }
    ctx.stripe.v1.invoices.retrieve.return_value = primeira
    # Rascunho da adesão não recebe consumo (não há consumo anterior à assinatura).
    assert evento(ctx, 'invoice.created', {**primeira, 'status': 'draft'}, 'evt_adesao_criada').status_code == 200
    assert evento(ctx, 'invoice.paid', primeira, 'evt_adesao_paga').status_code == 200
    ctx.stripe.v1.invoice_items.create.assert_not_called()


def usos(ctx):
    with ctx.Sessao() as db:
        return db.scalars(select(UsoIA).where(UsoIA.account_id == ctx.ids.account)
                          .order_by(UsoIA.iniciado_em, UsoIA.chave)).all()


def conta(ctx):
    with ctx.Sessao() as db:
        return db.get(ContaConsumo, ctx.ids.account)


def preco(tarifa, unidades):
    return calcular(tarifa, unidades)


class VozFalsa:
    """httpx.Client da ElevenLabs: registra payloads e responde áudio ou erro."""

    def __init__(self, status=200):
        self.status, self.payloads = status, []
        voz = self

        class Resposta:
            headers = {}

            @property
            def status_code(self):
                return voz.status

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b''

            def raise_for_status(self):
                if voz.status >= 400:
                    req = httpx.Request('POST', 'https://api.elevenlabs.io')
                    raise httpx.HTTPStatusError('erro', request=req, response=httpx.Response(voz.status, request=req))

            def iter_bytes(self):
                yield b'ID3' + b'\x00' * 10
                yield b'audio'

        class Cliente:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def stream(self, metodo, url, headers, json):
                voz.payloads.append(json)
                return Resposta()

            def post(self, url, headers, json):
                voz.payloads.append(json)
                r = Resposta()
                r.content = b'ID3audio'
                return r

        self.Cliente = Cliente


def test_ciclo_completo_adesao_uso_renovacao_pagamento(e2e, monkeypatch):
    agora = int(time.time())
    inicio, fim = agora - 3600, agora + 30 * 86400
    publicar_tarifas(e2e)
    llm = MagicMock(return_value=resposta_llm('energico', 200, 5))
    monkeypatch.setattr('app.llm.client._client.messages.create', llm)
    voz = VozFalsa()
    monkeypatch.setattr('app.tts.client.httpx.Client', voz.Cliente)
    url = f'/live/{e2e.ids.radio}/tts'

    # Antes da adesão nada pago é autorizado, e o motivo chega ao painel.
    r = e2e.client.post(url, json={'texto': FALA_LONGA, 'tipo': 'abertura'}, headers=e2e.user)
    assert r.status_code == 402 and 'assinatura' in r.json()['detail']
    assert usos(e2e) == [] and voz.payloads == []

    ativar(e2e, inicio, fim)
    with e2e.Sessao() as db:
        account = db.get(Account, e2e.ids.account)
        assert (account.plano_status, account.plano) == ('ativo', 'flex')
        assert db.get(FaturaConsumo, 'in_adesao').estado == 'paga'
    assert int(conta(e2e).ciclo_fim.replace(tzinfo=timezone.utc).timestamp()) == fim
    # Recém-assinada gera sem configurar nada: limite financeiro padrão.
    assert conta(e2e).limite == int(settings.ia_limite_padrao_brl * 1_000_000)

    # Operação 1: classificação de tom (texto) + locução, entregues.
    r = e2e.client.post(url, json={'texto': FALA_LONGA, 'tipo': 'abertura'}, headers=e2e.user)
    assert r.status_code == 200 and r.content.startswith(b'ID3')
    classificacao, locucao = usos(e2e)
    caracteres = len(voz.payloads[0]['text'])
    assert classificacao.operacao == locucao.operacao
    assert {u.funcionalidade for u in (classificacao, locucao)} == {'locucao'}
    assert (classificacao.tipo, classificacao.modelo, classificacao.estado) == ('llm', 'claude-haiku-4-5', 'concluido')
    assert classificacao.unidades == {'entrada': '200', 'saida': '5', 'cache_write': '0', 'cache_read': '0', 'buscas': '0'}
    assert (locucao.tipo, locucao.modelo, locucao.estado) == ('tts', 'eleven_v3', 'concluido')
    assert locucao.unidades == {'caracteres': str(caracteres)}
    custo_c, preco_c = preco(TARIFA_CLASSIFICACAO, {'entrada': 200, 'saida': 5})
    custo_v, preco_v = preco(TARIFA_VOZ, {'caracteres': caracteres})
    assert (classificacao.custo_bruto, classificacao.preco) == (custo_c, preco_c)
    assert (locucao.custo_bruto, locucao.preco) == (custo_v, preco_v) and preco_v == 2 * custo_v
    # Reserva interna de 15% registrada à parte, nunca somada ao preço.
    assert locucao.reserva_interna == int(custo_v * 0.15)
    assert conta(e2e).exposicao == preco_c + preco_v

    # Operação 2: provedor de voz falha -> operação inteira sem cobrança, exposição liberada.
    voz.status = 500
    r = e2e.client.post(url, json={'texto': FALA_LONGA + ' Fim.', 'tipo': 'abertura'}, headers=e2e.user)
    assert r.status_code == 502
    falhas = [u for u in usos(e2e) if u.operacao != locucao.operacao]
    assert len(falhas) == 2 and {u.estado for u in falhas} == {'falha'} and {u.preco for u in falhas} == {0}
    assert conta(e2e).exposicao == preco_c + preco_v
    voz.status = 200

    # Painel: previsão = mensalidade + consumo concluído.
    consumo = centavos(preco_c + preco_v)
    c = e2e.client.get('/billing/consumo-ia', headers=e2e.user).json()
    assert c['consumo_brl'] == consumo / 100 and c['previsao_brl'] == pytest.approx(69.90 + consumo / 100)
    assert c['medicao_ativa'] is True and c['aviso'] is None
    assert len(e2e.client.get('/billing/extrato', headers=e2e.user).json()) == 4

    # Renovação: rascunho do Stripe recebe o consumo do período encerrado, uma linha por modelo.
    renovacao = {'id': 'in_renov', 'customer': 'cus_e2e', 'status': 'draft', 'billing_reason': 'subscription_cycle',
                 'parent': {'subscription_details': {'subscription': 'sub_e2e'}},
                 'period_start': inicio, 'period_end': agora + 60, 'total': 6990 + consumo}
    e2e.stripe.v1.invoices.retrieve.return_value = renovacao
    e2e.stripe.v1.invoices.line_items.list.return_value.auto_paging_iter.return_value = iter([])
    assert evento(e2e, 'invoice.created', renovacao, 'evt_renov_criada').status_code == 200
    itens = {c.args[0]['description'].split(' · ')[1]: c.args[0] for c in e2e.stripe.v1.invoice_items.create.call_args_list}
    assert itens['eleven_v3']['amount'] == centavos(preco_v)
    assert all(i['invoice'] == 'in_renov' and i['currency'] == 'brl' and i['description'].startswith('locucao')
               for i in itens.values())
    e2e.stripe.v1.invoices.update.assert_called_with('in_renov', {'auto_advance': True})
    # Reentrega do mesmo evento não repete itens.
    chamadas = e2e.stripe.v1.invoice_items.create.call_count
    assert evento(e2e, 'invoice.created', renovacao, 'evt_renov_criada').json()['status'] == 'duplicado'
    assert e2e.stripe.v1.invoice_items.create.call_count == chamadas
    with e2e.Sessao() as db:
        f = db.get(FaturaConsumo, 'in_renov')
        assert f.estado == 'apurada' and f.consumo == preco_c + preco_v
        assert f.total_centavos == sum(linha['centavos'] for linha in f.linhas)
        assert {db.get(UsoIA, u.id).fatura_id for u in (classificacao, locucao)} == {'in_renov'}
        assert {db.get(UsoIA, u.id).fatura_id for u in falhas} == {None}

    # Finalização, cartão recusado (bloqueia novas gerações), nova tentativa paga na mesma fatura.
    e2e.stripe.v1.invoices.retrieve.return_value = {**renovacao, 'status': 'open'}
    assert evento(e2e, 'invoice.finalized', renovacao, 'evt_renov_final').status_code == 200
    assert evento(e2e, 'invoice.payment_failed', renovacao, 'evt_renov_falha').status_code == 200
    with e2e.Sessao() as db:
        assert db.get(Account, e2e.ids.account).plano_status == 'inadimplente'
    r = e2e.client.post(url, json={'texto': 'Outra fala', 'tipo': 'abertura'}, headers=e2e.user)
    assert r.status_code == 402
    e2e.stripe.v1.invoices.retrieve.return_value = {**renovacao, 'status': 'paid'}
    assert evento(e2e, 'invoice.paid', renovacao, 'evt_renov_paga').status_code == 200
    with e2e.Sessao() as db:
        assert db.get(Account, e2e.ids.account).plano_status == 'ativo'
        assert db.get(FaturaConsumo, 'in_renov').estado == 'paga'
        assert db.query(FaturaConsumo).count() == 2
        assert db.query(EventoCobranca).count() == 6
    assert conta(e2e).exposicao == 0


def test_cache_integral_nao_gera_nova_cobranca(e2e, monkeypatch):
    agora = int(time.time())
    publicar_tarifas(e2e)
    ativar(e2e, agora - 60, agora + 86400)
    llm = MagicMock(return_value=resposta_llm('calmo', 150, 3))
    monkeypatch.setattr('app.llm.client._client.messages.create', llm)
    voz = VozFalsa()
    monkeypatch.setattr('app.tts.client.httpx.Client', voz.Cliente)
    corpo = {'texto': 'Boa tarde!', 'tipo': 'abertura'}
    for _ in range(2):
        assert e2e.client.post(f'/live/{e2e.ids.radio}/tts', json=corpo, headers=e2e.user).status_code == 200
    assert llm.call_count == 1 and len(voz.payloads) == 1
    assert len(usos(e2e)) == 2


def test_recusa_de_cobranca_nao_vira_erro_generico(e2e, monkeypatch):
    agora = int(time.time())
    publicar_tarifas(e2e)
    ativar(e2e, agora - 60, agora + 86400)
    assert e2e.client.put('/billing/limite-financeiro', json={'limite_brl': 0}, headers=e2e.user).status_code == 200
    monkeypatch.setattr('app.llm.client._client.messages.create', MagicMock(return_value=resposta_llm('neutro', 10, 1)))
    voz = VozFalsa()
    monkeypatch.setattr('app.tts.client.httpx.Client', voz.Cliente)
    with e2e.Sessao() as db, db.begin():
        p = Patrocinador(account_id=e2e.ids.account, nome='Padaria', texto='Padaria do bairro.', voz_id='voz-e2e')
        db.add(p)
        db.flush()
        pid = p.id
    # A rota converte qualquer exceção em 502; o painel precisa ver o motivo real.
    r = e2e.client.get(f'/patrocinadores/{pid}/audio', headers=e2e.user)
    assert r.status_code == 402 and 'Limite financeiro' in r.json()['detail']
    assert voz.payloads == []
    c = e2e.client.get('/billing/consumo-ia', headers=e2e.user).json()
    assert c['aviso'] == 'esgotado'


def test_suporte_nao_cobra_nem_bloqueia_inadimplente(e2e, monkeypatch):
    with e2e.Sessao() as db, db.begin():
        db.get(Account, e2e.ids.account).plano_status = 'inadimplente'
    monkeypatch.setattr('app.llm.client._client.messages.create',
                        MagicMock(return_value=resposta_llm('Acesse Assinatura e regularize.', 900, 40)))
    r = e2e.client.post('/suporte/chat', json={'mensagem': 'Como regularizo o pagamento?'}, headers=e2e.user)
    assert r.status_code == 200 and 'regularize' in r.json()['resposta']
    assert usos(e2e) == []


def test_thread_solta_entrega_a_propria_operacao(e2e):
    from app.billing.consumo_ia import concluir, reservar
    from app.billing.contexto_ia import contexto_conta, tarefa_independente
    agora = int(time.time())
    publicar_tarifas(e2e)
    ativar(e2e, agora - 60, agora + 86400)
    liberar = threading.Event()

    def classificar_depois():
        liberar.wait(5)
        uid = reservar('llm', 'claude-haiku-4-5', unidades_max={'entrada': 500, 'saida': 10, 'cache_write': 0,
                                                              'cache_read': 0, 'buscas': 0})
        concluir(uid, unidades={'entrada': 100, 'saida': 2, 'cache_write': 0, 'cache_read': 0, 'buscas': 0})

    with e2e.Sessao() as db:
        account = db.get(Account, e2e.ids.account)
        with contexto_conta(account):
            t = threading.Thread(target=tarefa_independente(classificar_depois))
            t.start()
    # A request já terminou quando a thread mede o uso.
    liberar.set()
    t.join(5)
    [u] = usos(e2e)
    assert u.estado == 'concluido' and u.preco > 0


def test_fechamento_absorve_operacao_abandonada_em_vez_de_travar_fatura(e2e):
    from app.billing.flex import autorizar
    agora = int(time.time())
    publicar_tarifas(e2e)
    ativar(e2e, agora - 7200, agora + 86400)
    with e2e.Sessao() as db, db.begin():
        preso = autorizar(db, e2e.ids.account, 'llm', 'claude-opus-5', {'entrada': 1000, 'saida': 100})
        db.get(UsoIA, preso).iniciado_em = datetime.now(timezone.utc) - timedelta(hours=2)
        recente = autorizar(db, e2e.ids.account, 'llm', 'claude-opus-5', {'entrada': 1000, 'saida': 100})
    renovacao = {'id': 'in_renov', 'customer': 'cus_e2e', 'status': 'draft', 'billing_reason': 'subscription_cycle',
                 'parent': {'subscription_details': {'subscription': 'sub_e2e'}},
                 'period_start': agora - 7200, 'period_end': agora + 60, 'total': 6990}
    e2e.stripe.v1.invoices.retrieve.return_value = renovacao
    e2e.stripe.v1.invoices.line_items.list.return_value.auto_paging_iter.return_value = iter([])
    # Operação recente ainda pode terminar: fatura fica em rascunho e o Stripe reentrega.
    assert evento(e2e, 'invoice.created', renovacao, 'evt_renov').status_code == 503
    e2e.stripe.v1.invoices.update.assert_called_with('in_renov', {'auto_advance': False})
    with e2e.Sessao() as db, db.begin():
        db.get(UsoIA, recente).iniciado_em = datetime.now(timezone.utc) - timedelta(hours=2)
    assert evento(e2e, 'invoice.created', renovacao, 'evt_renov').status_code == 200
    e2e.stripe.v1.invoices.update.assert_called_with('in_renov', {'auto_advance': True})
    e2e.stripe.v1.invoice_items.create.assert_not_called()
    with e2e.Sessao() as db:
        assert {(u.estado, u.preco) for u in db.scalars(select(UsoIA))} == {('falha', 0)}
    assert conta(e2e).exposicao == 0


@freeze_time('2026-08-10 15:00:00')
def test_whatsapp_mede_por_mensagem_e_reentrega_nao_cobra(e2e, monkeypatch):
    import asyncio

    async def _sem_debounce(segundos):
        return None
    monkeypatch.setattr(asyncio, 'sleep', _sem_debounce)
    monkeypatch.setattr('app.whatsapp.webhook.avaliar_adequacao_programa', lambda texto, programa: (True, ''))
    monkeypatch.setattr('app.whatsapp.webhook.avaliar_adequacao_ao_vivo', lambda texto, programa: (True, ''))
    monkeypatch.setattr('app.llm.prompt_builder.obter_clima_atual', lambda cidade: None)
    enviadas = []
    monkeypatch.setattr('app.whatsapp.webhook.enviar_mensagem', lambda *a: enviadas.append(a))
    llm = MagicMock(return_value=resposta_llm('Oi! Que bom te ouvir.', 1200, 30))
    monkeypatch.setattr('app.llm.client._client.messages.create', llm)
    with e2e.Sessao() as db, db.begin():
        db.add_all([TarifaIA(id=f't{i}', vigente_desde=datetime(2026, 1, 1, tzinfo=timezone.utc),
                             **{k: v for k, v in t.items() if k != 'contrato_e_qualidade_confirmados'})
                    for i, t in enumerate((TARIFA_CLASSIFICACAO, TARIFA_TEXTO))])
        db.get(Account, e2e.ids.account).plano_status = 'ativo'
        db.add(Programa(radio_config_id=e2e.ids.radio, nome='Manhã', horario_inicio=datetime(2026, 1, 1, 10).time(),
                        horario_fim=datetime(2026, 1, 1, 14).time(), limite_mensagens_hora=1000))

    def enviar(message_id):
        corpo = json.dumps({'userID': 'user-e2e', 'event': {'Info': {
            'Chat': '5511999999999@s.whatsapp.net', 'FromMe': False, 'ID': message_id, 'PushName': 'Ana'},
            'Message': {'conversation': 'Bom dia! Manda um abraço pra minha mãe'}}}).encode()
        assinatura = hmac.new(b'hmac-e2e', corpo, hashlib.sha256).hexdigest()
        return e2e.client.post('/webhook/whatsapp', content=corpo, headers={'x-hmac-signature': assinatura})

    assert enviar('msg-1').status_code == 200
    medidos = usos(e2e)
    assert medidos and llm.call_count == len(medidos)
    assert {(u.canal, u.funcionalidade, u.estado) for u in medidos} == {('whatsapp', 'atendimento_whatsapp', 'concluido')}
    assert {u.operacao for u in medidos} == {f'whatsapp:{e2e.ids.account}:msg-1'}
    # Mesmo evento reentregue pelo WuzAPI: sem nova chamada paga.
    enviar('msg-1')
    assert len(usos(e2e)) == len(medidos) and llm.call_count == len(medidos)


def test_cancelamento_fatura_so_consumo_restante_sem_mensalidade_futura(e2e, monkeypatch):
    agora = int(time.time())
    publicar_tarifas(e2e)
    ativar(e2e, agora - 3600, agora + 30 * 86400)
    monkeypatch.setattr('app.llm.client._client.messages.create', MagicMock(return_value=resposta_llm('neutro', 100, 2)))
    voz = VozFalsa()
    monkeypatch.setattr('app.tts.client.httpx.Client', voz.Cliente)
    assert e2e.client.post(f'/live/{e2e.ids.radio}/tts', json={'texto': FALA_LONGA, 'tipo': 'abertura'},
                           headers=e2e.user).status_code == 200
    consumo = sum(u.preco for u in usos(e2e))

    cancelamento = int(time.time()) + 1
    cancelada = {'id': 'sub_e2e', 'customer': 'cus_e2e', 'status': 'canceled', 'canceled_at': cancelamento,
                 'start_date': agora - 3600}
    e2e.stripe.v1.subscriptions.retrieve.return_value = cancelada
    final = {'id': 'in_final', 'customer': 'cus_e2e', 'status': 'draft', 'metadata': {'assinatura_cancelada': 'sub_e2e'}}
    e2e.stripe.v1.invoices.create.return_value = final
    e2e.stripe.v1.invoices.line_items.list.return_value.auto_paging_iter.return_value = iter([])
    assert evento(e2e, 'customer.subscription.deleted', cancelada, 'evt_cancel').status_code == 200

    params = e2e.stripe.v1.invoices.create.call_args.args[0]
    # Fatura avulsa: sem item de assinatura, portanto sem mensalidade de período futuro.
    assert params['pending_invoice_items_behavior'] == 'exclude' and params['auto_advance'] is False
    itens = [c.args[0] for c in e2e.stripe.v1.invoice_items.create.call_args_list]
    assert {i['invoice'] for i in itens} == {'in_final'}
    assert sum(i['amount'] for i in itens) == sum(
        linha['centavos'] for linha in e2e.client.get('/billing/faturas', headers=e2e.user).json()[0]['linhas'])
    e2e.stripe.v1.invoices.update.assert_called_with('in_final', {'auto_advance': True})
    with e2e.Sessao() as db:
        assert db.get(Account, e2e.ids.account).plano_status == 'cancelado'
        f = db.get(FaturaConsumo, 'in_final')
        assert f.consumo == consumo and int(f.fim.replace(tzinfo=timezone.utc).timestamp()) == cancelamento

    # Pagamento da fatura final não reativa a conta; novas gerações seguem bloqueadas.
    e2e.stripe.v1.invoices.retrieve.return_value = {**final, 'status': 'paid', 'total': 110}
    assert evento(e2e, 'invoice.paid', final, 'evt_final_paga').status_code == 200
    with e2e.Sessao() as db:
        assert db.get(Account, e2e.ids.account).plano_status == 'cancelado'
    assert conta(e2e).exposicao == 0
    assert e2e.client.post(f'/live/{e2e.ids.radio}/tts', json={'texto': 'Mais uma', 'tipo': 'abertura'},
                           headers=e2e.user).status_code == 402


def test_admin_lista_modelos_em_uso_sem_tarifa(e2e, monkeypatch):
    monkeypatch.setattr(settings, 'vinheta_trilha_ia_habilitada', True)
    pendentes = lambda: {(p['tipo'], p['modelo']) for p in  # noqa: E731
                         e2e.client.get('/billing/admin/tarifas/pendentes', headers=e2e.root).json()['pendentes']}
    assert e2e.client.get('/billing/admin/tarifas/pendentes', headers=e2e.user).status_code == 401
    assert {('llm', settings.llm_model), ('llm', settings.llm_classification_model), ('tts', 'eleven_v3'),
            ('stt', 'scribe_v1'), ('music', settings.elevenlabs_music_model)} <= pendentes()
    publicar_tarifas(e2e)
    assert pendentes() == {('stt', 'scribe_v1'), ('music', settings.elevenlabs_music_model)}


TARIFA_SONNET = {**TARIFA_TEXTO, 'modelo': 'claude-sonnet-5', 'unidades': {
    'entrada': {'preco': '2', 'divisor': '1000000'}, 'saida': {'preco': '10', 'divisor': '1000000'},
    'cache_write': {'preco': '2.5', 'divisor': '1000000'}, 'cache_read': {'preco': '0.2', 'divisor': '1000000'},
    'buscas': {'preco': '0.01', 'divisor': '1'},
}}
TARIFA_FLASH = {**TARIFA_VOZ, 'modelo': 'eleven_flash_v2_5', 'unidades': {'caracteres': {'preco': '0.05', 'divisor': '1000'}}}


def gerador_configuracao_medido(chamadas):
    """Gera persona via cliente real de LLM (medido); devolve configuração válida fixa."""
    from app.billing.contexto_ia import atual
    from app.llm.client import gerar_configuracao
    from app.tts.voices import VOZES_DISPONIVEIS

    def gerar(descricao, tipo_radio=None, account=None, roster_existente=None):
        gerar_configuracao('Crie o locutor', descricao)
        chamadas.append(atual.get().modelo_texto)
        return (
            {'nome_locutor': 'Duda', 'personalidade': 'animada', 'voz_id': VOZES_DISPONIVEIS[0]['voz_id'],
             'timezone': 'America/Sao_Paulo'},
            {'nome': 'Manhã Duda', 'tom': 'animado', 'horario_inicio': '06:00:00', 'horario_fim': '09:00:00'},
        )
    return gerar


def test_catalogo_de_combinacoes_so_com_tarifas_e_preco_por_hora(e2e, monkeypatch):
    monkeypatch.setattr(settings, 'ia_combinacoes', ['premium', 'equilibrada', 'agil', 'essencial'])
    assert e2e.client.get('/billing/combinacoes', headers=e2e.user).json()['combinacoes'] == []
    publicar_tarifas(e2e)
    catalogo = e2e.client.get('/billing/combinacoes', headers=e2e.user).json()
    # Só Premium tem texto (Opus) e voz (v3) publicados; Sonnet/Flash ainda não.
    assert [c['id'] for c in catalogo['combinacoes']] == ['premium']
    premium = catalogo['combinacoes'][0]
    assert premium['recomendada'] and (premium['modelo_texto'], premium['modelo_voz']) == ('claude-opus-5', 'eleven_v3')
    # 6 min de fala/h: 12 gerações (1500/150 tokens), 36 classificações (500/32), 6000 caracteres.
    esperado = (calcular(TARIFA_TEXTO, {'entrada': 18000, 'saida': 1800})[1]
                + calcular(TARIFA_CLASSIFICACAO, {'entrada': 18000, 'saida': 1152})[1]
                + calcular(TARIFA_VOZ, {'caracteres': 6000})[1])
    assert premium['preco_hora_brl'] == pytest.approx(esperado / 1_000_000, abs=1e-4)
    assert catalogo['minutos_fala_por_hora'] == 6 and catalogo['mensalidade_brl'] == 69.9
    # Programa sem escolha usa os modelos padrão; o painel mostra quais são.
    assert catalogo['padrao'] == {'texto': settings.llm_model, 'voz': settings.elevenlabs_model}
    # Explica só os modelos das combinações oferecidas, dizendo se escrevem ou falam.
    assert {m: d['funcao'] for m, d in catalogo['modelos'].items()} == {'claude-opus-5': 'texto', 'eleven_v3': 'voz'}

    for tarifa in (TARIFA_SONNET, TARIFA_FLASH):
        assert e2e.client.post('/billing/admin/tarifas', json=tarifa, headers=e2e.root).status_code == 200
    precos = {c['id']: c['preco_hora_brl'] for c in
              e2e.client.get('/billing/combinacoes', headers=e2e.user).json()['combinacoes']}
    assert list(precos) == ['premium', 'equilibrada', 'agil', 'essencial']
    assert precos['premium'] > precos['equilibrada'] > precos['agil'] > precos['essencial']


def test_combinacao_desabilitada_por_configuracao_nao_aparece(e2e, monkeypatch):
    publicar_tarifas(e2e)
    for tarifa in (TARIFA_SONNET, TARIFA_FLASH):
        e2e.client.post('/billing/admin/tarifas', json=tarifa, headers=e2e.root)
    # Padrão: as 6 combinações dos 3 textos com as 2 vozes, da mais cara à mais barata.
    assert [c['id'] for c in e2e.client.get('/billing/combinacoes', headers=e2e.user).json()['combinacoes']] == [
        'premium', 'equilibrada', 'voz_premium', 'texto_premium', 'agil', 'essencial']
    monkeypatch.setattr(settings, 'ia_combinacoes', [])
    assert e2e.client.get('/billing/combinacoes', headers=e2e.user).json()['combinacoes'] == []


def test_locutor_gerado_com_combinacao_escolhida_e_valor(e2e, monkeypatch):
    agora = int(time.time())
    publicar_tarifas(e2e)
    for tarifa in (TARIFA_SONNET, TARIFA_FLASH):
        e2e.client.post('/billing/admin/tarifas', json=tarifa, headers=e2e.root)
    ativar(e2e, agora - 60, agora + 86400)
    llm = MagicMock(return_value=resposta_llm('{"ok": true}', 3000, 800))
    monkeypatch.setattr('app.llm.client._client.messages.create', llm)
    chamadas = []
    monkeypatch.setattr('app.config.router.gerar_configuracao_ia', gerador_configuracao_medido(chamadas))
    monkeypatch.setattr('app.config.router.criar_vinhetas_com_seguranca', lambda *a, **k: None)

    # Combinação sem tarifa publicada (ou inexistente) é recusada antes de gerar.
    r = e2e.client.post('/config/radialistas/gerar-ia', json={'descricao': 'manhã', 'combinacao_id': 'inexistente'},
                        headers=e2e.user)
    assert r.status_code == 422 and llm.call_count == 0

    r = e2e.client.post('/config/radialistas/gerar-ia', json={'descricao': 'manhã animada', 'combinacao_id': 'agil'},
                        headers=e2e.user)
    assert r.status_code == 201, r.text
    corpo = r.json()
    # A persona foi gerada com o texto da combinação.
    assert llm.call_args.kwargs['model'] == 'claude-sonnet-5' and chamadas == ['claude-sonnet-5']
    assert corpo['combinacao']['id'] == 'agil' and corpo['combinacao']['preco_hora_brl'] > 0
    esperado = calcular(TARIFA_SONNET, {'entrada': 3000, 'saida': 800})[1] / 1_000_000
    assert corpo['custo_geracao_brl'] == pytest.approx(esperado, abs=1e-4)
    programa_id, radialista_id = corpo['programa']['id'], corpo['radialista']['id']
    modelos = conta(e2e).modelos
    assert modelos[str(programa_id)] == {'texto': 'claude-sonnet-5', 'voz': 'eleven_flash_v2_5',
                                         'combinacao': 'agil', 'programa_id': programa_id}
    assert modelos[f'radialista:{radialista_id}']['combinacao'] == 'agil'
    [geracao] = [u for u in usos(e2e) if u.modelo == 'claude-sonnet-5']
    assert geracao.estado == 'concluido' and geracao.funcionalidade == 'configuracao_ia'

    # Fala do programa sai com a voz da combinação.
    voz = VozFalsa()
    monkeypatch.setattr('app.tts.client.httpx.Client', voz.Cliente)
    r = e2e.client.post(f'/live/{radialista_id}/tts', headers=e2e.user,
                        json={'texto': 'Bom dia!', 'tom': 'neutro', 'tipo': 'abertura', 'programa_id': programa_id})
    assert r.status_code == 200 and voz.payloads[-1]['model_id'] == 'eleven_flash_v2_5'
    assert [u.modelo for u in usos(e2e) if u.tipo == 'tts'] == ['eleven_flash_v2_5']

    # Troca de combinação vale para as próximas gerações do programa.
    r = e2e.client.put('/billing/combinacao', json={'combinacao_id': 'premium', 'programa_id': programa_id},
                       headers=e2e.user)
    assert r.status_code == 200 and r.json()[str(programa_id)]['voz'] == 'eleven_v3'
    e2e.client.post(f'/live/{radialista_id}/tts', headers=e2e.user,
                    json={'texto': 'Boa tarde!', 'tom': 'neutro', 'tipo': 'abertura', 'programa_id': programa_id})
    assert voz.payloads[-1]['model_id'] == 'eleven_v3'


def test_preview_e_commit_com_combinacao(e2e, monkeypatch):
    agora = int(time.time())
    publicar_tarifas(e2e)
    ativar(e2e, agora - 60, agora + 86400)
    llm = MagicMock(return_value=resposta_llm('{"ok": true}', 2000, 500))
    monkeypatch.setattr('app.llm.client._client.messages.create', llm)
    chamadas = []
    monkeypatch.setattr('app.config.router.gerar_configuracao_ia', gerador_configuracao_medido(chamadas))
    monkeypatch.setattr('app.config.router.criar_vinhetas_com_seguranca', lambda *a, **k: None)
    r = e2e.client.post('/config/radialistas/gerar-ia/preview', json={'descricao': 'noite', 'combinacao_id': 'premium'},
                        headers=e2e.user)
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview['combinacao']['id'] == 'premium' and preview['custo_geracao_brl'] > 0
    assert chamadas == ['claude-opus-5']
    r = e2e.client.post('/config/radialistas/gerar-ia/commit', headers=e2e.user, json={
        'radialista': preview['radialista'], 'programa': preview['programa'], 'geracao_id': preview['geracao_id'],
        'combinacao_id': 'premium'})
    assert r.status_code == 201, r.text
    assert conta(e2e).modelos[str(r.json()['programa']['id'])]['combinacao'] == 'premium'


def test_catalogo_mostra_composicao_do_custo_e_preco_do_exemplo(e2e, monkeypatch):
    from app.billing import combinacoes
    monkeypatch.setattr(combinacoes, 'exemplos', lambda: {'premium': {
        'pedido': 'Anuncie Twist and Shout.', 'texto': 'Boa tarde!', 'audio_url': '/exemplos/combinacoes/premium.mp3',
        'duracao_segundos': 23.8, 'caracteres_voz': 480, 'unidades_texto': {'entrada': 2800, 'saida': 160}}})
    publicar_tarifas(e2e)
    combos = {c['id']: c for c in e2e.client.get('/billing/combinacoes', headers=e2e.user).json()['combinacoes']}
    premium = combos['premium']
    assert combos['voz_premium']['exemplo'] is None  # sem exemplo gravado, o card só não mostra o áudio
    partes = premium['custo_hora_brl']
    assert sum(partes.values()) == pytest.approx(premium['preco_hora_brl'], abs=1e-3)
    assert partes['voz'] == pytest.approx(calcular(TARIFA_VOZ, {'caracteres': 6000})[1] / 1e6, abs=1e-4)
    assert premium['preco_mes_referencia_brl'] == pytest.approx(premium['preco_hora_brl'] * 30, abs=1e-2)
    assert premium['preco_mil_caracteres_brl'] == pytest.approx(1.1)
    # Preço do exemplo = unidades medidas na geração × tarifa vigente (texto + voz).
    esperado = (calcular(TARIFA_TEXTO, {'entrada': 2800, 'saida': 160})[1] + calcular(TARIFA_VOZ, {'caracteres': 480})[1]) / 1e6
    assert premium['exemplo']['preco_brl'] == pytest.approx(esperado, abs=1e-4)
    assert premium['exemplo']['audio_url'] == '/exemplos/combinacoes/premium.mp3' and premium['exemplo']['voz_padrao']
