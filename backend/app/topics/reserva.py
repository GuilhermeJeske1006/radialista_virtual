"""Reserva estrategica (ver Fase D do plano-assuntos.md): gera, offline e uma vez por semana por
programa, um lote de ganchos atemporais -- curiosidade, almanaque, pergunta de conversa, memoria
afetiva -- que nunca expiram. E' o que garante que o bloco de comentario NUNCA fica sem pauta,
mesmo de madrugada, em cidade pequena, em feriado, quando nenhuma fonte perecivel (noticia,
efemeride, pedido de ouvinte) tem nada fresco.

Nasce com score baixo de proposito (ver peso_base/_SCORE_RESERVA): so' sobe ao topo da escolha
de app.topics.pauta_conversa.proximo_assunto quando o resto ja' esgotou nesta sessao -- a
cascata inteira (perecivel -> permanente -> reserva) sai de graca so' ordenando por score, sem
logica se/senao separada por camada (ver docstring de pauta_conversa).

ADR item 4: Programa.publico_alvo e' opcional -- quando vazio, deriva um briefing de publico a
partir de sinal OBSERVADO (horario, generos, tom, cidade, o que o publico de fato pede), nao de
um campo de cadastro que na pratica chegaria generico do mesmo jeito.
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.redis_client import redis_client
from app.llm.client import gerar_classificacao
from app.llm.json_utils import extrair_json
from app.models.account import Account
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.musica_historico import MusicaHistorico
from app.models.programa import Programa

logger = logging.getLogger("radialista.topics.reserva")

_QTD_RESERVA_POR_RODADA = 25
_DIAS_INTERVALO_RESERVA = 7
_TTL_MARCADOR_RESERVA = (_DIAS_INTERVALO_RESERVA + 1) * 24 * 60 * 60
_SCORE_RESERVA = 2.0
_MAX_PEDIDOS_NO_BRIEFING = 3


def _faixa_horaria(hora: int) -> str:
    if hora < 5:
        return "madrugada (publico noturno, quem trabalha a noite ou esta acordado tarde)"
    if hora < 11:
        return "manha (quem esta saindo de casa/trabalho cedo, rotina comecando)"
    if hora < 18:
        return "tarde (dia a dia, quem esta trabalhando ou em casa)"
    return "noite (fim de dia, publico mais tranquilo/afetivo)"


def _pedidos_observados(db: Session, programa_id: int) -> list[str]:
    linhas = (
        db.query(MusicaHistorico.query, func.count().label("contagem"))
        .filter(MusicaHistorico.programa_id == programa_id, MusicaHistorico.origem == "pedido_ouvinte")
        .group_by(MusicaHistorico.query)
        .order_by(func.count().desc())
        .limit(_MAX_PEDIDOS_NO_BRIEFING)
        .all()
    )
    return [query for query, _contagem in linhas]


def montar_briefing_publico(db: Session, programa: Programa, account: Account) -> str:
    if programa.publico_alvo:
        return programa.publico_alvo

    partes = [
        f"Programa no periodo de {_faixa_horaria(programa.horario_inicio.hour)}.",
        f"Tom do programa: {programa.tom}.",
    ]
    if programa.generos_musicais:
        partes.append(f"Generos musicais: {', '.join(programa.generos_musicais)}.")
    if account.cidade:
        partes.append(f"Cidade: {account.cidade}.")
    pedidos = _pedidos_observados(db, programa.id)
    if pedidos:
        partes.append(f"Interesses observados via pedido do publico: {', '.join(pedidos)}.")
    return " ".join(partes)


_SYSTEM_PROMPT_RESERVA = (
    "Voce e' produtor de pauta de uma radio brasileira. Recebe o perfil de um programa (briefing "
    "de publico, tom, generos musicais, topicos permitidos/proibidos) e precisa gerar um estoque "
    "de ganchos de conversa ATEMPORAIS -- que nunca ficam velhos, prontos pro locutor puxar em "
    "qualquer dia: curiosidade real (almanaque, historia, expressao regional), pergunta leve pra "
    "jogar pro ouvinte, memoria afetiva ligada ao genero musical do programa, observacao sobre "
    "vida cotidiana compartilhada (dia da semana, fim de mes, estacao do ano). NUNCA gere gancho "
    "que dependa de um fato datavel (noticia, evento especifico) -- isso e' outra fonte, aqui e' "
    "so' o que nunca expira.\n"
    f"Gere {_QTD_RESERVA_POR_RODADA} ganchos DIFERENTES entre si, respeitando topicos proibidos.\n"
    "Responda APENAS com um JSON compacto (lista), sem markdown:\n"
    '[{"titulo": "", "gancho": "", "tags": [""], "pergunta_ouvinte": ""}]'
)


def _marcador_recente(programa_id: int) -> bool:
    return redis_client.get(f"reserva_gerada_em:{programa_id}") is not None


def _marcar_gerada(programa_id: int) -> None:
    redis_client.set(f"reserva_gerada_em:{programa_id}", "1", ex=_TTL_MARCADOR_RESERVA)


def gerar_reserva_semanal(db: Session, programa: Programa, account: Account, *, forcar: bool = False) -> int:
    if not forcar and _marcador_recente(programa.id):
        return 0

    briefing = montar_briefing_publico(db, programa, account)
    mensagem = (
        f"{briefing}\nTopicos permitidos: {', '.join(programa.topicos_permitidos) or 'qualquer um'}\n"
        f"Topicos proibidos: {', '.join(programa.topicos_proibidos) or 'nenhum'}"
    )
    try:
        resposta = gerar_classificacao(_SYSTEM_PROMPT_RESERVA, mensagem, max_tokens=4000)
        dados = extrair_json(resposta)
    except Exception:
        logger.warning("Falha ao gerar reserva estrategica: programa_id=%s", programa.id, exc_info=True)
        return 0

    if not isinstance(dados, list):
        return 0

    gravados = 0
    for item in dados:
        if not isinstance(item, dict):
            continue
        titulo = str(item.get("titulo") or "").strip()
        gancho = str(item.get("gancho") or "").strip()
        if not titulo or not gancho:
            continue
        tags = [str(t).strip().lower() for t in (item.get("tags") or []) if str(t).strip()]
        assunto = Assunto(
            account_id=account.id,
            origem="reserva",
            origem_ref_id=None,
            titulo=titulo,
            gancho=gancho,
            fatos=[],
            tags=tags,
            pergunta_ouvinte=str(item.get("pergunta_ouvinte") or "").strip(),
            validade_ate=None,
            peso_base=1.5,
        )
        db.add(assunto)
        db.flush()
        db.add(AssuntoPrograma(
            assunto_id=assunto.id, programa_id=programa.id,
            score=_SCORE_RESERVA, ponte=briefing, eixos_sugeridos=[],
        ))
        gravados += 1

    db.commit()
    _marcar_gerada(programa.id)
    if gravados == 0:
        logger.warning("reserva_estrategica_vazia programa_id=%s", programa.id)
    return gravados
