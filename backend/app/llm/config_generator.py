import json
import logging
import unicodedata

from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS
from app.llm.client import gerar_classificacao, gerar_configuracao
from app.llm.exemplos_config import exemplos_texto
from app.llm.json_utils import extrair_json
from app.llm.tipos_radio import contexto_prompt_tipo_radio
from app.models.account import Account
from app.tts.voices import VOZES_DISPONIVEIS, descricao_voz, voz_valida

logger = logging.getLogger("radialista.config_generator")

_CAMPOS_PROGRAMA_JSON = (
    '{"nome": str, "descricao": str, "dias_semana": [int], "horario_inicio": "HH:MM", '
    '"horario_fim": "HH:MM", "tom": str, "topicos_permitidos": [str], "topicos_proibidos": [str], '
    '"mensagem_saudacao": str, "mensagem_recusa": str, "limite_mensagens_hora": int, '
    '"estrutura_blocos": [str], "perfil_programacao": "padrao" ou "musical_companhia", '
    '"ia_pode_adicionar_blocos": bool, "generos_musicais": [str], '
    '"musicas_permitidas": [str], "musicas_bloqueadas": [str], "criterios_busca_musicas": str, '
    '"assuntos_ao_vivo": [str], "tipos_noticias": [str], "fontes_noticias": [str], '
    '"pode_pesquisar": bool, "fontes_pesquisa": [str], "instrucoes_pesquisa": str, '
    '"perfil": "musical" ou "jornalismo" ou "esportivo" ou "variedades" ou "religioso" ou '
    '"comunitario", "dose_noticia": "nenhuma" ou "pitada" ou "equilibrada" ou "jornalistica"}'
)

_CAMPOS_RADIALISTA_JSON = (
    '{"nome_locutor": str, "personalidade": str, "voz_id": str, "timezone": "America/Sao_Paulo"}'
)

_BLOCOS_CANONICOS = (
    "retomada", "identificacao", "abertura", "musica", "comentario", "noticia",
    "escalada", "giro", "servico", "plantao", "reporter", "chamada_ouvinte", "encerramento",
)

_REGRAS_COMUNS = [
    "Para programas jornalísticos, boletins e comentários sobre atualidades, habilite pode_pesquisar=true "
    "e inclua blocos 'noticia' na estrutura. Preencha tipos_noticias com editorias concretas. "
    "NÃO invente fontes_noticias nem fontes_pesquisa (nomes de portal, domínio ou URL) -- deixe essas "
    "duas listas vazias, salvo se o usuário citar explicitamente um veículo real; elas são cadastradas "
    "à parte pelo dono da rádio e um domínio inventado quebra a apuração de notícia de verdade. "
    "Use instrucoes_pesquisa para priorizar notícias recentes da cidade/região, conferir datas e "
    "atribuir os fatos às fontes. Notícias não devem virar apenas curiosidades ou efemérides.",
    "perfil='jornalismo' é pra rádio majoritariamente noticiosa: use dose_noticia='jornalistica' e "
    "estrutura_blocos podendo incluir, além de 'noticia', os blocos 'escalada' (manchetes rápidas de "
    "abertura), 'giro' (atualização de notícias já dadas), 'servico' (trânsito/tempo/utilidade "
    "pública) e 'plantao' (só pra notícia de urgência real). Pra qualquer outro perfil, notícia é "
    "dosagem, não o programa inteiro: use dose_noticia='pitada' (programa musical com raríssima "
    "menção a notícia) ou 'equilibrada' (alguma notícia, sem virar jornal), e só inclua bloco "
    "'noticia'/'servico' na estrutura se isso realmente fizer sentido pro pedido do usuário.",
    "Use perfil_programacao='musical_companhia' quando o pedido for um programa predominantemente "
    "musical, com poucas intervenções de companhia. Nesse formato use ia_pode_adicionar_blocos=false "
    "e estrutura_blocos=['musica','musica','identificacao','musica','musica','retomada']; a abertura "
    "e o encerramento são automáticos. Para variedades, entrevistas, debate ou jornalismo, use 'padrao'.",
    "dias_semana usa inteiros (0=segunda ... 6=domingo); lista vazia significa todos os dias.",
    "horario_inicio e horario_fim no formato 24h HH:MM.",
    "Nunca inclua nenhum destes temas em topicos_permitidos, generos_musicais ou qualquer outro campo "
    "(sempre bloqueados no sistema): {bloqueados}.",
    "Inclua politica, religiao e temas sensiveis em topicos_proibidos por padrao, a menos que o "
    "usuario peca explicitamente o contrario.",
    "Preencha com conteudo relevante e especifico pro pedido do usuario -- nada generico tipo 'a "
    "definir' -- EXCETO musicas_permitidas e musicas_bloqueadas, que devem ficar vazias a menos que o "
    "usuario cite musicas/artistas especificos: sao whitelist/blacklist restritivas usadas de verdade "
    "na busca de musica, e uma lista inventada de 8 titulos vira a playlist inteira da radio.",
    "estrutura_blocos so pode usar estes valores (nada fora daqui -- bloco fora do vocabulario nao "
    f"recebe comportamento automatico nenhum): {', '.join(_BLOCOS_CANONICOS)}. Sequencia plausivel "
    "ex: abertura, musica, chamada_ouvinte, noticia, encerramento.",
    "Mantenha cada lista com no maximo 8 itens e cada texto curto e direto, pra caber a resposta "
    "inteira no limite de tokens.",
    "O sistema ja filtra automaticamente, na busca de musica, covers amadores/caseiros, karaoke, "
    "compilacoes/coletaneas ('as mais tocadas', mega mix, top N), video de baixa resolucao e "
    "conteudo tipo reacao/documentario/making-of -- nao repita isso em criterios_busca_musicas. Use "
    "esse campo pra criterios de CONTEUDO que esse filtro automatico nao cobre (ex: evitar letra "
    "explicita, variar artista, priorizar lancamentos recentes ou classicos, conforme o pedido).",
]


def _catalogo_vozes_texto(vozes_em_uso: set[str] | None = None) -> str:
    vozes_em_uso = vozes_em_uso or set()
    linhas = []
    for v in VOZES_DISPONIVEIS:
        marca = (
            " -- ja usada por outro radialista dessa conta, so repita se combinar muito melhor "
            "que as demais"
            if v["voz_id"] in vozes_em_uso
            else ""
        )
        linhas.append(f'- "{v["voz_id"]}": {v["nome"]} ({v["genero"]}, {v["descricao"]}){marca}')
    return "\n".join(linhas)


def _regras_comuns_texto() -> str:
    bloqueados = ", ".join(TERMOS_SEMPRE_BLOQUEADOS)
    return "\n".join(regra.format(bloqueados=bloqueados) for regra in _REGRAS_COMUNS)


def _linha_perfil_tipo_radio(tipo_radio: str | None) -> str | None:
    contexto = contexto_prompt_tipo_radio(tipo_radio)
    if not contexto:
        return None
    return (
        f"Perfil da radio (tipo pre-definido escolhido pelo usuario): {contexto} "
        "Use isso como base pros campos de genero musical, tom e topicos, mesmo que a "
        "descricao do usuario abaixo seja curta ou vaga -- so desvie desse perfil se a "
        "descricao pedir algo claramente diferente."
    )


def _linha_contexto_conta(account: Account | None) -> str | None:
    """Identidade real da radio (nome, cidade, frequencia, slogan) -- sem isso a IA gera um
    radialista/programa generico que poderia servir pra qualquer radio do Brasil, em vez de
    algo com sotaque, referencia regional e identidade de marca proprios dessa conta."""
    if account is None:
        return None
    dados = []
    if account.nome_radio:
        dados.append(f"nome '{account.nome_radio}'")
    if account.cidade:
        dados.append(
            f"cidade/regiao {account.cidade} (adapte referencias regionais, gírias e sotaque a "
            "essa cidade quando fizer sentido pra personalidade e pros topicos)"
        )
    if account.frequencia:
        dados.append(f"frequencia {account.frequencia}")
    if account.slogan:
        dados.append(f"slogan '{account.slogan}'")
    if not dados:
        return None
    return f"Dados reais dessa radio (use pra dar identidade e coerencia de marca): {', '.join(dados)}."


_DIAS_ABREV = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def _texto_dias_semana(dias: list[int] | None) -> str:
    if not dias:
        return "todos os dias"
    return "/".join(_DIAS_ABREV[d] for d in dias if 0 <= d <= 6)


def _texto_horario_programa(programa: dict) -> str:
    inicio = programa.get("horario_inicio")
    fim = programa.get("horario_fim")
    if not inicio or not fim:
        return ""
    return f", {_texto_dias_semana(programa.get('dias_semana'))} {inicio}-{fim}"


def _linha_roster_existente(roster_existente: list[dict] | None) -> str | None:
    """Radialistas/programas ja existentes na conta -- sem isso a IA pode gerar um radialista
    quase identico a um que ja existe (mesmo nome, mesma personalidade, mesmo estilo de
    programa), o que confunde o ouvinte e nao agrega nada de novo pra radio."""
    if not roster_existente:
        return None
    linhas = []
    for radialista in roster_existente:
        personalidade = (radialista.get("personalidade") or "").strip()
        programas = radialista.get("programas") or []
        if not personalidade and not programas:
            continue
        partes = [str(radialista.get("nome_locutor") or "sem nome")]
        if personalidade:
            partes.append(f"personalidade: {personalidade[:150]}")
        if programas:
            resumo = "; ".join(
                f"'{p['nome']}' (tom: {p['tom']}{_texto_horario_programa(p)})" for p in programas
            )
            partes.append(f"programas: {resumo}")
        linhas.append(" -- ".join(partes))
    if not linhas:
        return None
    texto = "\n".join(f"- {linha}" for linha in linhas)
    return (
        f"Radialistas e programas que ja existem nessa radio:\n{texto}\n"
        "NAO repita nome, personalidade nem estilo de programa iguais aos de cima -- crie algo "
        "com identidade propria, mas que combine com o universo dessa radio. NAO proponha "
        "horario_inicio/horario_fim que colida com os horarios acima nos mesmos dias -- o "
        "sistema rejeita a criacao quando o horario de dois programas se sobrepoe nos mesmos dias "
        "da semana."
    )


def _linha_programas_existentes(programas_existentes: list[dict] | None) -> str | None:
    """Todos os programas da conta (desse radialista e dos outros), usado so na geracao de
    programa avulso. Nome/genero repetido so' importa pros programas do MESMO radialista, mas
    conflito de horario vale pra conta inteira -- so um programa toca por vez na frequencia."""
    if not programas_existentes:
        return None

    proprios = [p for p in programas_existentes if p.get("mesmo_radialista")]
    outros = [p for p in programas_existentes if not p.get("mesmo_radialista")]
    linhas = []

    if proprios:
        texto = "; ".join(
            f"'{p['nome']}' (tom: {p['tom']}, generos: "
            f"{', '.join(p.get('generos_musicais') or []) or 'nao definido'}{_texto_horario_programa(p)})"
            for p in proprios
        )
        linhas.append(
            f"Esse radialista ja apresenta: {texto}. NAO repita nome nem generos praticamente "
            "identicos -- crie um programa com identidade propria dentro do mesmo universo."
        )
    if outros:
        texto = "; ".join(f"'{p['nome']}'{_texto_horario_programa(p)}" for p in outros)
        linhas.append(f"Outros locutores dessa mesma radio ja ocupam a grade em: {texto}.")
    if not linhas:
        return None

    linhas.append(
        "NAO proponha horario_inicio/horario_fim que colida com NENHUM dos horarios acima nos "
        "mesmos dias, nem os dos programas de outros locutores -- so um programa toca por vez "
        "nessa radio, e o sistema rejeita a criacao quando ha sobreposicao de horario."
    )
    return "\n".join(linhas)


def _linha_voz_radialista(voz_id: str | None) -> str | None:
    descricao = descricao_voz(voz_id)
    if not descricao:
        return None
    return (
        f"A voz ja escolhida pra esse radialista e: {descricao}. Escreva a personalidade e o "
        "tom do programa de um jeito que combine com essa voz (ex: nao escreva personalidade "
        "'grave e solene' pra uma voz descrita como jovem e energetica)."
    )


def _montar_system_prompt_completo(
    tipo_radio: str | None = None,
    account: Account | None = None,
    roster_existente: list[dict] | None = None,
) -> str:
    linhas = [
        "Voce e um especialista em programacao de radio no Brasil.",
        "A partir de uma descricao curta do usuario (genero musical, tom, publico etc.), gere a "
        "configuracao completa de um radialista virtual e do seu primeiro programa, prontos pra uso.",
        "",
        "Responda APENAS com um JSON compacto, sem markdown, sem comentarios e sem explicacao, "
        "exatamente no formato:",
        f'{{"radialista": {_CAMPOS_RADIALISTA_JSON}, "programa": {_CAMPOS_PROGRAMA_JSON}}}',
        "",
    ]
    for linha in (
        _linha_perfil_tipo_radio(tipo_radio),
        _linha_contexto_conta(account),
        _linha_roster_existente(roster_existente),
    ):
        if linha:
            linhas.append(linha)
    linhas.append(_regras_comuns_texto())
    linhas.append(
        "voz_id tem que ser exatamente um destes ids do catalogo (escolha o que combinar melhor "
        "com o tom pedido e com a personalidade que voce vai escrever):"
    )
    linhas.append(_catalogo_vozes_texto())
    return "\n".join(linhas)


def _montar_system_prompt_persona(
    tipo_radio: str | None = None,
    account: Account | None = None,
    roster_existente: list[dict] | None = None,
) -> str:
    """Prompt so' da persona (nome/personalidade/voz) -- ver Fase 3 do plano de melhoria:
    gerar a persona primeiro e so' depois o programa (com a persona ja resolvida como contexto,
    ver _montar_system_prompt_programa) rende resultado mais coerente que gerar os ~25 campos
    dos dois de uma vez, e e' o que viabiliza refinamento parcial (trocar so' a voz/nome sem
    regenerar a grade inteira, ver Fase 7)."""
    vozes_em_uso = {r["voz_id"] for r in (roster_existente or []) if r.get("voz_id")}
    linhas = [
        "Voce e um especialista em programacao de radio no Brasil.",
        "A partir de uma descricao curta do usuario (genero musical, tom, publico etc.), crie a "
        "persona de um radialista virtual novo: nome, personalidade e voz.",
        "",
        "Responda APENAS com um JSON compacto, sem markdown, sem comentarios e sem explicacao, "
        "exatamente no formato:",
        _CAMPOS_RADIALISTA_JSON,
        "",
    ]
    for linha in (
        _linha_perfil_tipo_radio(tipo_radio),
        _linha_contexto_conta(account),
        _linha_roster_existente(roster_existente),
    ):
        if linha:
            linhas.append(linha)
    linhas.append(
        "voz_id tem que ser exatamente um destes ids do catalogo (escolha o que combinar melhor "
        "com o tom pedido e com a personalidade que voce vai escrever):"
    )
    linhas.append(_catalogo_vozes_texto(vozes_em_uso))
    return "\n".join(linhas)


def programas_existentes_do_roster(roster_existente: list[dict] | None) -> list[dict]:
    """Achata o roster (radialistas + seus programas, ver app.config.router) no formato flat
    que _linha_programas_existentes espera. Usado quando gerar_configuracao_ia gera um
    radialista NOVO -- por definicao ele ainda nao tem programa proprio, entao todo programa
    existente na conta e' 'de outro radialista' (mesmo_radialista sempre False)."""
    return [
        {**programa, "mesmo_radialista": False}
        for radialista in (roster_existente or [])
        for programa in (radialista.get("programas") or [])
    ]


def _montar_system_prompt_programa(
    nome_locutor: str,
    personalidade: str,
    tipo_radio: str | None = None,
    account: Account | None = None,
    voz_id: str | None = None,
    programas_existentes: list[dict] | None = None,
) -> str:
    linhas = [
        "Voce e um especialista em programacao de radio no Brasil.",
        f"O radialista virtual '{nome_locutor}' ja existe, com esta personalidade: "
        f"{personalidade or 'nao definida'}.",
        "A partir de uma descricao curta do usuario (genero musical, tom, publico, horario etc.), "
        "gere a configuracao completa de um NOVO programa pra esse radialista, prontos pra uso. "
        "O tom e as mensagens do programa devem soar coerentes com a personalidade do radialista.",
        "",
        "Responda APENAS com um JSON compacto, sem markdown, sem comentarios e sem explicacao, "
        "exatamente no formato:",
        _CAMPOS_PROGRAMA_JSON,
        "",
    ]
    for linha in (
        _linha_perfil_tipo_radio(tipo_radio),
        _linha_contexto_conta(account),
        _linha_voz_radialista(voz_id),
        _linha_programas_existentes(programas_existentes),
    ):
        if linha:
            linhas.append(linha)
    linhas.append(_regras_comuns_texto())
    linhas.append(exemplos_texto())
    return "\n".join(linhas)


_PERFIS_VALIDOS = ("musical", "jornalismo", "esportivo", "variedades", "religioso", "comunitario")
_DOSES_NOTICIA_VALIDAS = ("nenhuma", "pitada", "equilibrada", "jornalistica")

# Campos-lista e campos-texto varridos por _sanitizar_programa. topicos_proibidos fica de fora
# de proposito -- ele EXISTE pra guardar tema sensivel (o usuario pode listar "politica",
# "religiao" etc ali), entao bloquear termo bloqueado nesse campo especifico seria ao contrario.
_CAMPOS_LISTA_SANITIZAVEIS = (
    "topicos_permitidos", "generos_musicais", "assuntos_ao_vivo", "tipos_noticias",
    "fontes_noticias", "fontes_pesquisa", "musicas_permitidas", "musicas_bloqueadas",
)
_CAMPOS_TEXTO_SANITIZAVEIS = (
    "nome", "descricao", "tom", "mensagem_saudacao", "mensagem_recusa",
    "criterios_busca_musicas", "instrucoes_pesquisa", "publico_alvo",
)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _normalizar(texto: str) -> str:
    return _sem_acento(str(texto).lower())


def _contem_termo_bloqueado(texto_normalizado: str, termos_normalizados: list[str]) -> bool:
    return any(termo in texto_normalizado for termo in termos_normalizados)


def _sanitizar_programa(programa: dict) -> dict:
    """Varre TODO campo de texto/lista do programa gerado atras de termo sempre-bloqueado, por
    substring normalizada (sem acento, minusculo) -- nao so' igualdade exata em dois campos.
    Sem isso, um termo bloqueado escrito dentro de uma frase (ou em qualquer campo fora dos dois
    checados antes) passava direto pro banco."""
    termos = [_normalizar(t) for t in TERMOS_SEMPRE_BLOQUEADOS]

    for campo in _CAMPOS_LISTA_SANITIZAVEIS:
        itens = programa.get(campo) or []
        programa[campo] = [t for t in itens if not _contem_termo_bloqueado(_normalizar(t), termos)]

    for campo in _CAMPOS_TEXTO_SANITIZAVEIS:
        valor = programa.get(campo)
        if valor and _contem_termo_bloqueado(_normalizar(valor), termos):
            logger.warning("Campo %r da geracao continha termo sempre-bloqueado -- esvaziado", campo)
            programa[campo] = ""

    if programa.get("perfil") not in _PERFIS_VALIDOS:
        programa["perfil"] = "musical"
    if programa.get("dose_noticia") not in _DOSES_NOTICIA_VALIDAS:
        programa["dose_noticia"] = "jornalistica" if programa["perfil"] == "jornalismo" else "pitada"
    return programa


_QUALIDADE_SYSTEM_PROMPT = (
    "Voce avalia a qualidade de uma configuracao de radialista/programa de radio, gerada por outra "
    "IA a partir de um pedido de usuario. Responda EXATAMENTE no formato 'NOTA: motivo', onde NOTA "
    "e um numero inteiro de 0 a 10 e motivo e uma frase curta (ex: '4: personalidade generica, "
    "poderia ser qualquer radio'). De nota abaixo de 6 se: a personalidade for generica/cliche sem "
    "nenhum traco especifico; tom, topicos ou generos_musicais forem vagos demais ('musicas "
    "variadas', 'assuntos gerais', 'a definir'); estrutura_blocos nao fizer sentido pro tipo de "
    "radio pedido; ou os campos parecerem copiados de um template sem adaptar ao pedido do usuario. "
    "De nota 8 a 10 se os campos forem especificos, coerentes entre si e claramente adaptados ao "
    "pedido e ao contexto informados."
)


def _avaliar_qualidade(radialista: dict | None, programa: dict) -> tuple[int, str]:
    """Pede uma segunda opiniao (modelo barato) sobre o quao especifica/adaptada ficou a
    configuracao gerada, pra decidir se vale regenerar em vez de entregar algo generico ao
    usuario. Nunca bloqueia a geracao por falha nessa avaliacao -- em qualquer erro, aprova
    (nota 10) e segue com o que foi gerado."""
    corpo = {"programa": programa}
    if radialista is not None:
        corpo["radialista"] = radialista
    resumo = json.dumps(corpo, ensure_ascii=False)
    try:
        resposta = gerar_classificacao(_QUALIDADE_SYSTEM_PROMPT, resumo)
    except Exception:
        logger.warning("Falha ao avaliar qualidade da configuracao gerada", exc_info=True)
        return 10, ""

    nota_texto, _, motivo = resposta.strip().partition(":")
    digitos = "".join(c for c in nota_texto if c.isdigit())
    try:
        nota = int(digitos) if digitos else 10
    except ValueError:
        nota = 10
    return nota, motivo.strip()


_NOTA_MINIMA_ACEITAVEL = 6


def gerar_persona_ia(
    descricao_usuario: str,
    tipo_radio: str | None = None,
    account: Account | None = None,
    roster_existente: list[dict] | None = None,
) -> dict:
    """Gera so' a persona (nome/personalidade/voz) de um radialista novo -- primeira metade de
    gerar_configuracao_ia (ver Fase 3), exposta a parte pra permitir refinamento parcial (Fase
    7: "outro nome"/"outra voz" na tela de revisao, sem regenerar o programa junto). Retorna o
    dict ja com voz_id valido (cai pra voz padrao se o LLM devolver um id fora do catalogo).
    Levanta ValueError se o LLM nao retornar um JSON valido -- quem chama decide o fallback."""
    entrada = descricao_usuario or "Sem descricao adicional -- use so o perfil do tipo de radio informado."
    system_prompt = _montar_system_prompt_persona(tipo_radio, account, roster_existente)
    radialista = _gerar_e_extrair_radialista(system_prompt, entrada)
    if not voz_valida(radialista.get("voz_id")):
        radialista["voz_id"] = VOZES_DISPONIVEIS[0]["voz_id"]
    return radialista


def gerar_configuracao_ia(
    descricao_usuario: str,
    tipo_radio: str | None = None,
    account: Account | None = None,
    roster_existente: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Gera configuracao completa de radialista + programa a partir de uma descricao livre, em
    DUAS chamadas (ver Fase 3 do plano de melhoria): primeiro a persona (nome/personalidade/voz),
    depois o programa com a persona ja resolvida como contexto -- mesma chamada de
    gerar_programa_ia, so' que pra um radialista que ainda nao existe. Gerar a persona sozinha
    primeiro rende melhor resultado que dividir atencao entre ~25 campos numa chamada so', e e'
    o que abre espaco pra refinamento parcial (trocar so' a voz sem regenerar a grade, Fase 7).

    `tipo_radio` (ver app/llm/tipos_radio.py) entra como perfil padrao no prompt, usado
    mesmo quando `descricao_usuario` esta vazia. `account` (nome/cidade/frequencia/slogan da
    radio) e `roster_existente` (radialistas/programas ja cadastrados na conta, ver
    app.config.router) sao contexto opcional pra deixar a geracao mais especifica e coerente
    com essa radio em particular, em vez de generica. Retorna (dados_radialista, dados_programa)
    ja sanitizados (voz_id valido, sem topicos sempre-bloqueados). Levanta ValueError se o
    LLM nao retornar um JSON valido/completo -- quem chama decide como reportar isso
    (ex.: 502 na API).
    """
    entrada = descricao_usuario or "Sem descricao adicional -- use so o perfil do tipo de radio informado."

    radialista = gerar_persona_ia(descricao_usuario, tipo_radio, account, roster_existente)

    programas_existentes = programas_existentes_do_roster(roster_existente)
    system_prompt_programa = _montar_system_prompt_programa(
        radialista.get("nome_locutor") or "",
        radialista.get("personalidade") or "",
        tipo_radio,
        account,
        radialista.get("voz_id"),
        programas_existentes,
    )
    programa = _gerar_e_extrair_programa(system_prompt_programa, entrada)

    nota, motivo = _avaliar_qualidade(radialista, programa)
    if nota < _NOTA_MINIMA_ACEITAVEL:
        logger.info("Programa gerado ficou generico (nota %s: %s) -- regenerando uma vez", nota, motivo)
        motivo_texto = motivo or "faltou especificidade"
        entrada_reforcada = (
            f"{entrada}\n\nATENCAO: uma tentativa anterior ficou generica demais ({motivo_texto}). "
            "Seja bem mais especifico e concreto em tom, topicos e generos_musicais -- evite "
            "qualquer termo vago tipo 'variado' ou 'geral'."
        )
        try:
            programa = _gerar_e_extrair_programa(system_prompt_programa, entrada_reforcada)
        except ValueError:
            logger.warning("Regeneracao falhou -- mantendo a primeira tentativa (nota %s)", nota)

    return radialista, _sanitizar_programa(programa)


def _gerar_e_extrair_radialista(system_prompt: str, entrada: str) -> dict:
    texto_resposta = gerar_configuracao(system_prompt, entrada)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo")
    try:
        return dict(extrair_json(texto_resposta))
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Resposta de geracao de persona invalida: %r", texto_resposta)
        raise ValueError("LLM retornou persona invalida") from exc


def gerar_programa_ia(
    descricao_usuario: str,
    nome_locutor: str,
    personalidade: str,
    tipo_radio: str | None = None,
    account: Account | None = None,
    voz_id: str | None = None,
    programas_existentes: list[dict] | None = None,
) -> dict:
    """Gera configuracao completa de um programa novo pra um radialista ja existente.

    `tipo_radio` (ver app/llm/tipos_radio.py) entra como perfil padrao no prompt, usado
    mesmo quando `descricao_usuario` esta vazia. `account`, `voz_id` (voz ja escolhida pro
    radialista) e `programas_existentes` (outros programas desse mesmo radialista) sao
    contexto opcional pra deixar a geracao mais especifica e coerente. Retorna dados_programa
    ja sanitizado. Levanta ValueError se o LLM nao retornar um JSON valido/completo -- quem
    chama decide como reportar isso (ex.: 502 na API).
    """
    system_prompt = _montar_system_prompt_programa(
        nome_locutor, personalidade, tipo_radio, account, voz_id, programas_existentes
    )
    entrada = descricao_usuario or "Sem descricao adicional -- use so o perfil do tipo de radio informado."

    programa = _gerar_e_extrair_programa(system_prompt, entrada)

    nota, motivo = _avaliar_qualidade(None, programa)
    if nota < _NOTA_MINIMA_ACEITAVEL:
        logger.info("Programa gerado ficou generico (nota %s: %s) -- regenerando uma vez", nota, motivo)
        motivo_texto = motivo or "faltou especificidade"
        entrada_reforcada = (
            f"{entrada}\n\nATENCAO: uma tentativa anterior ficou generica demais ({motivo_texto}). "
            "Seja bem mais especifico e concreto em tom, topicos e generos_musicais -- evite "
            "qualquer termo vago tipo 'variado' ou 'geral'."
        )
        try:
            programa = _gerar_e_extrair_programa(system_prompt, entrada_reforcada)
        except ValueError:
            logger.warning("Regeneracao falhou -- mantendo a primeira tentativa (nota %s)", nota)

    return _sanitizar_programa(programa)


def _gerar_e_extrair_programa(system_prompt: str, entrada: str) -> dict:
    texto_resposta = gerar_configuracao(system_prompt, entrada)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo")

    try:
        programa = dict(extrair_json(texto_resposta))
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Resposta de geracao de programa invalida: %r", texto_resposta)
        raise ValueError("LLM retornou configuracao invalida") from exc

    return programa


def _reparar_json(system_prompt: str, dados_invalidos: dict, erros: list[dict]) -> dict:
    """Uma unica tentativa de reparo (nunca loop -- mesmo padrao de _avaliar_qualidade):
    reenvia o JSON que falhou validacao Pydantic + os erros de campo, pedindo pro LLM corrigir
    SO o que quebrou, mantendo o resto igual. Levanta ValueError se o reparo tambem nao
    produzir JSON valido; quem chama decide o fallback (ex.: defaults por campo, ver Fase 6)."""
    detalhes = "; ".join(
        f"{'.'.join(str(p) for p in erro.get('loc', ()))}: {erro.get('msg', '')}" for erro in erros
    )
    pedido = (
        f"JSON anterior invalido: {json.dumps(dados_invalidos, ensure_ascii=False)}\n"
        f"Erros de validacao: {detalhes}\n"
        "Devolva o MESMO JSON completo, no MESMO formato de antes, corrigindo APENAS os campos "
        "com erro listados acima -- mantenha os demais campos exatamente iguais."
    )
    texto_resposta = gerar_configuracao(system_prompt, pedido)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo no reparo")
    try:
        return dict(extrair_json(texto_resposta))
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Reparo tambem retornou JSON invalido: %r", texto_resposta)
        raise ValueError("Reparo retornou JSON invalido") from exc


def reparar_configuracao_ia(
    tipo_radio: str | None,
    account: Account | None,
    roster_existente: list[dict] | None,
    dados_radialista: dict,
    dados_programa: dict,
    erros: list[dict],
) -> tuple[dict, dict]:
    """Reparo (ver _reparar_json) pro par radialista+programa de gerar_configuracao_ia, quando
    o par gerado falhou validacao Pydantic no router. Reconstroi o mesmo system_prompt (funcao
    deterministica dos mesmos argumentos usados na geracao original)."""
    system_prompt = _montar_system_prompt_completo(tipo_radio, account, roster_existente)
    corrigido = _reparar_json(
        system_prompt, {"radialista": dados_radialista, "programa": dados_programa}, erros
    )
    radialista = dict(corrigido["radialista"])
    programa = dict(corrigido["programa"])
    if not voz_valida(radialista.get("voz_id")):
        radialista["voz_id"] = VOZES_DISPONIVEIS[0]["voz_id"]
    return radialista, _sanitizar_programa(programa)


def reparar_programa_ia(
    nome_locutor: str,
    personalidade: str,
    tipo_radio: str | None,
    account: Account | None,
    voz_id: str | None,
    programas_existentes: list[dict] | None,
    dados_programa: dict,
    erros: list[dict],
) -> dict:
    """Reparo (ver _reparar_json) pro programa avulso de gerar_programa_ia."""
    system_prompt = _montar_system_prompt_programa(
        nome_locutor, personalidade, tipo_radio, account, voz_id, programas_existentes
    )
    corrigido = _reparar_json(system_prompt, dados_programa, erros)
    return _sanitizar_programa(dict(corrigido))


# --- Fase 7 do plano de melhoria: refinamento parcial ---------------------------------------
#
# Em vez de "gerar tudo de novo" consumir uma geracao completa toda vez que o cliente nao gosta
# de UM detalhe da proposta, a tela de revisao oferece acoes mais baratas e precisas:
#   - "outro nome"/"outra voz"  -> gerar_persona_ia de novo (Fase 3), mantendo o programa como
#     esta;
#   - "refazer a grade"         -> gerar_programa_ia de novo com a MESMA persona (ja existente
#     nas funcoes acima, nao precisa de codigo novo aqui);
#   - "ajustar" + texto livre   -> ajustar_programa_ia/ajustar_configuracao_ia abaixo, que
#     reaproveita a proposta atual como ponto de partida em vez de gerar do zero.


def _montar_system_prompt_ajuste_programa(tipo_radio: str | None = None, account: Account | None = None) -> str:
    linhas = [
        "Voce e um especialista em programacao de radio no Brasil.",
        "Voce recebe um programa de radio ja configurado (gerado por IA ou editado pelo usuario) "
        "e um pedido de ajuste em linguagem livre. Aplique SO o que foi pedido -- todo campo que "
        "o pedido nao menciona tem que permanecer EXATAMENTE igual ao valor recebido, mesmo texto "
        "e mesmas listas, nao reescreva o que nao foi pedido pra mudar.",
        "",
        "Responda APENAS com um JSON compacto, sem markdown, sem comentarios e sem explicacao, "
        "exatamente no formato:",
        _CAMPOS_PROGRAMA_JSON,
        "",
    ]
    for linha in (_linha_perfil_tipo_radio(tipo_radio), _linha_contexto_conta(account)):
        if linha:
            linhas.append(linha)
    linhas.append(_regras_comuns_texto())
    return "\n".join(linhas)


def _montar_system_prompt_ajuste_completo(tipo_radio: str | None = None, account: Account | None = None) -> str:
    linhas = [
        "Voce e um especialista em programacao de radio no Brasil.",
        "Voce recebe a persona de um radialista virtual e o programa dele, ja configurados "
        "(gerados por IA ou editados pelo usuario), e um pedido de ajuste em linguagem livre. "
        "Aplique SO o que foi pedido -- todo campo que o pedido nao menciona tem que permanecer "
        "EXATAMENTE igual ao valor recebido, nao reescreva o que nao foi pedido pra mudar.",
        "",
        "Responda APENAS com um JSON compacto, sem markdown, sem comentarios e sem explicacao, "
        "exatamente no formato:",
        f'{{"radialista": {_CAMPOS_RADIALISTA_JSON}, "programa": {_CAMPOS_PROGRAMA_JSON}}}',
        "",
    ]
    for linha in (_linha_perfil_tipo_radio(tipo_radio), _linha_contexto_conta(account)):
        if linha:
            linhas.append(linha)
    linhas.append(_regras_comuns_texto())
    return "\n".join(linhas)


def ajustar_programa_ia(
    instrucao: str,
    programa_atual: dict,
    tipo_radio: str | None = None,
    account: Account | None = None,
) -> dict:
    """Aplica um ajuste em linguagem livre (ex.: "mais serio", "tira o bloco de noticia",
    "comeca as seis") sobre um programa ja gerado/editado -- uma chamada so', reaproveitando o
    que ja existe em vez de regenerar do zero (ver Fase 7 do plano de melhoria). Levanta
    ValueError se o LLM nao retornar JSON valido."""
    system_prompt = _montar_system_prompt_ajuste_programa(tipo_radio, account)
    pedido = (
        f"Programa atual: {json.dumps(programa_atual, ensure_ascii=False)}\n"
        f"Ajuste pedido pelo usuario: {instrucao}\n"
        "Devolva o JSON completo do programa, no MESMO formato, com o ajuste aplicado."
    )
    texto_resposta = gerar_configuracao(system_prompt, pedido)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo no ajuste")
    try:
        programa = dict(extrair_json(texto_resposta))
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Ajuste de programa retornou JSON invalido: %r", texto_resposta)
        raise ValueError("Ajuste retornou JSON invalido") from exc
    return _sanitizar_programa(programa)


def ajustar_configuracao_ia(
    instrucao: str,
    radialista_atual: dict,
    programa_atual: dict,
    tipo_radio: str | None = None,
    account: Account | None = None,
) -> tuple[dict, dict]:
    """Como ajustar_programa_ia, mas pro par radialista+programa (proposta ainda nao commitada
    da tela de revisao de gerar_configuracao_ia, ver Fase 7 do plano de melhoria)."""
    system_prompt = _montar_system_prompt_ajuste_completo(tipo_radio, account)
    pedido = (
        f"Radialista e programa atuais: "
        f"{json.dumps({'radialista': radialista_atual, 'programa': programa_atual}, ensure_ascii=False)}\n"
        f"Ajuste pedido pelo usuario: {instrucao}\n"
        'Devolva o JSON completo no formato {"radialista": ..., "programa": ...}, com o ajuste aplicado.'
    )
    texto_resposta = gerar_configuracao(system_prompt, pedido)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo no ajuste")
    try:
        dados = extrair_json(texto_resposta)
        radialista = dict(dados["radialista"])
        programa = dict(dados["programa"])
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Ajuste de radialista+programa retornou JSON invalido: %r", texto_resposta)
        raise ValueError("Ajuste retornou JSON invalido") from exc
    if not voz_valida(radialista.get("voz_id")):
        radialista["voz_id"] = VOZES_DISPONIVEIS[0]["voz_id"]
    return radialista, _sanitizar_programa(programa)
