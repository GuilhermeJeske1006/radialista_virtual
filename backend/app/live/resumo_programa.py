"""Resumo de um dia de programa a partir do banco (F11, item 2): o que o relatório pós-programa precisa, sem depender
de resumo enviado pelo cliente.

Fontes: o as-run (só o que o player confirmou conta como ao ar), as promessas criadas no dia e os pedidos recebidos no
dia. O que o banco não guarda (orçamento da fala, hard time do relógio) fica de fora e é listado em `NAO_MEDIDO`, para
o relatório não mostrar zero onde não houve medida.
"""

from __future__ import annotations

import datetime
from collections import Counter
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.live.cortes import _e_fala
from app.live.memoria import repeticao_estrutura
from app.live.oralidade import avisos as avisos_de_oralidade
from app.models.as_run_evento import AsRunEvento
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.promessa_no_ar import PromessaNoAr

NAO_MEDIDO = ("orcamento", "hard_time")
_PEDIDOS_PENDENTES = ("em_fila", "selecionado")


def _utc(valor: datetime.datetime) -> datetime.datetime:
    # SQLite devolve datetime sem fuso; as linhas são gravadas em UTC.
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=datetime.timezone.utc)


def janela_do_dia(data: datetime.date, timezone: str) -> tuple[datetime.datetime, datetime.datetime]:
    inicio = datetime.datetime.combine(data, datetime.time(0), tzinfo=ZoneInfo(timezone))
    return inicio, inicio + datetime.timedelta(days=1)


def resumo_do_dia(db: Session, account_id: int, programa, radio_config_id: int, data: datetime.date,
                  timezone: str) -> tuple[dict, dict]:
    """(resumo no formato do simulador, contagem do as-run) do dia `data` no fuso da rádio."""
    inicio, fim = janela_do_dia(data, timezone)

    def no_dia(quando: datetime.datetime | None) -> bool:
        return quando is not None and inicio <= _utc(quando) < fim

    eventos = [e for e in db.query(AsRunEvento).filter_by(account_id=account_id, programa_id=programa.id)
               .order_by(AsRunEvento.ordem.asc()) if no_dia(e.criado_em)]
    status = Counter(e.status for e in eventos)
    falas_no_ar = [e.texto for e in eventos
                   if e.status == "confirmado" and _e_fala({"tipo": e.tipo, "texto": e.texto})]

    promessas = Counter()
    for promessa in db.query(PromessaNoAr).filter_by(programa_id=programa.id, radio_config_id=radio_config_id):
        if no_dia(promessa.criada_em):
            chave = "cancelada_com_contingencia" if promessa.estado == "cancelada" and promessa.contingencia \
                else promessa.estado
            promessas[chave] += 1

    pedidos = Counter(p.estado for p in db.query(FilaAoVivo).filter_by(programa_id=programa.id,
                                                                       radio_config_id=radio_config_id)
                      if no_dia(p.criado_em))

    resumo = {
        "promessas": {
            "cumpridas": promessas["cumprida"], "vencidas": promessas["vencida"],
            "canceladas_com_contingencia": promessas["cancelada_com_contingencia"],
            "abertas_no_fim": promessas["aberta"],
        },
        "promessa_vencida": promessas["vencida"],
        "pedidos": {
            "recebidos": sum(pedidos.values()), "executados": pedidos["executado"],
            "nao_atendidos": pedidos["nao_atendido"], "expirados": pedidos["expirado"],
            "pendentes_fim": sum(pedidos[e] for e in _PEDIDOS_PENDENTES),
        },
        "aviso_oralidade": sum(len(avisos_de_oralidade(texto)) for texto in falas_no_ar),
        "repeticao_estrutura": repeticao_estrutura(falas_no_ar),
    }
    as_run = {"enviados": len(eventos), "confirmados": status["confirmado"], "falharam": status["falhou"],
              "sem_relato": status["enviado"]}
    return resumo, as_run
