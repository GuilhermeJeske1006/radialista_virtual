"""Texto das 3 vinhetas de um programa (abertura, passagem, encerramento) -- uma unica chamada ao
LLM pedindo as tres em JSON. Nao consome a cota de geracoes de IA do usuario (ver
_registrar_geracao_ia em app.config.router): e' efeito colateral de criar o programa, nao um
pedido de geracao."""
import logging
import re

from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS
from app.llm.client import gerar_configuracao
from app.llm.json_utils import extrair_json
from app.llm.prompt_builder import instrucao_frequencia_falada, separador_frequencia
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.numeros import numero_por_extenso
from app.util.texto import lista_ou, sem_acento

logger = logging.getLogger("radialista.vinhetas")

PAPEIS = ("abertura", "passagem", "encerramento")

NOMES_PAPEL = {"abertura": "Abertura", "passagem": "Passagem", "encerramento": "Encerramento"}

# Vinheta longa demais deixa de ser vinheta -- corta no limite de uma fala de ~8s.
_MAX_CARACTERES = 160

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF‍️]", flags=re.UNICODE
)
_MARKDOWN_RE = re.compile(r"[*_#`~>\[\]|]")

_SYSTEM_PROMPT = (
    "Você escreve vinhetas de rádio brasileiras: frases curtas, de identificação, faladas por "
    "cima de uma trilha instrumental. Ritmo de vinheta, não de locutor conversando. Responda "
    "SOMENTE com JSON válido, sem texto antes ou depois, no formato "
    '{"abertura": "...", "passagem": "...", "encerramento": "..."}.'
)


def _frequencia_falada(frequencia: str) -> str:
    """"98.5 FM" -> "noventa e oito ponto cinco FM" -- so' usado no template local, que nao
    passa pelo LLM (o LLM recebe a mesma regra via instrucao_frequencia_falada)."""
    separador = separador_frequencia(frequencia)

    def _trocar(match: re.Match) -> str:
        inteiro, decimal = match.group(1), match.group(2)
        texto = numero_por_extenso(int(inteiro))
        if decimal is not None and separador:
            texto += f" {separador} " + numero_por_extenso(int(decimal))
        return texto

    return re.sub(r"(\d+)(?:[.,](\d+))?", _trocar, frequencia)


def _identificacao_radio(account: Account) -> str:
    nome = (account.nome_radio or "").strip() or "nossa rádio"
    if account.frequencia:
        return f"{nome}, {_frequencia_falada(account.frequencia.strip())}"
    return nome


def textos_template(account: Account, radialista: RadioConfig, programa: Programa) -> dict[str, str]:
    """Fallback local quando o LLM falha duas vezes -- o programa nunca fica sem vinheta."""
    radio = _identificacao_radio(account)
    locutor = (radialista.nome_locutor or "").strip()
    com_locutor = f", com {locutor}" if locutor else ""
    slogan = f" {account.slogan.strip().rstrip('.')}." if (account.slogan or "").strip() else ""
    return {
        "abertura": f"Tá começando o {programa.nome}{com_locutor}, aqui na {radio}.",
        "passagem": f"Você está ouvindo {programa.nome}, na {radio}.{slogan}",
        "encerramento": f"Terminou o {programa.nome}. Obrigado pela companhia. {radio}.{slogan}".strip(),
    }


def _montar_mensagem(account: Account, radialista: RadioConfig, programa: Programa) -> str:
    linhas = [
        f"Programa: {programa.nome}.",
        f"Descrição do programa: {programa.descricao or 'sem descrição'}.",
        f"Tom do programa: {programa.tom}.",
        f"Gêneros musicais: {lista_ou(programa.generos_musicais, 'variados')}.",
        f"Locutor: {radialista.nome_locutor or 'sem nome definido'}.",
        f"Personalidade do locutor: {radialista.personalidade or 'não informada'}.",
        f"Rádio: {account.nome_radio or 'não informado'}.",
        f"Frequência: {account.frequencia or 'não informada'}.",
        f"Slogan: {account.slogan or 'não informado'}.",
        f"Cidade: {account.cidade or 'não informada'}.",
        "",
        "Escreva as 3 vinhetas deste programa:",
        '- "abertura": apresenta o programa (ex.: "Começa agora o <programa>, com <locutor>...").',
        '- "passagem": identificação curta pra virada de bloco (programa + rádio ou slogan).',
        '- "encerramento": fecha o programa e reforça a marca da rádio.',
        "",
        "Regras:",
        "- Cada vinheta tem de 1 a 2 frases curtas, de 3 a 8 segundos falados (no máximo 18 palavras).",
        "- Português do Brasil com acentuação correta. Sem emoji, sem markdown, sem aspas internas.",
        "- Não invente dados da rádio que não foram informados acima.",
    ]
    instrucao = instrucao_frequencia_falada(account.frequencia)
    if instrucao:
        linhas.append(f"- {instrucao}")
    return "\n".join(linhas)


def _limpar(texto: str) -> str:
    texto = _EMOJI_RE.sub("", texto)
    texto = _MARKDOWN_RE.sub("", texto)
    texto = re.sub(r"\s+", " ", texto).strip().strip('"').strip()
    if len(texto) > _MAX_CARACTERES:
        corte = texto[:_MAX_CARACTERES]
        fim_frase = max(corte.rfind("."), corte.rfind("!"), corte.rfind("?"))
        texto = corte[: fim_frase + 1] if fim_frase > 20 else corte.rsplit(" ", 1)[0]
    return texto


def _contem_termo_bloqueado(texto: str) -> bool:
    normalizado = sem_acento(texto.lower())
    return any(sem_acento(termo.lower()) in normalizado for termo in TERMOS_SEMPRE_BLOQUEADOS)


def _validar_resposta(bruto: str) -> dict[str, str]:
    dados = extrair_json(bruto)
    if not isinstance(dados, dict):
        raise ValueError("resposta nao e' um objeto JSON")
    textos = {}
    for papel in PAPEIS:
        valor = dados.get(papel)
        if not isinstance(valor, str) or not _limpar(valor):
            raise ValueError(f"vinheta {papel!r} ausente ou vazia")
        textos[papel] = _limpar(valor)
    return textos


def gerar_textos_vinhetas(account: Account, radialista: RadioConfig, programa: Programa) -> dict[str, str]:
    """Devolve {papel: texto} pras 3 vinhetas. JSON invalido ganha 1 retry; se falhar de novo
    (ou o LLM estiver fora), cai no template local. Nunca levanta excecao."""
    mensagem = _montar_mensagem(account, radialista, programa)
    textos = None
    for tentativa in (1, 2):
        try:
            textos = _validar_resposta(gerar_configuracao(_SYSTEM_PROMPT, mensagem))
            break
        except Exception:
            logger.warning(
                "Falha ao gerar texto das vinhetas (tentativa %s/2): programa_id=%s",
                tentativa, programa.id, exc_info=True,
            )

    template = textos_template(account, radialista, programa)
    if textos is None:
        logger.warning("Vinhetas caindo no template local: programa_id=%s", programa.id)
        return template

    for papel, texto in textos.items():
        if _contem_termo_bloqueado(texto):
            logger.warning("Vinheta %r continha termo sempre-bloqueado -- trocada pelo template", papel)
            textos[papel] = template[papel]
    return textos
