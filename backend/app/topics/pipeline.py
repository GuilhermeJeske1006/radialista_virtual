"""Orquestra o pipeline do banco de assuntos pra uma conta -- derivacao (Fase B) + casamento
(Fase C) + reserva (Fase D), nessa ordem. Chamado pelo worker de noticias (ver app.news.worker),
logo apos a coleta -- roda fora do ciclo de fala, nunca no caminho sincrono do ao vivo (ver
app.topics.pauta_conversa, que so' LE o que este pipeline ja' escreveu).

Limites por rodada (_MAX_*) existem pra' um backlog acumulado (primeira vez que o pipeline roda
numa conta com meses de Noticia/MusicaHistorico) nao virar uma rajada de centenas de chamadas de
LLM numa unica rodada de 10 minutos -- o proprio scheduler (a cada _INTERVALO_COLETA_NOTICIAS_
MINUTOS, ver app.main) drena o resto nas rodadas seguintes.
"""

import datetime
import logging

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.musica import Musica
from app.models.musica_historico import MusicaHistorico
from app.models.noticia import Noticia
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics import matcher, reserva
from app.topics.fontes.de_efemeride import derivar_de_efemeride
from app.topics.fontes.de_musica import derivar_de_musica
from app.topics.fontes.de_noticia import derivar_de_noticia
from app.topics.fontes.de_ouvinte import derivar_de_ouvinte

logger = logging.getLogger("radialista.topics.pipeline")

_MAX_NOTICIAS_POR_RODADA = 20
_MAX_MUSICAS_POR_RODADA = 20
_JANELA_NOTICIAS_HORAS = 48
_JANELA_MUSICAS_HORAS = 24


def _derivar_de_noticias(db: Session, account: Account) -> None:
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_JANELA_NOTICIAS_HORAS)
    noticias = (
        db.query(Noticia)
        .filter(Noticia.account_id == account.id, Noticia.ativa.is_(True), Noticia.coletado_em >= limiar)
        .order_by(Noticia.coletado_em.desc())
        .limit(_MAX_NOTICIAS_POR_RODADA)
        .all()
    )
    for noticia in noticias:
        try:
            derivar_de_noticia(db, noticia, account)
        except Exception:
            logger.warning("Falha ao derivar assunto de noticia: noticia_id=%s", noticia.id, exc_info=True)
            db.rollback()


def _derivar_de_musicas(db: Session, account: Account, radios: list[RadioConfig]) -> None:
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_JANELA_MUSICAS_HORAS)
    radio_ids = [r.id for r in radios]
    if not radio_ids:
        return
    programa_ids = [p.id for p in db.query(Programa.id).filter(Programa.radio_config_id.in_(radio_ids)).all()]
    if not programa_ids:
        return
    historicos = (
        db.query(MusicaHistorico)
        .filter(
            MusicaHistorico.programa_id.in_(programa_ids),
            MusicaHistorico.song_id.isnot(None),
            MusicaHistorico.criado_em >= limiar,
        )
        .order_by(MusicaHistorico.criado_em.desc())
        .limit(_MAX_MUSICAS_POR_RODADA)
        .all()
    )
    musicas_ja_vistas: set[int] = set()
    for historico in historicos:
        try:
            assunto_musica = derivar_de_musica(db, historico, account.id)
            if assunto_musica is not None and historico.song_id not in musicas_ja_vistas:
                musicas_ja_vistas.add(historico.song_id)
                musica = db.get(Musica, historico.song_id)
                programa_da_musica = db.get(Programa, historico.programa_id)
                if musica is not None:
                    derivar_de_efemeride(
                        db, musica, account.id,
                        generos_extra=programa_da_musica.generos_musicais if programa_da_musica else None,
                    )
        except Exception:
            logger.warning("Falha ao derivar assunto de musica: historico_id=%s", historico.id, exc_info=True)
            db.rollback()


def _derivar_de_ouvintes(db: Session, account: Account, radios: list[RadioConfig]) -> None:
    for radio in radios:
        try:
            derivar_de_ouvinte(db, radio.id, account.id)
        except Exception:
            logger.warning("Falha ao derivar assunto de ouvinte: radio_config_id=%s", radio.id, exc_info=True)
            db.rollback()


def _gerar_reservas(db: Session, radios: list[RadioConfig], account: Account) -> None:
    radio_ids = [r.id for r in radios]
    if not radio_ids:
        return
    programas = db.query(Programa).filter(Programa.radio_config_id.in_(radio_ids), Programa.ativo.is_(True)).all()
    for programa in programas:
        try:
            reserva.gerar_reserva_semanal(db, programa, account)
        except Exception:
            logger.warning("Falha ao gerar reserva estrategica: programa_id=%s", programa.id, exc_info=True)
            db.rollback()


def executar_para_conta(db: Session, account: Account) -> None:
    radios = db.query(RadioConfig).filter_by(account_id=account.id).all()

    _derivar_de_noticias(db, account)
    _derivar_de_musicas(db, account, radios)
    _derivar_de_ouvintes(db, account, radios)

    try:
        matcher.casar_conta(db, account)
    except Exception:
        logger.warning("Falha ao casar assuntos da conta: account_id=%s", account.id, exc_info=True)
        db.rollback()

    _gerar_reservas(db, radios, account)
