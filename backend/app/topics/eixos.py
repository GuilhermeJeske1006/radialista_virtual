"""Eixos de abordagem de um assunto (ver Fase E do plano-assuntos.md e ADR item 1): o que gira
quando o mesmo gancho volta a ser pauta, no lugar do bloqueio total de tema que existia antes
(ver _historico_temas em app.live.router). Mesmo papel que ANGULOS_NOTICIA (app.news.pauta)
cumpre pra noticia -- aqui pro assunto de comentario.

A escolha do eixo efetivo e' sempre prompt-time (ver app.topics.pauta_conversa), nunca decidida
no matcher: o matcher so' sugere um cardapio (AssuntoPrograma.eixos_sugeridos, ver
app.topics.matcher) de quais eixos este gancho rende bem pra este programa.
"""

EIXOS_ASSUNTO: tuple[str, ...] = ("fato", "impacto", "memoria", "pergunta", "servico", "curiosidade")

# Quantas vezes no maximo o mesmo Assunto pode voltar a ser pauta de comentario numa mesma
# sessao ao vivo, girando de eixo a cada volta -- ver Fase E / ADR item 6. Igual ao espirito de
# MAX_REPETICOES_POR_NOTICIA (app.news.pauta), mas deliberadamente menor que len(EIXOS_ASSUNTO):
# nem todo gancho rende os 6 eixos (ver eixos_sugeridos), e a rotacao entre POOL de assuntos
# importa mais aqui do que esgotar todo o cardapio de um so.
MAX_RETORNOS_POR_ASSUNTO = 3

# Instrucao de prompt injetada como sufixo do briefing (ver app.topics.pauta_conversa.
# montar_pauta_assunto) -- mesmo padrao do "ANGULO DESTE BLOCO" em app.news.pauta.montar_lauda:
# o fato/briefing e' sempre o mesmo, so' a instrucao de abordagem muda.
INSTRUCAO_EIXO: dict[str, str] = {
    "fato": "Apresente o gancho em si, direto, como quem informa algo novo pro ouvinte.",
    "impacto": "Foque no que isso muda na pratica pro dia a dia de quem ouve, nao no dado frio em si.",
    "memoria": "Puxe pelo lado afetivo -- uma lembranca, uma sensacao, uma associacao pessoal, nao o fato cru.",
    "pergunta": "Feche abrindo uma pergunta real pro ouvinte responder (WhatsApp/redes) -- gancho pra interacao.",
    "servico": "Traga como utilidade pratica -- o que fazer, aonde ir, o que evitar por causa disso.",
    "curiosidade": "Trate como curiosidade leve, tom de 'voce sabia', sem peso de noticia ou opiniao.",
}
