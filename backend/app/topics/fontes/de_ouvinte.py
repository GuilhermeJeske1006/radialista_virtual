"""Deriva gancho de conversa a partir do que o ouvinte mandou -- ver Fase B/1.3 do
plano-assuntos.md: "o que os ouvintes mandaram e' a melhor pauta de radio que existe", hoje usada
so' pra tocar pedido, nunca como pauta de comentario.

Puramente programatico (sem LLM): agrega MusicaHistorico(origem="pedido_ouvinte") por
query_normalizada, mesmo agrupamento que _pedidos_publico_mais_frequentes (app.live.router) ja
faz pra escolher musica -- aqui vira pauta em vez de so' criterio de busca. So' quando um pedido
se repete de verdade (>= _MIN_PEDIDOS_PARA_PAUTA) dentro da janela: um pedido isolado e' so' um
pedido, tres pedidos da mesma coisa no mesmo dia e' assunto ("hoje o pessoal ta pedindo X").
"""

import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assunto import Assunto
from app.models.musica_historico import MusicaHistorico
from app.models.programa import Programa

_JANELA_HORAS = 24
_MIN_PEDIDOS_PARA_PAUTA = 3
_TAGS_OUVINTE = ["ouvinte", "pedido_recorrente"]


def _ja_derivada_hoje(db: Session, account_id: int, titulo: str) -> bool:
    inicio_dia = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_JANELA_HORAS)
    return (
        db.query(Assunto.id)
        .filter(
            Assunto.account_id == account_id,
            Assunto.origem == "ouvinte",
            Assunto.titulo == titulo,
            Assunto.criado_em >= inicio_dia,
        )
        .first()
        is not None
    )


def derivar_de_ouvinte(db: Session, radio_config_id: int, account_id: int) -> list[Assunto]:
    limiar = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=_JANELA_HORAS)
    linhas = (
        db.query(MusicaHistorico.query_normalizada, MusicaHistorico.query, func.count().label("contagem"))
        .join(Programa, Programa.id == MusicaHistorico.programa_id)
        .filter(
            Programa.radio_config_id == radio_config_id,
            MusicaHistorico.origem == "pedido_ouvinte",
            MusicaHistorico.criado_em >= limiar,
        )
        .group_by(MusicaHistorico.query_normalizada, MusicaHistorico.query)
        .having(func.count() >= _MIN_PEDIDOS_PARA_PAUTA)
        .all()
    )

    assuntos = []
    for _query_normalizada, query_original, contagem in linhas:
        titulo = f"Pedidos recorrentes: {query_original}"
        if _ja_derivada_hoje(db, account_id, titulo):
            continue
        assunto = Assunto(
            account_id=account_id,
            origem="ouvinte",
            origem_ref_id=None,
            titulo=titulo,
            gancho=f"Hoje varios ouvintes pediram \"{query_original}\" ({contagem} pedidos).",
            fatos=[f"\"{query_original}\" foi pedida {contagem} vezes nas ultimas {_JANELA_HORAS}h."],
            tags=list(_TAGS_OUVINTE),
            validade_ate=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=_JANELA_HORAS),
            peso_base=6.0,
        )
        db.add(assunto)
        assuntos.append(assunto)
    if assuntos:
        db.commit()
    return assuntos
