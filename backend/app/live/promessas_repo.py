"""Promessas no banco (F4): registro, leitura e resolução de `promessas_no_ar`.

Sem Redis (D3). Uma leitura indexada por /proxima (programa, ocorrência, estado); sem promessa no texto, nenhuma
escrita. A resolução trava as linhas (`with_for_update`): duas abas do painel não resolvem a mesma promessa
duas vezes. Logs só com ids: o trecho pode ter nome de ouvinte (auditoria 10).
"""

import datetime
import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.live.promessas import EventoAgendado, PromessaDetectada, PromessaRef
from app.live.relogio import ocorrencia_em
from app.models.promessa_no_ar import PromessaNoAr

logger = logging.getLogger("radialista.live")

PREFIXO_ETAPA = "etapa:"


def _agora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _evento(linha: PromessaNoAr, acao: str, motivo: str = "") -> None:
    linha.eventos = [*(linha.eventos or []), {"acao": acao, "estado": linha.estado, "motivo": motivo,
                                              "em": _agora().isoformat()}]


def ocorrencia_chave(programa, timezone: str, instante: datetime.datetime) -> str:
    """Chave da ocorrência do programa que contém `instante` (com ou sem relógio); fora da grade, o dia local."""
    from zoneinfo import ZoneInfo

    ocorrencia = ocorrencia_em(programa, timezone, instante)
    if ocorrencia is not None:
        return ocorrencia.chave
    return f"manual:{instante.astimezone(ZoneInfo(timezone)).date().isoformat()}"


def registrar(db: Session, *, programa, ocorrencia: str, request_id: str,
              itens: Iterable[tuple[PromessaDetectada, EventoAgendado]], commit: bool = True) -> list[PromessaNoAr]:
    """Promessas novas, já casadas com o evento da agenda. Idempotente por (request_id, trecho)."""
    novas: list[PromessaNoAr] = []
    for promessa, evento in itens:
        repetida = db.query(PromessaNoAr.id).filter(
            PromessaNoAr.programa_id == programa.id, PromessaNoAr.request_id == request_id,
            PromessaNoAr.trecho == promessa.frase,
        ).first()
        if repetida is not None:
            continue
        linha = PromessaNoAr(
            programa_id=programa.id, radio_config_id=programa.radio_config_id, ocorrencia=ocorrencia,
            request_id=request_id, tipo=promessa.tipo, classe=promessa.classe, marcador=promessa.marcador,
            trecho=promessa.frase, evento_alvo=evento.chave, evento_tipo=evento.tipo, evento_rotulo=evento.rotulo,
            prazo=evento.inicio, prazo_posicao=evento.posicao, estado="aberta", eventos=[],
        )
        _evento(linha, "registrar")
        db.add(linha)
        novas.append(linha)
    if novas:
        db.flush()
        for linha in novas:
            logger.info("promessa_registrada promessa_id=%s programa_id=%s evento_alvo=%s classe=%s", linha.id,
                        programa.id, linha.evento_alvo, linha.classe)
        if commit:
            db.commit()
    return novas


def abertas(db: Session, programa_id: int, ocorrencia: str) -> list[PromessaNoAr]:
    return (
        db.query(PromessaNoAr)
        .filter(PromessaNoAr.programa_id == programa_id, PromessaNoAr.ocorrencia == ocorrencia,
                PromessaNoAr.estado == "aberta")
        .order_by(PromessaNoAr.id.asc())
        .all()
    )


def obrigacoes(db: Session, programa_id: int, ocorrencia: str) -> frozenset[str]:
    """Chaves das etapas do relógio que têm promessa aberta ("0:1620"): viram obrigação no backtiming."""
    return frozenset(linha.evento_alvo[len(PREFIXO_ETAPA):] for linha in abertas(db, programa_id, ocorrencia)
                     if linha.evento_alvo.startswith(PREFIXO_ETAPA))


def para_ref(linha: PromessaNoAr) -> PromessaRef:
    tipo = linha.evento_tipo if linha.evento_tipo in ("participacao", "quadro", "informacao") else linha.tipo
    prazo = linha.prazo
    if prazo is not None and prazo.tzinfo is None:
        prazo = prazo.replace(tzinfo=datetime.timezone.utc)
    return PromessaRef(id=linha.id, tipo=tipo, trecho=linha.trecho, evento_alvo=linha.evento_alvo,
                       rotulo=linha.evento_rotulo, prazo=prazo, prazo_posicao=linha.prazo_posicao)


def resolver(db: Session, ids: Iterable[int], estado: str, motivo: str, contingencia: str = "",
             commit: bool = True) -> list[PromessaNoAr]:
    """Leva as promessas ainda abertas de `ids` a `estado` (cumprida, cancelada, vencida), com trava de linha."""
    ids = list(ids)
    if not ids:
        return []
    linhas = (
        db.query(PromessaNoAr)
        .filter(PromessaNoAr.id.in_(ids), PromessaNoAr.estado == "aberta")
        .order_by(PromessaNoAr.id.asc())
        .with_for_update()
        .all()
    )
    for linha in linhas:
        linha.estado, linha.motivo, linha.resolvida_em = estado, motivo, _agora()
        if contingencia:
            linha.contingencia = contingencia
        _evento(linha, estado, motivo)
        logger.info("promessa_resolvida promessa_id=%s programa_id=%s estado=%s motivo=%s", linha.id,
                    linha.programa_id, estado, motivo)
    if linhas and commit:
        db.commit()
    return linhas


def vencer(db: Session, programa_id: int, *, exceto_ocorrencia: str | None = None, ocorrencia: str | None = None,
           motivo: str = "transmissao_encerrada", commit: bool = True) -> list[PromessaNoAr]:
    """Marca vencidas as abertas de outra ocorrência (`exceto_ocorrencia`) ou as que sobraram de `ocorrencia`
    depois do encerramento. É o único caminho para "vencida"."""
    consulta = db.query(PromessaNoAr.id).filter(PromessaNoAr.programa_id == programa_id,
                                                PromessaNoAr.estado == "aberta")
    if exceto_ocorrencia is not None:
        consulta = consulta.filter(PromessaNoAr.ocorrencia != exceto_ocorrencia)
    if ocorrencia is not None:
        consulta = consulta.filter(PromessaNoAr.ocorrencia == ocorrencia)
    ids = [linha.id for linha in consulta.all()]
    return resolver(db, ids, "vencida", motivo, commit=commit)
