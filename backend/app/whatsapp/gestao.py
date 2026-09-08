"""Operação da fila e das conversas, sempre restrita à rádio autenticada."""

import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_account, exigir_admin, get_current_usuario
from app.db.database import get_db
from app.models.account import Account
from app.models.conversa_ouvinte import ConversaOuvinte
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.whatsapp.atendimento import ocorrencia, ESTADOS_ABERTOS, registrar_evento
from app.llm.intent import classificar_intencao
from app.guardrails.content_filter import (
    contem_topico_proibido,
    avaliar_adequacao_programa,
)

router = APIRouter(prefix="/ouvintes", tags=["ouvintes"])


class Config(BaseModel):
    ativo: bool


@router.get("/config")
def config(account: Account = Depends(get_current_account)):
    return {"ativo": account.atendimento_ouvinte_ativo}


@router.put("/config")
def configurar(
    dados: Config, usuario=Depends(exigir_admin), db: Session = Depends(get_db)
):
    usuario.account.atendimento_ouvinte_ativo = dados.ativo
    db.commit()
    return {"ativo": dados.ativo}


class AcaoPedido(BaseModel):
    acao: Literal["aprovar", "recusar", "cancelar", "transferir", "reenfileirar"]
    texto_autorizado: str = Field(default="", max_length=1500)
    nome: str | None = Field(default=None, max_length=100)
    motivo: str = Field(default="", max_length=300)
    programa_id: int | None = None
    autorizacao_confirmada: bool = False


def buscar_pedido(db, account, pedido_id):
    pedido = (
        db.query(FilaAoVivo)
        .join(RadioConfig)
        .filter(FilaAoVivo.id == pedido_id, RadioConfig.account_id == account.id)
        .with_for_update()
        .first()
    )
    if pedido is None:
        raise HTTPException(404, "Pedido não encontrado")
    return pedido


@router.patch("/pedidos/{pedido_id}")
def alterar_pedido(
    pedido_id: int,
    dados: AcaoPedido,
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_usuario),
):
    pedido = buscar_pedido(db, account, pedido_id)
    programa_anterior = pedido.programa_id
    if pedido.estado == "executado" or pedido.atendido:
        raise HTTPException(409, "Participação já executada")
    if pedido.estado == "selecionado" and dados.acao != "reenfileirar":
        raise HTTPException(
            409,
            "Participação selecionada no player; interrompa o bloco antes de reenfileirar",
        )
    if dados.acao == "transferir":
        programa = (
            db.query(Programa)
            .join(RadioConfig)
            .filter(
                Programa.id == dados.programa_id,
                RadioConfig.account_id == account.id,
                RadioConfig.ativo.is_(True),
                Programa.ativo.is_(True),
            )
            .first()
        )
        if not programa:
            raise HTTPException(404, "Programa não encontrado")
        from app.guardrails.schedule import programa_no_ar

        config = db.get(RadioConfig, programa.radio_config_id)
        if not programa_no_ar(programa, config.timezone):
            raise HTTPException(
                409, "Transfira para um programa dentro do horário de exibição"
            )
        pedido.programa_id = programa.id
        pedido.radio_config_id = programa.radio_config_id
        pedido.transmissao = ocorrencia(programa, config.timezone)
        pedido.estado = "aguardando_revisao"
        pedido.texto_autorizado = ""
        pedido.motivo = (
            dados.motivo
            or "Transferido pela equipe; conferir autorização no novo programa"
        )
    elif dados.acao == "aprovar":
        if pedido.estado not in ESTADOS_ABERTOS or not pedido.programa_id:
            raise HTTPException(409, "Vincule a um programa atual antes de aprovar")
        texto = dados.texto_autorizado.strip()
        if not texto or not dados.autorizacao_confirmada:
            raise HTTPException(
                422, "Confirme a autorização e informe apenas o conteúdo para o ar"
            )
        programa = db.get(Programa, pedido.programa_id)
        config = db.get(RadioConfig, pedido.radio_config_id)
        from app.guardrails.schedule import programa_no_ar

        if (
            not programa
            or not programa_no_ar(programa, config.timezone)
            or pedido.transmissao != ocorrencia(programa, config.timezone)
        ):
            raise HTTPException(
                409, "Transmissão encerrada; transfira o pedido antes de aprovar"
            )
        conteudo = texto + " " + (pedido.musica_query or "")
        if (
            contem_topico_proibido(conteudo, programa)
            or not avaliar_adequacao_programa(conteudo, programa)[0]
        ):
            raise HTTPException(422, "Conteúdo incompatível com o programa")
        if any(
            item.casefold() in conteudo.casefold()
            for item in programa.musicas_bloqueadas or []
        ):
            raise HTTPException(422, "Música ou artista bloqueado neste programa")
        if pedido.tipo == "musica" and (
            programa.generos_musicais or programa.musicas_permitidas
        ):
            acao, _, _ = classificar_intencao(
                config, programa, f"Quero pedir a música/artista: {pedido.musica_query}"
            )
            if acao != "musica":
                raise HTTPException(
                    422,
                    "Pedido fora do perfil musical do programa ou classificação indisponível",
                )
        pedido.texto_autorizado = texto
        pedido.estado = "em_fila"
        pedido.motivo = "Autorização de divulgação conferida pela equipe"
        if dados.nome is not None:
            pedido.nome = dados.nome.strip()
            c = (
                db.query(ConversaOuvinte)
                .filter_by(account_id=account.id, telefone=pedido.telefone)
                .first()
            )
            if c:
                c.nome = pedido.nome
    elif dados.acao == "reenfileirar":
        # Não presume que ausência de callback significa que não tocou.
        if pedido.estado != "selecionado":
            raise HTTPException(
                409, "Apenas seleções sem confirmação podem ser reenfileiradas"
            )
        pedido.estado = "aguardando_revisao"
        pedido.selecao_token = None
        pedido.motivo = dados.motivo or "Revisão solicitada após interrupção do player"
    else:
        pedido.estado = "cancelado" if dados.acao == "cancelar" else "nao_atendido"
        pedido.motivo = dados.motivo or "Decisão da equipe"
    registrar_evento(pedido, dados.acao, usuario.id, programa_anterior)
    db.commit()
    return {"id": pedido.id, "estado": pedido.estado}


class Reproducao(BaseModel):
    token: str
    programa_id: int
    resultado: Literal["executado", "falhou", "interrompido"]


@router.post("/pedidos/{pedido_id}/reproducao")
def confirmar(
    pedido_id: int,
    dados: Reproducao,
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    pedido = buscar_pedido(db, account, pedido_id)
    if pedido.selecao_token != dados.token or pedido.programa_id != dados.programa_id:
        raise HTTPException(409, "Confirmação não pertence à seleção atual")
    if pedido.estado in ("executado", "nao_atendido"):
        return {"estado": pedido.estado}
    if pedido.estado != "selecionado":
        raise HTTPException(409, "Pedido não está selecionado")
    pedido.atendido = dados.resultado == "executado"
    pedido.estado = "executado" if pedido.atendido else "nao_atendido"
    pedido.atendido_em = (
        datetime.datetime.now(datetime.timezone.utc) if pedido.atendido else None
    )
    pedido.motivo = (
        "Player confirmou reprodução"
        if pedido.atendido
        else f"Player: {dados.resultado}"
    )
    registrar_evento(pedido, f"player_{dados.resultado}")
    db.commit()
    return {"estado": pedido.estado}


@router.get("/conversas")
def listar(account=Depends(get_current_account), db: Session = Depends(get_db)):
    itens = (
        db.query(ConversaOuvinte)
        .filter_by(account_id=account.id)
        .order_by(ConversaOuvinte.atualizado_em.desc())
        .limit(50)
        .all()
    )
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    for c in itens:
        if c.atualizado_em.replace(tzinfo=datetime.timezone.utc) < limite:
            c.historico = []
            c.pendente = {}
    db.commit()
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "telefone": c.telefone,
            "humano": c.humano,
            "historico": c.historico,
            "atualizado_em": c.atualizado_em,
        }
        for c in itens
    ]


class AtendimentoHumano(BaseModel):
    humano: bool
    nome: str | None = Field(default=None, max_length=100)


@router.patch("/conversas/{conversa_id}")
def assumir(
    conversa_id: int,
    dados: AtendimentoHumano,
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    c = (
        db.query(ConversaOuvinte)
        .filter_by(id=conversa_id, account_id=account.id)
        .with_for_update()
        .first()
    )
    if not c:
        raise HTTPException(404, "Conversa não encontrada")
    from app.whatsapp.locks import bloquear_conversa

    with bloquear_conversa(account.id, c.telefone):
        c.humano = dados.humano
        if dados.nome is not None:
            c.nome = dados.nome.strip()
        db.commit()
    return {"humano": c.humano}


@router.get("/indicadores")
def indicadores(account=Depends(get_current_account), db: Session = Depends(get_db)):
    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    contagens = (
        db.query(FilaAoVivo.estado, func.count(FilaAoVivo.id))
        .join(RadioConfig)
        .filter(RadioConfig.account_id == account.id, FilaAoVivo.criado_em >= desde)
        .group_by(FilaAoVivo.estado)
        .all()
    )
    return {"dias": 30, "pedidos_por_estado": dict(contagens)}


@router.get("/pedidos")
def listar_pedidos(account=Depends(get_current_account), db: Session = Depends(get_db)):
    from app.live.router import PedidoFilaResponse
    from app.whatsapp.atendimento import expirar

    for p in (
        db.query(Programa)
        .join(RadioConfig)
        .filter(RadioConfig.account_id == account.id)
        .all()
    ):
        expirar(db, p, db.get(RadioConfig, p.radio_config_id).timezone)
    pedidos = (
        db.query(FilaAoVivo)
        .join(RadioConfig)
        .filter(RadioConfig.account_id == account.id)
        .order_by(FilaAoVivo.criado_em.desc())
        .limit(100)
        .all()
    )
    return [PedidoFilaResponse.model_validate(p) for p in pedidos]


@router.get("/programas")
def listar_programas(
    account=Depends(get_current_account), db: Session = Depends(get_db)
):
    itens = (
        db.query(Programa)
        .join(RadioConfig)
        .filter(
            RadioConfig.account_id == account.id,
            RadioConfig.ativo.is_(True),
            Programa.ativo.is_(True),
        )
        .all()
    )
    return [{"id": p.id, "nome": p.nome} for p in itens]


@router.get("/envios-pendentes")
def envios_pendentes(
    account=Depends(get_current_account), db: Session = Depends(get_db)
):
    from app.models.interaction_log import InteractionLog

    itens = (
        db.query(InteractionLog)
        .join(RadioConfig)
        .filter(
            RadioConfig.account_id == account.id,
            InteractionLog.resposta_pendente.is_not(None),
        )
        .order_by(InteractionLog.criado_em.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": i.id,
            "nome": i.nome,
            "telefone": i.telefone,
            "texto": i.resposta_pendente,
            "status": i.status,
        }
        for i in itens
    ]


class Reenvio(BaseModel):
    confirmei_nao_entregue: bool


@router.post("/envios-pendentes/{log_id}/reenviar")
def reenviar(
    log_id: int,
    dados: Reenvio,
    account=Depends(get_current_account),
    db: Session = Depends(get_db),
):
    from app.models.interaction_log import InteractionLog
    from app.whatsapp.atendimento import conversa, enviar_resposta_pendente
    from app.whatsapp.locks import bloquear_conversa

    log = (
        db.query(InteractionLog)
        .join(RadioConfig)
        .filter(InteractionLog.id == log_id, RadioConfig.account_id == account.id)
        .first()
    )
    if not log:
        raise HTTPException(404, "Envio não encontrado")
    if not dados.confirmei_nao_entregue:
        raise HTTPException(
            422, "Confira no WhatsApp se a mensagem não foi entregue antes de reenviar"
        )
    with bloquear_conversa(account.id, log.telefone):
        db.refresh(log)
        c = conversa(db, account.id, log.telefone)
        config = db.get(RadioConfig, log.radio_config_id)
        if (
            c.humano
            or not account.atendimento_ouvinte_ativo
            or not config.resposta_automatica_whatsapp
            or not account.wuzapi_token
        ):
            raise HTTPException(
                409, "Envio automático pausado; continue pelo WhatsApp da rádio"
            )
        mais_nova = (
            db.query(InteractionLog)
            .join(RadioConfig)
            .filter(
                RadioConfig.account_id == account.id,
                InteractionLog.telefone == log.telefone,
                InteractionLog.id > log.id,
            )
            .first()
        )
        if mais_nova:
            raise HTTPException(
                409,
                "A conversa avançou; confira e responda pelo WhatsApp para não enviar contexto antigo",
            )
        enviar_resposta_pendente(db, account, c, log)
    return {"status": log.status}
