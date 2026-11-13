"""Catálogo de formatos de programa (F6 do plano de melhoria de rádio).

Um formato é a promessa editorial do programa (pesquisa §3): o que o ouvinte espera, a unidade de fala, o roteiro
sem estrutura, o relógio sugerido e o comportamento do ao vivo. O valor fica em `Programa.perfil_programacao`
(sem migração, D1); `resolver_formato` traduz o valor gravado (alias, caixa, espaços) para o `Formato` canônico e
nunca devolve um formato não implementado (cai em `padrao`).

Puro: não importa o router, o relógio, o banco, o Redis nem o LLM (grafo sem ciclo: `formato` ← `formatos` ←
`orcamento` ← `relogio`). Os números do musical vêm de `app.live.formato.ORCAMENTOS`, sem cópia. Todo valor
numérico é hipótese de projeto (skill referencia-radio e pesquisa §3/§9), declarado aqui, nunca solto no código.
Desenho em docs/melhoria-radio/f6/auditoria.md (§6.3 a §6.5).
"""

import logging
from dataclasses import dataclass
from typing import Literal, Mapping

from app.live.formato import ORCAMENTOS, ROTEIRO_MUSICAL, ROTEIRO_PADRAO, _tipo_fala, orcamento_fala

logger = logging.getLogger("radialista.live.formatos")

ID_PADRAO = "padrao"
ID_MUSICAL = "musical_adulto"
FONTE = "docs/pesquisa-radio-locufy.md §3; skill referencia-radio"

# Frase da meta lida pelo dublê do LLM da simulação (scripts/simulacao/dubles.py, META_BLOCO_RE): não mudar a forma.
META_LOCUCAO = "Meta de locução: {minimo} a {maximo} segundos, no máximo {palavras} palavras."
REGRA_PROMESSA = "Não prometa intervalo, retorno ou conteúdo futuro sem programação confirmada."
REGRA_FACTUAL = "Mantenha as regras factuais e de atendimento dos pedidos reais."

# Seção do formato no prompt (`linhas_do_formato`, §6.9 e D10): só nos formatos com promessa (nunca no `padrao`).
SECAO_PROGRAMA = "Programa {programa}, formato {formato}. Promessa: {promessa}."
SECAO_PUBLICO = " Público: {publico}."
SECAO_PREVALECE = "A promessa do formato prevalece sobre o perfil do horário."
SECAO_PARTICIPACAO = "Participação neste formato: {participacao}"
SECAO_TEMAS = "Temas que exigem revisão humana neste formato: {temas}; sem conteúdo aprovado, não trate deles."
SECAO_REORIENTACAO = "Reoriente quem acabou de chegar: nome do programa e da rádio em uma frase."
# Papéis do bloco em que a seção pede a reorientação (a frequência com memória é da F8).
PAPEIS_REORIENTACAO = ("retomada", "identificacao", "retorno", "quadro")


@dataclass(frozen=True)
class Unidade:
    """Unidade de fala de um papel de bloco, em segundos."""

    min_s: float
    alvo_s: float
    max_s: float
    max_palavras: int | None = None      # teto do formato; None = só pelo ritmo da voz

    @classmethod
    def de_orcamento(cls, minimo: int, maximo: int, palavras: int | None = None) -> "Unidade":
        """Unidade a partir de (mínimo, máximo, palavras), com o alvo no ponto médio (a conta da F2)."""
        return cls(minimo, (minimo + maximo) / 2, maximo, palavras)


@dataclass(frozen=True)
class Comportamento:
    """O que o formato decide no ao vivo (cada campo substitui um uso do antigo booleano `formato_musical`)."""

    ciclo: Literal["musical", "padrao"]        # roteiro sem relógio: _tipo_proximo_bloco / tipo_na_posicao
    musica_sem_fala: bool                      # bloco de música sem pedido vira só música (sem relógio)
    uma_faixa_por_bloco: bool                  # citadas não tocam junto da faixa do bloco de música
    multivoz: bool                             # diálogo entre apresentadores permitido
    naturalidade_encenada: bool                # expressão regional, mudança de ideia, imperfeição, maneirismos
    hora_e_marco: bool                         # sorteio de hora certa e marco de tempo
    convite: Literal["qualquer_bloco", "so_chamada"]   # onde o convite ao ouvinte pode entrar
    tom_tts: str | None                        # tom fixo da síntese; None = pelo bloco
    ia_pode_adicionar_blocos: bool             # False: ignora a flag do programa (nunca insere blocos extras)
    preenchimento_relogio: bool                # link de preenchimento antes do hard time
    abertura_apos_intervalo: bool              # abertura da volta aceita depois do patrocinador (D17)


@dataclass(frozen=True)
class Formato:
    id: str
    nome: str                                  # painel
    promessa: str                              # §3 "Promessa"
    conteudo: str                              # §3 "Conteúdo"
    conducao: str                              # §3 "Condução sugerida"
    unidade_principal: str                     # §3/skill, para o painel ("link de 10 a 35 s")
    unidades: Mapping[str, Unidade]            # papel do bloco -> unidade; "*" obrigatório
    aplica_orcamento: bool                     # False só no padrao (observa, F2)
    comportamento: Comportamento
    roteiro_padrao: tuple[str, ...]            # roteiro com a estrutura vazia
    relogio_padrao: str | None                 # "A" | "B" | "C": sugestão no painel (D7), conferida por teste
    blocos_relogio: Mapping[str, str]          # tipo de evento -> bloco (sobrescreve RegraBloco.bloco_padrao)
    funcoes: Mapping[str, str]                 # papel -> função do bloco na direção do formato
    temas_revisao: tuple[str, ...]             # declarados; a revisão humana é da F12
    participacao: str                          # política em uma frase
    reorientacao_s: int | None                 # intervalo alvo entre reorientações ("Você está no...")
    faixa_fala_pct: tuple[float, float] | None  # coerência: fala / hora esperada (simulação)
    # Direção do formato no prompt (direcao_formato): cabeçalho e regras de condução depois da meta.
    direcao_cabecalho: str = ""
    direcao_regras: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    implementado: bool = True
    requer: str = ""                           # condição para implementar (formatos futuros)
    fonte: str = FONTE

    def __hash__(self) -> int:
        # Os mapas são dicts: o hash do formato é o do id (único no catálogo).
        return hash(self.id)


# ---------------------------------------------------------------------------------------------------------
# Comportamentos
# ---------------------------------------------------------------------------------------------------------

COMPORTAMENTO_PADRAO = Comportamento(
    ciclo="padrao", musica_sem_fala=False, uma_faixa_por_bloco=False, multivoz=True, naturalidade_encenada=True,
    hora_e_marco=True, convite="qualquer_bloco", tom_tts=None, ia_pode_adicionar_blocos=True,
    preenchimento_relogio=True, abertura_apos_intervalo=False,
)
COMPORTAMENTO_MUSICAL = Comportamento(
    ciclo="musical", musica_sem_fala=True, uma_faixa_por_bloco=True, multivoz=False, naturalidade_encenada=False,
    hora_e_marco=False, convite="so_chamada", tom_tts="neutro", ia_pode_adicionar_blocos=False,
    preenchimento_relogio=False, abertura_apos_intervalo=False,
)


# ---------------------------------------------------------------------------------------------------------
# Formatos implementados
# ---------------------------------------------------------------------------------------------------------

PADRAO = Formato(
    id=ID_PADRAO,
    nome="Livre (sem formato)",
    promessa="Segue a estrutura de blocos e as instruções do próprio programa, sem promessa de formato.",
    conteudo="Definido pela estrutura de blocos, pelos assuntos e pelas notícias do programa.",
    conducao="Definida pela persona, pelo tom e pelo horário do programa.",
    unidade_principal="fala de 15 a 30 s (só observada, sem ajuste)",
    # 15 a 30 s correspondem às "4 a 6 frases de rádio" do prompt (F2); só medem, não reescrevem.
    unidades={"*": Unidade.de_orcamento(15, 30)},
    aplica_orcamento=False,
    comportamento=COMPORTAMENTO_PADRAO,
    roteiro_padrao=ROTEIRO_PADRAO,
    relogio_padrao=None,
    blocos_relogio={},
    funcoes={},
    temas_revisao=(),
    participacao="",
    reorientacao_s=None,
    faixa_fala_pct=None,
)

MUSICAL_ADULTO = Formato(
    id=ID_MUSICAL,
    nome="Musical adulto",
    promessa="Acompanhar com curadoria.",
    conteudo="Canções familiares, cultura e serviço breve.",
    conducao="Discreta, acolhedora, sem pressa artificial.",
    unidade_principal="link de 10 a 35 s",
    # Herda ORCAMENTOS sem mudança (D5): a divergência com o link de 10 a 35 s da pesquisa é decisão do usuário.
    unidades={**{papel: Unidade.de_orcamento(*valores) for papel, valores in ORCAMENTOS.items()},
              "*": Unidade.de_orcamento(*orcamento_fala("*"))},
    aplica_orcamento=True,
    comportamento=COMPORTAMENTO_MUSICAL,
    roteiro_padrao=ROTEIRO_MUSICAL,
    relogio_padrao="A",
    # Etapas de fala longa do relógio viram retomada curta: a música ocupa o centro.
    blocos_relogio={tipo: "retomada" for tipo in ("link", "curadoria", "conversa", "quadro", "entrevista", "resumo")},
    funcoes={
        "abertura": "Receba o ouvinte e apresente o programa uma única vez.",
        "retomada": "Faça uma retomada breve; o programa já está em andamento.",
        "identificacao": "Diga apenas o nome da rádio ou do programa e uma assinatura curta.",
        "musica": "Anuncie brevemente a faixa confirmada e o pedido real, quando fornecido.",
        "encerramento": "Despeça-se do programa. Não prometa retorno após intervalo.",
        "*": "Cumpra somente a função deste bloco, de forma breve.",
    },
    temas_revisao=("notícia grave ou tragédia", "saúde e medicamento", "política", "religião"),
    participacao="Pedido real anunciado no bloco de música; sem pedido, nada: a música fala.",
    reorientacao_s=900,
    faixa_fala_pct=(1.0, 8.0),
    direcao_cabecalho="FORMATO MUSICAL DE COMPANHIA: a música ocupa o centro do programa.",
    direcao_regras=(
        "Esta duração substitui a orientação genérica de quatro a seis frases.",
        "Fale com proximidade e energia moderada; use português coloquial, sem linguagem de publicidade genérica, "
        "adjetivos em série, hesitações encenadas ou risadas obrigatórias.",
        "Não acrescente assunto, hora, clima, pergunta, convite ao WhatsApp ou gancho só para preencher.",
        "Não anuncie cada música da sequência, não peça [BLOCO_MUSICAS:N] e não invente vinhetas.",
    ),
    aliases=("musical_companhia",),
)


# ---------------------------------------------------------------------------------------------------------
# Formatos futuros (D13): só estrutura, nunca resolvidos; a API recusa e o painel mostra o que vem
# ---------------------------------------------------------------------------------------------------------

def _futuro(id_: str, nome: str, promessa: str, conteudo: str, conducao: str, unidade_principal: str,
            unidade: tuple[int, int], requer: str, relogio_padrao: str | None = None) -> Formato:
    return Formato(
        id=id_, nome=nome, promessa=promessa, conteudo=conteudo, conducao=conducao,
        unidade_principal=unidade_principal, unidades={"*": Unidade.de_orcamento(*unidade)}, aplica_orcamento=True,
        comportamento=COMPORTAMENTO_PADRAO, roteiro_padrao=ROTEIRO_PADRAO, relogio_padrao=relogio_padrao,
        blocos_relogio={}, funcoes={}, temas_revisao=(), participacao="", reorientacao_s=None, faixa_fala_pct=None,
        implementado=False, requer=requer,
    )


FUTUROS = (
    _futuro("hits", "Hits", "Conectar com o que está acontecendo.",
            "Sucessos, artistas, cultura pop e participação.", "Ágil, com uma ideia por entrada.",
            "link de 10 a 40 s", (10, 40), "", "A"),
    _futuro("regional", "Regional/raiz", "Pertencimento e memória.",
            "Repertório regional, tradições e festas.", "Familiar, respeitando o vocabulário local.",
            "entrada de 20 a 90 s", (20, 90), "Vocabulário local aprovado pela rádio.", "A"),
    _futuro("noturno", "Romântico/noturno", "Companhia em outro ritmo.",
            "Música, dedicatórias e memórias.", "Suave e sóbria, sem teatralização constante.",
            "entrada de 15 a 45 s", (15, 45), "Regra 9 da skill referencia-radio: não pressupor solidão.", "A"),
    _futuro("religioso", "Religioso", "Comunidade, música e reflexão de fé.",
            "Oração, mensagens, agenda e participação.", "Acolhedora, coerente com a tradição.",
            "reflexão de 1 a 5 min", (60, 300), "Tradição e roteiro aprovados pela comunidade (pesquisa §4.15)."),
    _futuro("morning", "Morning show", "Começar o dia junto.",
            "Humor, rotina, serviço e música.", "Energia moderada e turnos claros.",
            "conversa de 2 a 6 min", (120, 360), "Bancada com papéis definidos (F13) e relógio C.", "C"),
    _futuro("esportivo", "Esportivo", "Acompanhar e interpretar a competição.",
            "Resultado, bastidor, análise e torcedor.", "Intensidade variável; separar fato e opinião.",
            "debate de 3 a 10 min", (180, 600),
            "Fontes esportivas e separação entre fato, opinião e rumor (pesquisa §4.9)."),
    _futuro("jornalistico", "Jornalístico", "Atualizar rapidamente.",
            "Manchetes, apuração, serviço e entrevistas.", "Clara, precisa, com fonte e horário.",
            "nota de 20 a 60 s; reportagem de 1 a 4 min", (20, 60),
            "Fontes e validade dos dados (F5, concluída) e relógio B; frente própria.", "B"),
)


FORMATOS: Mapping[str, Formato] = {formato.id: formato for formato in (PADRAO, MUSICAL_ADULTO, *FUTUROS)}
_ALIASES: Mapping[str, str] = {alias: formato.id for formato in FORMATOS.values() for alias in formato.aliases}


# ---------------------------------------------------------------------------------------------------------
# Resolvedor e consultas
# ---------------------------------------------------------------------------------------------------------

def resolver_formato(valor) -> Formato:
    """Formato canônico de um valor gravado: alias → canônico; vazio, desconhecido ou não implementado → padrao."""
    if isinstance(valor, Formato):
        return valor
    chave = str(valor or "").strip().lower()
    if not chave:
        return PADRAO
    formato = FORMATOS.get(_ALIASES.get(chave, chave))
    if formato is None:
        logger.warning("formato_desconhecido formato=%s", chave[:40])
        return PADRAO
    if not formato.implementado:
        logger.warning("formato_nao_implementado formato=%s", formato.id)
        return PADRAO
    return formato


def formato_do_programa(programa) -> Formato:
    return resolver_formato(getattr(programa, "perfil_programacao", None))


def formato_pelo_booleano(musical: bool) -> Formato:
    """Compatibilidade com quem ainda passa o antigo booleano `formato_musical`."""
    return MUSICAL_ADULTO if musical else PADRAO


def ids_aceitos() -> frozenset[str]:
    """Valores que a API grava: os ids implementados e os aliases deles."""
    return frozenset(chave for formato in FORMATOS.values() if formato.implementado
                     for chave in (formato.id, *formato.aliases))


def _papel_pelo_tipo(tipo: str, primeira: bool) -> str:
    papel = _tipo_fala(tipo)
    return "retomada" if papel == "abertura" and not primeira else papel


def papel_do_bloco(formato: Formato, tipo: str, primeira: bool, quadro: bool = False) -> str:
    """Chave de `formato.unidades`: `quadro` (quadro fixo, se o formato declara), senão o tipo do bloco (abertura
    fora da largada é retomada), senão `*`. O papel `quadro` só vem do programa (`quadro=True`, quadro fixo), nunca do
    nome do bloco (§6.3)."""
    if quadro and "quadro" in formato.unidades:
        return "quadro"
    papel = _papel_pelo_tipo(tipo, primeira)
    if papel == "quadro" and not quadro:
        return "*"
    return papel if papel in formato.unidades else "*"


def unidade(formato, tipo: str, primeira: bool, quadro: bool = False) -> Unidade:
    formato = resolver_formato(formato)
    return formato.unidades[papel_do_bloco(formato, tipo, primeira, quadro)]


def direcao_formato(formato, tipo: str, primeira: bool = False,
                    orcamento: tuple[float, float, int | None] | None = None) -> str:
    """Direção do formato no prompt do bloco; vazia no `padrao`. `orcamento` (mínimo s, máximo s, palavras)
    substitui a unidade do formato quando o relógio ou o ritmo da voz já calcularam o espaço do bloco."""
    formato = resolver_formato(formato)
    if not formato.direcao_cabecalho:
        return ""
    papel = papel_do_bloco(formato, tipo, primeira)
    if orcamento is None:
        u = formato.unidades[papel]
        orcamento = (u.min_s, u.max_s, u.max_palavras)
    minimo, maximo, palavras = orcamento
    partes = [
        formato.direcao_cabecalho,
        formato.funcoes.get(papel) or formato.funcoes.get("*", ""),
        META_LOCUCAO.format(minimo=minimo, maximo=maximo, palavras=palavras),
        *formato.direcao_regras,
        REGRA_PROMESSA,
        REGRA_FACTUAL,
    ]
    return " ".join(parte for parte in partes if parte)



def linhas_do_formato(formato, *, programa: str, tipo: str, primeira: bool, quadro: bool = False,
                      retorno: bool = False, publico: str = "") -> list[str]:
    """Seção do formato no prompt do bloco (§6.9): programa, formato, promessa e público (só quando preenchido); a
    promessa do formato acima do perfil do horário; participação; temas que exigem revisão humana; e, nos papéis de
    `PAPEIS_REORIENTACAO` (quadro fixo, retorno do intervalo), a reorientação. Vazia no `padrao`."""
    formato = resolver_formato(formato)
    if formato.id == ID_PADRAO:
        return []
    publico = " ".join(str(publico or "").split()).rstrip(".")
    linhas = [
        SECAO_PROGRAMA.format(programa=programa, formato=formato.nome, promessa=formato.promessa.rstrip("."))
        + (SECAO_PUBLICO.format(publico=publico) if publico else ""),
        SECAO_PREVALECE,
    ]
    if formato.participacao:
        linhas.append(SECAO_PARTICIPACAO.format(participacao=formato.participacao))
    if formato.temas_revisao:
        linhas.append(SECAO_TEMAS.format(temas=", ".join(formato.temas_revisao)))
    papel = "quadro" if quadro else _papel_pelo_tipo(tipo, primeira)
    papeis = {"*" if papel == "quadro" and not quadro else papel, *(("retorno",) if retorno else ())}
    if papeis & set(PAPEIS_REORIENTACAO):
        linhas.append(SECAO_REORIENTACAO)
    return linhas
