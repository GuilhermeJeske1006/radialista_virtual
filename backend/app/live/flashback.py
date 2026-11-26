"""Direção e reserva do flashback 1970–1999. Sem rede nem efeitos colaterais."""
import re

from app.live.identidade_musical import normalizar

ID = "flashback"
INTERVALO_ARTISTA_MIN = 45
ROTEIRO = (
    "abertura", "musica", "musica", "comentario", "musica", "musica", "identificacao",
    "musica", "musica", "chamada_ouvinte", "musica", "musica", "vinheta",
)
# Obras de reserva, não IDs de vídeo: toda resolução ainda precisa validar artista,
# título, versão e disponibilidade. A seleção não usa o ano de upload como ano da obra.
RESERVA = (
    ("Cyndi Lauper", "Girls Just Want to Have Fun"),
    ("Michael Jackson", "Billie Jean"),
    ("Madonna", "Like a Prayer"),
    ("a-ha", "Take on Me"),
    ("Tears For Fears", "Everybody Wants To Rule The World"),
    ("Eurythmics", "Sweet Dreams (Are Made of This)"),
    ("Queen", "Another One Bites the Dust"),
    ("Billy Joel", "Uptown Girl"),
    ("Annie Lennox", "Walking on Broken Glass"),
    ("Cher", "Believe"),
    ("Tim Maia", "Não Quero Dinheiro (Só Quero Amar)"),
    ("Jorge Ben Jor", "Taj Mahal"),
    ("Lulu Santos", "Tempos Modernos"),
    ("Legião Urbana", "Tempo Perdido"),
    ("Earth, Wind & Fire", "September"),
    ("Kool & The Gang", "Celebration"),
    ("Bee Gees", "Stayin' Alive"),
    ("ABBA", "Dancing Queen"),
    ("Rick Astley", "Never Gonna Give You Up"),
    ("Depeche Mode", "Enjoy the Silence"),
    ("Pet Shop Boys", "West End Girls"),
    ("New Order", "Blue Monday"),
    ("Eiffel 65", "Blue (Da Ba Dee)"),
    ("Snap!", "Rhythm Is a Dancer"),
    ("Corona", "The Rhythm of the Night"),
    ("Whitney Houston", "I Wanna Dance with Somebody"),
    ("Donna Summer", "Hot Stuff"),
    ("Gloria Gaynor", "I Will Survive"),
    ("Michael Jackson", "Don't Stop 'Til You Get Enough"),
    ("Cyndi Lauper", "Time After Time"),
    ("Madonna", "Into the Groove"),
    ("Queen", "Under Pressure"),
    ("Tim Maia", "Réu Confesso"),
    ("Jorge Ben Jor", "Fio Maravilha"),
    ("Lulu Santos", "Toda Forma de Amor"),
    ("Billy Joel", "We Didn't Start the Fire"),
)

# Fatos editoriais mínimos, com procedência. Não se derivam histórias do ano de
# publicação de um vídeo, nem se preenchem créditos por memória do modelo.
FATOS = (
    ("Like a Prayer", "A produção principal de Like a Prayer é de Madonna e Patrick Leonard; "
     "Bill Bottrell tem crédito em produção adicional e remix.",
     "https://www.madonna.com/products/like-a-prayer-single"),
    ("Time After Time", "Time After Time faz parte do álbum She's So Unusual, de Cyndi Lauper.",
     "https://www.youtube.com/watch?v=7wBgcalM4c4"),
    ("Billie Jean", "Billie Jean faz parte do álbum Thriller, de Michael Jackson.",
     "https://www.michaeljackson.com/albums/thriller/"),
    ("Beat It", "Beat It faz parte do álbum Thriller, de Michael Jackson.",
     "https://www.michaeljackson.com/albums/thriller/"),
)


def ativo(programa) -> bool:
    return getattr(programa, "perfil_programacao", "") == ID


def artista_da_faixa(titulo: str, canal: str) -> str:
    canal = re.sub(r"\s*(?:-\s*Topic|VEVO|Official|Oficial)\s*$", "", canal, flags=re.I).strip()
    return normalizar(canal or titulo.split(" - ", 1)[0]).replace(" ", "")


def instrucao_editorial(ctx) -> list[str]:
    if not ativo(ctx.programa):
        return []
    historico = " ".join(ctx.memoria.historico)
    linhas = [
        "DIREÇÃO DO FLASHBACK: uma intenção e uma ideia por entrada; música é o centro.",
        "Comece anúncios pelo artista e título confirmados. Identificação contém só rádio, frequência e programa.",
        "Não transforme toda entrada em história de pista ou lista de locais de trabalho. "
        "Referência local só quando acrescentar algo. Não afirme público lotado, demanda ou participação inexistente.",
        "Transição pode começar direto no assunto. Não force callback, 'e já que', 'e falando' ou 'olha só'.",
        "Uma curiosidade por comentário. Ano de upload ou remaster NÃO é data de lançamento da canção. "
        "Só atribua ano, álbum, autoria, produção ou história quando constar dos fatos verificados abaixo. "
        "Ao usar um fato histórico, use exatamente a frase verificada, sem acrescentar créditos ou datas. "
        "Sem fato verificado, converse sobre a experiência de ouvir, sem inventar bastidor ou memória pessoal.",
        "Não anuncie música nos comentários: citar uma obra não a acrescenta à fila.",
        "Convide à participação somente no bloco de chamada, com uma pergunta concreta. "
        "Não repita convite no anúncio seguinte e não diga que há mensagens sem dados reais.",
    ]
    repetidas = [expressao for expressao in ("pista", "malharia", "olha só", "e já que", "no volante")
                 if normalizar(historico).count(normalizar(expressao)) >= 2]
    if repetidas:
        linhas.append("Evite nesta entrada as expressões já repetidas: " + ", ".join(repetidas) + ".")
    dias = getattr(ctx.programa, "dias_semana", []) or list(range(7))
    nomes = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
    linhas.append("Grade cadastrada, não invente outra frequência: " + ", ".join(nomes[d] for d in dias)
                  + f"; das {ctx.programa.horario_inicio:%H:%M} às {ctx.programa.horario_fim:%H:%M}.")
    linhas.append("Não diga 'segunda metade' antes da metade real da duração; evite marcos desnecessários.")
    fatos = [f"{fato} Fonte: {fonte}" for titulo, fato, fonte in FATOS
             if normalizar(titulo) in normalizar(historico)]
    linhas.append("Fatos verificados para esta entrada: " + (" ".join(fatos) if fatos else "nenhum."))
    return linhas


def avisos_editoriais(fala: str, historico: tuple[str, ...]) -> list[str]:
    """Uma reescrita compartilhada corrige repetição; nunca acrescenta chamadas ao LLM."""
    recentes = normalizar(" ".join(historico))
    atual = normalizar(fala)
    repetidas = [t for t in ("pista", "malharia", "olha so", "e ja que", "no volante")
                 if recentes.count(t) >= 2 and t in atual]
    return ["Reescreva sem as expressões já saturadas: " + ", ".join(repetidas)] if repetidas else []


def restringir_fatos(fala: str, historico: tuple[str, ...], nome_programa: str) -> str:
    """Depois da reescrita, retira alegações históricas sem apoio no banco editorial.

    Não tenta confirmar uma história com outra inferência do modelo. As frases
    verificadas são literais para não confundir produtor principal e remix.
    """
    contexto = normalizar(" ".join(historico))
    permitidos = {normalizar(fato) for titulo, fato, _ in FATOS if normalizar(titulo) in contexto}
    alegacao = re.compile(r"\b(19\d{2}|20\d{2}|mil novecentos|dois mil|album|disco de|"
                         r"produz\w*|producao|produtor\w*|compos\w*|lanc\w*|grav\w*|premi\w*|grammy|"
                         r"fundad\w*|vendeu|paradas|vezes por semana)\b")
    frases = re.split(r"(?<=[.!?])\s+", fala)
    seguras = [f for f in frases if not alegacao.search(normalizar(f))
               or normalizar(re.sub(r"\[[^\]]+\]", "", f)) in permitidos]
    resultado = " ".join(seguras).strip()
    if len(resultado.split()) < 5:
        resultado = f"Um refrão conhecido muda o ritmo do dia. A seleção de clássicos continua no {nome_programa}."
    return resultado


def candidatos(programa, artistas_recentes: set[str], titulos_tocados: set[str]) -> list[tuple[str, str]]:
    from app.live.music import titulo_ja_tocado
    itens = []
    for entrada in getattr(programa, "musicas_permitidas", []) or []:
        if " - " in entrada:
            itens.append(tuple(entrada.split(" - ", 1)))
    itens = itens or list(RESERVA)
    return [(a, t) for a, t in itens if not titulo_ja_tocado(t, titulos_tocados)
            and normalizar(a).replace(" ", "") not in artistas_recentes]


def pedido_aprovado(programa, query: str) -> tuple[str, str] | None:
    solicitado = normalizar(query)
    for artista, titulo in candidatos(programa, set(), set()):
        if solicitado in {normalizar(titulo), normalizar(f"{artista} {titulo}"), normalizar(f"{titulo} {artista}")}:
            return artista, titulo
    return None
