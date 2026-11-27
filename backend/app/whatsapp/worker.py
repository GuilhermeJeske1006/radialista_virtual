"""Consumidor durável: python -m app.whatsapp.worker. Um processo pode reiniciar sem perder jobs."""
import datetime
import logging

from app.util.log_seguro import configurar_logging
import time
import uuid
import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import defer
from redis import RedisError
from app.config.settings import settings
from app.db.database import SessionLocal
from app.models.account import Account
from app.models.radio_config import RadioConfig
from app.models.programa import Programa
from app.models.conversa_ouvinte import ConversaOuvinte
from app.models.mensagem_ouvinte import MensagemOuvinte
from app.models.interaction_log import InteractionLog
from app.models.canal_whatsapp import EntradaWhatsapp, EnvioWhatsapp, agora
from app.whatsapp.locks import bloquear_conversa
from app.whatsapp.eventos import registrar
from app.whatsapp.transmissao import utc

logger = logging.getLogger("radialista.whatsapp.worker")


class FalhaEntrada(Exception):
    def __init__(self, entrada_id, original):
        self.entrada_id, self.original = entrada_id, original


def persistir(db, account, config, programa, extraido, payload):
    telefone, nome, texto, audio, imagem, mime, _, _, from_me, chave = extraido
    chave = chave or f"local:{uuid.uuid4().hex}"
    existente = db.query(EntradaWhatsapp).filter_by(chave=chave).first()
    if existente:
        return {"status": "ignorado", "motivo": "duplicada"}
    info = (payload.get("event") or {}).get("Info") or {}
    msg = (payload.get("event") or {}).get("Message") or {}
    context = (msg.get("extendedTextMessage") or msg.get("audioMessage") or msg.get("imageMessage") or {}).get("contextInfo") or {}
    item = EntradaWhatsapp(chave=chave, account_id=account.id, radio_config_id=config.id,
        programa_id=programa.id if programa else None, telefone=telefone, nome=nome,
        provider_id=info.get("ID") or info.get("Id") or info.get("id") or payload.get("id"), citada_id=context.get("stanzaId"), from_me=from_me,
        tipo="audio" if audio else "imagem" if imagem else "texto", texto=texto,
        payload={"audio": audio, "imagem": imagem, "mime": mime},
        disponivel_em=agora() + datetime.timedelta(seconds=0 if from_me else settings.whatsapp_debounce_s))
    db.add(item)
    try:
        db.query(Account.id).filter_by(id=account.id).with_for_update().one()
        from app.whatsapp.atendimento import conversa
        c = conversa(db, account.id, telefone, nome)
        c.atualizado_em = agora()
        registrar(db, account.id, "mensagem.recebida", telefone=telefone)
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.query(EntradaWhatsapp).filter_by(chave=chave).first():
            return {"status": "ignorado", "motivo": "duplicada"}
        raise
    return {"status": "recebido", "mensagem_id": item.id}


def _texto(db, item):
    if item.payload.get("audio") or item.payload.get("imagem"):
        from app.guardrails.http_rate_limit import limite_excedido
        if limite_excedido(f"whatsapp_midia:{item.account_id}:{item.telefone}", 30, 3600):
            raise ValueError("limite_midia")
        if item.payload.get("audio"):
            from app.stt.client import transcrever_audio, stt_habilitado
            if not stt_habilitado():
                raise ValueError("audio_sem_stt")
            descricao = transcrever_audio(item.payload["audio"])
        else:
            from app.llm.client import descrever_imagem
            descricao = descrever_imagem(item.payload["imagem"], item.payload.get("mime", "image/jpeg"))
        if not descricao:
            raise RuntimeError("midia_sem_texto")
        item.texto = "\n".join(t for t in (item.texto, descricao) if t)
        item.payload = {}  # Checkpoint antes do agente: retry não paga a mesma mídia novamente.
        db.commit()
    return item.texto or "[mídia não textual]"


def processar_entrada(db, item_id):
    item = db.get(EntradaWhatsapp, item_id)
    if not item or item.estado != "pendente":
        return False
    with bloquear_conversa(item.account_id, item.telefone, db):
        db.refresh(item)
        if item.estado != "pendente":
            return False
        account = db.get(Account, item.account_id)
        if not account.atendimento_ouvinte_ativo:
            return False  # Pausa recuperável; não entrega o job a outro fluxo.
        config = db.get(RadioConfig, item.radio_config_id)
        from app.whatsapp.atendimento import conversa, _atender, envio_adiado
        if item.from_me:
            eco = db.query(EnvioWhatsapp).filter_by(account_id=account.id, provider_id=item.provider_id).first() if item.provider_id else None
            if not eco:
                c = conversa(db, account.id, item.telefone)
                c.humano = True
                c.historico = [*c.historico, {"role": "assistant", "content": (item.texto or "[mídia]")[:4000]}][-10:]
                c.atualizado_em = agora()
                db.add(InteractionLog(radio_config_id=config.id, telefone=item.telefone,
                    mensagem_usuario=item.texto or "[mídia]", wuzapi_message_id=item.chave,
                    origem="radio", status="enviada"))
            item.estado, item.payload = "processada", {}
            registrar(db, account.id, "conversa.atualizada", telefone=item.telefone)
            db.commit()
            return True
        grupo = db.query(EntradaWhatsapp).options(defer(EntradaWhatsapp.payload)).filter_by(
            account_id=account.id, telefone=item.telefone, programa_id=item.programa_id,
            estado="pendente", from_me=False).order_by(EntradaWhatsapp.id).limit(50).all()
        grupo = [i for i in grupo if not i.tentativas or utc(i.disponivel_em) <= agora()]
        from app.whatsapp.atendimento import ocorrencia
        programa_recebido = db.get(Programa, item.programa_id) if item.programa_id else None
        if programa_recebido:
            original = ocorrencia(programa_recebido, config.timezone, item.criado_em)
            grupo = [i for i in grupo if ocorrencia(programa_recebido, config.timezone, i.criado_em) == original]
        if not grupo:
            return False
        # Não atravessar o backoff de uma mídia que falhou.
        ultima = max(utc(i.disponivel_em) for i in grupo)
        limite = utc(grupo[0].criado_em) + datetime.timedelta(seconds=settings.whatsapp_agrupamento_max_s)
        if agora() < min(ultima, limite):
            return False
        from app.billing.contexto_ia import contexto_conta, atual, identificar
        from app.guardrails.provedores import contexto_capacidade
        with contexto_conta(account), contexto_capacidade(prioridade=1):
            atual.get().canal, atual.get().funcionalidade = "whatsapp", "atendimento_whatsapp"
            atual.get().operacao = f"whatsapp:{account.id}:{grupo[0].id}"
            identificar(account)
            textos = []
            for entrada in grupo:
                try:
                    textos.append(_texto(db, entrada))
                except Exception as exc:
                    raise FalhaEntrada(entrada.id, exc) from exc
            for entrada, texto in zip(grupo, textos):
                existente = db.query(MensagemOuvinte).filter_by(chave=entrada.chave).first()
                if not existente:
                    db.add(MensagemOuvinte(chave=entrada.chave, account_id=account.id, radio_config_id=config.id,
                        programa_id=entrada.programa_id, telefone=entrada.telefone, texto=texto))
                entrada.estado = "processada"
            db.flush()
            programa = db.get(Programa, item.programa_id) if item.programa_id else None
            from app.guardrails.schedule import programa_no_ar
            if programa and (not programa.ativo or not programa_no_ar(programa, config.timezone)
                or agora() - utc(grupo[0].criado_em) > datetime.timedelta(hours=1)
                or ocorrencia(programa, config.timezone, grupo[0].criado_em) != ocorrencia(programa, config.timezone)):
                programa = None
            bolhas = db.query(MensagemOuvinte).filter(MensagemOuvinte.chave.in_([i.chave for i in grupo]),
                MensagemOuvinte.estado == "pendente").order_by(MensagemOuvinte.id).all()
            texto = "\n".join(b.texto for b in bolhas)
            from app.guardrails.content_filter import contem_topico_proibido, avaliar_adequacao_programa
            from app.guardrails.rate_limiter import dentro_do_limite
            c = db.query(ConversaOuvinte).filter_by(account_id=account.id, telefone=item.telefone).first()
            bloqueio = None
            if programa and not (c and c.humano):
                if not dentro_do_limite(f"account:{account.id}:programa:{programa.id}", item.telefone, programa.limite_mensagens_hora):
                    bloqueio = "rate_limit"
                elif contem_topico_proibido(texto, programa) or not avaliar_adequacao_programa(texto, programa)[0]:
                    bloqueio = "conteudo"
            for b in bolhas:
                b.estado = "processada"
            if bloqueio:
                db.add(InteractionLog(radio_config_id=config.id, telefone=item.telefone, nome=item.nome,
                    mensagem_usuario=texto, wuzapi_message_id=grupo[-1].chave, status=f"bloqueado_{bloqueio}"))
                registrar(db, account.id, "conversa.atualizada", telefone=item.telefone)
                db.commit()
            else:
                from app.whatsapp.atendimento import referencia_mensagem
                referencia = None
                citada_id = next((i.citada_id for i in reversed(grupo) if i.citada_id), None)
                if citada_id:
                    enviada = db.query(EnvioWhatsapp).filter_by(account_id=account.id,
                        telefone=item.telefone, provider_id=citada_id).first()
                    recebida = db.query(EntradaWhatsapp).filter_by(account_id=account.id,
                        telefone=item.telefone, provider_id=citada_id).first()
                    referencia = {"texto": enviada.texto if enviada else recebida.texto,
                        "provider_id": citada_id} if enviada or recebida else None
                ref_token = referencia_mensagem.set(referencia)
                token = envio_adiado.set(True)
                try:
                    _atender(db, account, config, programa, item.telefone, item.nome, texto, grupo[-1].chave)
                finally:
                    envio_adiado.reset(token)
                    referencia_mensagem.reset(ref_token)
                from app.whatsapp.memoria import atualizar
                c = db.query(ConversaOuvinte).filter_by(account_id=account.id, telefone=item.telefone).one()
                atualizar(db, c)
        return True


def processar_envio(db, envio_id):
    envio = db.get(EnvioWhatsapp, envio_id)
    if not envio or envio.estado not in ("pendente", "falha_conexao") or envio.tentativas >= 2:
        return False
    with bloquear_conversa(envio.account_id, envio.telefone, db):
        db.refresh(envio)
        if envio.estado not in ("pendente", "falha_conexao"):
            return False
        account = db.get(Account, envio.account_id)
        log = db.get(InteractionLog, envio.log_id)
        config = db.get(RadioConfig, log.radio_config_id)
        from app.whatsapp.atendimento import conversa, enviar_resposta_pendente
        c = conversa(db, account.id, envio.telefone)
        if not account.wuzapi_token:
            return False
        if envio.automatico:
            nova = db.query(InteractionLog.id).join(RadioConfig).filter(
                RadioConfig.account_id == account.id, InteractionLog.telefone == c.telefone,
                InteractionLog.origem == "ouvinte", InteractionLog.id > log.id,
            ).first()
            if nova:
                envio.estado, log.status, log.resposta_pendente = "superado", "resposta_superada", None
                registrar(db, account.id, "mensagem.atualizada", log_id=log.id)
                db.commit()
                return True
            encaminhamento = envio.chave.startswith("encaminhamento:")
            if not account.atendimento_ouvinte_ativo or not config.resposta_automatica_whatsapp or (c.humano and not encaminhamento):
                envio.estado, log.status = "pausado", "aguardando_humano"
                registrar(db, account.id, "mensagem.atualizada", log_id=log.id)
                db.commit()
                return True
            enviar_resposta_pendente(db, account, c, log)
        else:
            from app.whatsapp.sender import enviar_mensagem
            envio.estado, log.status = "incerto", "envio_incerto"
            envio.tentativas += 1
            db.commit()
            try:
                envio.provider_id = enviar_mensagem(envio.telefone, envio.texto, account.wuzapi_token)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                envio.estado, log.status = "falha_conexao", "falha_envio"
            except Exception:
                pass  # Persistido como incerto antes do POST; não reenviar sem conferência.
            else:
                envio.estado, log.status, log.resposta_pendente = "aceito_pelo_provedor", "enviada", None
                c.historico = [*c.historico, {"role": "assistant", "content": envio.texto}][-10:]
            registrar(db, account.id, "mensagem.atualizada", log_id=log.id, estado=envio.estado)
            db.commit()
        return True


def executar_rodada(factory=SessionLocal):
    with factory() as db:
        ids = [i for (i,) in db.query(EntradaWhatsapp.id).filter(
            EntradaWhatsapp.estado == "pendente", EntradaWhatsapp.disponivel_em <= agora(),
        ).order_by(EntradaWhatsapp.id).limit(100).all()]
    for item_id in ids:
        with factory() as db:
            try:
                processar_entrada(db, item_id)
            except Exception as exc:
                db.rollback()
                original = getattr(exc, "original", exc)
                if isinstance(original, OperationalError):
                    logger.warning("whatsapp_banco_indisponivel id=%s", item_id)
                    continue
                item = db.get(EntradaWhatsapp, getattr(exc, "entrada_id", item_id))
                if item and item.estado == "pendente":
                    if isinstance(original, RedisError) or (isinstance(original, HTTPException) and original.status_code in (429, 503)):
                        # Infraestrutura/capacidade indisponível não transforma uma
                        # mensagem válida em falha definitiva nem gasta suas tentativas.
                        item.disponivel_em = agora() + datetime.timedelta(seconds=15)
                        db.commit()
                        continue
                    item.tentativas += 1
                    item.erro = type(getattr(exc, "original", exc)).__name__
                    item.disponivel_em = agora() + datetime.timedelta(seconds=min(300, 2 ** item.tentativas))
                    if item.tentativas >= settings.whatsapp_tentativas_max:
                        item.estado = "falhou"
                        registrar(db, item.account_id, "mensagem.atualizada", telefone=item.telefone, estado="falhou")
                    db.commit()
                logger.warning("whatsapp_job_falhou id=%s erro=%s", item_id, type(exc).__name__)
    with factory() as db:
        ids = [i for (i,) in db.query(EnvioWhatsapp.id).filter(
            EnvioWhatsapp.estado.in_(("pendente", "falha_conexao")), EnvioWhatsapp.tentativas < 2,
        ).order_by(EnvioWhatsapp.id).limit(100).all()]
    for envio_id in ids:
        with factory() as db:
            try:
                processar_envio(db, envio_id)
            except Exception as exc:
                db.rollback()
                logger.warning("whatsapp_envio_falhou id=%s erro=%s", envio_id, type(exc).__name__)
    with factory() as db:
        db.query(EntradaWhatsapp).filter(EntradaWhatsapp.criado_em < agora() - datetime.timedelta(
            hours=settings.whatsapp_midia_retencao_horas)).update({"payload": {}}, synchronize_session=False)
        db.commit()


if __name__ == "__main__":
    configurar_logging()
    while True:
        try:
            executar_rodada()
        except Exception as exc:
            logger.warning("whatsapp_worker_indisponivel erro=%s", type(exc).__name__)
        time.sleep(1)
