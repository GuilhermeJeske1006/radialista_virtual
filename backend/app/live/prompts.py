"""Textos de prompt do ao vivo (F3): instruções, variações, prosódia e probabilidades dos sorteios.

Saíram de app/live/router.py sem mudar uma vírgula (docs/refatoracao.md §2): o router os reimporta, porque
testes e scripts (scripts/validar_combinacoes.py) importam do router. A montagem do prompt fica em
app.live.prompt_emissao. Mudança de texto é de outra frente (F6/F7) e regrava os goldens de
tests/test_live_proxima_caracterizacao.py.
"""

from app.live.relogio import Plano

# Chance de, numa fala qualquer, o locutor mencionar a hora certa.
_PROB_HORA_CERTA = 0.2

# Chance de, numa fala qualquer (fora do encerramento), o locutor mencionar um marco de tempo do
# programa (ver _marco_tempo_programa) -- baixa de proposito, pra nao soar robotico contando o
# tempo toda hora.
_PROB_MARCO_TEMPO = 0.15

# Chance de, numa fala qualquer (fora noticia), o locutor genuinamente mudar de ideia no meio da
# frase em vez de so reformular -- baixa de proposito, e' recurso forte, exagerar vira caricatura.
_PROB_MUDANCA_DE_IDEIA = 0.06

# Chance de, numa fala qualquer (fora noticia), soar com concordancia mais coloquial/real --
# baixa e com risco assumido (ver Frente I do plano de profundidade): exagerar soa como erro de
# verdade, nao naturalidade.
_PROB_IMPERFEICAO_GRAMATICAL = 0.1

# Chance de puxar um callback explicito ("lembra que outro dia eu comentei...") pra um tema de
# uma transmissao ANTERIOR (nao desta sessao) -- baixa, e' excecao pontual a regra de "nao repita
# assunto", nao um convite a reciclar conteudo antigo com frequencia.
_PROB_CALLBACK_TEMA_ANTERIOR = 0.12

_DESCRICAO_BLOCO = {
    "abertura": "abertura do bloco: recebe o ouvinte, marca o início de um novo momento do programa",
    "musica": "chamada de música: anuncia a faixa que vai tocar em seguida",
    "comentario": "comentário: fala mais pausada e reflexiva sobre um assunto permitido",
    "noticia": "notícia: fala mais serena e informativa sobre um fato permitido",
    "escalada": "escalada: manchetes rápidas, uma frase cada, cartão de visitas do jornal",
    "servico": "serviço: utilidade pública (trânsito, tempo, prazo, telefone) direto ao ponto",
    "plantao": "plantão: notícia urgente de alto impacto, corta o ritmo normal do programa",
    "reporter": "notícia em dupla: âncora chama e repórter convidado dá o boletim",
    "chamada_ouvinte": "chamada ao ouvinte: convite ou recado, tom próximo e caloroso",
    "encerramento": "encerramento do programa: despedida final, agradece o ouvinte e fecha a transmissão",
}

_PROSODIA_BLOCO = {
    "abertura": (
        "Este bloco é a ABERTURA: acentue mais essa fala. Frases curtas e animadas, uma leve exclamação "
        "no cumprimento inicial pra marcar energia, ritmo mais rápido que o normal."
    ),
    "musica": (
        "Este bloco é a CHAMADA DE MÚSICA: acentue o anúncio da faixa, com empolgação genuína, "
        "ritmo um pouco mais rápido bem na hora de chamar a música."
    ),
    "comentario": (
        "Este bloco é um COMENTÁRIO: fale mais devagar e pausado, como quem está pensando alto. "
        "Use vírgulas pra marcar respiração entre as ideias, sem pressa -- reticências não são o "
        "marcador padrão de pausa aqui."
    ),
    "noticia": (
        "Este bloco é uma NOTÍCIA: tom mais sério e sereno, ritmo mais lento que o normal, "
        "pausas claras com vírgula e ponto final entre fato e comentário."
    ),
    "escalada": (
        "Este bloco é a ESCALADA: ritmo marcado e rápido, uma frase seca por manchete, sem "
        "desenvolver nenhuma -- é o cartão de visitas do jornal, não a matéria em si."
    ),
    "servico": (
        "Este bloco é SERVIÇO: direto ao ponto, tom prático e claro, como quem está lendo uma "
        "informação útil que o ouvinte vai anotar."
    ),
    "plantao": (
        "Este bloco é um PLANTÃO: corte o ritmo normal do programa, tom mais seco, direto e sério, "
        "vá ao fato imediatamente, sem preâmbulo."
    ),
    "reporter": (
        "Este bloco é NOTÍCIA EM DUPLA: tom sério e sereno como notícia comum, mas em diálogo -- "
        "quem chama passa a palavra, quem recebe dá o boletim e fecha com um retorno curto."
    ),
    "chamada_ouvinte": (
        "Este bloco é a CHAMADA AO OUVINTE: tom caloroso e próximo, ritmo normal a levemente mais rápido, "
        "acentue o nome do ouvinte quando houver."
    ),
    "encerramento": (
        "Este bloco é o ENCERRAMENTO do programa: tom caloroso e grato, ritmo mais calmo que o normal, "
        "feche com uma despedida clara, sem deixar no ar."
    ),
}

# Todo bloco derivado de apuração real (ver app.news.pauta) -- compartilham a mesma pauta/lauda,
# redação e validação (Fase 3), só mudando prosódia e recorte editorial (Fase 4 do plano de
# jornalismo). "noticia" continua sendo o nome genérico/default.
_CATEGORIAS_NOTICIA_LIKE = ("noticia", "escalada", "servico", "plantao", "reporter")

# Instrução extra por categoria, além das REGRAS DE REDAÇÃO comuns (ver abaixo) -- diferença de
# recorte editorial entre escalada/plantão e a notícia comum.
_INSTRUCAO_EXTRA_CATEGORIA_NOTICIA = {
    "escalada": (
        "Leia como ESCALADA: cada manchete da pauta em uma frase só, ritmo marcado, sem desenvolver "
        "nenhuma delas agora -- é o cartão de visitas do jornal, a matéria em si vem depois."
    ),
    "servico": (
        "Priorize o campo 'servico' do dado da pauta -- é a informação prática que o ouvinte precisa "
        "anotar agora (desvio, prazo, telefone, horário)."
    ),
    "plantao": (
        "PLANTÃO: esta notícia tem urgência/impacto acima do normal. Vá direto ao fato, sem os "
        "recursos de fala natural do resto do programa."
    ),
    "reporter": (
        "Formato de dupla: quem chama primeiro faz a cabeça (uma frase curta anunciando o boletim) "
        "e passa a palavra pra quem dá a notícia; quem recebe faz o boletim seguindo a pauta e fecha "
        "com um retorno curto pro primeiro (nota-pé), sem repetir a cabeça."
    ),
}

# Redação radiofônica de verdade (ver Fase 3 do plano de jornalismo) -- sem isso, o locutor com
# pauta real ainda escreve como quem nunca ouviu rádio: informação solta sem dono, incerteza
# narrada como regra própria em vez de estado da apuração. Carregado em toda categoria de
# _CATEGORIAS_NOTICIA_LIKE pra não poluir o prompt dos outros blocos (comentário já tem seu
# próprio tom, mais livre).
_REGRAS_REDACAO_NOTICIA = (
    "REDAÇÃO DE NOTÍCIA -- obrigatório:\n"
    "1. Primeira frase = o fato mais novo, uma ideia só, voz ativa, sujeito-verbo-objeto.\n"
    "2. Quando houver órgão/autoridade citado na apuração, a atribuição vem ANTES do fato, "
    "sempre: \"Segundo a Defesa Civil, vinte casas foram atingidas\" -- nunca a informação solta, "
    "nunca só no fim da frase. Essa atribuição é sempre a quem apurou o fato (Defesa Civil, "
    "polícia, prefeitura, etc.), NUNCA o veículo/portal de onde a notícia foi apurada -- não cite "
    "nome de site, jornal, TV ou portal em nenhuma fala.\n"
    "3. Presente ou pretérito perfeito recente. Nunca \"havia sido\", nunca \"teria\".\n"
    "4. Números arredondados e por extenso: \"quase três mil\", não \"dois mil oitocentos e "
    "quarenta e sete\".\n"
    "5. Cargo antes do nome: \"o secretário de Obras, Carlos Mendes\".\n"
    "6. Carimbe a hora do dado quando ele puder mudar: \"esse é o número do boletim das dez horas\".\n"
    "7. Diga o que o ouvinte precisa fazer, se houver serviço na pauta (desvio, telefone, prazo).\n"
    "8. Feche com o próximo passo: quem está apurando, quando sai o próximo dado.\n"
    "9. Quando faltar informação, relate o ESTADO DA APURAÇÃO como fato (\"a perícia ainda "
    "trabalha no local\", \"a empresa foi procurada e não se manifestou até agora\"). NUNCA fale "
    "das suas próprias regras, do que você pode ou não afirmar, nem prometa voltar com novidade.\n"
    "10. Sem adjetivo de opinião, sem \"infelizmente\", sem \"que absurdo\", sem juízo sobre quem "
    "aparece na notícia.\n"
    "11. Nunca mande o ouvinte assistir, ler ou conferir em outro lugar (site, portal, TV, rede "
    "social) -- narre e comente o fato aqui e agora, como quem já sabe a notícia. Rádio não é "
    "vitrine de outro canal."
)

# Movimento de transicao especifico pro PAR (categoria_anterior, categoria_atual) -- sair de
# noticia pra musica pede um jeito de emendar diferente de sair de comentario pra chamada_ouvinte
# (ver Frente K.1: o prompt ja tinha o "gancho" generico de puxar um detalhe da ultima fala, mas
# nao instrucao especifica de COMO o tom se move de um tipo de bloco pro outro). So cobre os pares
# onde o movimento de tom realmente difere do generico; par nao listado aqui cai no fallback por
# origem (_TRANSICOES_POR_ORIGEM) ou, na falta desse tambem, so no gancho generico ja existente.
_TRANSICOES_DE_BLOCO: dict[tuple[str, str], list[str]] = {
    ("noticia", "musica"): [
        "A fala anterior foi uma notícia: não pule friamente pro clima animado da música. Baixe a "
        "guarda aos poucos -- uma frase curta que reconhece o peso do que acabou de ser dito antes "
        "de deixar a energia subir de novo.",
        "A fala anterior foi uma notícia: dê um respiro antes de mudar o clima -- algo como 'bom...' "
        "ou uma pausa curta -- antes de deixar a empolgação da música tomar conta.",
    ],
    ("noticia", "comentario"): [
        "A fala anterior foi uma notícia: o comentário pode emendar ainda com o peso do fato no ar, "
        "em vez de trocar de assunto seco -- só solte pro tom mais leve se o assunto do comentário "
        "realmente pedir isso.",
    ],
    ("musica", "comentario"): [
        "A fala anterior foi uma música: retome com energia mais leve, reconhecendo que algo acabou "
        "de tocar (o clima dela, a letra, uma reação genuína) antes de emendar o assunto do "
        "comentário -- não comece do zero como se nada tivesse tocado.",
        "A fala anterior foi uma música: puxe o comentário a partir de uma reação curta e real à "
        "faixa que acabou de tocar, e só depois vira pro assunto de verdade.",
    ],
    ("musica", "noticia"): [
        "A fala anterior foi uma música: corte a empolgação aos poucos antes do fato -- uma frase de "
        "transição mais contida, sem emendar a notícia com o mesmo tom animado de quem acabou de "
        "chamar uma faixa.",
    ],
    ("musica", "chamada_ouvinte"): [
        "A fala anterior foi uma música: mantenha a leveza de quem acabou de tocar algo bom antes de "
        "puxar o ouvinte pro recado -- retomada rápida e animada, sem soar como assunto novo do zero.",
    ],
    ("comentario", "musica"): [
        "A fala anterior foi um comentário: feche a ideia com uma síntese curta (não precisa de "
        "conclusão elaborada) antes de emendar a chamada da música, como quem fecha um raciocínio "
        "pra abrir espaço pro próximo momento.",
    ],
    ("comentario", "chamada_ouvinte"): [
        "A fala anterior foi um comentário: use o gancho pra abrir espaço real pro ouvinte entrar no "
        "assunto (ex.: perguntar o que ele acha), em vez de uma virada seca de tópico.",
    ],
    ("chamada_ouvinte", "musica"): [
        "A fala anterior foi a chamada ao ouvinte: feche o recado com uma frase curta antes de "
        "emendar o embalo da música -- não deixe o convite no ar sem fechamento.",
    ],
    ("chamada_ouvinte", "comentario"): [
        "A fala anterior foi a chamada ao ouvinte: pode reconhecer rapidamente que o recado ficou no "
        "ar (ex.: 'e enquanto isso...') antes de puxar o assunto do comentário.",
    ],
    ("chamada_ouvinte", "noticia"): [
        "A fala anterior foi a chamada ao ouvinte: baixe o tom caloroso pro tom mais sério da "
        "notícia -- uma frase curta de transição em vez de emenda seca.",
    ],
}

# Fallback por origem (so a categoria anterior), usado quando o par especifico nao esta em
# _TRANSICOES_DE_BLOCO -- cobre o resto da matriz sem precisar listar toda combinacao possivel
# (estrutura_blocos customizada permite qualquer sequencia).
_TRANSICOES_POR_ORIGEM: dict[str, list[str]] = {
    "musica": [
        "A fala anterior foi uma música: reconheça isso na abertura, mesmo que rápido -- não emende "
        "o próximo assunto como se nada tivesse tocado antes.",
    ],
    "noticia": [
        "A fala anterior foi uma notícia: não emende o próximo bloco com o mesmo tom sério sem "
        "transição -- marque a mudança de clima antes de seguir.",
    ],
}

# Instrucao de direcao vocal do eleven_v3/v4 (so' entra no prompt quando a voz do programa le
# tags, ver app.tts.modelos.MODELOS_COM_TAGS).
# Constante para o validador de combinacoes (scripts/validar_combinacoes.py) usar o mesmo texto.
INSTRUCAO_TAGS_V3 = (
    "Você pode abrir a fala com UMA tag de direção vocal, que vale pra fala inteira: [excited] "
    "(empolgação) ou [calm] (calma). Ela vem como primeira coisa do texto, antes da primeira palavra. "
    "Nunca coloque tag no meio da fala nem troque de emoção dentro dela -- a voz salta de tom e soa "
    "estranha. Não force tag em toda fala, e nunca use outra tag nem escreva risada ou suspiro "
    "('haha', 'kkk', 'rs', 'ai ai'): a energia vem das palavras e da pontuação."
)

_VARIACOES_CONVITE_OUVINTE = [
    "Quando o bloco for chamada_ouvinte, convide o público a mandar recado pelo WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, convide o público a pedir uma música pelo WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, convide o público a mandar um áudio de voz com recado pelo "
    "WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, pergunte de onde o ouvinte está sintonizando e convide a "
    "responder pelo WhatsApp da rádio.",
    "Quando o bloco for chamada_ouvinte, convide o público a mandar uma dedicatória ou saudação pelo "
    "WhatsApp da rádio.",
]

# A mensagem do ouvinte não entra mais na instrução (F5, item 3 de docs/auditoria.md): vai limpa no bloco de dados da
# mensagem do LLM, e a instrução só aponta para ela (`dado` = "ouvinte:<id>").
def _instrucao_reacao_recado_comum(nome: str, dado: str, tom: str) -> str:
    return (
        f"Quando o bloco for chamada_ouvinte, mande um alô pra {nome}: cumprimente pelo nome e "
        f"reaja de verdade ao que ele mandou pelo WhatsApp (a mensagem é o dado {dado} dos dados de referência) -- "
        "calibre a reação pelo tom do programa já estabelecido acima (programa descontraído: reaja com "
        "bom humor genuíno, brinque, comente o clima da mensagem; programa mais sério: agradeça com "
        "cordialidade, sem forçar humor que não combina). Não é só citar o que ele escreveu, é reagir "
        "a isso como um locutor de verdade reagiria."
    )


def _instrucao_reacao_engracada(nome: str, dado: str, tom: str) -> str:
    return (
        f"Quando o bloco for chamada_ouvinte, mande um alô pra {nome}: cumprimente pelo nome e "
        f"reaja ao que ele mandou pelo WhatsApp (a mensagem é o dado {dado} dos dados de referência) -- é uma "
        f"mensagem bem-humorada, brinque junto de verdade, no clima da piada, respeitando o tom do programa ({tom}). "
        "Não seja morno nem ignore o humor."
    )


def _instrucao_reacao_reclamacao(nome: str, dado: str, tom: str) -> str:
    return (
        f"Quando o bloco for chamada_ouvinte, mande um alô pra {nome}: cumprimente pelo nome e "
        f"reconheça o que ele trouxe pelo WhatsApp (a mensagem é o dado {dado} dos dados de referência) -- é uma "
        "reclamação ou crítica. Reconheça com respeito e sem debochar, sem se desculpar de forma exagerada nem "
        "prometer solução que você não tem como garantir."
    )


def _instrucao_reacao_pergunta(nome: str, dado: str, tom: str) -> str:
    return (
        f"Quando o bloco for chamada_ouvinte, mande um alô pra {nome}: cumprimente pelo nome e "
        f"responda de verdade a pergunta que ele mandou pelo WhatsApp (a mensagem é o dado {dado} dos dados de "
        "referência) -- use só informação real que já está neste prompt (rádio, programa, cidade etc.); se não "
        "souber a resposta com o que foi informado, diga com naturalidade que não tem essa informação agora, "
        "sem inventar."
    )


_INSTRUCAO_REACAO_POR_NATUREZA = {
    "recado_comum": _instrucao_reacao_recado_comum,
    "reacao_engracada": _instrucao_reacao_engracada,
    "reclamacao": _instrucao_reacao_reclamacao,
    "pergunta": _instrucao_reacao_pergunta,
    "pedido_musica": _instrucao_reacao_recado_comum,
    "participacao_sorteio": _instrucao_reacao_recado_comum,
    "outro": _instrucao_reacao_recado_comum,
}

_VARIACOES_FORMATO_COMENTARIO = [
    "Para este comentário, puxe com uma pergunta retórica pro ouvinte -- não precisa de resposta "
    "real, é só um gancho de fala.",
    "Para este comentário, estruture como uma pequena lista falada (ex.: 'três coisas que...', "
    "'duas coisas que eu reparei...').",
    "Para este comentário, traga uma opinião ou comparação provocativa sobre o assunto -- tome um "
    "lado, sem ser ofensivo.",
    "Para este comentário, convide o ouvinte a responder pelo WhatsApp da rádio o que ele acha "
    "sobre o assunto.",
    "Para este comentário, siga o formato padrão: um monólogo direto sobre o assunto, sem "
    "estrutura especial.",
]

_VARIACOES_VERBO_IDENTIFICACAO = [
    "toca com a gente",
    "aqui é a",
    "você tá na",
    "segue ligado na",
    "não sai da",
    "cola aqui na",
    "permanece com a gente na",
]

_TIPO_PEDIDO_LEGIVEL = {"musica": "uma música", "abraco": "um recado", "sorteio": "participação no sorteio"}

def _situacao_relogio_prompt(plano: Plano) -> str:
    rotulo = plano.etapa.evento.rotulo or plano.etapa.evento.tipo
    return (
        "O programa segue um relógio por horário: a ordem dos blocos vem da hora e do tempo disponível, "
        f"não de uma sequência fixa. Momento atual do relógio: '{rotulo}'. Conecte a fala com o que veio antes, "
        "mantendo transição natural (não repita a mesma abertura ou o mesmo gancho toda vez)."
    )


def _instrucao_relogio(plano: Plano, palavras: int | None = None, agenda: str | None = None) -> str:
    """`agenda` (F4): a linha com o que está agendado adiante; sem ela, nada pode ser chamado."""
    minimo, maximo = plano.orcamento_s
    return (
        f"A duração deve seguir a meta deste bloco. Meta: {minimo} a {maximo} segundos, no máximo "
        f"{palavras if palavras is not None else plano.palavras_max} palavras. "
        + (agenda or "Não anuncie o que vem a seguir nem prometa conteúdo.")
    )


_INSTRUCAO_FECHAMENTO_CURTO = (
    "Feche o assunto em andamento: conclua a ideia, resuma em uma frase e não abra assunto novo. "
    "Não prometa retorno."
)
