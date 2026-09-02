"""Catalogo fechado de tipos de radio pre-definidos.

Usado como perfil padrao nas geracoes via IA (app/llm/config_generator.py) quando o
usuario nao descreve o programa, ou pra enriquecer uma descricao curta. `Account.tipo_radio`
guarda o `value` escolhido -- ver app/models/account.py.
"""

TIPOS_RADIO: list[dict] = [
    {
        "value": "sertaneja",
        "label": "Sertaneja / Country",
        "contexto_prompt": (
            "Radio de perfil sertanejo (raiz e universitario). Generos: sertanejo raiz, "
            "sertanejo universitario, modao. Tom caloroso, regional, proximo do ouvinte do "
            "interior. Blocos comuns: recado/dedicatoria ao ouvinte, chamada de musica, "
            "comentario sobre o dia a dia da roca/cidade pequena."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: Jorge & Mateus, Ze Neto & Cristiano, Marilia "
            "Mendonca, Chitaozinho & Xororo. Ex. de topicos: vida no campo, festa do peao, "
            "colheita, dedicatoria pro trabalhador rural."
        ),
    },
    {
        "value": "gospel",
        "label": "Gospel / Crista",
        "contexto_prompt": (
            "Radio de perfil gospel/crista. Generos: musica gospel, louvor e adoracao. Tom "
            "acolhedor e edificante. Evita temas sensiveis fora da fe. Foco em mensagens de "
            "esperanca, fe e superacao. Topicos proibidos por padrao: politica partidaria e "
            "criticas a outras religioes."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: Aline Barros, Fernandinho, Gabriela Rocha, "
            "Thalles Roberto. Ex. de topicos: testemunho de fe, versiculo do dia, familia, "
            "superacao."
        ),
    },
    {
        "value": "jovem_pop",
        "label": "Jovem / Pop / Hits",
        "contexto_prompt": (
            "Radio de perfil jovem/pop. Generos: pop nacional e internacional, hits do momento. "
            "Tom animado e agil, linguagem informal e proxima. Interacao forte com o ouvinte via "
            "WhatsApp (pedidos de musica, enquetes). Blocos curtos e dinamicos."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: Anitta, Luisa Sonza, pop internacional atual "
            "(charts). Ex. de topicos: enquete relampago, top da semana, fofoca leve de "
            "celebridade, pedido de musica via WhatsApp."
        ),
    },
    {
        "value": "jornalismo_noticia",
        "label": "Jornalismo / Noticia",
        "contexto_prompt": (
            "Radio de perfil jornalistico/noticioso. Menos musica, mais blocos de noticia e "
            "comentario. Tom mais formal e informativo. Fontes de noticia sao obrigatorias em "
            "fontes_noticias/fontes_pesquisa. Topicos_permitidos devem cobrir atualidades, "
            "cidade/regiao e utilidade publica."
        ),
        "exemplos": (
            "Ex. de topicos concretos: transito da cidade, previsao do tempo, economia local, "
            "servico publico (saude, educacao). Ex. de fontes_noticias: agencias de noticia "
            "nacionais e portal de noticias da regiao."
        ),
    },
    {
        "value": "popular_mix",
        "label": "Popular / Variedades",
        "contexto_prompt": (
            "Radio popular de variedades, 'radio de cidade'. Mix de generos: sertanejo, pagode, "
            "forro, pop nacional. Tom caloroso e acessivel, publico familiar amplo (todas as "
            "idades). Blocos variados: musica, recado, noticia local, humor leve."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: sertanejo raiz, Thiaguinho e pagode romantico, "
            "forro pe de serra, Michel Telo. Ex. de topicos: recado de aniversario, noticia da "
            "cidade, dica de utilidade publica."
        ),
    },
    {
        "value": "regional_flashback",
        "label": "Regional / Retro / Flashback",
        "contexto_prompt": (
            "Radio de perfil retro/flashback. Generos: MPB, rock nacional e internacional dos "
            "anos 80/90, flashback. Tom nostalgico e tranquilo, publico adulto/idoso. Blocos "
            "com curiosidades sobre epocas e artistas classicos."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: Roberto Carlos, Legiao Urbana, Rita Lee, rock "
            "internacional anos 80. Ex. de topicos: curiosidade sobre a musica/artista, memoria "
            "afetiva, 'nessa data' historica."
        ),
    },
    {
        "value": "eletronica_dance",
        "label": "Eletronica / Dance / Balada",
        "contexto_prompt": (
            "Radio de perfil eletronico/dance. Generos: musica eletronica, funk, dance, remixes. "
            "Tom agitado e energico, linguagem jovem e informal. Blocos rapidos, foco em manter "
            "o clima animado."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: Alok, funk ostentacao, house/EDM internacional. "
            "Ex. de topicos: agenda de festa/balada, lancamento de remix, hit do momento nas "
            "pistas."
        ),
    },
    {
        "value": "mpb_variedades",
        "label": "MPB / Variedades",
        "contexto_prompt": (
            "Radio de perfil MPB/variedades. Generos: MPB, bossa nova, samba de raiz. Tom mais "
            "culto e tranquilo, comentarios com mais profundidade (cultura, musica, cotidiano). "
            "Publico adulto exigente."
        ),
        "exemplos": (
            "Ex. de artistas/generos concretos: Caetano Veloso, Tom Jobim, Elis Regina, Clara "
            "Nunes. Ex. de topicos: historia da musica brasileira, cultura, cotidiano com olhar "
            "mais reflexivo."
        ),
    },
]

_TIPOS_POR_VALUE = {t["value"]: t for t in TIPOS_RADIO}


def tipo_radio_valido(value: str | None) -> bool:
    return not value or value in _TIPOS_POR_VALUE


def contexto_prompt_tipo_radio(value: str | None) -> str | None:
    tipo = _TIPOS_POR_VALUE.get(value or "")
    if not tipo:
        return None
    contexto = tipo["contexto_prompt"]
    exemplos = tipo.get("exemplos")
    return f"{contexto} {exemplos}" if exemplos else contexto
