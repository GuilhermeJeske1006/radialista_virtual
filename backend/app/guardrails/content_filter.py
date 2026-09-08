import json
import logging

from app.llm.client import gerar_classificacao
from app.models.programa import Programa

logger = logging.getLogger("radialista.guardrails")

# Filtro de seguranca sempre ativo, independente da configuracao da radio.
TERMOS_SEMPRE_BLOQUEADOS = ["arma", "bomba", "suicidio", "droga ilicita"]


def contem_topico_proibido(texto: str, programa: Programa) -> bool:
    texto_lower = texto.lower()
    termos = list(programa.topicos_proibidos) + TERMOS_SEMPRE_BLOQUEADOS
    return any(termo.lower() in texto_lower for termo in termos)


def avaliar_adequacao_programa(texto: str, programa: Programa) -> tuple[bool, str]:
    """Segunda camada do guardrail, via LLM -- roda so' depois que contem_topico_proibido ja
    passou (aquela e' a rede de seguranca dura e barata, essa aqui e' julgamento). Pega intencao
    disfarcada, sarcasmo ou conteudo que so' e' problematico NESTE programa (ex.: piada pesada
    que cabe num programa informal e nao cabe num serio) -- coisa que comparacao literal de
    substring nao enxerga.

    Retorna (adequado, motivo). Falha do LLM cai pro lado seguro -- NAO libera (fail-closed) --
    e nunca propaga excecao pro webhook, mesmo padrao de custo controlado ja usado em
    classificar_categoria_bloco (app.live.router)."""
    topicos_proibidos = (
        ", ".join(programa.topicos_proibidos) if programa.topicos_proibidos else "nenhum especifico"
    )
    system_prompt = "\n".join(
        [
            f"Voce e' o guardrail de conteudo de um programa de radio. Tom do programa: {programa.tom}.",
            f"Topicos proibidos especificos deste programa: {topicos_proibidos}.",
            "Um ouvinte mandou uma mensagem pro WhatsApp da radio, que pode ir ao ar lida pelo "
            "locutor. Julgue se o CONTEUDO e' adequado pra ir ao ar NESTE programa especifico, "
            "considerando o tom dele -- nao so' comparacao literal de palavra, mas intencao "
            "disfarcada, sarcasmo, ou piada que cabe num programa e nao cabe em outro mais serio.",
            "Responda APENAS com um JSON compacto, sem markdown e sem explicacao:",
            '{"adequado": true|false, "motivo": "razao curta"}',
        ]
    )

    try:
        texto_resposta = gerar_classificacao(system_prompt, texto)
        dados = json.loads(texto_resposta)
        return bool(dados.get("adequado")), str(dados.get("motivo") or "")
    except Exception:
        logger.exception("Falha ao avaliar adequacao de conteudo via LLM, bloqueando por seguranca")
        return False, "falha_avaliacao_llm"


def avaliar_adequacao_ao_vivo(texto: str, programa: Programa) -> tuple[bool, str]:
    """Terceira camada, so' pra mensagem que veio de audio (nota de voz) E vai realmente ao ar
    (abraco/musica/sorteio) -- as duas camadas acima julgam TEMA a partir do texto transcrito,
    mas o STT (app.stt.client) devolve so' o texto: tom de voz agressivo, barulho de fundo ou
    audio de baixa qualidade nao aparecem no topico nem no tom, so' sobram como sinais indiretos
    na propria transcricao (escrita hostil, fragmentacao/incoerencia tipica de audio ruim).

    Retorna (apropriado, motivo). Falha do LLM cai pro lado seguro -- NAO libera (fail-closed) --
    mesmo padrao de avaliar_adequacao_programa."""
    system_prompt = "\n".join(
        [
            f"Voce e' o guardrail de qualidade de audio-ao-vivo de um programa de radio. Tom do "
            f"programa: {programa.tom}.",
            "Este texto e' a transcricao (STT) de uma nota de voz que um ouvinte mandou pro "
            "WhatsApp da radio -- esse pedido especifico vai ser lido/tocado ao vivo pelo "
            "locutor. Julgue se e' apropriado ir ao vivo AGORA, considerando sinais que sobram "
            "na transcricao mesmo sem ouvir o audio: tom agressivo ou hostil, ou fragmentacao/"
            "incoerencia tipica de audio com ruido de fundo ou qualidade muito baixa (nao "
            "confunda isso com erro normal de autocorretor de texto digitado -- aqui e' audio).",
            "Responda APENAS com um JSON compacto, sem markdown e sem explicacao:",
            '{"apropriado": true|false, "motivo": "razao curta"}',
        ]
    )

    try:
        texto_resposta = gerar_classificacao(system_prompt, texto)
        dados = json.loads(texto_resposta)
        return bool(dados.get("apropriado")), str(dados.get("motivo") or "")
    except Exception:
        logger.exception("Falha ao avaliar adequacao de audio ao vivo, bloqueando por seguranca")
        return False, "falha_avaliacao_llm"
