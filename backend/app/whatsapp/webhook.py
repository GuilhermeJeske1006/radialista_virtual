import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.guardrails.content_filter import contem_topico_proibido
from app.guardrails.rate_limiter import dentro_do_limite
from app.guardrails.schedule import encontrar_programa_atual
from app.llm.intent import classificar_intencao
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

logger = logging.getLogger("radialista.webhook")
router = APIRouter()


def _registrar_log(db: Session, config: RadioConfig, telefone: str, mensagem: str, status: str) -> None:
    db.add(
        InteractionLog(
            radio_config_id=config.id,
            telefone=telefone,
            mensagem_usuario=mensagem,
            resposta=None,
            status=status,
        )
    )
    db.commit()


def _extrair_mensagem(payload: dict) -> tuple[str, str, str, str] | None:
    """Extrai (telefone, nome, texto, wuzapi_token) do payload do WuzAPI.

    Formato confirmado (API.md do projeto): {"type": "Message", "token": "...",
    "event": {"Info": {...}, "Message": {"Conversation": "..."}}}.
    Mantem fallbacks defensivos para variacoes de casing/formato.
    """
    wuzapi_token = payload.get("token")
    if not wuzapi_token:
        return None

    evento = payload.get("event", payload)

    info = evento.get("Info") or evento.get("info") or {}
    if info.get("FromMe"):
        return None

    telefone = info.get("Sender") or info.get("sender") or info.get("Chat") or payload.get("phone")
    nome = info.get("PushName") or info.get("Pushname") or info.get("pushName") or payload.get("pushname") or ""

    mensagem = evento.get("Message") or evento.get("message") or {}
    texto = (
        mensagem.get("conversation")
        or mensagem.get("Conversation")
        or mensagem.get("extendedTextMessage", {}).get("text")
        or payload.get("body")
        or payload.get("text")
    )

    if not telefone or not texto:
        return None

    telefone = str(telefone).split("@")[0]
    return telefone, str(nome), str(texto), str(wuzapi_token)


@router.post("/webhook/whatsapp")
async def receber_webhook(request: Request, db: Session = Depends(get_db)):
    """Ouve mensagens do WhatsApp. O bot nunca responde direto no chat.

    Cada mensagem so pode gerar um de tres destinos: entra na fila pra virar um
    "alo" ao vivo (abraco), entra na fila pra virar um pedido de musica ao vivo
    (musica), ou fica so registrada (guardar). Quem fala com o ouvinte e o
    locutor, ao vivo, via /live/programa/proxima -- nunca o bot no WhatsApp.
    """
    payload = await request.json()
    logger.info("Webhook recebido: %s", payload)

    extraido = _extrair_mensagem(payload)
    if extraido is None:
        return {"status": "ignorado"}

    telefone, nome, texto_usuario, wuzapi_token = extraido

    config = db.query(RadioConfig).filter_by(wuzapi_token=wuzapi_token, ativo=True).first()
    if config is None:
        logger.warning("Nenhuma RadioConfig ativa para o token recebido")
        return {"status": "ignorado"}

    programas = db.query(Programa).filter_by(radio_config_id=config.id, ativo=True).all()
    programa_atual = encontrar_programa_atual(programas, config.timezone)
    if programa_atual is None:
        _registrar_log(db, config, telefone, texto_usuario, "bloqueado_horario")
        return {"status": "bloqueado", "motivo": "horario"}

    if not dentro_do_limite(wuzapi_token, telefone, programa_atual.limite_mensagens_hora):
        _registrar_log(db, config, telefone, texto_usuario, "bloqueado_rate_limit")
        return {"status": "bloqueado", "motivo": "rate_limit"}

    if contem_topico_proibido(texto_usuario, programa_atual):
        _registrar_log(db, config, telefone, texto_usuario, "bloqueado_conteudo")
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
        _registrar_log(db, config, telefone, texto_usuario, "fila_musica" if acao == "musica" else "fila_abraco")
        return {"status": "ok", "acao": acao}

    _registrar_log(db, config, telefone, texto_usuario, "guardado")
    return {"status": "ok", "acao": "guardar"}
