"""Pre-geracao da primeira fala de cada programa, uns segundos antes do horario_inicio --
sem isso, o inicio pontual depende inteiramente do painel do navegador estar aberto com
antecedencia pra disparar o prefetch client-side (ver FilaPreparo em useLiveEngine.ts); se
ninguem abriu o painel a tempo, o LLM+TTS da primeira fala so' comeca quando o horario chega,
e o programa comeca atrasado. Roda in-process (mesmo BackgroundScheduler de
app.news.worker::iniciar_scheduler_noticias em app.main), sujeito ao mesmo sleep por
inatividade do free tier do Render -- so' resolve pontualidade enquanto o processo esta' de pe.

Chama gerar_proxima_fala/gerar_audio_fala direto (mesmas funcoes do endpoint HTTP, so' sem
passar pela camada ASGI) pra reusar a logica de verdade (patrocinador, vinheta, dialogo
multi-voz, sintese embutida) em vez de duplicar-la aqui.
"""

import base64
import datetime
import json
import logging
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config.redis_client import redis_client
from app.db.database import SessionLocal
from app.guardrails.schedule import segundos_ate_inicio_hoje
from app.live.router import (
    LiveProgramRequest,
    LiveTtsRequest,
    gerar_audio_fala,
    gerar_proxima_fala,
)
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

logger = logging.getLogger("radialista.live.prewarm")

# Mesma antecedencia usada pelo prefetch client-side (ANTECEDENCIA_PREPARO_SEGUNDOS em
# useLiveEngine.ts) -- preparar antes disso so' adianta o custo de TTS sem ganho, preparar
# depois nao deixa margem contra a latencia de LLM+TTS.
_JANELA_PREWARM_SEGUNDOS = 90
_TTL_CACHE_SEGUNDOS = 5 * 60
_TTL_DEDUPE_SEGUNDOS = 6 * 60 * 60


def _chave_cache(programa_id: int) -> str:
    return f"preparo_antecipado:{programa_id}"


def _chave_dedupe(programa_id: int, data_iso: str) -> str:
    return f"preparo_antecipado_feito:{programa_id}:{data_iso}"


def consumir_preparo_antecipado(programa_id: int) -> dict | None:
    """Le e apaga o preparo antecipado (uso unico -- ver GET .../preparo em live/router.py)."""
    bruto = redis_client.get(_chave_cache(programa_id))
    if not bruto:
        return None
    redis_client.delete(_chave_cache(programa_id))
    try:
        return json.loads(bruto)
    except (TypeError, ValueError):
        return None


def _sintetizar_audio_b64(
    radialista_id: int, account: Account, db: Session, texto: str, tipo: str, voz_id: str | None,
    texto_anterior: str | None, programa_id: int,
) -> str | None:
    dados = LiveTtsRequest(
        texto=texto,
        tipo=tipo,
        voz_id=voz_id,
        perfil_pos_producao="radio_fm",
        texto_anterior=texto_anterior,
        programa_id=programa_id,
    )
    try:
        resposta = gerar_audio_fala(radialista_id, dados, account=account, db=db)
    except Exception:
        logger.warning("prewarm: falha ao sintetizar audio de uma linha do dialogo, programa_id=%s", programa_id, exc_info=True)
        return None
    corpo = getattr(resposta, "body", None)
    return base64.b64encode(corpo).decode("ascii") if corpo else None


def preparar_programa(db: Session, account: Account, radialista: RadioConfig, programa: Programa) -> None:
    dados = LiveProgramRequest(incluir_audio=True, historico=[], total_falas=0, perfil_pos_producao="radio_fm")
    try:
        resposta = gerar_proxima_fala(radialista.id, programa.id, dados, account=account, db=db)
    except Exception:
        logger.warning("prewarm: falha ao gerar a primeira fala antecipada, programa_id=%s", programa.id, exc_info=True)
        return

    payload = json.loads(resposta.model_dump_json())

    # Dialogo multi-voz nao tem sintese embutida em gerar_proxima_fala (precisa de uma voz por
    # linha) -- o frontend normalmente busca cada audio via /tts depois; aqui adianta esse
    # mesmo trabalho pra' o preparo antecipado sair completo.
    if resposta.falas:
        audios = []
        anterior = None
        for linha in resposta.falas:
            audios.append(
                _sintetizar_audio_b64(radialista.id, account, db, linha.texto, resposta.tipo, linha.voz_id, anterior, programa.id)
            )
            anterior = linha.texto
        payload["audios_falas_base64"] = audios

    redis_client.set(_chave_cache(programa.id), json.dumps(payload), ex=_TTL_CACHE_SEGUNDOS)
    logger.info("prewarm: preparo antecipado pronto para programa_id=%s tipo=%s", programa.id, resposta.tipo)


def executar_tick() -> None:
    """Ponto de entrada de uma rodada: acha programas a 0-90s do horario_inicio de hoje, ainda
    sem preparo feito, e prepara a primeira fala de cada um. Pensado pra rodar com intervalo
    curto (ver app.main, 20s) -- a janela de 90s e' estreita demais pra' um cron de minuto."""
    db = SessionLocal()
    try:
        for radialista in db.query(RadioConfig).all():
            account = db.get(Account, radialista.account_id)
            if account is None:
                continue

            programas = db.query(Programa).filter_by(radio_config_id=radialista.id, ativo=True).all()
            for programa in programas:
                segundos = segundos_ate_inicio_hoje(programa, radialista.timezone)
                if segundos is None or not (0 <= segundos <= _JANELA_PREWARM_SEGUNDOS):
                    continue

                hoje_iso = datetime.datetime.now(ZoneInfo(radialista.timezone)).date().isoformat()
                chave_feito = _chave_dedupe(programa.id, hoje_iso)
                if not redis_client.set(chave_feito, "1", nx=True, ex=_TTL_DEDUPE_SEGUNDOS):
                    continue  # ja preparado (ou tentado) pra essa ocorrencia de hoje

                try:
                    preparar_programa(db, account, radialista, programa)
                except Exception:
                    logger.warning("prewarm: falha inesperada no tick, programa_id=%s", programa.id, exc_info=True)
    finally:
        db.close()
