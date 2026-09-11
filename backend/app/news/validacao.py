"""Rede de seguranca de redação do bloco de notícia (ver Fase 3 do plano de jornalismo):
detecta a fala de IA se narrando ("fico só no que está confirmado") em vez de noticiar, e a
fala sem atribuição de fonte -- os dois erros mais frequentes quando o locutor tem pauta mas
não tem redação jornalística. Consultado por app.live.router junto da checagem de
similaridade já existente, reaproveitando o mesmo retry único (sem custo extra de rodada)."""

# Frases-sintoma de locutor narrando a própria regra em vez de noticiar (ver Fase 2.4 do plano:
# "o não-dito se reporta como fato sobre a apuração, nunca como disclaimer sobre o locutor").
FRASES_PROIBIDAS_NOTICIA = (
    "sem especular",
    "só no que está confirmado",
    "no que foi confirmado",
    "não posso afirmar",
    "não posso confirmar",
    "não tenho como confirmar",
    "quando tiver mais informação",
    "assim que tiver novidade",
    "prefiro não opinar",
    "não vou entrar no mérito",
    "não tenho notícia",
    "sem notícia nova",
)

# Marcadores de atribuição -- pelo menos um precisa aparecer na fala pra contar como fonte
# citada (ver Fase 3, regra 2: "a atribuição vem ANTES do fato, sempre").
MARCADORES_ATRIBUICAO = (
    "segundo",
    "de acordo com",
    "informou",
    "confirmou",
    "divulgou",
    "anunciou",
    "afirmou",
    "apurou",
    "revelou",
)


def frase_proibida_em(texto: str) -> str | None:
    """Devolve a frase proibida encontrada (pra citar explicitamente no retry) ou None."""
    normalizado = texto.lower()
    for frase in FRASES_PROIBIDAS_NOTICIA:
        if frase in normalizado:
            return frase
    return None


def tem_atribuicao(texto: str) -> bool:
    """Atribuição a quem informou o fato (autoridade/órgão citado na apuração, ex.: 'a Defesa
    Civil informou...') -- nunca ao veículo/portal de onde a notícia foi coletada (ver
    app.news.pauta, que não expõe mais Noticia.fonte_nome no prompt pra evitar isso)."""
    normalizado = texto.lower()
    return any(marcador in normalizado for marcador in MARCADORES_ATRIBUICAO)
