"""Casa cada Assunto (gancho, ver app.topics.derivador) com cada programa ativo -- o coracao do
plano-assuntos.md (Fase C). Roda no worker (ver app.topics.pipeline), nunca no caminho de fala.

Custo (ver ADR secao 5): casar por rodada de coleta pra TODO programa ativo escala com
programas_ativos x rodadas/dia e fica caro rapido (1440 chamadas/dia/conta com 10 programas em
144 rodadas). O conserto e' so' casar programa que esta no ar agora ou entra na proxima hora
(ver _programas_na_janela) -- colapsa pra 1-2 programas por rodada relevante, nao 10 -- mais um
pre-filtro por tag antes de qualquer chamada de LLM (ver _sobrepoe_tags) e um teto diario com
degradacao pra score puro por tags quando estourado (ver _TETO_CHAMADAS_HAIKU_POR_CONTA_DIA).
"""

import datetime
import logging
import unicodedata

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.config.redis_client import redis_client
from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS
from app.guardrails.schedule import programa_no_ar
from app.llm.client import gerar_classificacao
from app.llm.json_utils import extrair_json
from app.models.account import Account
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics.eixos import EIXOS_ASSUNTO

logger = logging.getLogger("radialista.topics.matcher")

_JANELA_PROXIMA_HORA_MINUTOS = 60
_LIMIAR_SCORE_TAGS = 0.15
_LIMIAR_MATCH_FINAL = 3.0
_MAX_GANCHOS_POR_CHAMADA = 20
_TETO_CHAMADAS_HAIKU_POR_CONTA_DIA = 300
_TTL_TETO_DIARIO = 2 * 24 * 60 * 60


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _normalizar_termos(termos: list[str]) -> set[str]:
    return {_sem_acento(t.strip().lower()) for t in termos if t and t.strip()}


# Preposicao/artigo/conjuncao comuns em portugues -- sem filtrar isso, duas frases quaisquer
# concordariam so' por "de"/"e"/"na" em comum, inflando o score de qualquer par ao acaso.
_PALAVRAS_IRRELEVANTES = {
    "de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "no", "na", "nos", "nas",
    "pro", "pra", "para", "com", "um", "uma", "uns", "umas", "que", "por", "se", "sua", "seu",
}


def _palavras_relevantes(frases: list[str]) -> set[str]:
    """topicos_permitidos/assuntos_ao_vivo/generos_musicais (ver app.models.programa.Programa)
    sao FRASES descritivas ("trânsito e chuva na região"), nao tokens atomicos -- comparar a
    frase inteira contra uma tag curta do gancho ("chuva") nunca bateria por igualdade exata
    (bug real, achado testando o fluxo ao vivo: nenhum gancho de chuva/transito casava com
    nenhum programa porque a frase inteira nunca era igual a tag curta). Explode em palavras,
    mesma ideia de _categoria_permitida em app.news.pauta (substring por palavra), aqui como
    conjunto pra permitir overlap parcial em vez de so' sim/nao."""
    palavras: set[str] = set()
    for frase in frases:
        if not frase or not frase.strip():
            continue
        for palavra in _sem_acento(frase.strip().lower()).split():
            if palavra not in _PALAVRAS_IRRELEVANTES:
                palavras.add(palavra)
    return palavras


def _comeca_em_breve(programa: Programa, timezone: str, minutos: int) -> bool:
    if not programa.ativo:
        return False
    agora = datetime.datetime.now(ZoneInfo(timezone))
    limite = agora + datetime.timedelta(minutes=minutos)
    if programa.data_especifica is not None and programa.data_especifica not in (agora.date(), limite.date()):
        return False
    if programa.dias_semana and agora.weekday() not in programa.dias_semana and limite.weekday() not in programa.dias_semana:
        return False
    inicio_hoje = datetime.datetime.combine(agora.date(), programa.horario_inicio, tzinfo=agora.tzinfo)
    if inicio_hoje < agora:
        inicio_hoje += datetime.timedelta(days=1)
    return agora <= inicio_hoje <= limite


def _programas_na_janela(db: Session, account: Account) -> list[Programa]:
    """Programa no ar agora, ou que comeca dentro de _JANELA_PROXIMA_HORA_MINUTOS -- ver ADR
    secao 5. Fora dessa janela, casar assunto pra ele seria gasto sem retorno imediato (o
    programa nem vai consumir o resultado antes do proximo ciclo do worker recalcular tudo)."""
    radios = db.query(RadioConfig).filter_by(account_id=account.id).all()
    programas = []
    for radio in radios:
        candidatos = db.query(Programa).filter_by(radio_config_id=radio.id, ativo=True).all()
        for programa in candidatos:
            if programa_no_ar(programa, radio.timezone) or _comeca_em_breve(programa, radio.timezone, _JANELA_PROXIMA_HORA_MINUTOS):
                programas.append(programa)
    return programas


def _bate_topico_proibido_ou_universal(assunto: Assunto, programa: Programa) -> bool:
    texto = _sem_acento(f"{assunto.titulo} {assunto.gancho}".lower())
    termos = list(programa.topicos_proibidos or []) + TERMOS_SEMPRE_BLOQUEADOS
    return any(_sem_acento(termo.lower()) in texto for termo in termos)

def _tags_programa(programa: Programa) -> set[str]:
    return _palavras_relevantes(
        list(programa.topicos_permitidos or []) + list(programa.assuntos_ao_vivo or []) + list(programa.generos_musicais or [])
    )


def _score_tags(assunto: Assunto, tags_programa: set[str]) -> float:
    """Sobreposicao simples (nao-Jaccard: o denominador e' so' o tamanho do gancho, nao da uniao)
    -- um programa com poucas tags configuradas nao deveria penalizar um gancho bem taggeado por
    causa disso; o que importa e' quanto do gancho bate com o que o programa aceita.

    Palavra por palavra dos dois lados (ver _palavras_relevantes) -- uma tag do gancho pode ser
    ela mesma composta ("meio ambiente"), entao explode os dois lados em vez de comparar frase
    inteira contra frase inteira."""
    tags_assunto = _palavras_relevantes(assunto.tags or [])
    if not tags_assunto:
        return 0.0
    if not tags_programa:
        # Programa sem nenhuma tag configurada nao filtra por tema -- deixa o haiku decidir
        # relevancia via descricao/tom (ver _casar_via_llm), mesma logica de
        # _categoria_permitida em app.news.pauta pra tipos_noticias vazio.
        return 1.0
    intersecao = tags_assunto & tags_programa
    return len(intersecao) / len(tags_assunto)


def _ja_casados(db: Session, programa_id: int, assunto_ids: list[int]) -> set[int]:
    if not assunto_ids:
        return set()
    linhas = (
        db.query(AssuntoPrograma.assunto_id)
        .filter(AssuntoPrograma.programa_id == programa_id, AssuntoPrograma.assunto_id.in_(assunto_ids))
        .all()
    )
    return {a for a, in linhas}


def _candidatos_nao_casados(db: Session, programa: Programa, account: Account) -> list[Assunto]:
    agora = datetime.datetime.now(datetime.timezone.utc)
    query = db.query(Assunto).filter(
        Assunto.account_id == account.id,
        Assunto.origem != "reserva",
        (Assunto.validade_ate.is_(None)) | (Assunto.validade_ate > agora),
    )
    todos = query.all()
    ja_casados = _ja_casados(db, programa.id, [a.id for a in todos])
    return [a for a in todos if a.id not in ja_casados]


def _teto_diario_estourado(account_id: int) -> bool:
    hoje = datetime.date.today().isoformat()
    chave = f"matcher_chamadas_haiku:{account_id}:{hoje}"
    atual = redis_client.get(chave)
    return atual is not None and int(atual) >= _TETO_CHAMADAS_HAIKU_POR_CONTA_DIA


def _registrar_chamada_haiku(account_id: int) -> None:
    hoje = datetime.date.today().isoformat()
    chave = f"matcher_chamadas_haiku:{account_id}:{hoje}"
    redis_client.incr(chave)
    redis_client.expire(chave, _TTL_TETO_DIARIO)


_SYSTEM_PROMPT_CASAMENTO = (
    "Voce e' o produtor de pauta de um programa de radio especifico. Recebe o perfil do programa "
    "e uma lista de ganchos de conversa candidatos (ja filtrados por tema). Pra cada gancho que "
    "genuinamente fizer sentido pra ESTE programa e' publico, devolva: um score de 0 a 10 de "
    "quanto ele rende conversa boa aqui, um briefing curto (1-2 frases) de PARA QUEM e POR QUE "
    "esse gancho importa pra esse publico especifico (NUNCA escreva como se fosse a fala do "
    "locutor -- e' nota de pauta, nao locucao), e quais eixos de abordagem ele rende bem dentre: "
    + ", ".join(EIXOS_ASSUNTO) + ".\n"
    "Gancho que nao combina com este programa (publico errado, tom incompativel, tema fora do "
    "que o programa cobre) simplesmente NAO aparece na resposta -- nao force encaixe.\n"
    "Responda APENAS com um JSON compacto (lista), sem markdown:\n"
    '[{"id": 0, "score": 0, "ponte": "", "eixos_sugeridos": [""]}]'
)


def _perfil_programa_texto(programa: Programa) -> str:
    return (
        f"Nome: {programa.nome}\nDescricao: {programa.descricao or 'nao informada'}\n"
        f"Publico: {programa.publico_alvo or 'nao informado'}\nTom: {programa.tom}\n"
        f"Horario: {programa.horario_inicio.strftime('%H:%M')} as {programa.horario_fim.strftime('%H:%M')}\n"
        f"Topicos permitidos: {', '.join(programa.topicos_permitidos) or 'qualquer um'}\n"
        f"Generos musicais: {', '.join(programa.generos_musicais) or 'nao informado'}"
    )


def _casar_via_llm(ganchos: list[Assunto], programa: Programa) -> dict[int, dict]:
    lista_ganchos = "\n".join(
        f"{a.id}) {a.titulo} -- {a.gancho} [tags: {', '.join(a.tags)}]" for a in ganchos
    )
    mensagem = f"{_perfil_programa_texto(programa)}\n\nGanchos candidatos:\n{lista_ganchos}"
    try:
        resposta = gerar_classificacao(_SYSTEM_PROMPT_CASAMENTO, mensagem, max_tokens=1500)
        dados = extrair_json(resposta)
    except Exception:
        logger.warning("Falha ao casar ganchos via LLM: programa_id=%s", programa.id, exc_info=True)
        return {}

    if not isinstance(dados, list):
        return {}

    resultado = {}
    for item in dados:
        if not isinstance(item, dict):
            continue
        try:
            assunto_id = int(item.get("id"))
            score = float(item.get("score") or 0)
        except (TypeError, ValueError):
            continue
        eixos = [e for e in (item.get("eixos_sugeridos") or []) if e in EIXOS_ASSUNTO]
        resultado[assunto_id] = {
            "score": max(0.0, min(10.0, score)),
            "ponte": str(item.get("ponte") or "").strip(),
            "eixos_sugeridos": eixos,
        }
    return resultado


def casar_programa(db: Session, programa: Programa, account: Account) -> int:
    candidatos = _candidatos_nao_casados(db, programa, account)
    if not candidatos:
        return 0

    tags_programa = _tags_programa(programa)
    sobreviventes = []
    for assunto in candidatos:
        if _bate_topico_proibido_ou_universal(assunto, programa):
            continue
        score_tags = _score_tags(assunto, tags_programa)
        if score_tags < _LIMIAR_SCORE_TAGS:
            continue
        sobreviventes.append((assunto, score_tags))
    if not sobreviventes:
        return 0

    sobreviventes.sort(key=lambda par: par[1], reverse=True)
    lote = sobreviventes[:_MAX_GANCHOS_POR_CHAMADA]

    gravados = 0
    if _teto_diario_estourado(account.id):
        # Degradacao (ver ADR secao 5): sem ponte escrita, score puro por tag, cardapio de eixo
        # aberto (eixos_sugeridos vazio == qualquer eixo serve, ver app.topics.pauta_conversa) --
        # pior que o caminho normal, mas nunca pior que a fala vazia de antes.
        logger.warning("matcher_teto_diario_estourado account_id=%s", account.id)
        for assunto, score_tags in lote:
            db.add(AssuntoPrograma(
                assunto_id=assunto.id, programa_id=programa.id,
                score=score_tags * 10, ponte="", eixos_sugeridos=[],
            ))
            gravados += 1
        db.commit()
        return gravados

    resultados = _casar_via_llm([a for a, _ in lote], programa)
    _registrar_chamada_haiku(account.id)
    for assunto, _score_tags_val in lote:
        dados_match = resultados.get(assunto.id)
        if dados_match is None or dados_match["score"] < _LIMIAR_MATCH_FINAL:
            continue
        db.add(AssuntoPrograma(
            assunto_id=assunto.id, programa_id=programa.id,
            score=dados_match["score"], ponte=dados_match["ponte"],
            eixos_sugeridos=dados_match["eixos_sugeridos"],
        ))
        gravados += 1
    db.commit()
    return gravados


def casar_conta(db: Session, account: Account) -> int:
    total = 0
    for programa in _programas_na_janela(db, account):
        try:
            total += casar_programa(db, programa, account)
        except Exception:
            logger.warning("Falha ao casar assuntos pro programa: programa_id=%s", programa.id, exc_info=True)
            db.rollback()
    return total
