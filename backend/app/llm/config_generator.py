import json
import logging

from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS
from app.llm.client import gerar_classificacao, gerar_configuracao
from app.llm.json_utils import extrair_json
from app.llm.tipos_radio import contexto_prompt_tipo_radio
from app.models.account import Account
from app.tts.voices import VOZES_DISPONIVEIS, descricao_voz, voz_valida

logger = logging.getLogger("radialista.config_generator")

_CAMPOS_PROGRAMA_JSON = (
    '{"nome": str, "descricao": str, "dias_semana": [int], "horario_inicio": "HH:MM", '
    '"horario_fim": "HH:MM", "tom": str, "topicos_permitidos": [str], "topicos_proibidos": [str], '
    '"mensagem_saudacao": str, "mensagem_recusa": str, "limite_mensagens_hora": int, '
    '"estrutura_blocos": [str], "ia_pode_adicionar_blocos": bool, "generos_musicais": [str], '
    '"musicas_permitidas": [str], "musicas_bloqueadas": [str], "criterios_busca_musicas": str, '
    '"assuntos_ao_vivo": [str], "tipos_noticias": [str], "fontes_noticias": [str], '
    '"pode_pesquisar": bool, "fontes_pesquisa": [str], "instrucoes_pesquisa": str}'
)

_CAMPOS_RADIALISTA_JSON = (
    '{"nome_locutor": str, "personalidade": str, "voz_id": str, "timezone": "America/Sao_Paulo"}'
)

_REGRAS_COMUNS = [
    "dias_semana usa inteiros (0=segunda ... 6=domingo); lista vazia significa todos os dias.",
    "horario_inicio e horario_fim no formato 24h HH:MM.",
    "Nunca inclua nenhum destes temas em topicos_permitidos, generos_musicais ou qualquer outro campo "
    "(sempre bloqueados no sistema): {bloqueados}.",
    "Inclua politica, religiao e temas sensiveis em topicos_proibidos por padrao, a menos que o "
    "usuario peca explicitamente o contrario.",
    "Preencha TODOS os campos com conteudo relevante e especifico pro pedido do usuario -- nada vazio, "
    "nada generico tipo 'a definir'. estrutura_blocos deve ser uma sequencia plausivel de blocos de um "
    "programa de radio (ex: abertura, musica, recado, noticia, encerramento).",
    "Mantenha cada lista com no maximo 8 itens e cada texto curto e direto, pra caber a resposta "
    "inteira no limite de tokens.",
    "O sistema ja filtra automaticamente, na busca de musica, covers amadores/caseiros, karaoke, "
    "compilacoes/coletaneas ('as mais tocadas', mega mix, top N), video de baixa resolucao e "
    "conteudo tipo reacao/documentario/making-of -- nao repita isso em criterios_busca_musicas. Use "
    "esse campo pra criterios de CONTEUDO que esse filtro automatico nao cobre (ex: evitar letra "
    "explicita, variar artista, priorizar lancamentos recentes ou classicos, conforme o pedido).",
]


def _catalogo_vozes_texto() -> str:
    return "\n".join(
        f'- "{v["voz_id"]}": {v["nome"]} ({v["genero"]}, {v["descricao"]})' for v in VOZES_DISPONIVEIS
    )


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
    texto = "\n".join(f"- {l}" for l in linhas)
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
    return "\n".join(linhas)


def _sanitizar_programa(programa: dict) -> dict:
    bloqueados = {termo.lower() for termo in TERMOS_SEMPRE_BLOQUEADOS}
    programa["topicos_permitidos"] = [
        t for t in (programa.get("topicos_permitidos") or []) if str(t).lower() not in bloqueados
    ]
    programa["generos_musicais"] = [
        t for t in (programa.get("generos_musicais") or []) if str(t).lower() not in bloqueados
    ]
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


def gerar_configuracao_ia(
    descricao_usuario: str,
    tipo_radio: str | None = None,
    account: Account | None = None,
    roster_existente: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Gera configuracao completa de radialista + programa a partir de uma descricao livre.

    `tipo_radio` (ver app/llm/tipos_radio.py) entra como perfil padrao no prompt, usado
    mesmo quando `descricao_usuario` esta vazia. `account` (nome/cidade/frequencia/slogan da
    radio) e `roster_existente` (radialistas/programas ja cadastrados na conta, ver
    app.config.router) sao contexto opcional pra deixar a geracao mais especifica e coerente
    com essa radio em particular, em vez de generica. Retorna (dados_radialista, dados_programa)
    ja sanitizados (voz_id valido, sem topicos sempre-bloqueados). Levanta ValueError se o
    LLM nao retornar um JSON valido/completo -- quem chama decide como reportar isso
    (ex.: 502 na API).
    """
    system_prompt = _montar_system_prompt_completo(tipo_radio, account, roster_existente)
    entrada = descricao_usuario or "Sem descricao adicional -- use so o perfil do tipo de radio informado."

    radialista, programa = _gerar_e_extrair_par(system_prompt, entrada)

    nota, motivo = _avaliar_qualidade(radialista, programa)
    if nota < _NOTA_MINIMA_ACEITAVEL:
        logger.info("Configuracao gerada ficou generica (nota %s: %s) -- regenerando uma vez", nota, motivo)
        motivo_texto = motivo or "faltou especificidade"
        entrada_reforcada = (
            f"{entrada}\n\nATENCAO: uma tentativa anterior ficou generica demais ({motivo_texto}). "
            "Seja bem mais especifico e concreto em personalidade, tom, topicos e generos_musicais "
            "-- evite qualquer termo vago tipo 'variado' ou 'geral'."
        )
        try:
            radialista, programa = _gerar_e_extrair_par(system_prompt, entrada_reforcada)
        except ValueError:
            logger.warning("Regeneracao falhou -- mantendo a primeira tentativa (nota %s)", nota)

    if not voz_valida(radialista.get("voz_id")):
        radialista["voz_id"] = VOZES_DISPONIVEIS[0]["voz_id"]

    return radialista, _sanitizar_programa(programa)


def _gerar_e_extrair_par(system_prompt: str, entrada: str) -> tuple[dict, dict]:
    texto_resposta = gerar_configuracao(system_prompt, entrada)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo")

    try:
        dados = extrair_json(texto_resposta)
        radialista = dict(dados["radialista"])
        programa = dict(dados["programa"])
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Resposta de geracao de configuracao invalida: %r", texto_resposta)
        raise ValueError("LLM retornou configuracao invalida") from exc

    return radialista, programa


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
