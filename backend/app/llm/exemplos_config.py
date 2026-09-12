import json

# Exemplos curados (few-shot) pro prompt de geracao de programa via IA -- ver Fase 9 do plano de
# melhoria. Pra uma saida estruturada de ~25 campos com nuance de dominio, um exemplo bom vale
# mais que dez regras em texto. Os tres sao deliberadamente de formato bem diferente entre si, e
# todos mostram musicas_permitidas vazio e estrutura_blocos so' com vocabulario canonico (ver
# achados 6 e 7 do plano) -- exatamente o que a regra em texto tem mais dificuldade de garantir
# sozinha. Ver Fase 10: o plano e' trocar isso por configuracoes REAIS aceitas pelos clientes
# assim que o loop de aprendizado (app.models.geracao_ia.GeracaoIA) acumular dado suficiente.
_EXEMPLOS = [
    {
        "descricao_usuario": "programa sertanejo pra tocar de manha, publico trabalhador, bastante musica",
        "saida": {
            "nome": "Trilha da Madrugada",
            "descricao": "Programa matinal sertanejo pro trabalhador que sai cedo de casa rumo ao servico.",
            "dias_semana": [0, 1, 2, 3, 4],
            "horario_inicio": "05:00",
            "horario_fim": "08:00",
            "tom": "caloroso e animado sem exagero, como um amigo que ja conhece a rotina do ouvinte",
            "topicos_permitidos": ["vida no campo", "trabalho", "familia", "futebol de fim de semana"],
            "topicos_proibidos": ["politica", "religiao"],
            "estrutura_blocos": ["abertura", "musica", "musica", "chamada_ouvinte", "musica", "comentario", "musica"],
            "perfil_programacao": "padrao",
            "generos_musicais": ["sertanejo raiz", "sertanejo universitario", "modao"],
            "musicas_permitidas": [],
            "musicas_bloqueadas": [],
            "criterios_busca_musicas": "priorizar sertanejo raiz e classicos, evitar remixes eletronicos",
            "fontes_noticias": [],
            "fontes_pesquisa": [],
            "perfil": "musical",
            "dose_noticia": "pitada",
        },
    },
    {
        "descricao_usuario": "radiojornal do meio dia, bem informativo, direto ao ponto",
        "saida": {
            "nome": "Jornal do Meio-Dia",
            "descricao": "Boletim informativo do meio-dia com as principais noticias da regiao.",
            "dias_semana": [0, 1, 2, 3, 4],
            "horario_inicio": "12:00",
            "horario_fim": "13:00",
            "tom": "serio e direto, sem sensacionalismo, como um apresentador de telejornal regional",
            "topicos_permitidos": ["politica local", "economia", "seguranca publica", "servico publico"],
            "topicos_proibidos": ["fofoca", "boato nao confirmado"],
            "estrutura_blocos": ["abertura", "escalada", "noticia", "noticia", "servico", "giro", "encerramento"],
            "perfil_programacao": "padrao",
            "generos_musicais": [],
            "musicas_permitidas": [],
            "musicas_bloqueadas": [],
            "fontes_noticias": [],
            "pode_pesquisar": True,
            "fontes_pesquisa": [],
            "instrucoes_pesquisa": "priorizar noticias das ultimas 24h, confirmar data e atribuir a fonte",
            "perfil": "jornalismo",
            "dose_noticia": "jornalistica",
        },
    },
    {
        "descricao_usuario": "programa noturno romantico, bastante interacao com ouvinte, pedidos e dedicatorias",
        "saida": {
            "nome": "Boa Noite, Coracao",
            "descricao": "Programa noturno romantico com pedidos e dedicatorias dos ouvintes.",
            "dias_semana": [],
            "horario_inicio": "22:00",
            "horario_fim": "00:00",
            "tom": "suave e intimista, quase sussurrado, como uma conversa a dois",
            "topicos_permitidos": ["relacionamentos", "saudade", "dedicatorias"],
            "topicos_proibidos": ["politica", "religiao"],
            "estrutura_blocos": ["abertura", "musica", "chamada_ouvinte", "musica", "chamada_ouvinte", "musica"],
            "perfil_programacao": "padrao",
            "generos_musicais": ["romantico", "mpb romantica", "sertanejo sofrencia"],
            "musicas_permitidas": [],
            "musicas_bloqueadas": [],
            "criterios_busca_musicas": "priorizar baladas romanticas, evitar musicas agitadas",
            "fontes_noticias": [],
            "fontes_pesquisa": [],
            "perfil": "musical",
            "dose_noticia": "nenhuma",
        },
    },
]


def exemplos_texto() -> str:
    linhas = [
        "Exemplos de saida bem formada pra pedidos parecidos -- copie o FORMATO e o nivel de "
        "detalhe/especificidade, nunca o conteudo literal (nome, tom, topicos etc. tem que ser "
        "proprios do pedido atual):"
    ]
    for exemplo in _EXEMPLOS:
        linhas.append(f'Pedido: "{exemplo["descricao_usuario"]}"')
        linhas.append(json.dumps(exemplo["saida"], ensure_ascii=False))
    return "\n".join(linhas)
