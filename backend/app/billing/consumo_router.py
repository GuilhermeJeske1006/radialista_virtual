from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.admin_sistema.dependencies import get_current_super_admin
from app.auth.dependencies import exigir_admin, get_current_account
from app.billing.flex import calcular, centavos, conta_consumo, numero, snapshot, tarifa_atual
from app.config.settings import settings
from app.db.database import get_db
from app.models.consumo_flex import ContaConsumo, FaturaConsumo, TarifaIA, UsoIA, agora

router = APIRouter(prefix='/billing', tags=['billing'])


@router.get('/consumo-ia')
def consumo_ia(account=Depends(get_current_account), db=Depends(get_db)):
    conta = db.get(ContaConsumo, account.id)
    usos = db.scalars(select(UsoIA).where(UsoIA.account_id == account.id, UsoIA.fatura_id.is_(None))).all()
    realizado = sum(u.preco for u in usos if u.estado in ('concluido', 'ajuste'))
    reservado = sum(u.reservado for u in usos if u.estado == 'reservado')
    # Conta ainda sem uso recebe o limite padrão na primeira autorização.
    limite, exposicao = (conta.limite, conta.exposicao) if conta else (int(settings.ia_limite_padrao_brl * 1000000), 0)
    mensalidade = 0 if account.plano_status == 'cancelado' else 69.9
    return {'mensalidade_brl': mensalidade, 'consumo_brl': centavos(realizado) / 100,
        'ciclo_inicio': conta.ciclo_inicio if conta else None, 'ciclo_fim': conta.ciclo_fim if conta else None,
        'reservado_brl': reservado / 1000000, 'comprometido_brl': exposicao / 1000000,
        'orcamento_brl': limite / 1000000, 'disponivel_brl': max(0, limite - exposicao) / 1000000,
        'previsao_brl': mensalidade + centavos(realizado) / 100, 'estimativa': True,
        'medicao_ativa': settings.ia_medicao_habilitada, 'bloqueio_ativo': settings.ia_orcamento_bloquear,
        'aviso': 'esgotado' if exposicao >= limite else '90_porcento' if exposicao >= limite * .9 else None,
        'regra_cambio': 'Câmbio congelado por vigência da tarifa; não é repasse exato da fatura do provedor.'}


class LimiteRequest(BaseModel):
    limite_brl: Decimal = Field(ge=0, le=100000)


@router.put('/limite-financeiro')
def limite(dados: LimiteRequest, account=Depends(get_current_account), db=Depends(get_db), _admin=Depends(exigir_admin)):
    conta = conta_consumo(db, account.id)
    conta.limite = int(numero(dados.limite_brl) * 1000000)
    db.commit()
    return {'limite_brl': str(dados.limite_brl)}


def uso_publico(u):
    return {'id': u.id, 'operacao': u.operacao, 'funcionalidade': u.funcionalidade,
        'canal': u.canal, 'contexto': u.contexto, 'modelo': u.modelo, 'unidades': u.unidades,
        'tarifa': u.tarifa, 'preco_brl': u.preco / 1000000, 'estado': u.estado,
        'iniciado_em': u.iniciado_em, 'fatura_id': u.fatura_id, 'original_id': u.original_id}


@router.get('/extrato')
def extrato(offset: int = 0, limite: int = Query(100, ge=1, le=100), account=Depends(get_current_account), db=Depends(get_db)):
    # Painel pede uma página + 1 item para saber se há próxima sem contar o extrato inteiro.
    usos = db.scalars(select(UsoIA).where(UsoIA.account_id == account.id).order_by(UsoIA.iniciado_em.desc(), UsoIA.id).offset(max(0, offset)).limit(limite)).all()
    return [uso_publico(u) for u in usos]


@router.get('/faturas')
def faturas(account=Depends(get_current_account), db=Depends(get_db)):
    return [{'id': f.id, 'inicio': f.inicio, 'fim': f.fim, 'estado': f.estado,
        'total_brl': f.total_centavos / 100, 'linhas': f.linhas, 'url': f.url}
        for f in db.scalars(select(FaturaConsumo).where(FaturaConsumo.account_id == account.id).order_by(FaturaConsumo.fim.desc()).limit(100))]


@router.get('/catalogo-modelos')
def catalogo(_account=Depends(get_current_account), db=Depends(get_db)):
    tarifas = db.scalars(select(TarifaIA).where(TarifaIA.vigente_desde <= agora()).order_by(TarifaIA.vigente_desde.desc(), TarifaIA.id.desc())).all()
    atuais = {}
    for t in tarifas:
        atuais.setdefault((t.tipo, t.modelo), {**snapshot(t), 'descricao': t.descricao, 'limitacoes': t.limitacoes, 'exemplos': t.exemplos})
    return list(atuais.values())


class ModeloRequest(BaseModel):
    texto: str
    voz: str | None = None
    programa_id: int | None = None


@router.get('/modelos')
def modelos(account=Depends(get_current_account), db=Depends(get_db)):
    c = db.get(ContaConsumo, account.id)
    return c.modelos if c else {}


@router.put('/modelos')
def modelos_salvar(dados: ModeloRequest, account=Depends(get_current_account), db=Depends(get_db), _admin=Depends(exigir_admin)):
    if dados.programa_id is not None:
        from app.config.router import _buscar_programa
        _buscar_programa(db, account, dados.programa_id)
    tarifa_atual(db, 'llm', dados.texto)
    if dados.voz:
        tarifa_atual(db, 'tts', dados.voz)
    c = conta_consumo(db, account.id)
    c.modelos = {**c.modelos, str(dados.programa_id) if dados.programa_id else 'whatsapp': dados.model_dump()}
    db.commit()
    return c.modelos


@router.get('/combinacoes')
def combinacoes(_account=Depends(get_current_account), db=Depends(get_db)):
    from app.billing.combinacoes import catalogo
    return catalogo(db)


class CombinacaoProgramaRequest(BaseModel):
    combinacao_id: str
    programa_id: int


@router.put('/combinacao')
def combinacao_salvar(dados: CombinacaoProgramaRequest, account=Depends(get_current_account), db=Depends(get_db),
                      _admin=Depends(exigir_admin)):
    """Troca a combinação de um programa existente; vale para as próximas gerações."""
    from app.billing.combinacoes import obter, salvar_escolha
    from app.config.router import _buscar_programa
    _buscar_programa(db, account, dados.programa_id)
    salvar_escolha(db, account.id, obter(db, dados.combinacao_id), programa_id=dados.programa_id)
    return db.get(ContaConsumo, account.id, populate_existing=True).modelos


class EstimativaRequest(BaseModel):
    tipo: str
    modelo: str
    unidades: dict[str, Decimal]


@router.post('/estimar')
def estimar(dados: EstimativaRequest, _account=Depends(get_current_account), db=Depends(get_db)):
    tarifa = tarifa_atual(db, dados.tipo, dados.modelo)
    _, preco = calcular(tarifa, dados.unidades)
    return {'tarifa_id': tarifa['id'], 'preco_brl': preco / 1000000, 'estimativa': True}


class TarifaRequest(BaseModel):
    tipo: str
    provedor: str
    modelo: str
    versao: str = Field(min_length=1, max_length=80)
    unidades: dict[str, dict[str, str]]
    moeda: str = 'USD'
    cambio: str
    acrescimo: str = '100'
    descricao: str
    limitacoes: str
    exemplos: list[dict] = Field(default_factory=list)
    contrato_e_qualidade_confirmados: bool


@router.get('/admin/tarifas/pendentes', dependencies=[Depends(get_current_super_admin)])
def tarifas_pendentes(db=Depends(get_db)):
    """Modelos em uso sem tarifa vigente. Com a medição ligada, cada um bloqueia (503)
    toda geração que depende dele -- conferir vazio antes de habilitar a cobrança."""
    em_uso = {('llm', settings.llm_model), ('llm', settings.llm_classification_model),
              ('tts', settings.elevenlabs_model), ('stt', 'scribe_v1')}
    if settings.vinheta_trilha_ia_habilitada:
        em_uso.add(('music', settings.elevenlabs_music_model))
    for c in db.scalars(select(ContaConsumo)):
        for escolha in (c.modelos or {}).values():
            em_uso |= {('llm', escolha.get('texto')), ('tts', escolha.get('voz'))}
    publicadas = set(db.execute(select(TarifaIA.tipo, TarifaIA.modelo).where(TarifaIA.vigente_desde <= agora())).all())
    return {'medicao_ativa': settings.ia_medicao_habilitada, 'bloqueio_ativo': settings.ia_orcamento_bloquear,
            'pendentes': [{'tipo': t, 'modelo': m} for t, m in sorted(em_uso - publicadas) if m]}


@router.post('/admin/tarifas', dependencies=[Depends(get_current_super_admin)])
def publicar(dados: TarifaRequest, db=Depends(get_db)):
    from app.config.settings import settings
    permitidos = {'llm': set(settings.ia_tarifas_llm), 'tts': set(settings.ia_tarifas_tts), 'stt': {'scribe_v1'}, 'music': {settings.elevenlabs_music_model}}
    unidades = {'llm': {'entrada', 'saida', 'cache_write', 'cache_read', 'buscas'}, 'tts': {'caracteres'}, 'stt': {'segundos'}, 'music': {'milissegundos'}}
    if dados.modelo not in permitidos.get(dados.tipo, set()) or set(dados.unidades) != unidades.get(dados.tipo):
        raise HTTPException(422, 'Modelo ou unidades incompatíveis com o adaptador')
    if not dados.contrato_e_qualidade_confirmados or dados.moeda not in ('USD', 'BRL'):
        raise HTTPException(422, 'Confirme contrato, moeda e qualidade antes de publicar')
    if dados.moeda == 'BRL' and numero(dados.cambio) != 1:
        raise HTTPException(422, 'Tarifa em reais exige câmbio 1')
    try:
        calcular(dados.model_dump(), {k: 1 for k in dados.unidades})
    except KeyError:
        raise HTTPException(422, 'Cada unidade exige preco e divisor') from None
    existente = db.scalar(select(TarifaIA).where(TarifaIA.tipo == dados.tipo, TarifaIA.modelo == dados.modelo, TarifaIA.versao == dados.versao))
    if existente:
        raise HTTPException(409, 'Versão já publicada; publique outra versão')
    t = TarifaIA(id=str(uuid4()), **dados.model_dump(exclude={'contrato_e_qualidade_confirmados'}))
    db.add(t)
    db.commit()
    return snapshot(t)


@router.get('/admin/consumo/{account_id}', dependencies=[Depends(get_current_super_admin)])
def consumo_admin(account_id: int, db=Depends(get_db)):
    return [{**uso_publico(u), 'custo_bruto_brl': u.custo_bruto / 1000000,
        'reserva_interna_brl': u.reserva_interna / 1000000,
        'contribuicao_brl': (u.preco - u.custo_bruto - u.reserva_interna) / 1000000}
        for u in db.scalars(select(UsoIA).where(UsoIA.account_id == account_id).order_by(UsoIA.iniciado_em.desc()).limit(200))]


class AmostraRequest(BaseModel):
    tipo: str
    modelo: str
    texto: str = Field(min_length=1, max_length=2000)
    voz_id: str | None = None


class ExecutarAmostraRequest(BaseModel):
    autorizacao: str


@router.post('/amostras/estimar')
def estimar_amostra(dados: AmostraRequest, account=Depends(get_current_account), db=Depends(get_db)):
    from jose import jwt
    from app.config.settings import settings
    if dados.tipo not in ('llm', 'tts') or (dados.tipo == 'tts' and not dados.voz_id):
        raise HTTPException(422, 'Selecione texto ou voz e uma voz compatível')
    t = tarifa_atual(db, dados.tipo, dados.modelo)
    if dados.tipo == 'tts':
        from app.tts.client import _preparar_sintese
        _, payload = _preparar_sintese(dados.texto, None, None, False, None, dados.modelo, 'atual', None, dados.voz_id)
        unidades = {'caracteres': len(payload['text'])}
    else:
        unidades = {'entrada': len(dados.texto.encode()) + 4096, 'saida': 512, 'cache_write': 0, 'cache_read': 0, 'buscas': 0}
    _, teto = calcular(t, unidades)
    claims = {'account_id': account.id, 'exp': int(agora().timestamp()) + 600, 'jti': str(uuid4()),
        'dados': dados.model_dump(), 'tarifa': t, 'unidades': unidades, 'tipo': 'amostra_consumo'}
    return {'limite_brl': teto / 1000000, 'autorizacao': jwt.encode(claims, settings.jwt_secret, algorithm='HS256'),
        'mensagem': 'Confirme para gerar. O uso medido será cobrado até este limite; estimativa válida por 10 minutos.'}


@router.post('/amostras/executar')
def executar_amostra(dados: ExecutarAmostraRequest, account=Depends(get_current_account)):
    import base64
    from jose import jwt, JWTError
    from app.config.settings import settings
    from app.billing.contexto_ia import atual
    from app.billing.consumo_ia import SessionLocal, concluir, falhar
    from app.billing.flex import autorizar
    try:
        claims = jwt.decode(dados.autorizacao, settings.jwt_secret, algorithms=['HS256'])
        if claims['account_id'] != account.id or claims['tipo'] != 'amostra_consumo':
            raise ValueError()
    except (JWTError, KeyError, ValueError):
        raise HTTPException(400, 'Estimativa inválida ou expirada') from None
    pedido = claims['dados']
    with SessionLocal() as db, db.begin():
        uid = autorizar(db, account.id, pedido['tipo'], pedido['modelo'], claims['unidades'],
            chave=claims['jti'], operacao=atual.get().operacao, funcionalidade='amostra_personalizada',
            tarifa_autorizada=claims['tarifa'])
    try:
        if pedido['tipo'] == 'llm':
            from app.llm.client import _client
            r = _client.messages.create(model=pedido['modelo'], max_tokens=512,
                messages=[{'role':'user', 'content':pedido['texto']}])
            unidades = {'entrada':r.usage.input_tokens, 'saida':r.usage.output_tokens,
                'cache_write':getattr(r.usage,'cache_creation_input_tokens',0) or 0,
                'cache_read':getattr(r.usage,'cache_read_input_tokens',0) or 0, 'buscas':0}
            texto = '\n'.join(b.text for b in r.content if b.type == 'text')
            concluir(uid, unidades=unidades, entregue=False if r.stop_reason == 'refusal' or not texto else None, request_id=r.id)
            return {'texto': texto, 'uso_id':uid}
        import httpx
        from app.tts.client import _preparar_sintese, _ELEVENLABS_URL, unidades_sintese
        headers, payload = _preparar_sintese(pedido['texto'], None, None, False, None, pedido['modelo'], 'atual', None, pedido['voz_id'])
        with httpx.Client(timeout=30) as c:
            r = c.post(_ELEVENLABS_URL.format(voice_id=pedido['voz_id']), headers=headers, json=payload)
            r.raise_for_status()
        if not r.content:
            raise HTTPException(502, 'Provedor retornou áudio vazio')
        concluir(uid, unidades=unidades_sintese(r, payload), entregue=None, request_id=r.headers.get('request-id'))
        return {'audio_base64':base64.b64encode(r.content).decode(), 'uso_id':uid}
    except BaseException:
        falhar(uid)
        raise


class CreditoRequest(BaseModel):
    uso_id: str
    credito_brl: Decimal = Field(gt=0, decimal_places=2)
    motivo: str = Field(min_length=5, max_length=500)
    chave: str = Field(min_length=8, max_length=120)


@router.post('/admin/creditos', dependencies=[Depends(get_current_super_admin)])
def creditar(dados: CreditoRequest, db=Depends(get_db)):
    from sqlalchemy import func, update
    from app.billing.stripe_client import cliente, dados_stripe
    original = db.get(UsoIA, dados.uso_id)
    if not original or original.estado != 'concluido':
        raise HTTPException(404, 'Uso faturável não encontrado')
    conta_consumo(db, original.account_id)
    chave = f'credito:{dados.chave}'
    existente = db.scalar(select(UsoIA).where(UsoIA.account_id == original.account_id, UsoIA.chave == chave))
    if existente:
        return uso_publico(existente)
    valor = int(dados.credito_brl * 1000000)
    creditado = -(db.scalar(select(func.coalesce(func.sum(UsoIA.preco), 0)).where(UsoIA.original_id == original.id)) or 0)
    if valor + creditado > original.preco:
        raise HTTPException(422, 'Crédito excede o preço ainda não corrigido deste uso')
    fatura = db.get(FaturaConsumo, original.fatura_id) if original.fatura_id else None
    request_id = None
    if fatura:
        c = cliente()
        remota = c.v1.invoices.retrieve(fatura.id)
        if remota.status not in ('paid', 'open'):
            raise HTTPException(409, 'Aguarde a emissão da fatura antes de criar crédito')
        # Crédito de fatura paga vai ao saldo do cliente, com documento do Stripe.
        parametros = {'invoice': fatura.id, 'amount': int(dados.credito_brl * 100),
            'memo': dados.motivo, 'metadata': {'uso_original': original.id, 'chave': chave}}
        if remota.status == 'paid':
            parametros['credit_amount'] = parametros['amount']
        nota = next((n for n in map(dados_stripe, c.v1.credit_notes.list({'invoice': fatura.id, 'limit':100}).auto_paging_iter())
            if n.get('metadata', {}).get('chave') == chave), None)
        if nota is None:
            nota = c.v1.credit_notes.create(parametros, options={'idempotency_key': f'{original.account_id}:{chave}'})
        request_id = dados_stripe(nota)["id"]
        if fatura.estado != 'paga':
            fatura.consumo -= valor
        fatura.total_centavos -= parametros['amount']
        fatura.linhas = [*fatura.linhas, {'ajuste': dados.motivo, 'original_id': original.id,
            'nota_credito': request_id, 'centavos': -parametros['amount']}]
    ajuste = UsoIA(id=str(uuid4()), account_id=original.account_id, chave=chave, operacao=original.operacao,
        funcionalidade='credito', canal='administracao', contexto={'motivo':dados.motivo},
        tipo=original.tipo, modelo=original.modelo, tarifa=original.tarifa, unidades={}, reservado=0,
        preco=-valor, original_id=original.id, fatura_id=original.fatura_id,
        estado='ajuste_aplicado' if fatura else 'ajuste', provedor_request_id=request_id, concluido_em=agora())
    db.add(ajuste)
    if not fatura or fatura.estado != 'paga':
        db.execute(update(ContaConsumo).where(ContaConsumo.account_id == original.account_id)
            .values(exposicao=ContaConsumo.exposicao - valor))
    db.commit()
    return uso_publico(ajuste)
