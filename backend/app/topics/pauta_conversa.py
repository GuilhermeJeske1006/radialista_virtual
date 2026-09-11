"""Le' o estoque de assunto ja' casado (ver app.topics.matcher/reserva) e escolhe o proximo pra
virar pauta do bloco de comentario do ao vivo -- ver Fase E do plano-assuntos.md e ADR.

Regra de ouro herdada do plano de jornalismo: isto roda SINCRONO no caminho de fala (chamado por
app.live.router), mas so' LE -- nunca deriva, nunca casa, nunca chama LLM. Mesmo papel que
app.news.pauta cumpre pra noticia.

Cascata (ver ADR item 6): a ordenacao por score ja' resolve perecivel -> permanente -> reserva
sozinha, sem logica if/elif separada por camada -- reserva nasce com peso_base baixo (ver
app.topics.reserva), entao so' sobe ao topo quando o resto (que teria score de match mais alto)
ja' estiver esgotado nesta sessao (ver _sem_estoque_na_sessao).
"""

import dataclasses
import datetime

from sqlalchemy.orm import Session

from app.config.redis_client import redis_client
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.topics.eixos import EIXOS_ASSUNTO, INSTRUCAO_EIXO, MAX_RETORNOS_POR_ASSUNTO
from app.topics.espelho import RegistroUso, ajustar_score, formatar_registro, parsear_registro

# Mesmo valor de _TTL_SESSAO_AO_VIVO em app.live.router -- duplicado aqui (nao importado) pra
# nao criar dependencia circular (router importa deste modulo, nao o contrario).
_TTL_SESSAO_AO_VIVO = 6 * 60 * 60
_MAX_ASSUNTOS_HISTORICO_SESSAO = 40
_JANELA_PENALIDADE_RADIO_HORAS = 4
_MAX_RADIO_HISTORICO = 100
_PENALIDADE_MESMO_GANCHO_NA_RADIO = 3.0

# Ligacoes entre blocos (ver Fase G do plano-assuntos.md) -- callback de curtissimo prazo, so'
# vale pro bloco de comentario logo em seguida, nunca pra sessao inteira (por isso TTL curto e
# consumo unico, ver _consumir_callback_musica/_consumir_callback_noticia_id).
_TTL_CALLBACK_MUSICA = 20 * 60
_TTL_CALLBACK_NOTICIA = 30 * 60
_BONUS_CALLBACK_NOTICIA = 100.0
_SEP_CALLBACK = "\x1f"


@dataclasses.dataclass
class AssuntoConversa:
    assunto_id: int
    titulo: str
    gancho: str
    fatos: list[str]
    ponte: str
    pergunta_ouvinte: str
    tags: list[str]
    origem: str
    eixo: str

    @property
    def tag_principal(self) -> str:
        return self.tags[0] if self.tags else ""


def _chave_sessao(programa_id: int) -> str:
    return f"assuntos_usados:{programa_id}"


def _chave_radio(radio_config_id: int) -> str:
    return f"assuntos_usados:radio:{radio_config_id}"


def _historico_sessao(programa_id: int) -> list[RegistroUso]:
    brutos = redis_client.lrange(_chave_sessao(programa_id), 0, _MAX_ASSUNTOS_HISTORICO_SESSAO - 1)
    return [r for r in (parsear_registro(b) for b in brutos) if r is not None]


def _historico_radio_recente(radio_config_id: int) -> list[RegistroUso]:
    """So' os registros dentro da janela de penalidade (ver ADR item 3) -- diferente do
    historico de sessao, que usa TODOS os _MAX_ASSUNTOS_HISTORICO_SESSAO pra quota (ver
    app.topics.espelho), aqui e' so' penalidade de curto prazo, nao quota."""
    agora = datetime.datetime.now(datetime.timezone.utc).timestamp()
    limite = agora - _JANELA_PENALIDADE_RADIO_HORAS * 3600
    brutos = redis_client.lrange(_chave_radio(radio_config_id), 0, _MAX_RADIO_HISTORICO - 1)
    registros = [r for r in (parsear_registro(b) for b in brutos) if r is not None]
    return [r for r in registros if r.epoch >= limite]


def registrar_assunto_usado(programa_id: int, radio_config_id: int, assunto_id: int, *, eixo: str, origem: str, tag_principal: str) -> None:
    registro = formatar_registro(assunto_id, eixo, origem, tag_principal)

    chave_sessao = _chave_sessao(programa_id)
    redis_client.lpush(chave_sessao, registro)
    redis_client.ltrim(chave_sessao, 0, _MAX_ASSUNTOS_HISTORICO_SESSAO - 1)
    redis_client.expire(chave_sessao, _TTL_SESSAO_AO_VIVO)

    # Cruzamento entre programas da mesma radio (ver ADR item 3): chave separada, por
    # assunto_id (gancho), nao pelo fato de origem -- dois programas comentando a mesma noticia
    # por ganchos DIFERENTES e' o comportamento desejado, nao uma colisao.
    chave_radio = _chave_radio(radio_config_id)
    redis_client.lpush(chave_radio, registro)
    redis_client.ltrim(chave_radio, 0, _MAX_RADIO_HISTORICO - 1)
    redis_client.expire(chave_radio, _TTL_SESSAO_AO_VIVO)


def _chave_callback_musica(programa_id: int) -> str:
    return f"callback_musica_assunto:{programa_id}"


def registrar_callback_musica(programa_id: int, titulo: str, contexto: str) -> None:
    """Musica puxa assunto (ver Fase G): o contexto real da faixa que acabou de tocar (ja'
    computado pra' anunciar a musica, ver app.live.router._contexto_musica -- nenhuma chamada de
    LLM nova aqui) fica disponivel como gancho de conversa pro bloco de comentario IMEDIATAMENTE
    seguinte. TTL curto -- se o proximo bloco nao for comentario a tempo, o callback so' expira,
    nunca vira pauta velha meses depois."""
    redis_client.set(_chave_callback_musica(programa_id), f"{titulo}{_SEP_CALLBACK}{contexto}", ex=_TTL_CALLBACK_MUSICA)


def _consumir_callback_musica(programa_id: int) -> tuple[str, str] | None:
    chave = _chave_callback_musica(programa_id)
    bruto = redis_client.get(chave)
    if bruto is None:
        return None
    redis_client.delete(chave)  # consumo unico -- nao deveria valer pra dois blocos de comentario seguidos
    titulo, _separador, contexto = bruto.partition(_SEP_CALLBACK)
    return titulo, contexto


def _chave_callback_noticia(programa_id: int) -> str:
    return f"callback_noticia_id:{programa_id}"


def registrar_callback_noticia(programa_id: int, noticia_id: int) -> None:
    """Noticia puxa comentario (ver Fase G): a pauta do bloco de noticia que acabou de ir ao ar
    fica com prioridade pra virar assunto do comentario seguinte -- por OUTRO eixo (o bloco de
    noticia usa o angulo dela propria, ver app.news.pauta.ANGULOS_NOTICIA; o gancho aqui e' um
    Assunto derivado dessa mesma noticia, ver app.topics.fontes.de_noticia, nunca usado ainda)."""
    redis_client.set(_chave_callback_noticia(programa_id), str(noticia_id), ex=_TTL_CALLBACK_NOTICIA)


def _consumir_callback_noticia_id(programa_id: int) -> int | None:
    chave = _chave_callback_noticia(programa_id)
    bruto = redis_client.get(chave)
    if bruto is None:
        return None
    redis_client.delete(chave)
    try:
        return int(bruto)
    except ValueError:
        return None


def pipeline_tem_estoque(db: Session, programa_id: int) -> bool:
    """True quando ja' existe pelo menos um casamento (ver app.topics.matcher/reserva) pra este
    programa -- usado por app.live.router pra distinguir 'pipeline nunca rodou pra esta conta
    ainda' (mantem geracao livre, comportamento anterior, sem regressao) de 'pipeline ativo mas
    esgotado nesta sessao' (so' ai' faz sentido a cascata pra musica, ver ADR item 6)."""
    return db.query(AssuntoPrograma.id).filter_by(programa_id=programa_id).first() is not None


def _candidatos(db: Session, programa_id: int) -> list[tuple[AssuntoPrograma, Assunto]]:
    agora = datetime.datetime.now(datetime.timezone.utc)
    linhas = (
        db.query(AssuntoPrograma, Assunto)
        .join(Assunto, Assunto.id == AssuntoPrograma.assunto_id)
        .filter(
            AssuntoPrograma.programa_id == programa_id,
            (Assunto.validade_ate.is_(None)) | (Assunto.validade_ate > agora),
        )
        .all()
    )
    return linhas


def proximo_assunto(db: Session, programa: Programa) -> AssuntoConversa | None:
    callback_musica = _consumir_callback_musica(programa.id)
    if callback_musica is not None:
        titulo, contexto = callback_musica
        return AssuntoConversa(
            assunto_id=0, titulo=titulo, gancho=contexto, fatos=[contexto], ponte="",
            pergunta_ouvinte="", tags=["musica", "memoria"], origem="musica", eixo="memoria",
        )

    candidatos = _candidatos(db, programa.id)
    if not candidatos:
        return None

    callback_noticia_id = _consumir_callback_noticia_id(programa.id)

    historico_sessao = _historico_sessao(programa.id)
    historico_radio = _historico_radio_recente(programa.radio_config_id)
    ids_penalizados_radio = {r.assunto_id for r in historico_radio}

    contagem_sessao: dict[int, int] = {}
    eixos_usados_sessao: dict[int, set[str]] = {}
    for registro in historico_sessao:
        contagem_sessao[registro.assunto_id] = contagem_sessao.get(registro.assunto_id, 0) + 1
        eixos_usados_sessao.setdefault(registro.assunto_id, set()).add(registro.eixo)

    avaliados = []
    for assunto_programa, assunto in candidatos:
        if contagem_sessao.get(assunto.id, 0) >= MAX_RETORNOS_POR_ASSUNTO:
            continue
        cardapio = assunto_programa.eixos_sugeridos or list(EIXOS_ASSUNTO)
        eixos_ja_usados = eixos_usados_sessao.get(assunto.id, set())
        eixos_restantes = [e for e in EIXOS_ASSUNTO if e in cardapio and e not in eixos_ja_usados]
        if not eixos_restantes:
            continue

        tag_principal = assunto.tags[0] if assunto.tags else ""
        score = ajustar_score(
            assunto_programa.score, origem=assunto.origem, tag_principal=tag_principal, historico=historico_sessao
        )
        if assunto.id in ids_penalizados_radio:
            score -= _PENALIDADE_MESMO_GANCHO_NA_RADIO
        if callback_noticia_id is not None and assunto.origem == "noticia" and assunto.origem_ref_id == callback_noticia_id:
            # Fase G: noticia que acabou de ir ao ar tem prioridade absoluta pro comentario
            # seguinte, ainda respeitando exhaustao de eixo/sessao (ja' filtrado acima).
            score += _BONUS_CALLBACK_NOTICIA

        avaliados.append((score, eixos_restantes[0], assunto_programa, assunto))

    if not avaliados:
        return None

    avaliados.sort(key=lambda item: item[0], reverse=True)
    _score, eixo, assunto_programa, assunto = avaliados[0]

    return AssuntoConversa(
        assunto_id=assunto.id,
        titulo=assunto.titulo,
        gancho=assunto.gancho,
        fatos=list(assunto.fatos or []),
        ponte=assunto_programa.ponte,
        pergunta_ouvinte=assunto.pergunta_ouvinte,
        tags=list(assunto.tags or []),
        origem=assunto.origem,
        eixo=eixo,
    )


def montar_pauta_assunto(assunto: AssuntoConversa) -> str:
    """Bloco 'PAUTA DESTE ASSUNTO' injetado no prompt -- mesmo padrao de
    app.news.pauta.montar_lauda: fatos + briefing (nunca fala pronta, ver ADR item 1) + a
    instrucao de eixo como sufixo, no lugar de reescrever o briefing por eixo."""
    linhas = [
        "PAUTA DESTE ASSUNTO (gancho de conversa -- use os fatos e o contexto, mas escreva a fala do zero):",
        f"- Gancho: {assunto.gancho}",
    ]
    if assunto.fatos:
        linhas.append(f"- Fatos: {'; '.join(assunto.fatos)}")
    if assunto.ponte:
        linhas.append(
            f"- Contexto pro publico deste programa: {assunto.ponte} (isto e' nota de pauta, "
            "nao leia como se fosse a fala pronta)"
        )
    instrucao = INSTRUCAO_EIXO.get(assunto.eixo, "")
    linhas.append(f"- EIXO DESTE BLOCO: {assunto.eixo.upper()} -- {instrucao}")
    if assunto.eixo == "pergunta" and assunto.pergunta_ouvinte:
        linhas.append(f"- Pergunta sugerida pro ouvinte: {assunto.pergunta_ouvinte}")
    return "\n".join(linhas)
