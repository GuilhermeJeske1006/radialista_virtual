"""Equilibrio de pauta (ver Fase F do plano-assuntos.md): sem isso o matcher empilha assunto da
mesma origem (um dia de temporal vira so' noticia de chuva). Mesmo espirito de limite_por_canal
em app.live.music pra nao saturar de um artista so'.

Cotas calculadas no READ, a partir do historico compacto de sessao (ver
app.topics.pauta_conversa._historico_assuntos) -- nunca um contador separado (ver ADR secao 2):
contador proprio seria segunda fonte de verdade pro mesmo fato, com risco de divergir do
historico quando um dos dois writes falha.

Por principio (ver ADR): restricao nova entra como PESO (ajusta o score), nunca como bloqueio
duro -- vira bloqueio so' quando houver estoque comprovado que o sustente, o que este
subsistema, na duvida, prefere nao assumir.
"""

import dataclasses
import datetime

ORIGENS_PERECIVEIS = {"noticia", "efemeride", "sazonal", "agenda"}
ORIGENS_PERMANENTES = {"musica", "ouvinte", "reserva"}

_MAX_CONSECUTIVOS_MESMA_ORIGEM = 2
_MAX_MESMA_TAG_POR_HORA = 3
_JANELA_TAG_SEGUNDOS = 60 * 60
_JANELA_PROPORCAO_PERMANENTE = 4  # 1 permanente esperado a cada N pereciveis seguidos

_PENALIDADE_ORIGEM_REPETIDA = 4.0
_PENALIDADE_TAG_SATURADA = 3.0
_BONUS_PERMANENTE_DEVIDO = 2.0


@dataclasses.dataclass
class RegistroUso:
    assunto_id: int
    eixo: str
    origem: str
    tag_principal: str
    epoch: int


def formatar_registro(assunto_id: int, eixo: str, origem: str, tag_principal: str) -> str:
    # "|" e' o separador do formato compacto -- tira de qualquer campo de texto livre (tag/
    # origem) pra nao quebrar o parse (ver ADR secao 2, nota de robustez).
    origem_seguro = (origem or "").replace("|", "-")
    tag_segura = (tag_principal or "").replace("|", "-")
    epoch = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    return f"{assunto_id}|{eixo}|{origem_seguro}|{tag_segura}|{epoch}"


def parsear_registro(bruto: str) -> RegistroUso | None:
    partes = bruto.split("|")
    if len(partes) != 5:
        return None
    try:
        return RegistroUso(
            assunto_id=int(partes[0]), eixo=partes[1], origem=partes[2],
            tag_principal=partes[3], epoch=int(partes[4]),
        )
    except ValueError:
        return None


def _permanente_devido(historico: list[RegistroUso]) -> bool:
    """True quando os ultimos _JANELA_PROPORCAO_PERMANENTE registros foram todos de origem
    perecivel -- hora de dar prioridade a algo permanente (ver Fase F)."""
    recentes = historico[:_JANELA_PROPORCAO_PERMANENTE]
    if len(recentes) < _JANELA_PROPORCAO_PERMANENTE:
        return False
    return all(r.origem in ORIGENS_PERECIVEIS for r in recentes)


def ajustar_score(score_base: float, *, origem: str, tag_principal: str, historico: list[RegistroUso]) -> float:
    """Historico vem do mais recente pro mais antigo (mesma ordem de LPUSH). Devolve o score
    ajustado -- nunca filtra, so' reordena (ver principio no docstring do modulo)."""
    score = score_base

    ultimos_dois = historico[:_MAX_CONSECUTIVOS_MESMA_ORIGEM]
    if len(ultimos_dois) == _MAX_CONSECUTIVOS_MESMA_ORIGEM and all(r.origem == origem for r in ultimos_dois):
        score -= _PENALIDADE_ORIGEM_REPETIDA

    if tag_principal:
        agora = datetime.datetime.now(datetime.timezone.utc).timestamp()
        contagem_tag = sum(
            1 for r in historico
            if r.tag_principal == tag_principal and (agora - r.epoch) <= _JANELA_TAG_SEGUNDOS
        )
        if contagem_tag >= _MAX_MESMA_TAG_POR_HORA:
            score -= _PENALIDADE_TAG_SATURADA

    if origem in ORIGENS_PERMANENTES and _permanente_devido(historico):
        score += _BONUS_PERMANENTE_DEVIDO

    return score
