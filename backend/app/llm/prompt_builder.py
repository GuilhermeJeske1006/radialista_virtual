import datetime
import random
import re
from zoneinfo import ZoneInfo

from app.config.redis_client import redis_client
from app.feriados import feriado_nacional_do_dia
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.numeros import numero_por_extenso
from app.weather.client import obter_clima_atual

# Mesmo TTL de sessao ao vivo usado em app/live/router.py::_TTL_SESSAO_AO_VIVO.
_TTL_SESSAO_AO_VIVO = 6 * 60 * 60


def _proxima_variacao(programa_id: int, chave: str, opcoes: list[str]) -> str:
    """Round-robin persistido no Redis por programa, mesmo primitivo de
    app/live/router.py::_proxima_variacao (reimplementado aqui pra evitar import circular --
    live/router.py importa de prompt_builder.py, nao o contrario). Injeta um item por vez de um
    pool (conhecimento local, bíblia da rádio, etc.), pra nao despejar a lista inteira numa fala
    so (soaria leitura de verbete)."""
    redis_key = f"rotacao:{chave}:{programa_id}"
    indice = redis_client.incr(redis_key)
    redis_client.expire(redis_key, _TTL_SESSAO_AO_VIVO)
    return opcoes[(indice - 1) % len(opcoes)]


def _fato_do_dia(programa_id: int, radialista_id: int, opcoes: list[str]) -> str:
    """Fato fixo por sessão ao vivo (não muda a cada fala, ao contrário de _proxima_variacao) --
    a primeira escolha grava no Redis (SETNX) e o resto do programa reusa o mesmo valor, pra não
    contradizer duas vezes na mesma transmissão (ver Frente H, estado do dia da persona)."""
    redis_key = f"fato_do_dia:{programa_id}:{radialista_id}"
    existente = redis_client.get(redis_key)
    if existente in opcoes:
        return existente
    novo = random.choice(opcoes)
    redis_client.set(redis_key, novo, nx=True, ex=_TTL_SESSAO_AO_VIVO)
    return redis_client.get(redis_key) or novo

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


_TEMPERATURA_CLIMA_RE = re.compile(r"^(-?\d+)°C, (.+)$")


def _clima_por_extenso(clima: str) -> str:
    """Troca o '23°C' de obter_clima_atual (ver app.weather.client) por 'vinte e três graus' --
    o número por extenso vai direto pro prompt, então já chega pro LLM na forma que ele deve
    repetir na fala, sem depender dele converter o algarismo sozinho. Devolve o texto original
    (sem quebrar o prompt) se o formato não bater com o esperado.
    """
    match = _TEMPERATURA_CLIMA_RE.match(clima)
    if not match:
        return clima
    temperatura, descricao = match.groups()
    return f"{numero_por_extenso(int(temperatura))} graus, {descricao}"


def _perfil_editorial(hora: int) -> str:
    """Preset fixo (sem configuração por programa) de prioridade editorial por horário do dia --
    ajuda o LLM a não abrir o programa com notícia pesada de manhã cedo nem soar animado demais
    de madrugada, sem precisar de nenhum campo novo em Programa (ver Frente B do plano de
    diversidade editorial)."""
    if 5 <= hora < 9:
        return "leve e energético, típico de início de manhã -- evite notícia pesada logo na abertura"
    if 9 <= hora < 11:
        return "leve, bom momento pra trânsito e utilidade"
    if 11 <= hora < 14:
        return "entretenimento leve, horário de almoço"
    if 14 <= hora < 18:
        return "resumo do dia, notícia mais séria já cabe bem"
    if 18 <= hora < 22:
        return "tom mais calmo, fim de tarde/noite"
    return "calmo e reflexivo, noite/madrugada"


def _feriado_municipal_do_dia(programa: Programa, data: datetime.date) -> str | None:
    """Feriado municipal de hoje, a partir da lista cadastrada manualmente no programa
    (programa.feriados_municipais, cada item {"data": "MM-DD", "nome": "..."}) -- ao contrário
    do feriado nacional, não dá pra calcular por fórmula nem existe fonte gratuita confiável
    pras ~5000 cidades brasileiras, então é o usuário quem informa (mesmo padrão de
    assuntos_ao_vivo/musicas_bloqueadas: lista curada, zero risco de invenção)."""
    hoje_mmdd = data.strftime("%m-%d")
    for feriado in programa.feriados_municipais or []:
        if feriado.get("data") == hoje_mmdd and feriado.get("nome"):
            return feriado["nome"]
    return None


def _contexto_atual(radialista: RadioConfig, account: Account, programa: Programa) -> str:
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
    texto += f" Perfil editorial deste horário: {_perfil_editorial(agora.hour)}."

    if agora.weekday() == 4:
        texto += " Hoje é sexta-feira: se fizer sentido, puxe comentário sobre fim de semana ou agenda de eventos."
    elif agora.weekday() == 0:
        texto += " Hoje é segunda-feira: se fizer sentido, puxe um resumo do fim de semana (jogo, evento, novidade)."

    feriado_nacional = feriado_nacional_do_dia(agora.date())
    if feriado_nacional:
        texto += f" Hoje é feriado nacional: {feriado_nacional}. Pode mencionar isso na fala se fizer sentido."

    feriado_municipal = _feriado_municipal_do_dia(programa, agora.date())
    if feriado_municipal:
        texto += f" Hoje também é feriado municipal aqui: {feriado_municipal}."

    clima = obter_clima_atual(account.cidade)
    if clima:
        texto += (
            f" Clima atual em {account.cidade}: {_clima_por_extenso(clima)}. Se for comentar o clima, "
            "prefira um comentário com tom regional de quem é dali (o calor típico daqui, a friagem que desce "
            "da serra, etc.) em vez de só citar o número -- só se tiver algo real configurado sobre o lugar "
            "pra apoiar isso, senão comente de forma genérica mesmo."
        )

    if account.cidade:
        texto += (
            f" Você pode citar o nome da cidade ({account.cidade}) pra reforçar identidade local quando "
            "fizer sentido. NUNCA invente trânsito, evento, time, bairro, comércio ou qualquer outro fato "
            "específico da cidade que não foi informado a você em algum lugar deste prompt -- sem dado "
            "real configurado, não puxe esse tipo de assunto local."
        )

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
            + (f" Fatos fixos sobre ele(a): {p.radialista.biografia}." if p.radialista.biografia else "")
            + (
                f" Traço marcante dele(a), use com moderação: "
                f"{_proxima_variacao(programa.id, f'traco_marcante_{p.radialista.id}', p.radialista.tracos_marcantes)}."
                if p.radialista.tracos_marcantes
                else ""
            )
            + (
                f" Fato fixo de hoje pra ele(a) citar se fizer sentido (só uma vez): "
                f"{_fato_do_dia(programa.id, p.radialista.id, p.radialista.fatos_do_dia)}."
                if p.radialista.fatos_do_dia
                else ""
            )
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
        if radialista.biografia:
            partes.append(
                f"Fatos fixos sobre você (sua biografia real): {radialista.biografia}. "
                "Esses fatos são sempre os mesmos -- nunca invente ou contradiga informação pessoal "
                "diferente dessa em nenhuma fala. Cite algum deles só quando fizer sentido natural na "
                "conversa, não em toda fala."
            )
        if radialista.tracos_marcantes:
            traco_marcante = _proxima_variacao(programa.id, f"traco_marcante_{radialista.id}", radialista.tracos_marcantes)
            partes.append(
                f"Um traço marcante seu, sua 'marca registrada' (implicância boba, piada interna, jeito "
                f"próprio de falar): {traco_marcante}. Use com moderação -- não em toda fala, senão vira "
                "caricatura."
            )
        if radialista.fatos_do_dia:
            fato_do_dia = _fato_do_dia(programa.id, radialista.id, radialista.fatos_do_dia)
            partes.append(
                f"Fato fixo de hoje pra você mencionar quando fizer sentido, só uma vez na transmissão (não "
                f"repita nem contradiga ao longo do programa): {fato_do_dia}."
            )
    partes += [
        f"Agora {'vocês apresentam' if multi_voz else 'você apresenta'} o programa '{programa.nome}'.",
    ]
    partes.append(_contexto_atual(radialista, account, programa))
    partes.append(
        "Divulgação de eventos: só mencione espontaneamente um evento específico quando houver "
        "autorização explícita da rádio nas instruções configuradas para divulgar aquele evento. "
        "O cadastro em conhecimento local, a lista de eventos recorrentes, os temas permitidos e "
        "sugestões de agenda ou resumo do fim de semana não constituem autorização para divulgação. "
        "Sem essa autorização, não faça chamadas, recomendações, convites nem publicidade do evento. "
        "Nunca presuma patrocínio, parceria ou apoio da rádio. Se o ouvinte perguntar diretamente "
        "sobre um evento, responda apenas de forma factual com as informações confirmadas disponíveis, "
        "sem tom promocional, convite ou incentivo para comparecer. "
        "Antes de mencionar qualquer evento da região, confira a data da edição (incluindo o ano) "
        "e, quando disponível, o horário de início e término, comparando com o contexto atual no fuso "
        "do locutor. Use apenas informações explicitamente fornecidas; a data de publicação de uma "
        "notícia não é a data do evento. Evento já encerrado nunca deve ser anunciado como atual ou "
        "futuro nem receber convite para comparecer: só mencione no passado se houver motivo relevante "
        "para a conversa, sem inventar como foi. Para eventos futuros, avalie a proximidade da data e "
        "a utilidade para o ouvinte; não puxe espontaneamente um evento distante sem motivo concreto. "
        "Só diga 'hoje', 'amanhã', 'neste fim de semana' ou 'está acontecendo' quando os dados "
        "confirmarem isso. Um evento recorrente cadastrado não confirma a realização nem a data da "
        "edição atual; não presuma que se repete neste ano. Se a data estiver ausente, ambígua ou "
        "desatualizada, não faça chamada espontânea: se o ouvinte perguntar, diga que a data não está "
        "confirmada nas informações disponíveis. Considere também a relação com a região e com o "
        "assunto da conversa antes de decidir se faz sentido falar do evento."
    )
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

    conhecimento = account.conhecimento_local or {}
    detalhes_locais = []
    if conhecimento.get("gentilico"):
        detalhes_locais.append(f"o gentílico de quem nasce/mora aqui é '{conhecimento['gentilico']}'")
    detalhes_locais += [f"o bairro {b}" for b in conhecimento.get("bairros") or []]
    detalhes_locais += [f"o ponto de referência {p}" for p in conhecimento.get("pontos_referencia") or []]
    detalhes_locais += [f"o evento local: {e}" for e in conhecimento.get("eventos_recorrentes") or []]
    if detalhes_locais:
        detalhe_local = _proxima_variacao(programa.id, "conhecimento_local", detalhes_locais)
        partes.append(
            f"Detalhe real do lugar onde a rádio fica, pra puxar assunto local com naturalidade quando "
            f"fizer sentido (não force, não cite em toda fala): {detalhe_local}."
        )

    biblia = account.biblia_radio or {}
    if biblia.get("historia"):
        partes.append(
            f"História real da rádio (fatos fixos, nunca invente nem contradiga): {biblia['historia']}."
        )
    detalhes_biblia = [f"programa da grade: {p}" for p in biblia.get("programas_grade") or []]
    detalhes_biblia += [f"rotina real da rádio: {r}" for r in biblia.get("rotina") or []]
    detalhes_biblia += [f"colega de trabalho que existe na rádio (mas não está ao vivo agora): {c}" for c in biblia.get("equipe") or []]
    detalhes_biblia += [f"hábito de trabalho real: {h}" for h in biblia.get("habitos_trabalho") or []]
    if detalhes_biblia:
        detalhe_biblia = _proxima_variacao(programa.id, "biblia_radio", detalhes_biblia)
        partes.append(
            f"Detalhe real de como a rádio funciona por dentro, pra soar como um lugar de trabalho de "
            f"verdade quando fizer sentido (não force, não cite em toda fala): {detalhe_biblia}."
        )

    if programa.topicos_proibidos:
        proibidos = ", ".join(programa.topicos_proibidos)
        partes.append(f"Nunca fale sobre: {proibidos}.")

    if programa.musicas_bloqueadas:
        bloqueadas = ", ".join(programa.musicas_bloqueadas)
        partes.append(f"Nunca toque, recomende ou promova estas músicas/artistas: {bloqueadas}.")

    if programa.estrutura_blocos:
        sequencia = " -> ".join(programa.estrutura_blocos)
        if programa.ia_pode_adicionar_blocos and getattr(programa, "perfil_programacao", "padrao") != "musical_companhia":
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
        partes.append(
            f"Pesquisa externa habilitada. Fontes de pesquisa permitidas: {fontes}. "
            "Na apuração jornalística, as fontes de notícias configuradas têm prioridade. "
            f"{programa.instrucoes_pesquisa} "
            "Notícias e fatos recentes só podem ser usados quando houver apuração com fontes "
            "anexada ao contexto. A autorização para pesquisar não comprova que uma busca ocorreu; "
            "sem apuração, não afirme que consultou portais nem use memória como notícia atual."
        )
    else:
        partes.append("Pesquisa externa desabilitada. Não invente notícias, links, números ou fatos recentes.")

    partes.append("Se perguntarem sobre outro assunto, recuse com simpatia e traga a conversa de volta para a rádio.")
    partes.append(
        "Pode noticiar ato administrativo e serviço público como fato -- obra, interdição, calendário, "
        "decreto, boletim oficial, concurso, horário de atendimento -- mesmo envolvendo prefeitura ou "
        "outro órgão público. NÃO pode noticiar disputa político-partidária, declaração de candidato, "
        "pesquisa eleitoral, nem emitir juízo de valor sobre governo, partido ou autoridade. Nunca opine "
        "sobre religião ou outro tema sensível que não seja fato administrativo/serviço público, mesmo "
        "que não esteja na lista de proibidos."
    )
    partes.append(
        "Nunca comente o próprio formato do programa nem fale sobre rádio em vez de fazer rádio -- "
        "proibidas frases como 'clima de rádio', 'cara de ao vivo', 'perto do ouvinte', 'sentir o pulso', "
        "'perfil da rádio', 'ritmo gostoso' e qualquer variação de linguagem que descreva o programa de fora "
        "em vez de simplesmente apresentá-lo."
    )
    partes.append(
        "Regra geral acima de qualquer outra: NUNCA invente fato específico sobre a cidade, a rádio, o "
        "clima, notícia, trânsito, evento, nome de rua/bairro/comércio, dado de ouvinte, ou qualquer outra "
        "informação factual que não foi explicitamente informada a você neste prompt. Se não tiver certeza "
        "ou não foi informado, não fale sobre aquele detalhe específico -- prefira comentar de forma "
        "genérica ou simplesmente não tocar no assunto, nunca preencher a lacuna inventando."
    )

    if multi_voz:
        partes.append(
            "Responda APENAS com um JSON compacto, sem markdown e sem texto fora do JSON, exatamente no formato "
            '{"linhas": [{"locutor": "<nome exato de um dos apresentadores acima>", "texto": "..."}]}. '
            "Gere entre 2 e 4 linhas alternando os apresentadores de forma natural, como uma conversa de verdade "
            "(um completa o outro, reage, faz pergunta) -- não uma lista de falas soltas e desconectadas."
        )

    return "\n".join(partes)
