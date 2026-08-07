import json
import logging

from app.llm.client import gerar_classificacao
from app.models.radio_config import RadioConfig

logger = logging.getLogger("radialista.intent")

ACOES_VALIDAS = {"abraco", "musica", "guardar"}


def classificar_intencao(config: RadioConfig, texto_usuario: str) -> tuple[str, str | None]:
    """Classifica a mensagem do ouvinte pra uma acao de bastidor -- o bot nunca responde no WhatsApp.

    Retorna (acao, musica_query):
    - "musica": ouvinte pediu uma musica/artista/dedicatoria -> entra na fila pra tocar ao vivo.
    - "abraco": ouvinte mandou recado/saudacao/desabafo que merece um alo ao vivo.
    - "guardar": fora de escopo, spam ou nao faz sentido ler no ar -- so fica registrado.
    """
    system_prompt = "\n".join(
        [
            f"Voce e o assistente de bastidores de {config.nome_locutor}, uma radio.",
            "Um ouvinte mandou mensagem no WhatsApp da radio. O bot NUNCA responde direto no WhatsApp.",
            "Sua unica tarefa: classificar a mensagem numa acao de bastidor pro locutor usar ao vivo.",
            '- "musica": pede uma musica, artista ou dedicatoria musical especifica.',
            '- "abraco": manda recado, saudacao, elogio ou desabafo que merece um alo ao vivo '
            "(locutor vai falar o nome dele e comentar o que ele mandou).",
            '- "guardar": fora do escopo da radio, spam, ou nao faz sentido ler ao vivo.',
            "Responda APENAS com um JSON compacto, sem markdown e sem explicacao:",
            '{"acao": "musica|abraco|guardar", "musica_query": "artista/musica pedida ou null"}',
        ]
    )

    try:
        texto_resposta = gerar_classificacao(system_prompt, texto_usuario)
    except Exception:
        logger.exception("Falha ao classificar intencao, usando fallback 'guardar'")
        return "guardar", None

    try:
        dados = json.loads(texto_resposta)
        acao = dados.get("acao")
        if acao not in ACOES_VALIDAS:
            raise ValueError(f"acao invalida: {acao!r}")
        musica_query = dados.get("musica_query")
        return acao, (str(musica_query) if musica_query else None)
    except (json.JSONDecodeError, AttributeError, ValueError):
        logger.warning("Resposta de classificacao invalida: %r", texto_resposta)
        return "guardar", None
