"""Explode um item bruto (noticia, contexto de musica, agenda...) em ganchos de conversa -- ver
Fase B do plano-assuntos.md. Uma chamada ao CLASSIFICATION_MODEL por item, mesmo padrao de custo
de app.news.curadoria.curar_item, rodando so' no worker (ver app.topics.pipeline), nunca no
caminho de fala.

Devolve lista vazia (nunca inventa gancho) quando o texto de origem nao tem materia real
suficiente -- mesma disciplina de app.llm.client.resumir_contexto_musica: melhor nenhum gancho
que um gancho fabricado sem fato por tras.
"""

import dataclasses
import logging

from app.llm.client import gerar_classificacao
from app.llm.json_utils import extrair_json

logger = logging.getLogger("radialista.topics.derivador")

_MAX_GANCHOS_POR_ITEM = 5


@dataclasses.dataclass
class GanchoDerivado:
    titulo: str
    gancho: str
    fatos: list[str]
    tags: list[str]
    pergunta_ouvinte: str = ""


_SYSTEM_PROMPT = (
    "Voce e' produtor de pauta de uma radio brasileira. Recebe um fato ou contexto real (noticia, "
    "historia de uma musica, agenda da cidade) e precisa explode-lo em ganchos de CONVERSA pro "
    "locutor comentar no ar -- nao em manchetes, em ideias de papo.\n"
    "Um gancho de conversa tem: um angulo especifico do fato (nao repita o fato inteiro em cada "
    "gancho, cada um pega um pedaco/consequencia/lado diferente), fatos reais que sustentam esse "
    "angulo (SO' do texto fornecido, nunca invente numero, nome ou dado que nao esteja ali), tags "
    "curtas (temas/publicos que esse gancho toca, ex.: trabalho, familia, transito, praia, musica) "
    "e, quando fizer sentido, uma pergunta pronta pra jogar pro ouvinte responder.\n"
    f"Gere de 1 a {_MAX_GANCHOS_POR_ITEM} ganchos, cada um genuinamente diferente dos outros -- "
    "nao varie so' a redacao do mesmo angulo. Se o texto fornecido nao tiver materia real "
    "suficiente pra nenhum gancho honesto, responda exatamente 'insuficiente', sem mais nada.\n"
    "Responda APENAS com um JSON compacto (lista), sem markdown, sem comentario:\n"
    '[{"titulo": "", "gancho": "", "fatos": [""], "tags": [""], "pergunta_ouvinte": ""}]'
)


def derivar_ganchos(texto_fonte: str, *, contexto: str = "") -> list[GanchoDerivado]:
    """`texto_fonte` e' o material bruto (titulo+resumo da noticia, contexto da musica etc.).
    `contexto` e' informacao auxiliar opcional (ex.: cidade da conta) que ajuda o modelo a avaliar
    relevancia sem virar fato em si."""
    mensagem = texto_fonte if not contexto else f"{texto_fonte}\n\nContexto adicional: {contexto}"
    try:
        resposta = gerar_classificacao(_SYSTEM_PROMPT, mensagem, max_tokens=1200)
    except Exception:
        logger.warning("Falha ao derivar ganchos de assunto", exc_info=True)
        return []

    resposta = resposta.strip()
    if not resposta or resposta.lower().startswith("insuficiente"):
        return []

    try:
        dados = extrair_json(resposta)
    except Exception:
        logger.warning("Resposta do derivador nao e' JSON valido: %r", resposta[:200])
        return []

    if not isinstance(dados, list):
        return []

    ganchos = []
    for item in dados[:_MAX_GANCHOS_POR_ITEM]:
        if not isinstance(item, dict):
            continue
        gancho_texto = str(item.get("gancho") or "").strip()
        titulo = str(item.get("titulo") or "").strip()
        if not gancho_texto or not titulo:
            continue
        fatos = [str(f).strip() for f in (item.get("fatos") or []) if str(f).strip()]
        tags = [str(t).strip().lower() for t in (item.get("tags") or []) if str(t).strip()]
        ganchos.append(
            GanchoDerivado(
                titulo=titulo,
                gancho=gancho_texto,
                fatos=fatos,
                tags=tags,
                pergunta_ouvinte=str(item.get("pergunta_ouvinte") or "").strip(),
            )
        )
    return ganchos
