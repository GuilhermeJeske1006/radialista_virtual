"""Atribuição de custos por request, incluindo dependências sync e streaming."""
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from uuid import uuid4
from threading import Lock
from copy import copy
from functools import partial, wraps
import inspect


@dataclass
class ContaIA:
    id: int | None = None
    plano: str | None = None
    operacao: str = field(default_factory=lambda: str(uuid4()))
    funcionalidade: str = ""
    canal: str = "painel"
    programa_id: int | None = None
    modelo_texto: str | None = None
    modelo_voz: str | None = None
    # Assistente de suporte é custo da operação coberta pela mensalidade: sem
    # cobrança nem bloqueio (conta inadimplente precisa perguntar como regularizar).
    faturavel: bool = True
    etapa: list[int] = field(default_factory=lambda: [0])
    lock: Lock = field(default_factory=Lock)
    # Lista compartilhada entre cópias da mesma operação (threads do pool).
    recusas: list = field(default_factory=list)

    def proxima_etapa(self):
        with self.lock:
            self.etapa[0] += 1
            return self.etapa[0]


atual: ContextVar[ContaIA | None] = ContextVar("conta_ia", default=None)

# Rótulo comercial do extrato e da linha da fatura -- nunca o path cru com IDs, que
# fragmentaria a fatura por programa. Serviços chamados também sobrescrevem
# (atendimento_whatsapp, vinhetas, roteiros_automaticos, amostra_personalizada).
_FUNCIONALIDADE_POR_PREFIXO = {
    "live": "programa_ao_vivo",
    "tts": "locucao",
    "config": "configuracao_ia",
    "onboarding": "configuracao_ia",
    "patrocinadores": "patrocinadores",
    "biblioteca-audio": "vinhetas",
    "categorias-vinheta": "vinhetas",
    "topics": "roteiros",
    "ouvintes": "participacao_ouvintes",
    "suporte": "suporte",
    "webhook": "atendimento_whatsapp",
}
_NAO_FATURAVEIS = {"suporte"}


def funcionalidade_da_rota(path):
    partes = [p for p in (path or "").split("/") if p]
    if not partes:
        return "tarefa"
    if partes[-1] == "tts":
        return "locucao"
    return _FUNCIONALIDADE_POR_PREFIXO.get(partes[0], partes[0][:80])


class ContextoIAMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        funcionalidade = funcionalidade_da_rota(scope.get("path"))
        conta = ContaIA(funcionalidade=funcionalidade, faturavel=funcionalidade not in _NAO_FATURAVEIS)
        headers = dict(scope.get('headers', []))
        if headers.get(b'idempotency-key'):
            from hashlib import sha256
            conta.operacao = sha256(scope.get('path', '').encode() + b':' + headers[b'idempotency-key']).hexdigest()
        token = atual.set(conta)
        sucesso = False
        status = 500
        substituida = False

        async def enviar(message):
            nonlocal status, substituida
            if message['type'] == 'http.response.start':
                status = message['status']
                # Rotas que convertem qualquer exceção em 502 esconderiam limite esgotado,
                # inadimplência ou tarifa ausente atrás de "tente de novo".
                if status >= 500 and conta.recusas:
                    recusa = conta.recusas[-1]
                    status, substituida = recusa.status_code, True
                    import json
                    corpo = json.dumps({'detail': recusa.detail}, ensure_ascii=False, default=str).encode()
                    await send({'type': 'http.response.start', 'status': status, 'headers': [
                        (b'content-type', b'application/json'), (b'content-length', str(len(corpo)).encode())]})
                    await send({'type': 'http.response.body', 'body': corpo})
                    return
            elif substituida:
                return
            await send(message)
        try:
            await self.app(scope, receive, enviar)
            sucesso = status < 400
        finally:
            try:
                encerrar_contexto(sucesso)
            finally:
                atual.reset(token)


def identificar(account):
    # O objeto pertence somente a esta request. Mutação permite que a dependência
    # executada pelo threadpool comunique a conta à rota e ao streaming.
    conta = atual.get()
    if conta is not None:
        conta.id, conta.plano = account.id, account.plano
        if conta.canal == 'whatsapp':
            from sqlalchemy.orm import object_session
            from app.models.consumo_flex import ContaConsumo
            db = object_session(account)
            config = db.get(ContaConsumo, account.id) if db else None
            conta.modelo_texto = (config.modelos.get('whatsapp', {}).get('texto')) if config else None


@contextmanager
def contexto_conta(account):
    token = atual.set(ContaIA(account.id, account.plano))
    sucesso = False
    try:
        yield
        sucesso = True
    finally:
        try:
            encerrar_contexto(sucesso)
        finally:
            atual.reset(token)


def tarefa_com_contexto(func, *args, **kwargs):
    """Capture no chamador, antes de entregar a outra thread; um contexto por tarefa.
    Mesma operação do chamador: use somente quando ele aguarda o resultado."""
    ctx = copy_context()
    conta = atual.get()
    if conta:
        ctx.run(atual.set, copy(conta))
    return partial(ctx.run, partial(func, *args, **kwargs))


def tarefa_independente(func, *args, **kwargs):
    """Thread solta que pode terminar depois da request: operação própria, entregue
    pelo próprio resultado. Com a operação do chamador, o uso ficaria 'medido' para
    sempre e travaria o fechamento do ciclo."""
    ctx = copy_context()
    conta = atual.get()
    if conta:
        filha = copy(conta)
        filha.operacao, filha.etapa, filha.lock, filha.recusas = str(uuid4()), [0], Lock(), []
        ctx.run(atual.set, filha)

    def executar():
        sucesso = False
        try:
            resultado = func(*args, **kwargs)
            sucesso = True
            return resultado
        finally:
            encerrar_contexto(sucesso)
    return partial(ctx.run, executar)


def por_conta(funcionalidade):
    """Escopo explícito para jobs que recebem Account, inclusive chamadas fora de HTTP.
    `funcionalidade` é o rótulo comercial do extrato e da fatura (nunca o nome do módulo)."""
    def decorar(func):
        signature = inspect.signature(func)

        @wraps(func)
        def executar(*args, **kwargs):
            account = signature.bind(*args, **kwargs).arguments["account"]
            with contexto_conta(account):
                atual.get().canal = "worker"
                atual.get().funcionalidade = funcionalidade
                return func(*args, **kwargs)
        return executar
    return decorar


def selecionar_programa(programa, funcionalidade=None):
    conta = atual.get()
    if conta:
        conta.programa_id = programa.id
        from sqlalchemy.orm import object_session
        from app.models.consumo_flex import ContaConsumo
        db = object_session(programa)
        config = db.get(ContaConsumo, conta.id) if db and conta.id else None
        modelos = (config.modelos or {}) if config else {}
        # Programa sem escolha própria herda a combinação com que o locutor foi gerado.
        escolha = modelos.get(str(programa.id)) or modelos.get(f"radialista:{programa.radio_config_id}") or {}
        conta.modelo_texto = escolha.get('texto')
        conta.modelo_voz = escolha.get('voz')
        if funcionalidade:
            conta.funcionalidade = funcionalidade


def selecionar_radialista(radialista):
    """Geração ligada ao locutor sem programa definido (novo programa) usa a combinação
    com que ele foi criado. Programa já selecionado tem precedência."""
    conta = atual.get()
    if not conta or not conta.id or conta.programa_id is not None:
        return
    from sqlalchemy.orm import object_session
    from app.models.consumo_flex import ContaConsumo
    db = object_session(radialista)
    config = db.get(ContaConsumo, conta.id) if db else None
    escolha = (config.modelos or {}).get(f"radialista:{radialista.id}") if config else None
    if escolha:
        conta.modelo_texto, conta.modelo_voz = escolha.get('texto'), escolha.get('voz')


def modelo_efetivo(tipo, padrao):
    conta = atual.get()
    if conta:
        return (conta.modelo_voz if tipo == 'tts' else conta.modelo_texto) or padrao
    return padrao


def encerrar_contexto(sucesso):
    from app.config.settings import settings
    conta = atual.get()
    if not (settings.ia_medicao_habilitada or settings.ia_orcamento_bloquear) or not conta or not conta.id:
        return
    from app.billing.consumo_ia import SessionLocal
    from app.billing.flex import entregar_operacao
    from app.models.consumo_flex import UsoIA
    from sqlalchemy import select
    with SessionLocal() as db, db.begin():
        if db.scalar(select(UsoIA.id).where(UsoIA.account_id == conta.id, UsoIA.operacao == conta.operacao).limit(1)):
            entregar_operacao(db, conta.id, conta.operacao, sucesso)
