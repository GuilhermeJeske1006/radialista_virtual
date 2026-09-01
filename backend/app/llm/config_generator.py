import json
import logging

from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS
from app.llm.client import gerar_configuracao
from app.llm.json_utils import extrair_json
from app.llm.tipos_radio import contexto_prompt_tipo_radio
from app.tts.voices import VOZES_DISPONIVEIS, voz_valida

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


def _montar_system_prompt_completo(tipo_radio: str | None = None) -> str:
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
    linha_perfil = _linha_perfil_tipo_radio(tipo_radio)
    if linha_perfil:
        linhas.append(linha_perfil)
    linhas.append(_regras_comuns_texto())
    linhas.append(
        "voz_id tem que ser exatamente um destes ids do catalogo (escolha o que combinar melhor "
        "com o tom pedido):"
    )
    linhas.append(_catalogo_vozes_texto())
    return "\n".join(linhas)


def _montar_system_prompt_programa(
    nome_locutor: str, personalidade: str, tipo_radio: str | None = None
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
    linha_perfil = _linha_perfil_tipo_radio(tipo_radio)
    if linha_perfil:
        linhas.append(linha_perfil)
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


def gerar_configuracao_ia(descricao_usuario: str, tipo_radio: str | None = None) -> tuple[dict, dict]:
    """Gera configuracao completa de radialista + programa a partir de uma descricao livre.

    `tipo_radio` (ver app/llm/tipos_radio.py) entra como perfil padrao no prompt, usado
    mesmo quando `descricao_usuario` esta vazia. Retorna (dados_radialista, dados_programa)
    ja sanitizados (voz_id valido, sem topicos sempre-bloqueados). Levanta ValueError se o
    LLM nao retornar um JSON valido/completo -- quem chama decide como reportar isso
    (ex.: 502 na API).
    """
    entrada = descricao_usuario or "Sem descricao adicional -- use so o perfil do tipo de radio informado."
    texto_resposta = gerar_configuracao(_montar_system_prompt_completo(tipo_radio), entrada)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo")

    try:
        dados = extrair_json(texto_resposta)
        radialista = dict(dados["radialista"])
        programa = dict(dados["programa"])
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Resposta de geracao de configuracao invalida: %r", texto_resposta)
        raise ValueError("LLM retornou configuracao invalida") from exc

    if not voz_valida(radialista.get("voz_id")):
        radialista["voz_id"] = VOZES_DISPONIVEIS[0]["voz_id"]

    return radialista, _sanitizar_programa(programa)


def gerar_programa_ia(
    descricao_usuario: str, nome_locutor: str, personalidade: str, tipo_radio: str | None = None
) -> dict:
    """Gera configuracao completa de um programa novo pra um radialista ja existente.

    `tipo_radio` (ver app/llm/tipos_radio.py) entra como perfil padrao no prompt, usado
    mesmo quando `descricao_usuario` esta vazia. Retorna dados_programa ja sanitizado.
    Levanta ValueError se o LLM nao retornar um JSON valido/completo -- quem chama decide
    como reportar isso (ex.: 502 na API).
    """
    system_prompt = _montar_system_prompt_programa(nome_locutor, personalidade, tipo_radio)
    entrada = descricao_usuario or "Sem descricao adicional -- use so o perfil do tipo de radio informado."
    texto_resposta = gerar_configuracao(system_prompt, entrada)
    if not texto_resposta:
        raise ValueError("LLM nao retornou conteudo")

    try:
        programa = dict(extrair_json(texto_resposta))
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Resposta de geracao de programa invalida: %r", texto_resposta)
        raise ValueError("LLM retornou configuracao invalida") from exc

    return _sanitizar_programa(programa)
