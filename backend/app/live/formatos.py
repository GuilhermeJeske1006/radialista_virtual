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
import re
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from typing import Literal, Mapping, Sequence

from app.live.formato import ORCAMENTOS, ROTEIRO_MUSICAL, ROTEIRO_PADRAO, _tipo_fala, orcamento_fala

logger = logging.getLogger("radialista.live.formatos")

ID_PADRAO = "padrao"
ID_MUSICAL = "musical_adulto"
ID_POPULAR = "popular_sertanejo"
ID_VARIEDADES = "variedades_leves"
FONTE = "docs/pesquisa-radio-locufy.md §3; skill referencia-radio"

# Frase da meta lida pelo dublê do LLM da simulação (scripts/simulacao/dubles.py, META_BLOCO_RE): não mudar a forma.
META_LOCUCAO = "Meta de locução: {minimo} a {maximo} segundos, no máximo {palavras} palavras."
# Sem teto de palavras (formato sem `max_palavras` e sem o orçamento calculado pelo ritmo da voz).
META_LOCUCAO_SEM_PALAVRAS = "Meta de locução: {minimo} a {maximo} segundos."
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
class LimitesCoerencia:
    """Limites de coerência próprios do formato (auditoria §9); None ou vazio = não se aplica."""

    sequencia_musical_min_s: int | None = None   # maior trecho só de música (promessa musical, pesquisa §4.4)
    interrupcoes_max_hora: int | None = None     # falas por hora no máximo
    categorias_fora: tuple[str, ...] = ()        # categorias de bloco que o formato não prevê


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
    limites: LimitesCoerencia = field(default_factory=LimitesCoerencia)
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
    hora_e_marco=False, convite="so_chamada", tom_tts=None, ia_pode_adicionar_blocos=False,
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
        "abertura": "Receba o ouvinte e apresente o programa uma única vez, com a companhia que a música faz. "
                    "Não prometa retorno nem intervalo ('daqui a pouco', 'meia hora', 'depois do intervalo'): a "
                    "abertura chega ao tamanho da unidade só com apresentação e o que o ouvinte vai ouvir agora.",
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
    # §9: a música ocupa o centro (nove minutos seguidos sem fala, no máximo dez falas por hora) e o musical não
    # tem comentário nem notícia.
    limites=LimitesCoerencia(sequencia_musical_min_s=540, interrupcoes_max_hora=10,
                             categorias_fora=("comentario", "noticia", "escalada", "servico", "plantao", "reporter")),
    aliases=("musical_companhia",),
)


# Popular/sertanejo e variedades leves (leva 2, tabela do §6.4). Ciclo e flags do padrão, mas com orçamento aplicado
# (D9), unidade por papel, roteiro próprio, relógio sugerido e abertura aceita na volta do intervalo (D17). As
# funções do bloco são estruturas de intenção (pesquisa §8), nunca frase pronta nem imitação de apresentador real.
COMPORTAMENTO_POPULAR = Comportamento(
    ciclo="padrao", musica_sem_fala=False, uma_faixa_por_bloco=False, multivoz=True, naturalidade_encenada=True,
    hora_e_marco=True, convite="qualquer_bloco", tom_tts=None, ia_pode_adicionar_blocos=True,
    preenchimento_relogio=True, abertura_apos_intervalo=True,
)
COMPORTAMENTO_VARIEDADES = Comportamento(
    ciclo="padrao", musica_sem_fala=False, uma_faixa_por_bloco=False, multivoz=True, naturalidade_encenada=True,
    hora_e_marco=True, convite="so_chamada", tom_tts=None, ia_pode_adicionar_blocos=True,
    preenchimento_relogio=True, abertura_apos_intervalo=True,
)

POPULAR_SERTANEJO = Formato(
    id=ID_POPULAR,
    nome="Popular/sertanejo",
    promessa="Companhia e reconhecimento.",
    conteudo="Música, recados, histórias e vida local.",
    conducao="Próxima e afetiva.",
    unidade_principal="entrada de 20 a 60 s",
    unidades={
        "abertura": Unidade(20, 40, 60),
        "retomada": Unidade(15, 25, 40),
        "identificacao": Unidade(3, 6, 10),
        "musica": Unidade(8, 15, 25),
        "chamada_ouvinte": Unidade(20, 40, 60),      # recados
        "comentario": Unidade(20, 35, 60),           # história, vida local
        "encerramento": Unidade(15, 30, 45),
        "*": Unidade(20, 35, 60),
    },
    aplica_orcamento=True,
    comportamento=COMPORTAMENTO_POPULAR,
    roteiro_padrao=("musica", "chamada_ouvinte", "musica", "comentario", "musica", "retomada"),
    relogio_padrao="A",   # D6: preset A com as unidades e os blocos do formato (o relógio efetivo é outro)
    blocos_relogio={},
    funcoes={
        "abertura": "Receba quem chega com proximidade, diga o nome do programa e da rádio e chame a primeira "
                    "música confirmada.",
        "retomada": "Retome o programa em andamento com uma frase próxima, sem repetir o que já foi ao ar.",
        "identificacao": "Diga o nome da rádio e do programa com uma assinatura curta e calorosa.",
        "musica": "Apresente a faixa confirmada pelo título e pelo artista; com pedido real, diga o nome "
                  "autorizado de quem pediu.",
        "chamada_ouvinte": "Leia o recado ou o pedido real pelo nome autorizado e responda com afeto; sem recado "
                           "real, faça um convite genérico para participar, sem inventar mensagem.",
        "comentario": "Conte uma história curta do cotidiano ou da vida local, sem inventar fato, nome ou lugar, "
                      "e volte para a música.",
        "encerramento": "Agradeça a companhia, diga o nome do programa e despeça-se sem prometer retorno que não "
                        "esteja agendado.",
        "*": "Cumpra a função deste bloco com proximidade, uma ideia por vez.",
    },
    temas_revisao=("luto em recado", "saúde e medicamento", "dívida, empréstimo e aposta", "política", "religião"),
    participacao="Recados e pedidos reais pelo nome autorizado; sem recado, convite genérico, sem simular "
                 "mensagem recebida.",
    reorientacao_s=1200,
    faixa_fala_pct=(4.0, 20.0),
    direcao_cabecalho="FORMATO POPULAR/SERTANEJO: a companhia e o reconhecimento do ouvinte ocupam o centro.",
    direcao_regras=(
        "Condução próxima e afetiva: fale com um ouvinte de cada vez, em português coloquial, sem caricatura de "
        "sotaque, bordão repetido ou exagero.",
        "Recado, pedido, nome e cidade de ouvinte só os reais e autorizados; não simule participação.",
        "Ajuste a energia ao horário sem mudar a identidade do programa.",
    ),
)

VARIEDADES_LEVES = Formato(
    id=ID_VARIEDADES,
    nome="Variedades leves",
    promessa="Ajudar na vida cotidiana, com leveza.",
    conteudo="Cidade, cultura, trabalho, tecnologia, serviço leve e quadro fixo.",
    conducao="Prática e inclusiva.",
    unidade_principal="quadro de 2 a 8 min",
    unidades={
        "abertura": Unidade(30, 60, 90),             # pergunta do dia
        "retomada": Unidade(15, 25, 40),
        "identificacao": Unidade(3, 6, 10),
        "musica": Unidade(8, 15, 25),
        "chamada_ouvinte": Unidade(20, 40, 60),      # respostas reais
        "comentario": Unidade(20, 45, 60),           # conversa
        "quadro": Unidade(60, 120, 180),             # por fala; o quadro inteiro (2 a 8 min) é a soma no relógio C
        "encerramento": Unidade(20, 35, 45),
        "*": Unidade(20, 35, 60),
    },
    aplica_orcamento=True,
    comportamento=COMPORTAMENTO_VARIEDADES,
    roteiro_padrao=("musica", "comentario", "musica", "chamada_ouvinte", "musica", "retomada"),
    relogio_padrao="C",
    blocos_relogio={"quadro": "@quadro"},
    funcoes={
        "abertura": "Abra com o nome do programa e da rádio e a pergunta do dia, sem supor a rotina de quem ouve; "
                    "peça respostas só se houver leitura agendada.",
        "retomada": "Retome o assunto em andamento em uma frase e situe o ouvinte no programa.",
        "identificacao": "Diga o nome da rádio e do programa e o tema do dia numa assinatura curta.",
        "musica": "Apresente a faixa confirmada de forma breve; ligue a música ao assunto só se a relação for real.",
        "chamada_ouvinte": "Leia só respostas reais à pergunta do dia, pelo nome autorizado; sem resposta real, faça "
                           "um convite para participar, sem simular mensagem.",
        "comentario": "Converse sobre um assunto útil do dia a dia com uma dica concreta e um exemplo, separando "
                      "serviço e opinião.",
        "quadro": "Conduza o quadro fixo: diga o nome do quadro, apresente o tema de hoje e dê passos simples, em "
                  "unidades pequenas.",
        "encerramento": "Resuma em uma frase o que foi útil hoje, agradeça a companhia e despeça-se sem prometer o "
                        "que não está agendado.",
        "*": "Cumpra a função deste bloco de forma prática, com uma ideia útil por vez.",
    },
    temas_revisao=("saúde", "finanças e investimento", "orientação jurídica e de consumo",
                   "alimentação com promessa de saúde", "política", "religião"),
    participacao="Pergunta do dia na abertura e leitura só de respostas reais; convite só com retorno agendado.",
    reorientacao_s=900,
    faixa_fala_pct=(15.0, 45.0),
    direcao_cabecalho="FORMATO VARIEDADES LEVES: o serviço útil do dia a dia, com leveza, ocupa o centro.",
    direcao_regras=(
        "Condução prática e inclusiva: uma ideia útil por fala, em frases curtas, sem supor que todo ouvinte tem "
        "a mesma rotina, casa ou renda.",
        "Marque com clareza a passagem entre serviço e conversa; dica de serviço só com informação confirmada.",
        "Convite para mandar mensagem só no bloco de chamada; leia apenas respostas reais de ouvintes.",
    ),
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


FORMATOS: Mapping[str, Formato] = {
    formato.id: formato for formato in (PADRAO, MUSICAL_ADULTO, POPULAR_SERTANEJO, VARIEDADES_LEVES, *FUTUROS)
}
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


def eh_quadro_fixo(programa, tipo: str) -> bool:
    """O bloco é quadro fixo do programa (`quadros_fixos[tipo]` com conteúdo), a mesma regra do relógio e do
    contexto."""
    return bool((getattr(programa, "quadros_fixos", None) or {}).get(tipo))


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
                    orcamento: tuple[float, float, int | None] | None = None, quadro: bool = False) -> str:
    """Direção do formato no prompt do bloco; vazia no `padrao`. `orcamento` (mínimo s, máximo s, palavras)
    substitui a unidade do formato quando o relógio ou o ritmo da voz já calcularam o espaço do bloco. `quadro`:
    o bloco é quadro fixo do programa."""
    formato = resolver_formato(formato)
    if not formato.direcao_cabecalho:
        return ""
    papel = papel_do_bloco(formato, tipo, primeira, quadro)
    if orcamento is None:
        u = formato.unidades[papel]
        orcamento = (u.min_s, u.max_s, u.max_palavras)
    minimo, maximo, palavras = orcamento
    meta = META_LOCUCAO if palavras is not None else META_LOCUCAO_SEM_PALAVRAS
    partes = [
        formato.direcao_cabecalho,
        formato.funcoes.get(papel) or formato.funcoes.get("*", ""),
        meta.format(minimo=minimo, maximo=maximo, palavras=palavras),
        *formato.direcao_regras,
        REGRA_PROMESSA,
        REGRA_FACTUAL,
    ]
    return " ".join(parte for parte in partes if parte)



def linhas_do_formato(formato, *, programa: str, tipo: str, primeira: bool, quadro: bool = False,
                      retorno: bool = False, publico: str = "", reorientacao_vencida: bool = False) -> list[str]:
    """Seção do formato no prompt do bloco (§6.9): programa, formato, promessa e público (só quando preenchido); a
    promessa do formato acima do perfil do horário; participação; temas que exigem revisão humana; e, nos papéis de
    `PAPEIS_REORIENTACAO` (quadro fixo, retorno do intervalo) ou quando passou o `reorientacao_s` do formato desde a
    última (`reorientacao_vencida`, F8 passo 3), a reorientação. Vazia no `padrao`."""
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
    if (papeis & set(PAPEIS_REORIENTACAO)) or (reorientacao_vencida and formato.reorientacao_s):
        linhas.append(SECAO_REORIENTACAO)
    return linhas


def pede_reorientacao(formato, *, tipo: str, primeira: bool, quadro: bool = False, retorno: bool = False,
                      reorientacao_vencida: bool = False) -> bool:
    """Se a seção do formato pede a reorientação neste bloco (mesma regra de `linhas_do_formato`)."""
    return SECAO_REORIENTACAO in linhas_do_formato(formato, programa="", tipo=tipo, primeira=primeira, quadro=quadro,
                                                   retorno=retorno, reorientacao_vencida=reorientacao_vencida)


def reorientacao_vencida(formato, desde_reorientacao_s: float | None) -> bool:
    """F8 (passo 3): passou o intervalo do formato desde a última reorientação. Sem memória (None), não pede."""
    formato = resolver_formato(formato)
    return bool(formato.reorientacao_s) and desde_reorientacao_s is not None \
        and desde_reorientacao_s >= formato.reorientacao_s


# ---------------------------------------------------------------------------------------------------------
# Coerência com o formato (§6.14 e §9): funções puras que só medem. Nada é reescrito nem removido por coerência
# (D21): o /proxima só registra `live_formato_aviso` e a simulação resume em resumo.json["formato"].
# ---------------------------------------------------------------------------------------------------------

AVISOS = ("fora_da_unidade", "bloco_fora_do_formato", "convite_fora_da_politica", "tema_revisao", "reorientacao")


@dataclass(frozen=True)
class ConfigCoerencia:
    # Hipóteses de projeto (auditoria §9); a primeira rodada da F6 calibra e registra.
    tolerancia_unidade: float = 0.15          # a mesma de settings.fala_tolerancia_orcamento (teste)
    fora_da_unidade_max_pct: float = 5.0      # falas fora da unidade do papel, em % das falas
    fator_reorientacao: float = 1.5           # maior intervalo sem reorientação ≤ fator × reorientacao_s
    instrucao_min_pct: float = 100.0          # blocos de fala com a direção do formato no prompt
    categoria_convite: str = "chamada_ouvinte"  # onde cabe o convite quando o formato é "so_chamada"
    # Convite ao ouvinte numa frase (texto sem acento e em minúsculas): verbo de convite e canal, ou o canal "aberto".
    convite: tuple[str, ...] = (
        r"\b(mande|manda|mandar|envie|envia|enviar|escreva|escreve|escrever|participe|participa|participar|conte|"
        r"conta|contar|comente|comenta|sugira|sugere|sugerir|peca|pede|pedir|ligue|liga)\b[^.!?]*"
        r"\b(whatsapp|mensagem|recado|audio|pedido|dedicatoria|alo|resposta)\b",
        r"\b(whatsapp|recado|mensagem)\b[^.!?]*\b(aberto|recebe|espera)\b",
    )
    # Palavras que marcam cada tema que exige revisão humana (texto sem acento, palavra inteira).
    temas: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {
        "notícia grave ou tragédia": ("tragedia", "acidente grave", "mortos", "morreram", "vitimas fatais",
                                      "desastre", "chacina", "assassinato"),
        "saúde e medicamento": ("remedio", "remedios", "medicamento", "medicamentos", "dose", "antibiotico",
                                "receita medica", "tratamento medico", "pressao alta", "diabetes"),
        "saúde": ("remedio", "remedios", "medicamento", "medicamentos", "dose", "doenca", "sintoma", "sintomas",
                  "diagnostico", "tratamento medico", "pressao alta", "diabetes"),
        "política": ("eleicao", "eleicoes", "candidato", "candidata", "partido politico", "deputado", "senador",
                     "vereador", "voto", "votar"),
        "religião": ("religiao", "igreja", "culto", "missa", "pastor", "padre", "oracao", "biblia"),
        "luto em recado": ("faleceu", "falecimento", "luto", "velorio", "sepultamento", "morreu"),
        "dívida, empréstimo e aposta": ("divida", "dividas", "emprestimo", "consignado", "aposta", "apostas",
                                        "apostar", "cassino", "juros"),
        "finanças e investimento": ("investimento", "investimentos", "investir", "bolsa de valores", "rendimento",
                                    "criptomoeda", "renda fixa", "juros"),
        "orientação jurídica e de consumo": ("advogado", "processo judicial", "processar", "direito do consumidor",
                                             "procon", "indenizacao"),
        "alimentação com promessa de saúde": ("emagrecer", "emagrecimento", "dieta", "detox", "cura", "curar",
                                              "previne"),
    })


CONFIG_COERENCIA = ConfigCoerencia()


@dataclass(frozen=True)
class FalaNoAr:
    """Uma fala que foi (ou vai) ao ar, só com o que a coerência precisa."""

    bloco: str                      # tipo do bloco (rótulo do roteiro ou do relógio)
    categoria: str
    texto: str
    duracao_s: float | None         # None = duração desconhecida (a unidade não é avaliada)
    inicio_s: float = 0.0           # segundos desde o início do programa
    primeira: bool = False          # a primeira fala do programa
    quadro: bool = False            # quadro fixo do programa
    retorno: bool = False           # volta do intervalo (patrocinador antes ou etapa "retorno" do relógio)
    teto_s: float | None = None     # máximo que o relógio deu a esta fala (None = sem relógio)
    # Segundos desde a última reorientação (ou desde o início do programa); None = sem memória (o /proxima, até a F8).
    desde_reorientacao_s: float | None = None


@dataclass(frozen=True)
class AvisoFormato:
    codigo: str                     # um de AVISOS
    fala: int | None = None         # índice da fala; None = aviso da hora (intervalo sem reorientação)
    detalhe: str = ""               # papel, categoria ou tema; nunca trecho de fala


@dataclass(frozen=True)
class RelatorioCoerencia:
    formato: str
    fala_pct: float
    faixa_fala_pct: tuple[float, float] | None
    falas: int
    falas_fora_da_unidade: int
    falas_fora_da_unidade_pct: float
    blocos_fora_do_formato: int
    maior_sequencia_musical_s: float
    interrupcoes_por_hora: float
    reorientacoes: int
    maior_intervalo_sem_reorientacao_s: float
    reorientacao_s: int | None
    convites: int
    convites_fora_da_politica: int
    temas_revisao_no_ar: int
    instrucao_no_prompt_pct: float | None
    instrucao_de_outro_formato: int | None
    avisos: tuple[AvisoFormato, ...]
    itens: Mapping[str, bool]
    coerencia_automatica: bool

    def como_dict(self) -> dict:
        dados = asdict(self)
        dados["faixa_fala_pct"] = list(self.faixa_fala_pct) if self.faixa_fala_pct else None
        dados["itens"] = dict(self.itens)
        dados["avisos"] = [asdict(aviso) for aviso in self.avisos]
        dados["avisos_por_codigo"] = {codigo: sum(1 for a in self.avisos if a.codigo == codigo) for codigo in AVISOS}
        return dados


def _sem_acento(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9.!?]+", " ", sem)


def _frases(texto: str) -> list[str]:
    return [frase.strip() for frase in re.split(r"[.!?]+", _sem_acento(texto)) if frase.strip()]


def convites_no_texto(texto: str, config: ConfigCoerencia = CONFIG_COERENCIA) -> int:
    """Frases com convite ao ouvinte (mandar recado, mensagem ou pedido; o canal aberto)."""
    padroes = [re.compile(p) for p in config.convite]
    return sum(1 for frase in _frases(texto) if any(p.search(frase) for p in padroes))


def temas_no_texto(texto: str, temas: Sequence[str], config: ConfigCoerencia = CONFIG_COERENCIA) -> list[str]:
    """Temas de `temas` (rótulos do catálogo) que a fala toca, pela lista de palavras de cada um."""
    alvo = f" {' '.join(_sem_acento(texto).replace('.', ' ').replace('!', ' ').replace('?', ' ').split())} "
    return [tema for tema in temas if any(f" {palavra} " in alvo for palavra in config.temas.get(tema, ()))]


def reorienta(texto: str, nomes: Sequence[str]) -> bool:
    """A fala diz o nome do programa ou da rádio ("Você está no…")."""
    alvo = f" {' '.join(re.sub(r'[.!?]', ' ', _sem_acento(texto)).split())} "
    return any(chave and f" {chave} " in alvo
               for chave in (" ".join(re.sub(r"[.!?]", " ", _sem_acento(nome)).split()) for nome in nomes))


def avisos_da_fala(formato, fala: FalaNoAr, *, nomes: Sequence[str] = (), indice: int | None = None,
                   config: ConfigCoerencia = CONFIG_COERENCIA) -> list[AvisoFormato]:
    """Avisos de uma fala (D21: só mede). `nomes`: programa e rádio, para a reorientação, que só é avaliada com a
    memória de quando foi a última (`desde_reorientacao_s`): passou de `fator_reorientacao` × `reorientacao_s` e esta
    fala também não reorienta."""
    formato = resolver_formato(formato)
    avisos: list[AvisoFormato] = []
    papel = papel_do_bloco(formato, fala.bloco, fala.primeira, fala.quadro)
    if formato.aplica_orcamento and fala.duracao_s is not None:
        u = formato.unidades[papel]
        reduzida = fala.teto_s is not None and fala.teto_s < u.max_s
        # Estendida: o relógio deu mais que a unidade (encerramento elástico, que ocupa o espaço até o fim).
        maximo = max(u.max_s, fala.teto_s) if fala.teto_s is not None else u.max_s
        if not reduzida and (fala.duracao_s < u.min_s or fala.duracao_s > maximo * (1 + config.tolerancia_unidade)):
            avisos.append(AvisoFormato("fora_da_unidade", indice, papel))
    if fala.categoria in formato.limites.categorias_fora:
        avisos.append(AvisoFormato("bloco_fora_do_formato", indice, fala.categoria))
    if formato.comportamento.convite == "so_chamada" and fala.categoria != config.categoria_convite \
            and convites_no_texto(fala.texto, config):
        avisos.append(AvisoFormato("convite_fora_da_politica", indice, fala.categoria))
    avisos += [AvisoFormato("tema_revisao", indice, tema)
               for tema in temas_no_texto(fala.texto, formato.temas_revisao, config)]
    if formato.reorientacao_s and nomes and fala.desde_reorientacao_s is not None \
            and fala.desde_reorientacao_s > config.fator_reorientacao * formato.reorientacao_s \
            and not reorienta(fala.texto, nomes):
        avisos.append(AvisoFormato("reorientacao", indice, papel))
    return avisos


def _maior_sequencia_musical(eventos: Sequence[tuple[str, float, float]]) -> float:
    maior, inicio, fim = 0.0, None, None
    for tipo, comeco, termino in sorted(eventos, key=lambda e: e[1]):
        if tipo != "musica":
            inicio = None
            continue
        inicio = comeco if inicio is None else inicio
        fim = termino
        maior = max(maior, fim - inicio)
    return round(maior, 2)


def coerencia(formato, falas: Sequence[FalaNoAr], *, duracao_programa_s: float, nomes: Sequence[str] = (),
              eventos: Sequence[tuple[str, float, float]] = (), instrucao: Mapping[str, int] | None = None,
              config: ConfigCoerencia = CONFIG_COERENCIA) -> RelatorioCoerencia:
    """Coerência de uma hora com o formato (auditoria §9). `eventos`: (tipo, início s, fim s) de tudo que foi ao ar,
    para a sequência musical; `instrucao`: canal lateral do dublê (`blocos`, `com_formato`, `com_outro`), blocos de
    fala cujo prompt tinha a direção do formato esperado e a de outro formato."""
    formato = resolver_formato(formato)
    falas = sorted(falas, key=lambda f: f.inicio_s)
    ultima, com_memoria = 0.0, []
    for fala in falas:
        com_memoria.append(replace(fala, desde_reorientacao_s=fala.inicio_s - ultima)
                           if fala.desde_reorientacao_s is None else fala)
        if nomes and reorienta(fala.texto, nomes):
            ultima = fala.inicio_s
    falas = com_memoria
    avisos = [aviso for i, fala in enumerate(falas) for aviso in avisos_da_fala(formato, fala, nomes=nomes, indice=i,
                                                                               config=config)]
    contagem = {codigo: sum(1 for a in avisos if a.codigo == codigo) for codigo in AVISOS}
    horas = duracao_programa_s / 3600 if duracao_programa_s else 1.0
    fala_pct = round(100 * sum(f.duracao_s or 0.0 for f in falas) / duracao_programa_s, 1) \
        if duracao_programa_s else 0.0
    marcos = [0.0, *(f.inicio_s for f in falas if nomes and reorienta(f.texto, nomes)), float(duracao_programa_s)]
    maior_intervalo = round(max(b - a for a, b in zip(marcos, marcos[1:])), 2)
    limite_reorientacao = config.fator_reorientacao * formato.reorientacao_s if formato.reorientacao_s else None
    if limite_reorientacao is not None and maior_intervalo > limite_reorientacao:
        avisos.append(AvisoFormato("reorientacao", None, "intervalo"))
    fora_unidade = contagem["fora_da_unidade"]
    fora_pct = round(100 * fora_unidade / len(falas), 1) if falas else 0.0
    sequencia = _maior_sequencia_musical(eventos)
    interrupcoes = round(len(falas) / horas, 1)
    instrucao_pct = outro = None
    if instrucao is not None:
        blocos = instrucao.get("blocos", 0)
        instrucao_pct = round(100 * instrucao.get("com_formato", 0) / blocos, 1) if blocos else 0.0
        outro = instrucao.get("com_outro", 0)

    limites = formato.limites
    itens: dict[str, bool] = {}
    if instrucao is not None:
        itens["instrucao_no_prompt"] = instrucao_pct >= config.instrucao_min_pct if formato.direcao_cabecalho \
            else instrucao_pct == 0
        itens["instrucao_de_outro_formato"] = outro == 0
    if formato.faixa_fala_pct is not None:
        itens["fala_pct"] = formato.faixa_fala_pct[0] <= fala_pct <= formato.faixa_fala_pct[1]
    if formato.aplica_orcamento:
        itens["falas_fora_da_unidade"] = fora_pct <= config.fora_da_unidade_max_pct
    itens["blocos_fora_do_formato"] = contagem["bloco_fora_do_formato"] == 0
    if limites.sequencia_musical_min_s is not None:
        itens["maior_sequencia_musical"] = sequencia >= limites.sequencia_musical_min_s
    if limites.interrupcoes_max_hora is not None:
        itens["interrupcoes_por_hora"] = interrupcoes <= limites.interrupcoes_max_hora
    if limite_reorientacao is not None:
        itens["reorientacao"] = maior_intervalo <= limite_reorientacao
    itens["convites_fora_da_politica"] = contagem["convite_fora_da_politica"] == 0
    itens["temas_revisao_no_ar"] = contagem["tema_revisao"] == 0
    return RelatorioCoerencia(
        formato=formato.id, fala_pct=fala_pct, faixa_fala_pct=formato.faixa_fala_pct, falas=len(falas),
        falas_fora_da_unidade=fora_unidade, falas_fora_da_unidade_pct=fora_pct,
        blocos_fora_do_formato=contagem["bloco_fora_do_formato"], maior_sequencia_musical_s=sequencia,
        interrupcoes_por_hora=interrupcoes,
        reorientacoes=sum(1 for f in falas if nomes and reorienta(f.texto, nomes)),
        maior_intervalo_sem_reorientacao_s=maior_intervalo, reorientacao_s=formato.reorientacao_s,
        convites=sum(1 for f in falas if convites_no_texto(f.texto, config)),
        convites_fora_da_politica=contagem["convite_fora_da_politica"],
        temas_revisao_no_ar=sum(1 for f in falas if temas_no_texto(f.texto, formato.temas_revisao, config)),
        instrucao_no_prompt_pct=instrucao_pct, instrucao_de_outro_formato=outro, avisos=tuple(avisos),
        itens=itens, coerencia_automatica=all(itens.values()),
    )
