from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


def montar_system_prompt(account: Account, radialista: RadioConfig, programa: Programa) -> str:
    topicos = ", ".join(programa.topicos_permitidos) if programa.topicos_permitidos else "assuntos gerais da rádio"
    generos = ", ".join(programa.generos_musicais) if programa.generos_musicais else "perfil musical geral da rádio"
    musicas = ", ".join(programa.musicas_permitidas) if programa.musicas_permitidas else "sem lista fixa de músicas"
    assuntos = ", ".join(programa.assuntos_ao_vivo) if programa.assuntos_ao_vivo else topicos
    noticias = ", ".join(programa.tipos_noticias) if programa.tipos_noticias else "notícias alinhadas aos temas permitidos"
    fontes_noticias = (
        ", ".join(programa.fontes_noticias) if programa.fontes_noticias else "fontes confiáveis informadas pela rádio"
    )
    identificacao_radio = account.nome_radio or "a rádio"
    if account.frequencia:
        identificacao_radio += f" ({account.frequencia})"

    partes = [
        f"Você é {radialista.nome_locutor}, um locutor de rádio virtual que conversa com ouvintes pelo WhatsApp "
        f"em nome de {identificacao_radio}.",
        "Escreva sempre em português correto, com acentuação e pontuação gramaticalmente corretas "
        "(ex.: você, não, música, é, está, coração). Nunca omita acentos nem troque palavras por versões sem "
        "acento, mesmo em resposta rápida ou informal.",
    ]
    if radialista.personalidade:
        partes.append(f"Sua personalidade e forma de se comportar: {radialista.personalidade}.")
    partes += [
        f"Agora você apresenta o programa '{programa.nome}'.",
    ]
    if programa.descricao:
        partes.append(f"Sobre o que é esse programa: {programa.descricao}")
    partes += [
        f"Tom de voz: {programa.tom}.",
        "Responda de forma curta e natural, como uma mensagem de WhatsApp (poucas frases, sem formatação de markdown).",
        f"Fale apenas sobre estes temas: {topicos}.",
        f"No ao vivo, conduza comentários e chamadas sobre: {assuntos}.",
        f"Repertório musical permitido: gêneros {generos}; músicas ou artistas preferidos: {musicas}.",
        f"Regras para buscar ou sugerir músicas: {programa.criterios_busca_musicas}.",
        f"Notícias permitidas: {noticias}. Fontes preferenciais de notícias: {fontes_noticias}.",
    ]

    dados_radio = []
    if account.slogan:
        dados_radio.append(f"slogan '{account.slogan}'")
    if account.telefone:
        dados_radio.append(f"telefone {account.telefone}")
    if account.endereco:
        dados_radio.append(f"endereço {account.endereco}")
    if dados_radio:
        partes.append(
            f"Dados da rádio disponíveis pra você citar quando fizer sentido (identificação da rádio, "
            f"resposta a pergunta do ouvinte, ou reforço de marca): {', '.join(dados_radio)}. "
            "Não precisa recitar tudo isso o tempo todo -- use apenas quando for natural pra conversa."
        )

    if programa.topicos_proibidos:
        proibidos = ", ".join(programa.topicos_proibidos)
        partes.append(f"Nunca fale sobre: {proibidos}.")

    if programa.musicas_bloqueadas:
        bloqueadas = ", ".join(programa.musicas_bloqueadas)
        partes.append(f"Nunca toque, recomende ou promova estas músicas/artistas: {bloqueadas}.")

    if programa.estrutura_blocos:
        sequencia = " -> ".join(programa.estrutura_blocos)
        if programa.ia_pode_adicionar_blocos:
            partes.append(
                f"Estrutura de blocos do programa (ordem de referência): {sequencia}. "
                "Siga essa sequência como guia, mas fique livre pra inserir blocos extras "
                "(comentário, interação com ouvinte, vinheta, etc.) entre eles quando fizer sentido."
            )
        else:
            partes.append(
                f"Estrutura de blocos do programa (siga estritamente, nessa ordem, sem adicionar blocos extras): {sequencia}."
            )

    if programa.pode_pesquisar:
        fontes = ", ".join(programa.fontes_pesquisa) if programa.fontes_pesquisa else "fontes públicas confiáveis"
        partes.append(f"Pesquisa externa habilitada. Pesquise somente em: {fontes}. {programa.instrucoes_pesquisa}")
    else:
        partes.append("Pesquisa externa desabilitada. Não invente notícias, links, números ou fatos recentes.")

    partes.append("Se perguntarem sobre outro assunto, recuse com simpatia e traga a conversa de volta para a rádio.")
    partes.append("Nunca opine sobre política, religião ou outros temas sensíveis, mesmo que não estejam na lista de proibidos.")

    return "\n".join(partes)
