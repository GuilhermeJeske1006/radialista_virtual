import asyncio
import datetime
import uuid
from sqlalchemy.exc import IntegrityError
from app.config.redis_client import redis_client
from app.guardrails.content_filter import (
    contem_topico_proibido,
    avaliar_adequacao_programa,
)
from app.guardrails.rate_limiter import dentro_do_limite
from app.guardrails.schedule import programa_no_ar
from app.models.interaction_log import InteractionLog
from app.models.conversa_ouvinte import ConversaOuvinte
from app.models.mensagem_ouvinte import MensagemOuvinte
from app.whatsapp.atendimento import _atender
from app.whatsapp.locks import bloquear_conversa


async def receber(db, account, config, programa, telefone, nome, texto, message_id):
    chave = message_id or f"radio:{account.id}:sem-id:{uuid.uuid4().hex}"
    item = db.query(MensagemOuvinte).filter_by(chave=chave).first()
    if item is None:
        item = MensagemOuvinte(
            chave=chave,
            account_id=account.id,
            radio_config_id=config.id,
            programa_id=programa.id if programa else None,
            telefone=telefone,
            texto=texto,
        )
        db.add(item)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            item = db.query(MensagemOuvinte).filter_by(chave=chave).one()
    if item.estado != "pendente":
        return {"status": "ignorado", "motivo": "duplicada"}
    marcador = f"inbox:debounce:{account.id}:{item.programa_id}:{telefone}"
    token = uuid.uuid4().hex
    redis_client.set(marcador, token, ex=60)
    from app.whatsapp.webhook import _DEBOUNCE_SEGUNDOS

    await asyncio.sleep(_DEBOUNCE_SEGUNDOS)
    if redis_client.get(marcador) != token:
        return {"status": "ok", "motivo": "aguardando_contexto"}
    # A operação síncrona contém chamadas ao LLM/provedor. Não bloqueia o loop HTTP.
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(
        processar, db, account, config, programa, telefone, nome, chave
    )


def processar(db, account, config, programa, telefone, nome, chave):
    with bloquear_conversa(account.id, telefone):
        item = (
            db.query(MensagemOuvinte).filter_by(chave=chave).populate_existing().one()
        )
        if item.estado != "pendente":
            return {"status": "ignorado", "motivo": "duplicada"}
        itens = (
            db.query(MensagemOuvinte)
            .filter_by(
                account_id=account.id,
                telefone=telefone,
                programa_id=item.programa_id,
                estado="pendente",
            )
            .order_by(MensagemOuvinte.id)
            .all()
        )
        texto = "\n".join(i.texto for i in itens)
        # Não leva uma conversa antiga para a transmissão seguinte do mesmo programa.
        agora = datetime.datetime.now(datetime.timezone.utc)
        recentes = [
            i
            for i in itens
            if agora - i.criado_em.replace(tzinfo=datetime.timezone.utc)
            < datetime.timedelta(hours=1)
        ]
        texto = "\n".join(i.texto for i in recentes)
        for i in itens:
            i.estado = "processada" if i in recentes else "expirada"
        if not texto:
            db.commit()
            return {"status": "ignorado", "motivo": "expirada"}
        programa_valido = (
            programa if programa and programa_no_ar(programa, config.timezone) else None
        )
        bloqueio = None
        c = (
            db.query(ConversaOuvinte)
            .filter_by(account_id=account.id, telefone=telefone)
            .first()
        )
        if programa_valido and not (c and c.humano):
            if not dentro_do_limite(
                f"account:{account.id}:programa:{programa.id}",
                telefone,
                programa.limite_mensagens_hora,
            ):
                bloqueio = "rate_limit"
            elif (
                contem_topico_proibido(texto, programa)
                or not avaliar_adequacao_programa(texto, programa)[0]
            ):
                bloqueio = "conteudo"
        if bloqueio:
            db.add(
                InteractionLog(
                    radio_config_id=config.id,
                    telefone=telefone,
                    nome=nome or None,
                    mensagem_usuario=texto,
                    wuzapi_message_id=chave,
                    status=f"bloqueado_{bloqueio}",
                )
            )
            db.commit()
            return {"status": "bloqueado", "motivo": bloqueio}
        try:
            return _atender(
                db, account, config, programa_valido, telefone, nome, texto, chave
            )
        except Exception:
            db.rollback()
            raise
