"""Memória da fala no ao vivo (F8, passo 1 da melhoria de rádio): helpers puros do histórico de falas.

Consolidado aqui sem mudar comportamento: primeira e última frase das falas recentes (`aberturas_e_fechamentos`,
que alimenta o aviso de não repetir abertura e fechamento no prompt) e a rede de segurança de repetição por
sobreposição de palavras (`fala_semelhante_no_historico`). `contexto.py` e `geracao.py` reexportam os nomes
privados antigos, então quem os importa segue igual.
"""

import re
from collections.abc import Callable, Sequence

from app.util.texto import sem_acento as _sem_acento

_FRASE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# tag de direcao vocal do eleven_v3 que o LLM pode inserir inline na fala (ver instrucao
# condicional em gerar_proxima_fala) -- removida antes de citar a frase de volta no prompt, pra
# nao confundir o LLM com uma tag que nao faz parte do texto falado de verdade.
_TAG_V3_DISPLAY_RE = re.compile(r"\[[a-zA-Z_]+\]\s*")
_MAX_CHARS_FRASE_HISTORICO = 80


def frases(texto: str) -> list[str]:
    texto_limpo = _TAG_V3_DISPLAY_RE.sub("", texto).strip()
    return [f.strip() for f in _FRASE_SPLIT_RE.split(texto_limpo) if f.strip()]


def primeira_frase(texto: str) -> str:
    partes = frases(texto)
    return partes[0][:_MAX_CHARS_FRASE_HISTORICO] if partes else ""


def ultima_frase(texto: str) -> str:
    partes = frases(texto)
    return partes[-1][:_MAX_CHARS_FRASE_HISTORICO] if partes else ""


# Quantas falas recentes (do mesmo tipo de bloco) considerar pro aviso de nao repetir
# abertura/fechamento no prompt -- nao precisa cobrir toda a janela de _historico_falas, so as
# poucas mais recentes bastam pra pegar o padrao mais obvio de repeticao.
_MAX_ABERTURAS_FECHAMENTOS_NO_PROMPT = 5


def aberturas_e_fechamentos(historico_falas: list[str]) -> tuple[list[str], list[str]]:
    """Primeira e ultima frase das falas recentes do mesmo tipo de bloco (ver _historico_falas) --
    usado pro prompt avisar o LLM a nao repetir o mesmo padrao de abertura/fechamento entre voltas
    do roteiro (ex: sempre comecar com "e ai galera" ou sempre fechar com "fica com a gente"),
    problema que o aviso generico de "nao repita a mesma abertura" (ver introducao_ao_vivo) sozinho
    nao resolve sem exemplos concretos do que ja foi usado.
    """
    aberturas: list[str] = []
    fechamentos: list[str] = []
    for fala_anterior in historico_falas[:_MAX_ABERTURAS_FECHAMENTOS_NO_PROMPT]:
        primeira = primeira_frase(fala_anterior)
        ultima = ultima_frase(fala_anterior)
        if primeira:
            aberturas.append(primeira)
        if ultima and ultima != primeira:
            fechamentos.append(ultima)
    return aberturas, fechamentos


# Sobreposicao de palavras (Jaccard) a partir da qual duas falas do mesmo tipo de bloco sao
# tratadas como repeticao. Falas muito curtas (menos que isso de palavras) nao entram na
# checagem -- sobreposicao alta em frase curta e normal, nao indica repeticao.
_LIMIAR_SIMILARIDADE_REPETICAO = 0.6
_MIN_PALAVRAS_SIMILARIDADE = 5

_PONTUACAO_RE = re.compile(r"[^\w\s]")


def palavras_normalizadas(texto: str) -> set[str]:
    sem_acento = _sem_acento(texto.lower())
    sem_pontuacao = _PONTUACAO_RE.sub(" ", sem_acento)
    return {p for p in sem_pontuacao.split() if p}


def _sem_frases(texto: str, ignorar: Callable[[str], bool] | None) -> str:
    if ignorar is None:
        return texto
    return " ".join(frase for frase in frases(texto) if not ignorar(frase))


def fala_semelhante_no_historico(fala: str, historico_falas: list[str],
                                 ignorar: Callable[[str], bool] | None = None) -> str | None:
    """Rede de seguranca em runtime: mesmo com as instrucoes de variacao no prompt, o LLM as
    vezes ainda produz uma fala quase igual a uma de varios blocos atras (janela enviada ao
    prompt so cobre as ultimas falas). Compara por sobreposicao de palavras contra o historico
    da sessao pro mesmo tipo de bloco; devolve a fala anterior que colidiu (pra citar no retry),
    ou None se nao achou repeticao.

    `ignorar(frase)`: frases que saem da comparação dos dois lados. F8 (passo 3): a reorientação ("Você está
    no ...") é repetição permitida e não pode, sozinha, fazer duas falas parecerem iguais.
    """
    palavras_fala = palavras_normalizadas(_sem_frases(fala, ignorar))
    if len(palavras_fala) < _MIN_PALAVRAS_SIMILARIDADE:
        return None
    for anterior in historico_falas:
        palavras_anterior = palavras_normalizadas(_sem_frases(anterior, ignorar))
        if len(palavras_anterior) < _MIN_PALAVRAS_SIMILARIDADE:
            continue
        uniao = palavras_fala | palavras_anterior
        if not uniao:
            continue
        similaridade = len(palavras_fala & palavras_anterior) / len(uniao)
        if similaridade >= _LIMIAR_SIMILARIDADE_REPETICAO:
            return anterior
    return None


# ---------------------------------------------------------------------------------------------------------
# Repetição por estrutura (F8, passo 2): a construção da fala, não as palavras. "Variar só sinônimos mantém a
# repetição" (pesquisa §8): duas falas que abrem com "Você está na rádio…" são a mesma abertura, mesmo trocando
# o nome. A classe "outra" não conta como estrutura repetida: são falas sem padrão reconhecível.
# ---------------------------------------------------------------------------------------------------------

_ABERTURAS = (
    ("pergunta", None),  # sentinela: decidida pelo "?" da primeira frase
    ("saudacao", re.compile(r"^(bom dia|boa tarde|boa noite|boa madrugada|oi|ola|e ai|pessoal|galera|gente)\b")),
    ("identificacao", re.compile(
        r"^(voce esta|voce ta|voce ouve|voce esta ouvindo|aqui e a|aqui e o|aqui eh a|esta e a|este e o|sintonizado"
        r"|radio )"
    )),
    ("retomada", re.compile(
        r"^(seguimos|continuamos|a (tarde|manha|noite|madrugada) continua|a gente continua)\b"
    )),
    ("agradecimento", re.compile(r"^(que bom|obrigad[oa]|valeu)\b")),
    ("chamada", re.compile(r"^(vamos|bora|agora|hoje|cheguei|chegou|atencao)\b")),
)

_FECHAMENTOS = (
    ("pergunta", None),  # sentinela: decidida pelo "?" da última frase
    ("despedida", re.compile(
        r"\b(ate (a|o|logo|amanha|breve|mais)|fica com a gente|fique com a gente|um abraco|tchau|volto ja|ate logo)\b"
    )),
    ("convite", re.compile(
        r"\b(manda|mande|conta|conte|escreve|escreva|liga|ligue|participe|manda seu|mande seu)\b"
    )),
)


def abertura_da_fala(texto: str) -> str:
    """Classe da construção de abertura: saudacao, identificacao, retomada, agradecimento, chamada, pergunta ou outra."""
    partes = frases(texto)
    if not partes:
        return "outra"
    primeira = partes[0]
    if primeira.endswith("?"):
        return "pergunta"
    normalizada = _sem_acento(primeira).strip().lower()
    for classe, padrao in _ABERTURAS:
        if padrao is not None and padrao.search(normalizada):
            return classe
    return "outra"


def fechamento_da_fala(texto: str) -> str:
    """Classe da construção de fechamento: pergunta, despedida, convite ou outra."""
    partes = frases(texto)
    if not partes:
        return "outra"
    ultima = partes[-1]
    if ultima.endswith("?"):
        return "pergunta"
    normalizada = _sem_acento(ultima).strip().lower()
    for classe, padrao in _FECHAMENTOS:
        if padrao is not None and padrao.search(normalizada):
            return classe
    return "outra"


def repeticao_estrutura(textos: list[str], seguidas: int = 3) -> int:
    """Janelas de `seguidas` falas em sequência com a mesma abertura reconhecida (classe diferente de "outra").
    Mesma convenção de `abertura_repetida` do simulador: cada janela conta uma vez."""
    classes = [abertura_da_fala(t) for t in textos]
    contagem = 0
    for i in range(seguidas - 1, len(classes)):
        janela = classes[i - seguidas + 1:i + 1]
        if janela[0] != "outra" and len(set(janela)) == 1:
            contagem += 1
    return contagem


# Linha do histórico que o painel manda: "tipo: fala" + sufixo opcional com as músicas do bloco.
_SUFIXO_MUSICAS_RE = re.compile(r"\s*\[Música\(s\) tocada\(s\) nesse bloco:.*\]\s*$")
_TIPOS_SEM_LOCUCAO = ("vinheta", "patrocinador")


def textos_do_historico(historico: Sequence[str]) -> list[str]:
    """Falas do histórico do painel, da mais antiga para a mais recente, sem o tipo, sem o sufixo de músicas e sem
    blocos de texto fixo (vinheta, patrocinador) ou vazios (música sem locução)."""
    textos: list[str] = []
    for linha in historico:
        tipo, separador, resto = (linha or "").partition(":")
        if not separador:
            continue
        texto = _SUFIXO_MUSICAS_RE.sub("", resto).strip()
        if texto and not _sem_acento(tipo.strip().lower()).startswith(_TIPOS_SEM_LOCUCAO):
            textos.append(texto)
    return textos


def abertura_repetida(textos: Sequence[str], seguidas: int = 2) -> str | None:
    """Classe de abertura (diferente de "outra") das `seguidas` últimas falas, quando todas abrem igual; senão None.
    Alimenta o aviso do prompt (F8, passo 2): a próxima fala não deve ser a terceira seguida com a mesma estrutura."""
    if len(textos) < seguidas:
        return None
    classes = {abertura_da_fala(texto) for texto in textos[-seguidas:]}
    classe = classes.pop() if len(classes) == 1 else "outra"
    return None if classe == "outra" else classe
