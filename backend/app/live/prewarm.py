"""Pre-geracao da primeira fala de cada programa, uns segundos antes do horario_inicio --
sem isso, o inicio pontual depende inteiramente do painel do navegador estar aberto com
antecedencia pra disparar o prefetch client-side (ver FilaPreparo em useLiveEngine.ts); se
ninguem abriu o painel a tempo, o LLM+TTS da primeira fala so' comeca quando o horario chega,
e o programa comeca atrasado. Roda in-process (mesmo BackgroundScheduler de
app.news.worker::iniciar_scheduler_noticias em app.main), sujeito ao mesmo sleep por
inatividade do free tier do Render -- so' resolve pontualidade enquanto o processo esta' de pe.

Chama gerar_proxima_fala direto (mesma funcao do endpoint HTTP, so' sem passar pela camada
ASGI) pra reusar a logica de verdade (patrocinador, vinheta, dialogo multi-voz, sintese
embutida -- inclusive por linha, ver audios_falas_base64) em vez de duplica-la aqui.
"""

import datetime
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config.redis_client import redis_client
from app.db.database import SessionLocal
from app.guardrails.schedule import segundos_ate_inicio_hoje
from app.live.router import LiveProgramRequest, gerar_proxima_fala
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.config.settings import settings
from app.guardrails.provedores import contexto_capacidade
from redis.exceptions import RedisError, WatchError

logger = logging.getLogger("radialista.live.prewarm")

# Mesma antecedencia usada pelo prefetch client-side (ANTECEDENCIA_PREPARO_SEGUNDOS em
# useLiveEngine.ts) -- preparar antes disso so' adianta o custo de TTS sem ganho, preparar
# depois nao deixa margem contra a latencia de LLM+TTS.
_JANELA_PREWARM_SEGUNDOS = 90
_TTL_CACHE_SEGUNDOS = 5 * 60
_TTL_DEDUPE_SEGUNDOS = 6 * 60 * 60
_pool = None
_vagas = None
_trava_pool = Lock()


def _executar_em_background(tarefa):
    """Pool e backlog limitados: o tick de 20s não fica preso às gerações."""
    global _pool, _vagas
    with _trava_pool:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=max(1, settings.live_prewarm_workers), thread_name_prefix="prewarm")
            _vagas = BoundedSemaphore(max(1, settings.live_prewarm_pendentes))
    if not _vagas.acquire(blocking=False):
        return False
    try:
        futuro = _pool.submit(tarefa)
    except BaseException:
        _vagas.release()
        raise
    futuro.add_done_callback(lambda _: _vagas.release())
    return True


def _remover_se_dono(chave, dono, pronto=False):
    for _ in range(8):
        try:
            with redis_client.pipeline() as pipe:
                pipe.watch(chave)
                if pipe.get(chave) != dono:
                    return
                pipe.multi()
                if pronto:
                    pipe.set(chave, "pronto", ex=_TTL_DEDUPE_SEGUNDOS)
                else:
                    pipe.delete(chave)
                pipe.execute()
                return
        except WatchError:
            continue


def _chave_cache(programa_id: int) -> str:
    return f"preparo_antecipado:{programa_id}"


def _chave_dedupe(programa_id: int, data_iso: str) -> str:
    return f"preparo_antecipado_feito:{programa_id}:{data_iso}"


def consumir_preparo_antecipado(programa_id: int) -> dict | None:
    """Le e apaga o preparo antecipado (uso unico -- ver GET .../preparo em live/router.py)."""
    # GETDEL: duas abas/servidores não consomem a mesma abertura ao mesmo tempo.
    bruto = redis_client.getdel(_chave_cache(programa_id))
    try:
        return json.loads(bruto)
    except (TypeError, ValueError):
        return None


from app.billing.contexto_ia import por_conta  # noqa: E402


@por_conta("programa_ao_vivo")
def preparar_programa(db: Session, account: Account, radialista: RadioConfig, programa: Programa) -> bool:
    # Horario em que a primeira fala vai ao ar: o relogio da hora (F1) decide por ele, nao por now().
    fuso = ZoneInfo(radialista.timezone)
    inicio_previsto = datetime.datetime.combine(datetime.datetime.now(fuso).date(), programa.horario_inicio, tzinfo=fuso)
    dados = LiveProgramRequest(incluir_audio=True, historico=[], total_falas=0, perfil_pos_producao="radio_fm",
                               inicio_previsto=inicio_previsto.isoformat())
    try:
        resposta = gerar_proxima_fala(radialista.id, programa.id, dados, account=account, db=db)
    except Exception:
        logger.warning("prewarm: falha ao gerar a primeira fala antecipada, programa_id=%s", programa.id, exc_info=True)
        raise

    # Dialogo multi-voz ja vem com audio por linha (ver audios_falas_base64 em
    # gerar_proxima_fala/_sintetizar_falas_multivoz) -- gerar_proxima_fala sintetiza tudo em
    # paralelo, sem precisar de um loop dedicado aqui como antes.
    payload = json.loads(resposta.model_dump_json())

    redis_client.set(_chave_cache(programa.id), json.dumps(payload), ex=_TTL_CACHE_SEGUNDOS)
    logger.info("prewarm: preparo antecipado pronto para programa_id=%s tipo=%s", programa.id, resposta.tipo)
    return True


def _preparar_pendente(radialista_id, programa_id, chave, dono):
    try:
        if redis_client.get(chave) != dono:
            return  # Lease expirado enquanto estava na fila local.
        # Nunca compartilhar a Session do tick entre threads.
        with SessionLocal() as db:
            radialista = db.get(RadioConfig, radialista_id)
            programa = db.get(Programa, programa_id)
            if radialista is None or programa is None:
                return
            segundos = segundos_ate_inicio_hoje(programa, radialista.timezone)
            if segundos is None or not (0 <= segundos <= _JANELA_PREWARM_SEGUNDOS):
                return
            account = db.get(Account, radialista.account_id)
            if account is None:
                return
            with contexto_capacidade(prioridade=0, timeout_s=min(65, max(1, segundos))):
                sucesso = preparar_programa(db, account, radialista, programa)
            if sucesso is not False:
                # Só deduplica por horas depois de terminar. Falha libera a próxima rodada.
                _remover_se_dono(chave, dono, pronto=True)
    except Exception:
        logger.warning("prewarm: falha no preparo programa_id=%s", programa_id, exc_info=True)
    finally:
        try:
            _remover_se_dono(chave, dono)
        except RedisError:
            logger.warning("prewarm: falha ao liberar lease programa_id=%s", programa_id)


def executar_tick() -> None:
    """Ponto de entrada de uma rodada: acha programas a 0-90s do horario_inicio de hoje, ainda
    sem preparo feito, e prepara a primeira fala de cada um. Pensado pra rodar com intervalo
    curto (ver app.main, 20s) -- a janela de 90s e' estreita demais pra' um cron de minuto."""
    db = SessionLocal()
    try:
        candidatos = []
        for radialista in db.query(RadioConfig).all():
            account = db.get(Account, radialista.account_id)
            if account is None:
                continue

            programas = db.query(Programa).filter_by(radio_config_id=radialista.id, ativo=True).all()
            for programa in programas:
                segundos = segundos_ate_inicio_hoje(programa, radialista.timezone)
                if segundos is None or not (0 <= segundos <= _JANELA_PREWARM_SEGUNDOS):
                    continue

                candidatos.append((segundos, radialista.id, programa.id, radialista.timezone))
        # Mais próximo de ir ao ar primeiro. O pool limitado e a fila global distribuem
        # os picos sem atrasar o horário de reprodução nem dormir no scheduler.
        for _, radialista_id, programa_id, timezone in sorted(candidatos):
            hoje_iso = datetime.datetime.now(ZoneInfo(timezone)).date().isoformat()
            chave_feito = _chave_dedupe(programa_id, hoje_iso)
            dono = uuid4().hex
            if not redis_client.set(chave_feito, dono, nx=True, ex=150):
                continue
            if not _executar_em_background(lambda r=radialista_id, p=programa_id, c=chave_feito, d=dono:
                                           _preparar_pendente(r, p, c, d)):
                _remover_se_dono(chave_feito, dono)
                break
    finally:
        db.close()
