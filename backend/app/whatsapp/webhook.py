import datetime
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.guardrails.content_filter import contem_topico_proibido
from app.guardrails.http_rate_limit import limitar_por_ip
from app.guardrails.rate_limiter import dentro_do_limite
from app.guardrails.schedule import encontrar_programa_atual
from app.llm.intent import classificar_intencao
from app.models.account import Account
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.billing.limites import limite_mensagens_efetivo, mensagens_respondidas_no_mes
from app.stt.client import stt_habilitado, transcrever_audio

logger = logging.getLogger("radialista.webhook")
router = APIRouter()


def _verificar_assinatura(account: Account, raw_body: bytes, assinatura: str | None) -> bool:
    """Confere o header x-hmac-signature (HMAC-SHA256 do corpo cru) que o WuzAPI manda
    quando a conta tem chave HMAC configurada (app/whatsapp/session_manager.py::configurar_hmac,
    chamado no onboarding). Sem isso, o "userID" no corpo -- id sequencial do WuzAPI, nao
    secreto -- seria a unica coisa "autenticando" o webhook, e daria pra forjar mensagem em
    nome de qualquer conta so' adivinhando um id pequeno.

    Contas criadas antes desse fix (ou que falharam ao configurar HMAC no onboarding, ver
    onboarding/router.py) ainda nao tem wuzapi_hmac_key -- pra elas, mantem o comportamento
    antigo (sem verificacao) pra nao quebrar producao existente.
    """
    if not account.wuzapi_hmac_key:
        return True
    esperado = hmac.new(account.wuzapi_hmac_key.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, assinatura or "")


def _registrar_log(
    db: Session,
    config: RadioConfig,
    telefone: str,
    nome: str | None,
    mensagem: str,
    status: str,
    origem: str = "ouvinte",
    wuzapi_message_id: str | None = None,
) -> None:
    db.add(
        InteractionLog(
            radio_config_id=config.id,
            wuzapi_message_id=wuzapi_message_id,
            telefone=telefone,
            nome=nome or None,
            mensagem_usuario=mensagem,
            resposta=None,
            status=status,
            origem=origem,
        )
    )
    db.commit()


def _radialista_no_ar(db: Session, account_id: int) -> tuple[RadioConfig | None, Programa | None]:
    """Acha, entre todos os radialistas ativos da conta (todos no mesmo numero de
    WhatsApp), qual esta na escala agora. Se nenhum estiver, devolve o primeiro
    radialista ativo so pra ter onde registrar o log de bloqueio por horario.
    """
    configs = db.query(RadioConfig).filter_by(account_id=account_id, ativo=True).order_by(RadioConfig.id.asc()).all()
    for config in configs:
        programas = db.query(Programa).filter_by(radio_config_id=config.id, ativo=True).all()
        programa_atual = encontrar_programa_atual(programas, config.timezone)
        if programa_atual is not None:
            return config, programa_atual
    return (configs[0], None) if configs else (None, None)


def _extrair_mensagem(
    payload: dict,
) -> tuple[str, str, str | None, str | None, str | None, str | None, bool, str | None] | None:
    """Extrai (telefone, nome, texto, audio_base64, wuzapi_token, wuzapi_user_id, from_me,
    message_id) do payload do WuzAPI.

    O corpo do webhook manda "userID" (id interno do usuario no WuzAPI), nao o
    "token" -- esse so aparece em chamadas manuais/teste. Aceita qualquer um
    dos dois pra identificar a radio; pelo menos um precisa estar presente.

    "Chat" e' o telefone do ouvinte tanto quando ele manda mensagem quanto quando
    a radio responde (FromMe=True) -- "Sender" so' bate com o ouvinte no primeiro
    caso; em FromMe ele vira a identidade (LID) de quem enviou pela radio.

    Mensagem de audio (audioMessage) nao traz texto -- o WuzAPI (com media_delivery
    configurado pra "base64", ver app/whatsapp/session_manager.py::configurar_entrega_midia)
    ja manda o audio decriptado em base64 no corpo do webhook. Quando so' isso vier,
    "texto" fica None e quem chama decide se transcreve (ver receber_webhook).
    """
    wuzapi_token = payload.get("token")
    wuzapi_user_id = payload.get("userID")
    if not wuzapi_token and not wuzapi_user_id:
        return None

    evento = payload.get("event", payload)

    info = evento.get("Info") or evento.get("info") or {}
    from_me = bool(info.get("FromMe") or info.get("IsFromMe"))
    message_id = info.get("ID") or info.get("Id") or info.get("id") or payload.get("id")

    telefone = (
        info.get("Chat") or info.get("chat") or info.get("Sender") or info.get("sender") or payload.get("phone")
    )
    nome = info.get("PushName") or info.get("Pushname") or info.get("pushName") or payload.get("pushname") or ""

    mensagem = evento.get("Message") or evento.get("message") or {}
    texto = (
        mensagem.get("conversation")
        or mensagem.get("Conversation")
        or mensagem.get("extendedTextMessage", {}).get("text")
        or payload.get("body")
        or payload.get("text")
    )

    audio_base64 = None
    if mensagem.get("audioMessage") or mensagem.get("AudioMessage"):
        audio_base64 = payload.get("base64")

    if not telefone or (not texto and not audio_base64):
        return None

    telefone = str(telefone).split("@")[0]
    return (
        telefone,
        str(nome),
        str(texto) if texto else None,
        audio_base64,
        str(wuzapi_token) if wuzapi_token else None,
        str(wuzapi_user_id) if wuzapi_user_id else None,
        from_me,
        str(message_id) if message_id else None,
    )


@router.post(
    "/webhook/whatsapp",
    dependencies=[Depends(limitar_por_ip("whatsapp_webhook", limite=60, janela_segundos=60))],
)
async def receber_webhook(request: Request, db: Session = Depends(get_db)):
    """Ouve mensagens do WhatsApp, dos dois lados da conversa. O bot nunca
    responde direto no chat -- mensagens FromMe sao as que a radio manda (via
    /live/programa/proxima ou digitadas a mao no numero conectado), so' ficam
    registradas, sem passar pelos guardrails/fila (esses valem so' pro ouvinte).

    Mensagem do ouvinte so pode gerar um de tres destinos: entra na fila pra
    virar um "alo" ao vivo (abraco), entra na fila pra virar um pedido de
    musica ao vivo (musica), ou fica so registrada (guardar). Audio (nota de
    voz) e' transcrito (ver app.stt.client) e daí em diante segue o mesmo
    caminho de uma mensagem de texto.
    """
    raw_body = await request.body()
    payload = json.loads(raw_body)
    logger.info("Webhook recebido: %s", payload)

    extraido = _extrair_mensagem(payload)
    if extraido is None:
        return {"status": "ignorado"}

    telefone, nome, texto_usuario, audio_base64, wuzapi_token, wuzapi_user_id, from_me, wuzapi_message_id = extraido

    if wuzapi_message_id is not None:
        ja_processada = (
            db.query(InteractionLog).filter_by(wuzapi_message_id=wuzapi_message_id).first()
        )
        if ja_processada is not None:
            logger.info("Mensagem %s ja processada, ignorando reentrega", wuzapi_message_id)
            return {"status": "ignorado", "motivo": "duplicada"}

    account = None
    if wuzapi_user_id:
        account = db.query(Account).filter_by(wuzapi_user_id=wuzapi_user_id).first()
    if account is None and wuzapi_token:
        account = db.query(Account).filter_by(wuzapi_token=wuzapi_token).first()
    if account is None:
        logger.warning("Nenhuma Account para o userID/token recebido")
        return {"status": "ignorado"}

    if not _verificar_assinatura(account, raw_body, request.headers.get("x-hmac-signature")):
        logger.warning("Assinatura HMAC invalida no webhook da conta %s", account.id)
        return {"status": "ignorado", "motivo": "assinatura_invalida"}

    # Numero de WhatsApp e' unico por conta, mas varios radialistas (agentes) podem
    # compartilha-lo, cada um no ar num horario diferente -- acha quem esta na escala agora.
    config, programa_atual = _radialista_no_ar(db, account.id)
    if config is None:
        logger.warning("Nenhum radialista ativo para a conta %s", account.id)
        return {"status": "ignorado"}

    if from_me:
        _registrar_log(
            db,
            config,
            telefone,
            None,
            texto_usuario or "[audio]",
            "enviada",
            origem="radio",
            wuzapi_message_id=wuzapi_message_id,
        )
        return {"status": "ok", "origem": "radio"}

    if texto_usuario is None and audio_base64:
        if not stt_habilitado():
            _registrar_log(
                db, config, telefone, nome, "[audio]", "bloqueado_audio_sem_stt", wuzapi_message_id=wuzapi_message_id
            )
            return {"status": "ignorado", "motivo": "audio_sem_stt"}
        try:
            texto_usuario = transcrever_audio(audio_base64)
        except Exception:
            logger.exception("Falha ao transcrever audio do WhatsApp")
            texto_usuario = None
        if not texto_usuario:
            _registrar_log(
                db, config, telefone, nome, "[audio]", "falha_transcricao", wuzapi_message_id=wuzapi_message_id
            )
            return {"status": "ignorado", "motivo": "falha_transcricao"}

    limite_mensagens = limite_mensagens_efetivo(db, account)
    if mensagens_respondidas_no_mes(db, account.id) >= limite_mensagens:
        _registrar_log(db, config, telefone, nome, texto_usuario, "bloqueado_plano", wuzapi_message_id=wuzapi_message_id)
        return {"status": "bloqueado", "motivo": "limite_plano"}

    if programa_atual is None:
        _registrar_log(db, config, telefone, nome, texto_usuario, "bloqueado_horario", wuzapi_message_id=wuzapi_message_id)
        return {"status": "bloqueado", "motivo": "horario"}

    if not dentro_do_limite(wuzapi_token, telefone, programa_atual.limite_mensagens_hora):
        _registrar_log(
            db, config, telefone, nome, texto_usuario, "bloqueado_rate_limit", wuzapi_message_id=wuzapi_message_id
        )
        return {"status": "bloqueado", "motivo": "rate_limit"}

    if contem_topico_proibido(texto_usuario, programa_atual):
        _registrar_log(
            db, config, telefone, nome, texto_usuario, "bloqueado_conteudo", wuzapi_message_id=wuzapi_message_id
        )
        return {"status": "bloqueado", "motivo": "conteudo"}

    acao, musica_query = classificar_intencao(config, texto_usuario)

    if acao in ("abraco", "musica"):
        db.add(
            FilaAoVivo(
                radio_config_id=config.id,
                telefone=telefone,
                nome=nome,
                tipo=acao,
                mensagem_usuario=texto_usuario,
                musica_query=musica_query,
            )
        )
        _registrar_log(
            db,
            config,
            telefone,
            nome,
            texto_usuario,
            "fila_musica" if acao == "musica" else "fila_abraco",
            wuzapi_message_id=wuzapi_message_id,
        )
        return {"status": "ok", "acao": acao}

    _registrar_log(db, config, telefone, nome, texto_usuario, "guardado", wuzapi_message_id=wuzapi_message_id)
    return {"status": "ok", "acao": "guardar"}
