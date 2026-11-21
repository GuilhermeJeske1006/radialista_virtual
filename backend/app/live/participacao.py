"""Participação de verdade (F4): regras editoriais 2 e 3 da skill referencia-radio. Puro: sem router, sem banco.

- "Toca agora" e nome de ouvinte só com o pedido selecionado para este bloco (`pedido_nao_selecionado`).
- Nenhum ouvinte inexistente: em frase de participação (abraço, recado, pediu...), nome com inicial maiúscula fora
  dos nomes conhecidos (`ouvinte_nao_autorizado`).
- Sem pedido real, convite genérico: mensagem ou pedido simulado (`participacao_simulada`).
- Pedido selecionado que some da fala (D10, `pedido_sem_mencao`): a reescrita pede o nome; persistindo, o router
  devolve o pedido à fila.

Citar quem já foi atendido nesta transmissão, sem construção de execução, é permitido (D8: o gancho do prompt
retoma o nome do ouvinte da fala anterior). O nome espiado do legado (D7) só vale com "chegou uma mensagem".
Desenho em docs/melhoria-radio/f4/auditoria.md §6.7. Padrões em `CONFIG_PARTICIPACAO`.
"""

import dataclasses
import re
from typing import TYPE_CHECKING, Iterable

from app.live.orcamento import frases
from app.live.promessas import normalizar
from app.live.validacao_fala import Violacao, mencoes_musica, nomes_nao_musica

if TYPE_CHECKING:
    from app.live.contexto import ContextoEmissao

CONFIG_PARTICIPACAO = {
    # Palavras que fazem da frase uma frase de participação (normalizadas).
    "pistas": ("abraco", "abracos", "beijo", "beijos", "alo", "recado", "recados", "mensagem", "mensagens",
               "pediu", "pedido", "pedida", "mandou", "escreveu", "dedicatoria", "contato", "saudacao"),
    # Construções de execução: o pedido vai ao ar agora.
    "execucao": ("pediu", "toca agora", "vai tocar", "ja ja", "recebi o seu pedido", "recebi seu pedido",
                 "pedido de", "pedida de", "atendendo", "quem pediu", "que pediu", "toca para", "toca pra"),
    # Com o nome espiado do legado (D7), só "chegou uma mensagem".
    "recente_permitido": ("chegou", "mensagem", "recado"),
    # Mensagem, recado ou pedido simulado (texto normalizado).
    "simulada": (r"\bchegou( agora)?( aqui)? (uma|um) (mensagem|recado|pedido)",
                 r"\bacabou de chegar\b",
                 r"\brecebi( aqui)? (uma|um) (mensagem|recado|pedido)",
                 r"\b(uma|um) ouvinte (que )?(pediu|mandou|escreveu)",
                 r"\bmuita gente (pediu|mandou)",
                 r"\btem gente pedindo"),
    # Palavras com inicial maiúscula que não são nome de ouvinte.
    "palavras_comuns": frozenset({
        "um", "uma", "o", "a", "os", "as", "e", "agora", "voce", "quem", "que", "alo", "quer", "obrigado",
        "obrigada", "boa", "bom", "recado", "mensagem", "whatsapp", "fica", "valeu", "olha", "entao", "aqui",
        "isso", "esse", "essa", "este", "esta", "mas", "pois", "hoje", "amanha", "parabens", "feliz", "abraco",
        "beijo", "manda", "mande", "pode", "vai", "vem", "tem", "da", "de", "do", "das", "dos", "para", "pra",
        "com", "na", "no", "em", "nesta", "neste", "radio", "programa", "deus", "nossa", "senhora", "oi", "ola",
    }),
    "tratamentos": ("seu", "dona", "sr", "sra", "dr", "dra", "tia", "tio"),
    "conectivos_nome": ("de", "da", "do", "dos", "das"),
    "instrucoes": {
        "com_selecionado": "Cite só {selecionado}; não cite outros ouvintes.",
        "sem_selecionado": "Não cite nomes de ouvintes nesta fala.",
        "simulada": "Não invente mensagem, recado ou pedido de ouvinte: sem pedido real, faça só um convite "
                    "genérico.",
        "sem_mencao": "Cumprimente {nome} pelo nome.",
    },
}

REGRAS_PARTICIPACAO = ("pedido_nao_selecionado", "ouvinte_nao_autorizado", "participacao_simulada",
                       "pedido_sem_mencao")

_CAP = r"[A-ZÀ-Ú][\wÀ-ú'’-]*"


def _padrao_nome(cfg: dict) -> re.Pattern:
    conectivos = "|".join(cfg["conectivos_nome"])
    return re.compile(rf"{_CAP}(?:\s(?:{conectivos})\s{_CAP}|\s{_CAP})*")


_NOME_RE = _padrao_nome(CONFIG_PARTICIPACAO)


@dataclasses.dataclass(frozen=True)
class NomesParticipacao:
    selecionados: tuple[str, ...] = ()       # pedido de música e de ouvinte deste bloco
    ja_atendidos: tuple[str, ...] = ()       # executados ou selecionados antes, nesta transmissão (D8)
    conhecidos: tuple[str, ...] = ()         # pedidos da transmissão e da fila (inclui os acima)
    recente: str | None = None               # espiado do legado (D7)
    excluidos: tuple[str, ...] = ()          # rádio, programa, locutor, elenco, cidade, quadros
    citaveis: tuple = ()                     # MusicaRef: títulos conhecidos (partes de menção de música)


@dataclasses.dataclass(frozen=True)
class MencaoOuvinte:
    regra: str
    nome: str
    frase: str


def _tem(normalizado: str, trecho: str) -> bool:
    alvo = normalizar(trecho)
    return bool(alvo) and f" {alvo} " in f" {normalizado} "


def _sem_tratamento(tokens: list[str], cfg: dict) -> list[str]:
    while tokens and tokens[0] in cfg["tratamentos"]:
        tokens = tokens[1:]
    return tokens


def cita_nome(texto: str, nome: str, *, primeiro_nome: bool = False, config: dict | None = None) -> bool:
    """O texto cita o ouvinte: nome inteiro ou sem o tratamento ("Ditinho" por "Seu Ditinho"); com
    `primeiro_nome`, também só o primeiro nome ("Lurdinha" por "Lurdinha Campos")."""
    cfg = config or CONFIG_PARTICIPACAO
    n = normalizar(texto)
    tokens = normalizar(nome).split()
    if not tokens:
        return False
    if _tem(n, " ".join(tokens)):
        return True
    resto = _sem_tratamento(tokens, cfg)
    if resto and resto != tokens and len(" ".join(resto)) >= 4 and _tem(n, " ".join(resto)):
        return True
    return primeiro_nome and bool(resto) and len(resto[0]) >= 3 and _tem(n, resto[0])


def _entre(nome: str, nomes: Iterable[str]) -> bool:
    alvo = normalizar(nome)
    return any(alvo == normalizar(outro) or cita_nome(nome, outro) or cita_nome(outro, nome) for outro in nomes
               if outro)


def _nome_desconhecido(trecho: str, cobertos: list[str], cfg: dict) -> str | None:
    """O que sobra do trecho com iniciais maiúsculas depois de tirar os nomes conhecidos e as palavras comuns;
    None quando não sobra nome."""
    alvo = normalizar(trecho)
    tokens = alvo.split()
    uteis = [t for t in tokens if t not in cfg["palavras_comuns"]]
    if not uteis:
        return None
    if any(f" {alvo} " in f" {c} " or f" {' '.join(uteis)} " in f" {c} " for c in cobertos):
        return None
    restante = f" {alvo} "
    for coberto in sorted(cobertos, key=len, reverse=True):
        restante = restante.replace(f" {coberto} ", " ")
    sobra = [t for t in restante.split() if t not in cfg["palavras_comuns"]]
    if not sobra:
        return None
    # Devolve o trecho original a partir do tratamento ou do primeiro token que sobrou.
    palavras = trecho.split()
    for i, palavra in enumerate(palavras):
        if normalizar(palavra) in sobra or normalizar(palavra) in cfg["tratamentos"]:
            return " ".join(palavras[i:]).strip(" ,.;:!?")
    return trecho.strip(" ,.;:!?")


def mencoes_participacao(texto: str, nomes: NomesParticipacao, config: dict | None = None) -> list[MencaoOuvinte]:
    """Violações de participação no texto (sem a D10, que depende do bloco). Puro: o simulador usa o mesmo."""
    cfg = config or CONFIG_PARTICIPACAO
    padrao = _NOME_RE if config is None else _padrao_nome(cfg)
    achadas: list[MencaoOuvinte] = []
    selecionados = [s for s in nomes.selecionados if s]
    for frase in frases(texto):
        n = normalizar(frase)
        execucao = any(_tem(n, e) for e in cfg["execucao"])
        citados: list[str] = []
        for nome in dict.fromkeys(c for c in nomes.conhecidos if c):
            if not cita_nome(frase, nome):
                continue
            citados.append(nome)
            if _entre(nome, selecionados):
                continue
            if nomes.recente and _entre(nome, [nomes.recente]):
                permitido = not execucao and any(_tem(n, c) for c in cfg["recente_permitido"])
            else:
                permitido = not execucao and _entre(nome, nomes.ja_atendidos)
            if not permitido:
                achadas.append(MencaoOuvinte("pedido_nao_selecionado", nome, frase))
        if any(_tem(n, p) for p in cfg["pistas"]):
            partes = [parte for m in mencoes_musica(frase, nomes.citaveis, [*nomes.excluidos, *nomes.conhecidos])
                      for parte in m.partes]
            cobertos = [normalizar(x) for x in [*nomes.excluidos, *nomes.conhecidos, *partes, "WhatsApp"]
                        if normalizar(x)]
            for achado in padrao.finditer(frase):
                trecho = achado.group(0)
                if not frase[:achado.start()].strip(" \"'“”‘’-—"):
                    # A primeira palavra da frase sempre tem maiúscula ("Alô", "Quer", "Contato de Fulano"): o
                    # nome, se houver, está no resto do trecho.
                    resto = trecho.split()[1:]
                    while resto and normalizar(resto[0]) in cfg["conectivos_nome"]:
                        resto = resto[1:]
                    if not resto:
                        continue
                    trecho = " ".join(resto)
                desconhecido = _nome_desconhecido(trecho, cobertos, cfg)
                if desconhecido:
                    achadas.append(MencaoOuvinte("ouvinte_nao_autorizado", desconhecido, frase))
        if not selecionados and not nomes.recente and any(re.search(r, n) for r in cfg["simulada"]):
            achadas.append(MencaoOuvinte("participacao_simulada", "", frase))
    return achadas


# ---------------------------------------------------------------------------------------------------------
# Sobre o ContextoEmissao
# ---------------------------------------------------------------------------------------------------------

def _citaveis(ctx: "ContextoEmissao") -> tuple:
    m = ctx.musica
    return tuple(r for r in (*m.citaveis, m.confirmada, *m.bloco, *m.tocou) if r is not None)


def nomes_permitidos(ctx: "ContextoEmissao") -> NomesParticipacao:
    p = ctx.participacao
    selecionados = tuple(dict.fromkeys(
        [*p.nomes_selecionados, *(x.nome for x in (p.pedido_musica, p.pedido_ouvinte) if x is not None and x.nome)]))
    conhecidos = tuple(dict.fromkeys([*selecionados, *p.nomes_conhecidos, *p.nomes_ja_atendidos,
                                      *([p.nome_recente] if p.nome_recente else []), *p.nomes_autorizados]))
    excluidos = tuple(n for n in nomes_nao_musica(ctx) if not _entre(n, conhecidos))
    return NomesParticipacao(selecionados=selecionados, ja_atendidos=tuple(p.nomes_ja_atendidos),
                             conhecidos=conhecidos, recente=p.nome_recente, excluidos=excluidos,
                             citaveis=_citaveis(ctx))


def _instrucao(regra: str, nomes: NomesParticipacao, cfg: dict) -> str:
    modelos = cfg["instrucoes"]
    if regra == "participacao_simulada":
        return modelos["simulada"]
    if nomes.selecionados:
        return modelos["com_selecionado"].format(selecionado=" e ".join(nomes.selecionados))
    return modelos["sem_selecionado"]


def checar_participacao(fala: str, ctx: "ContextoEmissao", config: dict | None = None) -> list[Violacao]:
    """Checagem pós-geração (fases "pre" e "final"): remove a oração ou a frase com a violação."""
    cfg = config or CONFIG_PARTICIPACAO
    nomes = nomes_permitidos(ctx)
    return [Violacao(m.regra, m.frase, m.nome, _instrucao(m.regra, nomes, cfg))
            for m in mencoes_participacao(fala, nomes, cfg)]


def pedido_sem_mencao(fala: str, ctx: "ContextoEmissao", config: dict | None = None) -> Violacao | None:
    """D10: chamada de ouvinte com pedido selecionado e o nome ausente da fala. Remediação "avisar": não há
    frase a tirar; a reescrita pede o nome e, persistindo, o router devolve o pedido à fila."""
    cfg = config or CONFIG_PARTICIPACAO
    pedido = ctx.participacao.pedido_ouvinte
    if ctx.categoria != "chamada_ouvinte" or pedido is None or not (pedido.nome or "").strip():
        return None
    if cita_nome(fala, pedido.nome, primeiro_nome=True, config=cfg):
        return None
    return Violacao("pedido_sem_mencao", fala.strip()[:120], pedido.nome,
                    cfg["instrucoes"]["sem_mencao"].format(nome=pedido.nome), "avisar")
