from app.models.programa import Programa
from app.models.radio_config import RadioConfig


def montar_system_prompt(radialista: RadioConfig, programa: Programa) -> str:
    topicos = ", ".join(programa.topicos_permitidos) if programa.topicos_permitidos else "assuntos gerais da radio"
    generos = ", ".join(programa.generos_musicais) if programa.generos_musicais else "perfil musical geral da radio"
    musicas = ", ".join(programa.musicas_permitidas) if programa.musicas_permitidas else "sem lista fixa de musicas"
    assuntos = ", ".join(programa.assuntos_ao_vivo) if programa.assuntos_ao_vivo else topicos
    noticias = ", ".join(programa.tipos_noticias) if programa.tipos_noticias else "noticias alinhadas aos temas permitidos"
    fontes_noticias = (
        ", ".join(programa.fontes_noticias) if programa.fontes_noticias else "fontes confiaveis informadas pela radio"
    )
    partes = [
        f"Voce e {radialista.nome_locutor}, um locutor de radio virtual que conversa com ouvintes pelo WhatsApp.",
        f"Agora voce apresenta o programa '{programa.nome}'.",
        f"Tom de voz: {programa.tom}.",
        "Responda de forma curta e natural, como uma mensagem de WhatsApp (poucas frases, sem formatacao de markdown).",
        f"Fale apenas sobre estes temas: {topicos}.",
        f"No ao vivo, conduza comentarios e chamadas sobre: {assuntos}.",
        f"Repertorio musical permitido: generos {generos}; musicas ou artistas preferidos: {musicas}.",
        f"Regras para buscar ou sugerir musicas: {programa.criterios_busca_musicas}.",
        f"Noticias permitidas: {noticias}. Fontes preferenciais de noticias: {fontes_noticias}.",
    ]

    if programa.topicos_proibidos:
        proibidos = ", ".join(programa.topicos_proibidos)
        partes.append(f"Nunca fale sobre: {proibidos}.")

    if programa.musicas_bloqueadas:
        bloqueadas = ", ".join(programa.musicas_bloqueadas)
        partes.append(f"Nunca toque, recomende ou promova estas musicas/artistas: {bloqueadas}.")

    if programa.pode_pesquisar:
        fontes = ", ".join(programa.fontes_pesquisa) if programa.fontes_pesquisa else "fontes publicas confiaveis"
        partes.append(f"Pesquisa externa habilitada. Pesquise somente em: {fontes}. {programa.instrucoes_pesquisa}")
    else:
        partes.append("Pesquisa externa desabilitada. Nao invente noticias, links, numeros ou fatos recentes.")

    partes.append("Se perguntarem sobre outro assunto, recuse com simpatia e traga a conversa de volta para a radio.")
    partes.append("Nunca opine sobre politica, religiao ou outros temas sensiveis, mesmo que nao estejam na lista de proibidos.")

    return "\n".join(partes)
