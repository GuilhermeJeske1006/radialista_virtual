import datetime
from zoneinfo import ZoneInfo

from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.weather.client import obter_clima_atual

_DIAS_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]


class ParticipantePrograma:
    """Um radialista participando de um programa, com papel e comportamento
    especificos daquele programa (ver app/models/programa_radialista.py)."""

    def __init__(self, radialista: RadioConfig, papel: str, comportamento: str):
        self.radialista = radialista
        self.papel = papel
        self.comportamento = comportamento


def _contexto_atual(radialista: RadioConfig, account: Account) -> str:
    """Data, hora e clima reais no fuso do radialista -- sem isso o modelo chuta
    (ou herda a data de treino) e erra dia da semana, hora do dia e clima quando
    o ouvinte pergunta ou quando o locutor comenta o tempo espontaneamente."""
    agora = datetime.datetime.now(ZoneInfo(radialista.timezone))
    dia_semana = _DIAS_SEMANA[agora.weekday()]
    texto = (
        f"Contexto atual (use pra se situar no tempo, nunca invente outra data/hora): "
        f"agora é {dia_semana}, {agora.strftime('%d/%m/%Y')}, {agora.strftime('%H:%M')} "
        f"(horário de {radialista.timezone})."
    )

    clima = obter_clima_atual(account.cidade)
    if clima:
        texto += f" Clima atual em {account.cidade}: {clima}."

    return texto


def montar_system_prompt(
    account: Account,
    radialista: RadioConfig,
    programa: Programa,
    roster: list[ParticipantePrograma] | None = None,
) -> str:
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

    separador_frequencia = None
    if account.frequencia:
        if "," in account.frequencia:
            separador_frequencia = "vírgula"
        elif "." in account.frequencia:
            separador_frequencia = "ponto"

    multi_voz = bool(roster) and len(roster) > 1

    if multi_voz:
        vozes_texto = "\n".join(
            f"- {p.radialista.nome_locutor} (papel: {p.papel}): "
            f"{p.comportamento or p.radialista.personalidade or 'sem instruções específicas de comportamento'}."
            for p in roster
        )
        partes = [
            f"Este programa é apresentado por vários locutores de rádio virtual conversando entre si, "
            f"em nome de {identificacao_radio}.",
            "Escreva sempre em português correto, com acentuação e pontuação gramaticalmente corretas "
            "(ex.: você, não, música, é, está, coração). Nunca omita acentos nem troque palavras por versões sem "
            "acento, mesmo em resposta rápida ou informal.",
            f"Os apresentadores deste programa são:\n{vozes_texto}",
            "Gere um diálogo natural entre eles, respeitando o papel e o comportamento de cada um -- cada "
            "locutor fala de acordo com sua própria personalidade, sem se confundir com a dos outros.",
        ]
    else:
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
        f"Agora {'vocês apresentam' if multi_voz else 'você apresenta'} o programa '{programa.nome}'.",
    ]
    partes.append(_contexto_atual(radialista, account))
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

    if separador_frequencia:
        partes.append(
            f"A frequência da rádio é {account.frequencia}. Ao falar a frequência (por escrito, já que "
            f"vira áudio depois), escreva o separador decimal por extenso -- diga '{separador_frequencia}' -- "
            f"nunca pule ele. Ex.: escreva 'noventa e oito {separador_frequencia} cinco FM', não '98.5 FM' "
            "nem 'noventa e oito cinco FM'."
        )

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

    if multi_voz:
        partes.append(
            "Responda APENAS com um JSON compacto, sem markdown e sem texto fora do JSON, exatamente no formato "
            '{"linhas": [{"locutor": "<nome exato de um dos apresentadores acima>", "texto": "..."}]}. '
            "Gere entre 2 e 4 linhas alternando os apresentadores de forma natural, como uma conversa de verdade "
            "(um completa o outro, reage, faz pergunta) -- não uma lista de falas soltas e desconectadas."
        )

    return "\n".join(partes)
