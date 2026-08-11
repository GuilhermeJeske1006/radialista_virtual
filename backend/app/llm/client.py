import logging

from anthropic import Anthropic

from app.config.settings import settings

logger = logging.getLogger("radialista.llm")

_client = Anthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-opus-5"
CLASSIFICATION_MODEL = "claude-haiku-4-5"


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
        logger.warning("LLM recusou gerar resposta")
        return "Desculpa, nao posso responder isso por aqui. Bora falar de outro assunto?"

    for block in response.content:
        if block.type == "text":
            return block.text

    return "Desculpa, nao consegui gerar uma resposta agora. Tenta de novo em instantes."


def gerar_classificacao(system_prompt: str, mensagem_usuario: str) -> str:
    """Chamada enxuta ao LLM pra classificacao de intencao (nao gera resposta pro usuario)."""
    response = _client.messages.create(
        model=CLASSIFICATION_MODEL,
        max_tokens=128,
        system=system_prompt,
        messages=[{"role": "user", "content": mensagem_usuario}],
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    return ""


def gerar_configuracao(system_prompt: str, mensagem_usuario: str) -> str:
    """Chamada ao LLM pra gerar configuracao estruturada (JSON) de radialista/programa.

    Usa mais max_tokens que gerar_classificacao pois o JSON de saida e rico (dezenas de campos).
    """
    response = _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
        system=system_prompt,
        messages=[{"role": "user", "content": mensagem_usuario}],
    )

    if response.stop_reason == "refusal":
        logger.warning("LLM recusou gerar configuracao")
        return ""

    for block in response.content:
        if block.type == "text":
            return block.text

    return ""


_TONS_VALIDOS = ("energico", "calmo", "neutro")

_TOM_SYSTEM_PROMPT = (
    "Classifique a intensidade emocional de uma fala de locutor de radio, pra ajustar a prosodia "
    "da voz sintetizada. Responda com exatamente uma palavra, sem pontuacao e sem explicacao: "
    "'energico' se a fala pede empolgacao, entusiasmo ou ritmo acelerado; 'calmo' se pede tom "
    "sereno, reflexivo ou pausado; 'neutro' se nao pede nem uma coisa nem outra."
)


_CATEGORIAS_BLOCO_VALIDAS = ("musica", "noticia", "chamada_ouvinte", "abertura", "comentario", "encerramento", "outro")

_CATEGORIA_BLOCO_SYSTEM_PROMPT = (
    "Classifique o nome de um bloco de programacao de radio numa destas categorias, respondendo "
    "com exatamente uma palavra dentre elas, sem pontuacao e sem explicacao:\n"
    "- musica: o bloco existe pra tocar uma faixa ou estilo musical, mesmo com nome de genero "
    "regional ou informal (ex.: 'Musica Vaneira', 'chamame e xote', 'bloco sertanejo raiz', "
    "'forro pé de serra', 'pagode do bom');\n"
    "- noticia: bloco de noticias, informe ou atualidades;\n"
    "- chamada_ouvinte: bloco de interacao com o ouvinte (recado, pedido, WhatsApp);\n"
    "- abertura: bloco de abertura/largada do programa;\n"
    "- comentario: bloco de comentario livre do locutor;\n"
    "- encerramento: bloco de despedida/fechamento do programa;\n"
    "- outro: nao se encaixa em nenhuma categoria acima, e fica como bloco livre."
)


def classificar_categoria_bloco(nome_bloco: str) -> str:
    """Classifica um nome de bloco customizado (ex.: 'chamame e xote') numa categoria conhecida,
    pra decidir se o bloco deve buscar musica de verdade, atender fila do whatsapp etc.

    So e chamado pra blocos que nao bateram com o prefixo exato de nenhuma categoria conhecida
    (ver app.live.router._categoria_bloco) -- nunca deve travar o ao vivo, entao qualquer falha
    ou resposta inesperada cai em 'outro' (bloco livre, comportamento atual sem essa categorizacao).
    """
    try:
        resposta = gerar_classificacao(_CATEGORIA_BLOCO_SYSTEM_PROMPT, nome_bloco)
    except Exception:
        logger.warning("Falha ao classificar categoria de bloco: %r", nome_bloco, exc_info=True)
        return "outro"

    resposta = resposta.strip().lower()
    for categoria in _CATEGORIAS_BLOCO_VALIDAS:
        if categoria in resposta:
            return categoria
    return "outro"


_TEMA_SYSTEM_PROMPT = (
    "Extraia o tema principal de uma fala de comentário ou notícia de locutor de rádio, em até "
    "quatro palavras, sem pontuação, sem explicação, sem aspas. Ex.: 'trânsito na cidade', "
    "'previsão do tempo', 'aniversário da rádio'."
)


def classificar_tema_fala(texto: str) -> str:
    """Extrai um rotulo curto do tema de uma fala de comentario/noticia, pra registrar no
    historico de temas da sessao (ver _historico_temas em app.live.router) -- a janela de
    historico enviada ao prompt so cobre as ultimas falas, entao sem isso o LLM nao tem como
    saber que ja comentou o mesmo assunto varios blocos atras. Nunca deve derrubar o ao vivo:
    qualquer falha cai em string vazia (chamador simplesmente nao registra tema nenhum).
    """
    try:
        resposta = gerar_classificacao(_TEMA_SYSTEM_PROMPT, texto)
    except Exception:
        logger.warning("Falha ao classificar tema da fala", exc_info=True)
        return ""
    return resposta.strip().strip(".").lower()


def classificar_tom_fala(texto: str, tipo_bloco: str | None) -> str:
    """Classifica o tom da fala ja gerada (energico/calmo/neutro) pra modular a voz no TTS
    de acordo com o conteudo real da fala, nao so com o tipo de bloco. Nunca deve derrubar a
    geracao de audio -- em qualquer falha ou resposta inesperada, cai pra 'neutro'.
    """
    mensagem = f"Tipo de bloco: {tipo_bloco or 'desconhecido'}.\nFala: {texto}"
    try:
        resposta = gerar_classificacao(_TOM_SYSTEM_PROMPT, mensagem)
    except Exception:
        logger.warning("Falha ao classificar tom da fala", exc_info=True)
        return "neutro"

    resposta = resposta.strip().lower()
    for tom in _TONS_VALIDOS:
        if tom in resposta:
            return tom
    return "neutro"


_CONTEXTO_MUSICA_SYSTEM_PROMPT = (
    "Voce recebe metadados de um video do YouTube que e uma musica (titulo, canal/artista, ano "
    "de publicacao, tags e descricao, quando existirem). Resuma em ate duas frases curtas um "
    "contexto real que um locutor de radio possa citar ao anunciar essa musica -- tema da letra, "
    "historia por tras dela, curiosidade real, ano. Use SOMENTE informacao que apareca no texto "
    "fornecido: nunca invente fato, data, premio ou curiosidade que voce nao tenha certeza de ter "
    "visto ali. Se nao houver informacao real suficiente pra dizer algo com confianca, responda "
    "exatamente 'insuficiente', sem mais nada."
)


def resumir_contexto_musica(titulo: str, canal: str, descricao: str, tags: list[str], ano: str | None) -> str:
    """Resume contexto real (tema/curiosidade) de uma musica a partir dos metadados do YouTube
    (ver _buscar_metadados_musica em app.live.music), pra injetar no prompt antes do locutor
    anunciar a faixa (ver _contexto_musica em app.live.router) -- em vez dele so' saber
    titulo/canal. O prompt e' estrito sobre so' usar o que foi fornecido e devolver
    'insuficiente' quando nao da, porque metadado de video costuma ser escasso e inventar fato
    sobre a musica (ano errado, premio que ela nunca ganhou) e pior que nao dizer nada.
    """
    mensagem = (
        f"Titulo: {titulo}\nCanal/artista: {canal}\nAno de publicacao: {ano or 'desconhecido'}\n"
        f"Tags: {', '.join(tags) if tags else 'nenhuma'}\nDescricao: {descricao or 'nenhuma'}"
    )
    try:
        resposta = gerar_classificacao(_CONTEXTO_MUSICA_SYSTEM_PROMPT, mensagem)
    except Exception:
        logger.warning("Falha ao resumir contexto de musica: titulo=%r", titulo, exc_info=True)
        return ""

    resposta = resposta.strip()
    if not resposta or resposta.lower().startswith("insuficiente"):
        return ""
    return resposta
