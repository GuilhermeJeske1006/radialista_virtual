"""Central operacional: histórico, autoria, envios, revisão e eventos isolados por conta."""
import asyncio
import datetime
import json
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from app.auth.dependencies import get_current_usuario
from app.auth.security import COOKIE_TOKEN, decodificar_token
from app.config.settings import settings
from app.db.database import get_db, SessionLocal
from app.models.account import Account
from app.models.usuario import Usuario
from app.models.conversa_ouvinte import ConversaOuvinte
from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig
from app.models.programa import Programa
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.canal_whatsapp import (EntradaWhatsapp, EnvioWhatsapp, EventoCanal, ConexaoEventos, LeituraConversa, NotaConversa, ResponsavelConversa,
    ContribuicaoOuvinte, DiscussaoPrograma, agora)
from app.whatsapp.eventos import registrar, depois
from app.whatsapp.locks import bloquear_conversa
from app.whatsapp.atendimento import ocorrencia
from app.whatsapp.transmissao import contexto_publico

router = APIRouter(prefix="/ouvintes", tags=["ouvintes"])


def buscar(db, account_id, conversa_id):
    c = db.query(ConversaOuvinte).filter_by(id=conversa_id, account_id=account_id).first()
    if not c:
        raise HTTPException(404, "Conversa não encontrada")
    return c


def logs(db, c):
    return db.query(InteractionLog).join(RadioConfig).filter(
        RadioConfig.account_id == c.account_id, InteractionLog.telefone == c.telefone)


def responsavel(db, c, usuario):
    item = db.get(ResponsavelConversa, c.id)
    u = db.get(Usuario, item.usuario_id) if item and item.usuario_id else None
    return {"responsavel_nome": u.nome if u else None,
            "pode_responder": not u or not u.ativo or u.id == usuario.id}


def bootstrap(db, account_id):
    # Apenas cria identidades que faltam. O histórico original continua intacto.
    existentes = db.query(ConversaOuvinte.telefone).filter_by(account_id=account_id)
    pares = db.query(InteractionLog.telefone, func.max(InteractionLog.criado_em)).join(RadioConfig).filter(
        RadioConfig.account_id == account_id, ~InteractionLog.telefone.in_(existentes),
    ).group_by(InteractionLog.telefone).all()
    if pares:
        db.query(Account.id).filter_by(id=account_id).with_for_update().one()
        for telefone, atualizado in pares:
            if not db.query(ConversaOuvinte.id).filter_by(account_id=account_id, telefone=telefone).first():
                db.add(ConversaOuvinte(account_id=account_id, telefone=telefone, atualizado_em=atualizado))
        db.commit()


@router.get("/central")
def listar(busca: str = "", modo: Literal["todas", "humano", "agente", "nao_lidas"] = "todas",
           pagina: int = 1, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    bootstrap(db, usuario.account_id)
    query = db.query(ConversaOuvinte).filter_by(account_id=usuario.account_id)
    if busca.strip():
        termo = f"%{busca.strip()[:100]}%"
        query = query.filter(or_(ConversaOuvinte.nome.ilike(termo), ConversaOuvinte.telefone.ilike(termo)))
    if modo in ("humano", "agente"):
        query = query.filter(ConversaOuvinte.humano.is_(modo == "humano"))
    if modo == "nao_lidas":
        leitura = db.query(LeituraConversa.ultimo_log_id).filter(
            LeituraConversa.conversa_id == ConversaOuvinte.id, LeituraConversa.usuario_id == usuario.id,
        ).correlate(ConversaOuvinte).scalar_subquery()
        query = query.filter(db.query(InteractionLog.id).join(RadioConfig).filter(
            RadioConfig.account_id == usuario.account_id, InteractionLog.telefone == ConversaOuvinte.telefone,
            InteractionLog.origem == "ouvinte", InteractionLog.id > func.coalesce(leitura, 0),
        ).exists())
    total = query.count()
    itens = query.order_by(ConversaOuvinte.atualizado_em.desc(), ConversaOuvinte.id.desc()).offset(
        (max(1, pagina) - 1) * 25).limit(25).all()
    resultado = []
    for c in itens:
        ultimo = logs(db, c).order_by(InteractionLog.id.desc()).first()
        leitura = db.query(LeituraConversa).filter_by(usuario_id=usuario.id, conversa_id=c.id).first()
        nao_lidas = logs(db, c).filter(InteractionLog.origem == "ouvinte",
            InteractionLog.id > (leitura.ultimo_log_id if leitura else 0)).count()
        resultado.append({"id": c.id, "telefone": c.telefone, "nome": c.nome or (ultimo.nome if ultimo else ""),
            "humano": c.humano, "atualizado_em": c.atualizado_em, "nao_lidas": nao_lidas,
            **responsavel(db, c, usuario),
            "ultima_mensagem": (ultimo.resposta or ultimo.mensagem_usuario)[:160] if ultimo else "Mensagem em processamento"})
    cursor = db.query(func.max(EventoCanal.sequencia)).filter_by(account_id=usuario.account_id).scalar() or 0
    return {"conversas": resultado, "pagina": max(1, pagina), "total": total,
            "total_paginas": max(1, (total + 24) // 25), "cursor": cursor}


@router.get("/conversas/{conversa_id}/mensagens")
def mensagens(conversa_id: int, antes: int | None = None, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    c = buscar(db, usuario.account_id, conversa_id)
    query = logs(db, c)
    if antes:
        query = query.filter(InteractionLog.id < antes)
    linhas = query.order_by(InteractionLog.id.desc()).limit(31).all()
    tem_mais = len(linhas) > 30
    linhas = list(reversed(linhas[:30]))
    ids = [i.id for i in linhas]
    envios = {e.log_id: e for e in db.query(EnvioWhatsapp).filter(EnvioWhatsapp.log_id.in_(ids)).all()}
    resultado = []
    for i in linhas:
        envio = envios.get(i.id)
        resultado.append({"id": str(i.id), "log_id": i.id, "origem": i.origem, "texto": i.mensagem_usuario,
            "status": envio.estado if envio and i.origem == "radio" else i.status, "em": i.criado_em,
            "usuario_id": envio.usuario_id if envio else None, "envio_id": envio.id if envio and i.origem == "radio" else None})
        if i.origem != "radio" and (i.resposta or i.resposta_pendente):
            resultado.append({"id": f"{i.id}:resposta", "log_id": i.id, "origem": "radio",
                "texto": i.resposta or i.resposta_pendente, "status": envio.estado if envio else (
                    "aceito_pelo_provedor" if i.resposta else "incerto"), "em": i.criado_em,
                "usuario_id": envio.usuario_id if envio else None, "envio_id": envio.id if envio else None})
    pendentes = db.query(EntradaWhatsapp).filter_by(account_id=usuario.account_id, telefone=c.telefone).filter(
        EntradaWhatsapp.estado.in_(("pendente", "falhou"))).order_by(EntradaWhatsapp.id).limit(30).all() if not antes else []
    for p in pendentes:
        resultado.append({"id": f"entrada:{p.id}", "log_id": None, "origem": "radio" if p.from_me else "ouvinte",
            "texto": p.texto or f"[{p.tipo}]", "status": "processando" if p.estado == "pendente" else "falha_processamento", "em": p.criado_em})
    return {"mensagens": resultado, "antes": linhas[0].id if tem_mais and linhas else None,
            "ultimo_log_id": max(ids, default=0), "conversa": {"id": c.id, "nome": c.nome, "telefone": c.telefone, "humano": c.humano, **responsavel(db, c, usuario)}}


class MensagemManual(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)
    chave: str = Field(min_length=8, max_length=100)


@router.post("/conversas/{conversa_id}/mensagens")
def enviar(conversa_id: int, dados: MensagemManual, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    c = buscar(db, usuario.account_id, conversa_id)
    with bloquear_conversa(usuario.account_id, c.telefone, db):
        db.refresh(c)
        chave = f"manual:{usuario.account_id}:{dados.chave}"
        envio = db.query(EnvioWhatsapp).filter_by(chave=chave).first()
        if envio:
            if envio.telefone != c.telefone or envio.texto != dados.texto.strip():
                raise HTTPException(409, "Chave já utilizada para outra mensagem")
            return {"id": envio.log_id, "estado": envio.estado}
        if not c.humano:
            raise HTTPException(409, "Assuma a conversa antes de enviar")
        dono = db.get(ResponsavelConversa, c.id)
        if dono and dono.usuario_id and dono.usuario_id != usuario.id:
            u = db.get(Usuario, dono.usuario_id)
            if u and u.ativo:
                raise HTTPException(409, "Conversa atribuída a outra pessoa da equipe")
        if not dono:
            dono = ResponsavelConversa(conversa_id=c.id)
            db.add(dono)
        dono.usuario_id = usuario.id
        if not dados.texto.strip():
            raise HTTPException(422, "Informe a mensagem")
        if not usuario.account.wuzapi_token:
            raise HTTPException(409, "Conecte o WhatsApp antes de enviar")
        from app.whatsapp.webhook import _radialista_no_ar
        config, _ = _radialista_no_ar(db, usuario.account_id)
        if not config:
            raise HTTPException(409, "Configure um radialista para registrar o atendimento")
        log = InteractionLog(radio_config_id=config.id, telefone=c.telefone, nome=c.nome,
            origem="radio", mensagem_usuario=dados.texto.strip(), resposta_pendente=dados.texto.strip(), status="pendente_envio")
        db.add(log)
        db.flush()
        envio = EnvioWhatsapp(chave=chave, account_id=usuario.account_id, log_id=log.id, telefone=c.telefone,
            texto=dados.texto.strip(), automatico=False, usuario_id=usuario.id)
        db.add(envio)
        c.atualizado_em = agora()
        registrar(db, usuario.account_id, "conversa.atualizada", conversa_id=c.id)
        db.commit()
    if not settings.whatsapp_worker_ativo:
        from app.whatsapp.worker import processar_envio
        processar_envio(db, envio.id)
    return {"id": log.id, "estado": envio.estado}


class Marcador(BaseModel):
    ultimo_log_id: int = Field(ge=0)


@router.post("/conversas/{conversa_id}/leitura")
def ler(conversa_id: int, dados: Marcador, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    c = buscar(db, usuario.account_id, conversa_id)
    db.query(Usuario.id).filter_by(id=usuario.id).with_for_update().one()
    ultimo = logs(db, c).with_entities(func.max(InteractionLog.id)).scalar() or 0
    leitura = db.query(LeituraConversa).filter_by(usuario_id=usuario.id, conversa_id=c.id).first()
    if not leitura:
        leitura = LeituraConversa(usuario_id=usuario.id, conversa_id=c.id, ultimo_log_id=0)
        db.add(leitura)
    leitura.ultimo_log_id = max(leitura.ultimo_log_id, min(dados.ultimo_log_id, ultimo))
    db.commit()
    return {"ultimo_log_id": leitura.ultimo_log_id}


class Nota(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


@router.post("/conversas/{conversa_id}/notas")
def anotar(conversa_id: int, dados: Nota, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    c = buscar(db, usuario.account_id, conversa_id)
    db.add(NotaConversa(conversa_id=c.id, usuario_id=usuario.id, texto=dados.texto.strip()))
    registrar(db, usuario.account_id, "conversa.atualizada", conversa_id=c.id)
    db.commit()
    return {"status": "ok"}


@router.get("/conversas/{conversa_id}/contexto")
def contexto(conversa_id: int, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    c = buscar(db, usuario.account_id, conversa_id)
    pedidos = db.query(FilaAoVivo).join(RadioConfig).filter(RadioConfig.account_id == usuario.account_id,
        FilaAoVivo.telefone == c.telefone).order_by(FilaAoVivo.id.desc()).limit(10).all()
    notas = db.query(NotaConversa).filter_by(conversa_id=c.id).order_by(NotaConversa.id.desc()).limit(20).all()
    from app.whatsapp.webhook import _radialista_no_ar
    _, programa = _radialista_no_ar(db, usuario.account_id)
    publico = contexto_publico(db, usuario.account_id, programa.id) if programa else None
    contribuicoes = db.query(ContribuicaoOuvinte).filter_by(conversa_id=c.id).order_by(ContribuicaoOuvinte.id.desc()).limit(10).all()
    from app.whatsapp.memoria import obter
    return {"pedidos": [{"id": p.id, "tipo": p.tipo, "estado": p.estado, "texto": p.texto_autorizado,
                         "programa_id": p.programa_id} for p in pedidos],
            "pendente": c.pendente, "programa_id": programa.id if programa else None, "publico": publico, "memoria": obter(db, c),
            "notas": [{"id": n.id, "texto": n.texto, "usuario_id": n.usuario_id, "em": n.criado_em} for n in notas],
            "contribuicoes": [{"id": x.id, "estado": x.estado, "log_id": x.log_id, "assunto_id": x.assunto_id} for x in contribuicoes]}


class Contribuicao(BaseModel):
    log_id: int
    programa_id: int
    discussao_id: int | None = None


@router.post("/conversas/{conversa_id}/contribuicoes")
def propor(conversa_id: int, dados: Contribuicao, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    c = buscar(db, usuario.account_id, conversa_id)
    log = logs(db, c).filter(InteractionLog.id == dados.log_id, InteractionLog.origem == "ouvinte").first()
    programa = db.query(Programa).join(RadioConfig).filter(Programa.id == dados.programa_id,
        RadioConfig.account_id == usuario.account_id).first()
    if not log or not programa:
        raise HTTPException(404, "Mensagem ou programa não encontrado")
    radio = db.get(RadioConfig, programa.radio_config_id)
    from app.guardrails.schedule import programa_no_ar
    if not programa_no_ar(programa, radio.timezone):
        raise HTTPException(409, "Escolha um programa em exibição")
    with bloquear_conversa(usuario.account_id, c.telefone, db):
        item = db.query(ContribuicaoOuvinte).filter_by(log_id=log.id).first()
        if item:
            return {"id": item.id, "estado": item.estado}
        if dados.discussao_id:
            d = db.query(DiscussaoPrograma).filter_by(id=dados.discussao_id, account_id=usuario.account_id,
                programa_id=programa.id, ocorrencia=ocorrencia(programa, radio.timezone), estado="aberta").first()
            if not d:
                raise HTTPException(409, "Discussão encerrada ou de outro programa")
        item = ContribuicaoOuvinte(account_id=usuario.account_id, conversa_id=c.id, log_id=log.id,
            programa_id=programa.id, ocorrencia=ocorrencia(programa, radio.timezone), discussao_id=dados.discussao_id)
        db.add(item)
        registrar(db, usuario.account_id, "pauta.atualizada", programa_id=programa.id)
        db.commit()
        return {"id": item.id, "estado": item.estado}


class RevisaoContribuicao(BaseModel):
    acao: Literal["aprovar", "recusar"]
    titulo: str = Field(default="", max_length=150)
    texto_autorizado: str = Field(default="", max_length=1500)
    autorizacao_confirmada: bool = False


@router.patch("/contribuicoes/{contribuicao_id}")
def revisar(contribuicao_id: int, dados: RevisaoContribuicao, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    item = db.query(ContribuicaoOuvinte).filter_by(id=contribuicao_id, account_id=usuario.account_id).with_for_update().first()
    if not item:
        raise HTTPException(404, "Contribuição não encontrada")
    if item.estado != "aguardando_revisao":
        return {"estado": item.estado, "assunto_id": item.assunto_id}
    if dados.acao == "recusar":
        item.estado = "recusada"
    else:
        if not dados.autorizacao_confirmada or not dados.texto_autorizado.strip() or not dados.titulo.strip():
            raise HTTPException(422, "Confirme autorização e informe título e conteúdo para o ar")
        programa = db.get(Programa, item.programa_id)
        radio = db.get(RadioConfig, programa.radio_config_id)
        from app.guardrails.schedule import programa_no_ar
        if item.ocorrencia != ocorrencia(programa, radio.timezone) or not programa_no_ar(programa, radio.timezone):
            raise HTTPException(409, "A transmissão da contribuição encerrou")
        from app.guardrails.content_filter import contem_topico_proibido, avaliar_adequacao_programa
        texto = dados.texto_autorizado.strip()
        if contem_topico_proibido(texto, programa) or not avaliar_adequacao_programa(texto, programa)[0]:
            raise HTTPException(422, "Conteúdo incompatível com o programa")
        assunto = Assunto(account_id=usuario.account_id, origem="ouvinte", origem_ref_id=item.id,
            titulo=dados.titulo.strip(), gancho=texto, fatos=[], tags=["ouvinte", "participacao"],
            validade_ate=agora() + datetime.timedelta(hours=1), peso_base=7)
        db.add(assunto)
        db.flush()
        db.add(AssuntoPrograma(assunto_id=assunto.id, programa_id=programa.id, score=8,
            ponte="Participação revisada da audiência. Relato pessoal, não um fato jornalístico verificado.",
            eixos_sugeridos=["pergunta", "memoria", "impacto"]))
        item.estado, item.assunto_id, item.texto_autorizado = "aprovada", assunto.id, texto
    item.usuario_id = usuario.id
    registrar(db, usuario.account_id, "pauta.atualizada", programa_id=item.programa_id)
    db.commit()
    return {"estado": item.estado, "assunto_id": item.assunto_id}


class ConfirmarReenvio(BaseModel):
    confirmei_nao_entregue: bool


@router.post("/envios/{envio_id}/reenviar")
def reenviar(envio_id: int, dados: ConfirmarReenvio, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    envio = db.query(EnvioWhatsapp).filter_by(id=envio_id, account_id=usuario.account_id).first()
    if not envio:
        raise HTTPException(404, "Envio não encontrado")
    if not dados.confirmei_nao_entregue:
        raise HTTPException(422, "Confira no WhatsApp se a mensagem não foi entregue")
    with bloquear_conversa(usuario.account_id, envio.telefone, db):
        db.refresh(envio)
        if envio.estado not in ("incerto", "falha_conexao", "pausado"):
            raise HTTPException(409, "Este envio não pode ser reenviado")
        c = db.query(ConversaOuvinte).filter_by(account_id=usuario.account_id, telefone=envio.telefone).one()
        if envio.automatico and c.humano:
            raise HTTPException(409, "Atendimento automático pausado")
        nova = logs(db, c).filter(InteractionLog.id > envio.log_id).first()
        if nova:
            raise HTTPException(409, "A conversa avançou; escreva uma nova resposta com o contexto atual")
        envio.estado, envio.tentativas = "pendente", 0
        registrar(db, usuario.account_id, "mensagem.atualizada", log_id=envio.log_id)
        db.commit()
    if not settings.whatsapp_worker_ativo:
        from app.whatsapp.worker import processar_envio
        processar_envio(db, envio.id)
    return {"estado": envio.estado}


@router.post("/entradas/{entrada_id}/reprocessar")
def reprocessar(entrada_id: int, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    item = db.query(EntradaWhatsapp).filter_by(id=entrada_id, account_id=usuario.account_id).first()
    if not item:
        raise HTTPException(404, "Entrada não encontrada")
    with bloquear_conversa(usuario.account_id, item.telefone, db):
        db.refresh(item)
        if item.estado != "falhou":
            raise HTTPException(409, "Apenas entradas com falha podem ser reprocessadas")
        if item.tipo != "texto" and not item.texto and not item.payload:
            raise HTTPException(409, "A mídia expirou; peça ao ouvinte para reenviar")
        item.estado, item.tentativas, item.erro, item.disponivel_em = "pendente", 0, "", agora()
        registrar(db, usuario.account_id, "mensagem.atualizada", telefone=item.telefone)
        db.commit()
    return {"estado": item.estado}


@router.get("/operacao")
def operacao(usuario=Depends(get_current_usuario), db=Depends(get_db)):
    aid = usuario.account_id
    entradas = dict(db.query(EntradaWhatsapp.estado, func.count()).filter_by(account_id=aid).group_by(EntradaWhatsapp.estado).all())
    envios = dict(db.query(EnvioWhatsapp.estado, func.count()).filter_by(account_id=aid).group_by(EnvioWhatsapp.estado).all())
    mais_antiga = db.query(func.min(EntradaWhatsapp.criado_em)).filter_by(account_id=aid, estado="pendente").scalar()
    falhas = db.query(EntradaWhatsapp).filter_by(account_id=aid, estado="falhou").order_by(EntradaWhatsapp.id.desc()).limit(20).all()
    return {"entradas": entradas, "envios": envios, "pendente_desde": mais_antiga,
            "falhas": [{"id": i.id, "telefone": i.telefone, "erro": i.erro} for i in falhas]}


@router.get("/eventos")
async def eventos(request: Request, cursor: int = 0, usuario=Depends(get_current_usuario), db=Depends(get_db)):
    inicial = cursor == 0 and "last-event-id" not in request.headers
    try:
        cursor = max(0, int(request.headers.get("last-event-id", cursor)))
    except ValueError:
        raise HTTPException(422, "Cursor inválido")
    account_id, usuario_id = usuario.account_id, usuario.id
    db.query(Account.id).filter_by(id=account_id).with_for_update().one()
    ativas = db.query(ConexaoEventos).filter(ConexaoEventos.account_id == account_id, ConexaoEventos.expira_em > agora())
    if ativas.count() >= 20 or ativas.filter(ConexaoEventos.usuario_id == usuario_id).count() >= 5:
        raise HTTPException(429, "Limite de conexões de atualização atingido")
    lease = uuid.uuid4().hex
    db.add(ConexaoEventos(id=lease, account_id=account_id, usuario_id=usuario_id,
                         expira_em=agora() + datetime.timedelta(minutes=3)))
    db.commit()  # Libera a conexão usada pelas dependências durante a vida do stream.
    credencial = request.cookies.get(COOKIE_TOKEN) or request.headers.get("authorization", "").removeprefix("Bearer ")

    async def stream():
        atual = cursor
        try:
            if inicial:
                with SessionLocal() as sessao:
                    atual = sessao.query(func.max(EventoCanal.sequencia)).filter_by(account_id=account_id).scalar() or 0
                dados = json.dumps({"id": atual, "tipo": "sincronizar"})
                yield f"id: {atual}\nevent: atualizacao\ndata: {dados}\n\n"
            # A reconexão periódica refaz as dependências; cada leitura também valida
            # expiração e desativação. Não há conexão SQL presa durante o await.
            for _ in range(120):
                if await request.is_disconnected() or decodificar_token(credencial) != usuario_id:
                    return
                with SessionLocal() as sessao:
                    u = sessao.get(Usuario, usuario_id)
                    if not u or not u.ativo or u.account_id != account_id:
                        return
                    lote = depois(sessao, account_id, atual)
                if lote:
                    for evento in lote:
                        atual = evento["id"]
                        dados = json.dumps(evento, ensure_ascii=False)
                        yield f"id: {atual}\nevent: atualizacao\ndata: {dados}\n\n"
                else:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(1)
        finally:
            from sqlalchemy.exc import SQLAlchemyError
            try:
                with SessionLocal() as sessao:
                    sessao.query(ConexaoEventos).filter_by(id=lease).delete()
                    sessao.commit()
            except SQLAlchemyError:
                pass  # O lease expira mesmo se o banco estiver temporariamente fora.
    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
