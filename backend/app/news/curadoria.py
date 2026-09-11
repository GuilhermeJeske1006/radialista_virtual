"""Curadoria editorial de item de feed (ver app.news.feeds.ItemFeed): enquadra numa categoria
fixa, atribui score de noticiabilidade e extrai os campos da "lauda" (ver
app.news.pauta.montar_lauda) que a locucao vai efetivamente usar -- tudo numa unica chamada ao
CLASSIFICATION_MODEL (haiku), mesmo padrao de custo de app.llm.client.classificar_categoria_bloco.

Roda uma vez por item, no worker (ver app.news.worker), nunca no caminho de fala. A restricao
por topico proibido ESPECIFICO de cada programa (Programa.topicos_proibidos) acontece depois,
por programa, em app.news.pauta -- aqui so' aplica o filtro universal (TERMOS_SEMPRE_BLOQUEADOS
e a regra de disputa politico-partidaria, validas pra qualquer radio).
"""

import dataclasses
import logging

from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS
from app.llm.client import gerar_classificacao
from app.llm.json_utils import extrair_json
from app.news.feeds import ItemFeed

logger = logging.getLogger("radialista.news.curadoria")

CATEGORIAS_NOTICIA = (
    "seguranca",
    "transito",
    "clima_defesa_civil",
    "saude",
    "economia",
    "servico_publico",
    "agenda_cultura",
    "geral",
)


@dataclasses.dataclass
class ResultadoCuradoria:
    categoria: str
    score: float
    quando: str = ""
    onde: str = ""
    numeros: str = ""
    pessoas: str = ""
    impacto: str = ""
    servico: str = ""
    proximo_passo: str = ""
    ainda_nao_divulgado: str = ""


_SYSTEM_PROMPT = (
    "Você é o editor de pauta de uma rádio brasileira. Recebe título, resumo, fonte e cidade de "
    "um item de feed de notícias e decide se ele vira pauta pra locução ao vivo.\n"
    "Enquadre numa categoria: " + ", ".join(CATEGORIAS_NOTICIA) + " (use 'geral' se não encaixar "
    "em nenhuma específica).\n"
    "Dê um score de 0 a 100 de noticiabilidade pra rádio LOCAL: proximidade da cidade informada, "
    "impacto no dia a dia do ouvinte, atualidade. Notícia nacional sem gancho local pontua baixo.\n"
    "Extraia, só com o que estiver no texto (nunca invente): quando aconteceu, onde, números "
    "arredondados relevantes, pessoas/cargos citados, o impacto prático pro ouvinte, serviço "
    "(o que o ouvinte deve fazer, se houver), o próximo passo da apuração (se houver) e o que "
    "ainda não foi divulgado/confirmado (se aplicável). Campo sem informação real vira string vazia.\n"
    "Bloqueie (bloqueada=true) conteúdo sobre disputa político-partidária, declaração de "
    "candidato, pesquisa eleitoral, ou que exponha vítima de crime ou menor de idade pelo nome. "
    "Ato administrativo e serviço público (obra, decreto, boletim oficial, calendário) NÃO é "
    "disputa partidária e não deve ser bloqueado por isso.\n"
    "Bloqueie também item que é só chamada pra consumir conteúdo em outro lugar -- resumo de "
    "vídeos do dia, galeria de fotos, \"ao vivo: acompanhe a transmissão\", proginha de TV/rádio "
    "reempacotado -- sem nenhum fato noticioso próprio, específico e datável. Isso não é pauta, "
    "é chamada de audiência pro outro canal da fonte.\n"
    "Responda APENAS com um JSON compacto, sem markdown:\n"
    '{"bloqueada": true|false, "categoria": "...", "score": 0, "quando": "", "onde": "", '
    '"numeros": "", "pessoas": "", "impacto": "", "servico": "", "proximo_passo": "", '
    '"ainda_nao_divulgado": ""}'
)


def _bloqueada_por_termo_universal(item: ItemFeed) -> bool:
    texto = f"{item.titulo} {item.resumo}".lower()
    return any(termo.lower() in texto for termo in TERMOS_SEMPRE_BLOQUEADOS)


def curar_item(item: ItemFeed, *, fonte_nome: str, fonte_tipo: str, cidade: str, peso_fonte: float = 1.0) -> ResultadoCuradoria | None:
    """Devolve None quando o item deve ser descartado (termo bloqueado, disputa partidária,
    exposição de vítima/menor, ou falha na classificação -- fail-closed: item duvidoso não vira
    pauta, mesma política de app.guardrails.content_filter.avaliar_adequacao_programa)."""
    if _bloqueada_por_termo_universal(item):
        return None

    mensagem = (
        f"Título: {item.titulo}\nResumo: {item.resumo}\nFonte: {fonte_nome} ({fonte_tipo})\nCidade: {cidade or 'não informada'}"
    )
    try:
        resposta = gerar_classificacao(_SYSTEM_PROMPT, mensagem, max_tokens=700)
        dados = extrair_json(resposta)
    except Exception:
        logger.warning("Falha ao curar item de feed: titulo=%r", item.titulo, exc_info=True)
        return None

    if not isinstance(dados, dict) or dados.get("bloqueada"):
        return None

    categoria = str(dados.get("categoria") or "geral").strip().lower()
    if categoria not in CATEGORIAS_NOTICIA:
        categoria = "geral"

    try:
        score = float(dados.get("score") or 0) * peso_fonte
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(100.0, score))

    return ResultadoCuradoria(
        categoria=categoria,
        score=score,
        quando=str(dados.get("quando") or ""),
        onde=str(dados.get("onde") or ""),
        numeros=str(dados.get("numeros") or ""),
        pessoas=str(dados.get("pessoas") or ""),
        impacto=str(dados.get("impacto") or ""),
        servico=str(dados.get("servico") or ""),
        proximo_passo=str(dados.get("proximo_passo") or ""),
        ainda_nao_divulgado=str(dados.get("ainda_nao_divulgado") or ""),
    )
