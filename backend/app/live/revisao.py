"""Fala em revisao humana (F12): o que o roteamento manda para aprovacao ou bloqueia nao vai ao ar como veio.

Quando `roteamento_revisao.rotear` devolve REVISAO ou PROIBIDO, o /proxima guarda o texto original aqui e entrega
uma fala substituta neutra (sem conteudo). O original nunca vai ao ar nesta etapa: aprovar so libera o texto para
conferencia; levar a fala aprovada ao ar depende de a fala ser reproduzida no ao vivo (fora desta etapa).

Prazo: a decisao vale ate `PRAZO_MINUTOS` depois da geracao. Passado o prazo, a fala expira e nao pode mais ser
aprovada, porque o bloco ja saiu do ar (a rotina do relogio segue). O estado `expirada` e gravado por
`expirar_vencidas`, chamado na listagem e na decisao.
"""

from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from app.live.roteamento_revisao import PROIBIDO, estado_inicial
from app.models.fala_em_revisao import FalaEmRevisao

PRAZO_MINUTOS = 20
AGUARDANDO = "aguardando_revisao"
APROVADA = "aprovada"
REJEITADA = "rejeitada"
EXPIRADA = "expirada"
BLOQUEADA = "bloqueado"  # rota PROIBIDO (mesmo valor de roteamento_revisao.ESTADO_BLOQUEADO): nao cabe decisao humana, so registro
ACOES = ("aprovar", "rejeitar")

# Falas substitutas: sem conteudo, a mesma ideia de reorientacao neutra da F4 (ver validacao_fala.fala_reserva_neutra).
FALAS_SUBSTITUTAS = (
    "Você continua com a gente na rádio.",
    "Seguimos com a programação.",
    "Vamos continuar com a nossa programação.",
)


class RevisaoInvalida(Exception):
    """Decisão não permitida: já decidida ou fora do prazo. O router converte em 409."""


def _utc(dt: datetime.datetime) -> datetime.datetime:
    # SQLite devolve datetime sem tzinfo; as linhas foram gravadas em UTC.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=datetime.timezone.utc)


def prazo_para(criado_em: datetime.datetime) -> datetime.datetime:
    return _utc(criado_em) + datetime.timedelta(minutes=PRAZO_MINUTOS)


def substituta(indice: int) -> str:
    return FALAS_SUBSTITUTAS[indice % len(FALAS_SUBSTITUTAS)]


def decidir(estado: str, prazo_em: datetime.datetime, agora: datetime.datetime, acao: str) -> str:
    """Estado novo após a ação do operador. Levanta RevisaoInvalida quando não cabe decisão."""
    if acao not in ACOES:
        raise ValueError(f"ação inválida: {acao!r}")
    if estado != AGUARDANDO:
        raise RevisaoInvalida("fala já decidida")
    if _utc(agora) > _utc(prazo_em):
        raise RevisaoInvalida("fora do prazo: o bloco já saiu do ar")
    return APROVADA if acao == "aprovar" else REJEITADA


def registrar(db: Session, account_id: int, programa_id: int, categoria: str, texto: str, rota: str,
              agora: datetime.datetime) -> FalaEmRevisao:
    estado = estado_inicial(rota)
    linha = FalaEmRevisao(
        account_id=account_id, programa_id=programa_id, categoria=categoria, texto=texto[:600],
        rota=rota, estado=estado, criado_em=agora,
        prazo_em=prazo_para(agora) if estado == AGUARDANDO else None,
        motivo="topico_proibido" if rota == PROIBIDO else "revisao",
    )
    db.add(linha)
    db.commit()
    return linha


def expirar_vencidas(db: Session, account_id: int, programa_id: int, agora: datetime.datetime) -> int:
    """Marca como expirada a fala que aguardava decisão e passou do prazo. Sem job: roda na listagem e na decisão,
    os únicos pontos em que o estado é lido. Devolve quantas expiraram."""
    vencidas = [
        linha for linha in db.query(FalaEmRevisao).filter_by(account_id=account_id, programa_id=programa_id,
                                                              estado=AGUARDANDO)
        if linha.prazo_em is not None and _utc(agora) > _utc(linha.prazo_em)
    ]
    for linha in vencidas:
        linha.estado = EXPIRADA
    if vencidas:
        db.commit()
    return len(vencidas)


def decidir_no_banco(db: Session, account_id: int, programa_id: int, fala_id: int, acao: str,
                     agora: datetime.datetime) -> FalaEmRevisao | None:
    expirar_vencidas(db, account_id, programa_id, agora)
    linha = db.query(FalaEmRevisao).filter_by(id=fala_id, account_id=account_id, programa_id=programa_id).first()
    if linha is None:
        return None
    if linha.prazo_em is None:
        raise RevisaoInvalida(f"fala sem decisão possível (estado {linha.estado})")
    if linha.estado == EXPIRADA:
        raise RevisaoInvalida("fora do prazo: o bloco já saiu do ar")
    linha.estado = decidir(linha.estado, linha.prazo_em, agora, acao)
    linha.decidido_em = agora
    db.commit()
    return linha
