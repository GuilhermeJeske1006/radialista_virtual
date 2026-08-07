from anthropic import Anthropic

from app.config.settings import settings

_client = Anthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-opus-5"


def gerar_resposta(system_prompt: str, mensagem_usuario: str) -> str:
    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
        system=system_prompt,
        messages=[{"role": "user", "content": mensagem_usuario}],
    )

    if response.stop_reason == "refusal":
        return "Desculpa, nao posso responder isso por aqui. Bora falar de outro assunto?"

    for block in response.content:
        if block.type == "text":
            return block.text

    return "Desculpa, nao consegui gerar uma resposta agora. Tenta de novo em instantes."


def gerar_classificacao(system_prompt: str, mensagem_usuario: str) -> str:
    """Chamada enxuta ao LLM pra classificacao de intencao (nao gera resposta pro usuario)."""
    response = _client.messages.create(
        model=MODEL,
        max_tokens=128,
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
        system=system_prompt,
        messages=[{"role": "user", "content": mensagem_usuario}],
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    return ""
