"""Validador pós-geração da fala do ao vivo (F3): regra editorial 1, "não anunciar música que não está
confirmada para tocar", e o fragmento que o encurtamento deixa abaixo do mínimo do tipo.

Determinístico, sem LLM e sem rede (no máximo 2 chamadas de LLM por /proxima continua valendo, F2). Os padrões
ficam em `CONFIG_VALIDACAO`. O mesmo detector (`mencoes_musica`) é importado pelo simulador
(scripts/simulacao/metricas.py): não existe um segundo validador.

Detecção de menção a música (docs/melhoria-radio/f3/auditoria.md §5.4):
- camada (a), títulos conhecidos (`EstadoMusical.citaveis`) citados como palavras inteiras, com inicial maiúscula;
- camada (b), construções de anúncio: um marcador ("toca agora", "vem aí", "pode esperar"...) seguido de um
  trecho com iniciais maiúsculas, ou a forma "<Trecho>, com/de <Trecho>", nas duas ordens (título e artista ou
  artista e título); trechos que são nomes da rádio, do programa, do locutor ou de ouvintes ficam de fora;
- camada (c), só no backend: citadas que o extrator do LLM devolveu e que não se resolveram em faixa.
Uma menção está confirmada se alguma parte dela for "a mesma música" (regra de app.live.music.titulo_ja_tocado)
da faixa confirmada, das faixas do bloco, das que já tocaram ou da música do pedido selecionado. Pedido em fila
não confirma nada.

Remediação (decisão D2): V1 entra como mais um motivo da reescrita única quando a citada não vai tocar de jeito
nenhum (fase "pre"); V2, na fala final, remove a frase (`remover_frases`), e a fala vazia vira só música (bloco de
música sem pedido) ou a reorientação neutra (`fala_reserva_neutra`), nunca uma promessa de conteúdo. Modo
`settings.validacao_musica_modo`: "corrigir" (padrão) ou "avisar" (só registra).

Ganchos: a F4 registra a checagem de promessas e participação e a F5 a de dados (`checar_dados`, que chama
app.dados.checagem.checar_fala) em `CHECAGENS_POS_GERACAO`, reaproveitando `Violacao`, `remover_frases` e
`fala_reserva_neutra`.
"""

import dataclasses
import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Callable, Iterable, Literal

from app.live.music import _MIN_CARACTERES_CONTENCAO, _titulo_normalizado, titulo_ja_tocado
from app.live.orcamento import estimar_duracao_s, frases

if TYPE_CHECKING:
    from app.live.contexto import ContextoEmissao, MusicaRef

logger = logging.getLogger("radialista.live")

Remediacao = Literal["remover_frase", "avisar", "fala_inteira"]
Acao = Literal["nenhuma", "reescrita", "mencao_removida", "fala_neutra", "fala_removida"]

CONFIG_VALIDACAO = {
    "musica": {
        # Construções de anúncio (camada b), sem diferença de maiúscula: o marcador abre a frase ou vem no meio.
        "marcadores": [
            "toca agora", "tocando agora", "agora vem", "agora vai", "agora toca", "vem aí", "já já vem", "vem",
            "a seguir", "na sequência", "pode esperar", "vamos de", "vamos ouvir", "bora ouvir", "bora de",
            "com vocês", "ouça", "agora", "e depois", "em seguida",
        ],
        # Palavras que podem ligar as partes de um nome com iniciais maiúsculas ("Moinho do Vale").
        "conectivos": ["de", "da", "do", "das", "dos", "na", "no", "nas", "nos", "e", "a", "o", "em"],
        # "<Título>, com <Artista>" e variações.
        "ligacoes_artista": ["com", "de", "do", "da"],
        "ligacoes_canonicas": ["com", "de"],
        # Começos que não fazem parte do nome ("Agora vem", "Quem chega agora é").
        "inicios_descartados": ["Vamos", "Bora", "Agora", "E", "Quem chega agora é", "Chega agora", "Vem"],
        "inicios_descartados_ligacao": ["de", "com", "é"],
        # Trecho de uma palavra só que nunca é música.
        "palavras_soltas": ["Agora", "Você", "E", "A", "O"],
        # Contenção mínima para "a mesma música" (a mesma de app.live.music).
        "min_caracteres_contencao": _MIN_CARACTERES_CONTENCAO,
        # Título conhecido só conta citado com inicial maiúscula (evita "as evidências mostram").
        "conhecida_exige_maiuscula": True,
    },
    "instrucoes": {
        "com_confirmada": "Você citou '{citada}', que não vai tocar. A única faixa confirmada é '{titulo}' de "
                          "'{artista}'; não cite outra.",
        "sem_confirmada": "Você citou '{citada}', que não vai tocar. Não cite música pelo nome.",
    },
    # Reorientação de quem acabou de sintonizar, da mais longa para a mais curta: vale a primeira que cabe no
    # máximo do orçamento (e tem os nomes preenchidos).
    "reserva_neutra": [
        "Você está no {programa}, na {radio}.",
        "Você está na {radio}.",
        "Você está no {programa}.",
    ],
}


# ---------------------------------------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Violacao:
    """Mesmo formato que a F5 (checar_fala) e a F4 (promessas) usam."""

    regra: str                      # "musica_nao_confirmada" | "fala_abaixo_do_minimo" | (F5) ... | (F4) ...
    trecho: str                     # frase onde está
    ref_id: str = ""                # título citado / dado_id / promessa_id
    instrucao_retry: str = ""       # texto para a reescrita única
    remediacao: Remediacao = "remover_frase"


@dataclasses.dataclass(frozen=True)
class MencaoMusica:
    trecho: str                     # o nome como aparece (título, ou artista quando vem primeiro)
    partes: tuple[str, ...]         # título e artista, em qualquer ordem
    frase: str
    camada: Literal["conhecida", "construcao"]
    rotulo: str                     # "Título - Artista" quando conhecida; senão as partes
    conhecida: "MusicaRef | None" = None


Checagem = Callable[[str, "ContextoEmissao"], list[Violacao]]


# ---------------------------------------------------------------------------------------------------------
# Detector (puro: o simulador usa o mesmo)
# ---------------------------------------------------------------------------------------------------------

def _norm(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _alternativa(itens: Iterable[str]) -> str:
    return "|".join(re.escape(i) for i in sorted(itens, key=len, reverse=True))


def _padroes(cfg: dict) -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    m = cfg["musica"]
    con = rf"(?:{_alternativa(m['conectivos'])}|com\s(?=[A-ZÀ-Ú]))"
    cap = r"[A-ZÀ-Ú][\wÀ-ú'’-]*"
    trecho = rf"{cap}(?:\s(?:{con}\s)?{cap})*"
    marca = rf"\b(?i:{_alternativa(m['marcadores'])}),?\s+(?P<t>{trecho})" \
            rf"(?:,\s(?:{_alternativa(m['ligacoes_artista'])})\s(?P<a>{trecho}))?"
    canonica = rf"(?P<t>{trecho}),\s(?:{_alternativa(m['ligacoes_canonicas'])})\s(?P<a>{trecho})"
    inicio = rf"^(?:(?:{_alternativa(m['inicios_descartados'])})\s" \
             rf"(?:{_alternativa(m['inicios_descartados_ligacao'])})?\s?)+"
    return re.compile(marca), re.compile(canonica), re.compile(inicio)


_PADROES = _padroes(CONFIG_VALIDACAO)


def _mesma(nome: str, conhecidos: Iterable[str]) -> bool:
    """`nome` é a mesma música (ou o mesmo nome) que algum de `conhecidos`: igualdade ou contenção de palavras
    inteiras nos dois sentidos, como app.live.music.titulo_ja_tocado."""
    return titulo_ja_tocado(nome, {_titulo_normalizado(k) for k in conhecidos if k})


def _nome_proprio(nome: str, nao_musica: Iterable[str]) -> bool:
    alvo = _norm(nome)
    return bool(alvo) and any(alvo == _norm(n) or _mesma(nome, [n]) for n in nao_musica if _norm(n))


def _frase_de(texto: str, inicio: int) -> str:
    """Frase (pela mesma divisão do encurtamento da F2) que contém a posição `inicio` do texto."""
    posicao = 0
    for frase in frases(texto):
        achada = texto.find(frase, posicao)
        if achada <= inicio < achada + len(frase):
            return frase
        posicao = max(posicao, achada + len(frase))
    return texto.strip()


def _palavras_com_posicao(texto: str) -> list[tuple[str, str, int]]:
    """(palavra original, normalizada, posição) de cada palavra do texto."""
    return [(m.group(0), _norm(m.group(0)), m.start()) for m in re.finditer(r"[\wÀ-ú'’]+", texto)
            if _norm(m.group(0))]


def _conhecidas_no_texto(texto: str, citaveis: Iterable["MusicaRef"], exigir_maiuscula: bool):
    """Títulos conhecidos citados como palavras inteiras: (ref, posição, trecho original)."""
    palavras = _palavras_com_posicao(texto)
    normalizadas = [p[1] for p in palavras]
    vistos = set()
    for ref in citaveis:
        alvo = _norm(ref.titulo).split()
        chave = tuple(alvo)
        if not alvo or chave in vistos:
            continue
        vistos.add(chave)
        for i in range(len(normalizadas) - len(alvo) + 1):
            if normalizadas[i:i + len(alvo)] != alvo:
                continue
            originais = [p[0] for p in palavras[i:i + len(alvo)]]
            if exigir_maiuscula and not originais[0][:1].isupper():
                continue
            fim = palavras[i + len(alvo) - 1][2] + len(originais[-1])
            yield ref, palavras[i][2], texto[palavras[i][2]:fim]


def mencoes_musica(texto: str, citaveis: Iterable["MusicaRef"] = (), nao_musica: Iterable[str] = (),
                   config: dict | None = None) -> list[MencaoMusica]:
    """Menções a música em `texto`, na ordem em que aparecem (camadas a e b). Puro."""
    cfg = config or CONFIG_VALIDACAO
    marca, canonica, inicio = _PADROES if config is None else _padroes(cfg)
    m_cfg = cfg["musica"]
    citaveis = list(citaveis)
    nao_musica = [n for n in nao_musica if n and n.strip()]
    achadas: list[tuple[int, MencaoMusica]] = []
    ocupados: list[tuple[int, int]] = []

    def conhecida_de(*partes: str):
        for ref in citaveis:
            if any(p and _norm(p) == _norm(ref.titulo) for p in partes):
                return ref
        for ref in citaveis:
            if any(p and _mesma(p, [ref.titulo]) for p in partes):
                return ref
        return None

    for padrao in (marca, canonica):
        for achado in padrao.finditer(texto):
            t = inicio.sub("", achado.group("t")).strip()
            a = (achado.group("a") or "").strip()
            if not t or any(_nome_proprio(p, nao_musica) for p in (t, a) if p):
                continue
            if len(_norm(t).split()) == 1 and t in m_cfg["palavras_soltas"] and not a:
                continue
            if any(achado.start("t") < fim and inicio_o < achado.end() for inicio_o, fim in ocupados):
                continue
            ocupados.append((achado.start("t"), achado.end()))
            ref = conhecida_de(t, a)
            rotulo = f"{ref.titulo} - {ref.artista}" if ref is not None and ref.artista else \
                (ref.titulo if ref is not None else (f"{t} - {a}" if a else t))
            achadas.append((achado.start("t"), MencaoMusica(
                trecho=t, partes=tuple(p for p in (t, a) if p), frase=_frase_de(texto, achado.start("t")),
                camada="construcao", rotulo=rotulo, conhecida=ref)))

    for ref, posicao, original in _conhecidas_no_texto(texto, citaveis, m_cfg["conhecida_exige_maiuscula"]):
        if _nome_proprio(original, nao_musica):
            continue
        if any(inicio_o <= posicao < fim for inicio_o, fim in ocupados):
            continue
        if any(m.conhecida is ref for _, m in achadas):
            continue
        ocupados.append((posicao, posicao + len(original)))
        achadas.append((posicao, MencaoMusica(
            trecho=original, partes=(ref.titulo,), frase=_frase_de(texto, posicao), camada="conhecida",
            rotulo=f"{ref.titulo} - {ref.artista}" if ref.artista else ref.titulo, conhecida=ref)))
    return [m for _, m in sorted(achadas, key=lambda par: par[0])]


def confirmada(mencao: MencaoMusica, permitidas: Iterable[str], artistas: Iterable[str] = ()) -> bool:
    """A menção é de uma música confirmada: alguma parte dela é a mesma música de um título permitido, ou ela cita
    só o artista de uma faixa permitida ("Com vocês, Banda X" antes da faixa da Banda X). Título errado com o
    artista certo continua sem confirmação."""
    permitidas = [p for p in permitidas if p]
    if any(_mesma(parte, permitidas) for parte in mencao.partes):
        return True
    artistas = [a for a in artistas if a]
    return len(mencao.partes) == 1 and _mesma(mencao.partes[0], artistas)


# ---------------------------------------------------------------------------------------------------------
# Checagem de música sobre o ContextoEmissao
# ---------------------------------------------------------------------------------------------------------

def titulos_permitidos(ctx: "ContextoEmissao") -> list[str]:
    """Confirmada, faixas do bloco, já tocadas e música do pedido selecionado. Pedido em fila não entra."""
    m = ctx.musica
    refs = [m.confirmada, *m.bloco, *m.tocou]
    return [ref.titulo for ref in refs if ref is not None and ref.titulo]


def artistas_permitidos(ctx: "ContextoEmissao") -> list[str]:
    m = ctx.musica
    return [ref.artista for ref in (m.confirmada, *m.bloco, *m.tocou) if ref is not None and ref.artista]


def nomes_nao_musica(ctx: "ContextoEmissao") -> list[str]:
    """Nomes próprios que não são música: rádio, programa, locutor, elenco, cidade, quadros e ouvintes."""
    nomes = [getattr(ctx.account, "nome_radio", ""), getattr(ctx.account, "cidade", ""), ctx.programa.nome,
             getattr(ctx.radialista, "nome_locutor", "")]
    nomes += [getattr(p.radialista, "nome_locutor", "") for p in ctx.roster]
    nomes += list((ctx.programa.quadros_fixos or {}).keys())
    nomes += list(ctx.participacao.nomes_autorizados)
    return [n for n in nomes if n]


def _instrucao(citada: str, ctx: "ContextoEmissao") -> str:
    modelos = CONFIG_VALIDACAO["instrucoes"]
    alvo = ctx.musica.confirmada
    if alvo is not None:
        return modelos["com_confirmada"].format(citada=citada, titulo=alvo.titulo, artista=alvo.artista)
    return modelos["sem_confirmada"].format(citada=citada)


def _frase_com_titulo(texto: str, titulo: str) -> str:
    alvo = f" {_norm(titulo)} "
    for frase in frases(texto):
        if alvo.strip() and alvo in f" {_norm(frase)} ":
            return frase
    return ""


def checar_musicas(fala: str, ctx: "ContextoEmissao") -> list[Violacao]:
    """Música anunciada que não está confirmada para tocar. Antes da resolução das citadas (fase "pre") só
    vale quando nenhuma citada vai tocar (bloco de música do formato musical ou com relógio)."""
    musica = ctx.musica
    if not musica.resolvido and musica.resolve_citadas:
        return []
    permitidas, artistas = titulos_permitidos(ctx), artistas_permitidos(ctx)
    violacoes: list[Violacao] = []
    for mencao in mencoes_musica(fala, musica.citaveis, nomes_nao_musica(ctx)):
        if confirmada(mencao, permitidas, artistas):
            continue
        violacoes.append(Violacao("musica_nao_confirmada", mencao.frase, mencao.trecho,
                                  _instrucao(mencao.trecho, ctx)))
    # Camada (c): o extrator achou uma citada que não virou faixa (sem resultado, fora do gênero, sem espaço).
    from app.live.song_service import dividir_artista_titulo

    for citada in musica.citadas_nao_resolvidas:
        partes = dividir_artista_titulo(citada)
        titulo = partes[1] if partes is not None else citada
        if _mesma(titulo, permitidas) or any(_mesma(titulo, [v.ref_id]) for v in violacoes):
            continue
        frase = _frase_com_titulo(fala, titulo)
        violacoes.append(Violacao("musica_nao_confirmada", frase, titulo, _instrucao(titulo, ctx),
                                  "remover_frase" if frase else "avisar"))
    return violacoes


def checar_promessas(fala: str, ctx: "ContextoEmissao") -> list[Violacao]:
    """F4: promessa sem evento agendado (app.live.promessas; importado na chamada, que importa este módulo)."""
    from app.live.promessas import checar_promessas as checar

    return checar(fala, ctx)


def checar_participacao(fala: str, ctx: "ContextoEmissao") -> list[Violacao]:
    """F4: pedido não selecionado, ouvinte inexistente e mensagem simulada (app.live.participacao)."""
    from app.live.participacao import checar_participacao as checar

    return checar(fala, ctx)


def checar_pedido_sem_mencao(fala: str, ctx: "ContextoEmissao") -> list[Violacao]:
    """F4 (D10): pedido de ouvinte selecionado que some da fala."""
    from app.live.participacao import pedido_sem_mencao

    violacao = pedido_sem_mencao(fala, ctx)
    return [violacao] if violacao is not None else []


def cobertura_extra(ctx: "ContextoEmissao") -> list[str]:
    """F5 (D17): textos configurados pela rádio que já entram no prompt e contam como fonte, só pela palavra-gatilho
    (descrição do programa, quadro do bloco, assunto sugerido, conhecimento local, bíblia, slogan), mais o contexto
    da faixa que vai tocar."""
    account, programa, v = ctx.account, ctx.programa, ctx.variacoes

    def textos(valor) -> list[str]:
        if isinstance(valor, dict):
            return [t for item in valor.values() for t in textos(item)]
        if isinstance(valor, (list, tuple)):
            return [t for item in valor for t in textos(item)]
        return [str(valor)] if valor else []

    return [*textos(getattr(programa, "descricao", "")), *textos(v.quadro_fixo), *textos(v.assunto_sugerido),
            *textos(getattr(account, "conhecimento_local", None)), *textos(getattr(account, "biblia_radio", None)),
            *textos(getattr(account, "slogan", "")), *textos(ctx.musica.contexto_faixa)]


def checar_dados(fala: str, ctx: "ContextoEmissao") -> list[Violacao]:
    """F5: afirmação de dado sem fonte ou vencido (app.dados.checagem; importado na chamada, que importa este
    módulo). A contingência do bloco e a reorientação neutra são isentas."""
    from app.dados.checagem import checar_fala

    nomes = {"radio": (getattr(ctx.account, "nome_radio", "") or "").strip(),
             "programa": (ctx.programa.nome or "").strip()}
    neutras = [m.format(**nomes) for m in CONFIG_VALIDACAO["reserva_neutra"]]
    return checar_fala(fala, ctx.dados, ctx.tempo.instante, ctx.radialista.timezone,
                       cobertura_extra=cobertura_extra(ctx),
                       isentas=[*(c.texto for c in ctx.chamadas.contingencias), *neutras])


def checar_bairro(fala: str, ctx: "ContextoEmissao") -> list[Violacao]:
    """"Aqui" num bairro que não é o da rádio ("aqui na Pomerânia" numa rádio do Centro; app.localizacao)."""
    from app.localizacao import aqui_em_outro_bairro, bairro_da_sede

    sede = bairro_da_sede(ctx.account)
    certo = (f"A rádio fica no bairro {sede}: 'aqui' é só o {sede}." if sede
             else "O bairro da rádio não foi informado: não diga 'aqui' com nome de bairro.")
    violacoes = []
    for frase in frases(fala):
        bairro = aqui_em_outro_bairro(frase, ctx.account)
        if bairro is not None:
            violacoes.append(Violacao(
                regra="bairro_errado", trecho=frase, ref_id=bairro,
                instrucao_retry=f"Você falou do {bairro} como se a rádio ficasse lá. {certo} Outro bairro é de "
                                f"onde o ouvinte fala ('lá no {bairro}', 'o pessoal do {bairro}').",
            ))
    return violacoes


CHECAGENS_POS_GERACAO: list[Checagem] = [checar_musicas, checar_promessas, checar_participacao,
                                         checar_pedido_sem_mencao, checar_dados, checar_bairro]

# Modo de cada regra (decisão D12 da F4): o nome do campo em settings. Regra fora daqui segue o da música.
MODO_POR_REGRA = {
    "musica_nao_confirmada": "validacao_musica_modo",
    "promessa_sem_evento": "validacao_promessa_modo",
    "pedido_nao_selecionado": "validacao_participacao_modo",
    "ouvinte_nao_autorizado": "validacao_participacao_modo",
    "participacao_simulada": "validacao_participacao_modo",
    "pedido_sem_mencao": "validacao_participacao_modo",
    "dado_sem_fonte": "validacao_dados_modo",
    "dado_vencido": "validacao_dados_modo",
    "bairro_errado": "validacao_local_modo",
}


def modo_da_regra(regra: str) -> str:
    from app.config.settings import settings

    return getattr(settings, MODO_POR_REGRA.get(regra, "validacao_musica_modo"))


def com_modo(violacao: Violacao, modo_musica: str | None = None) -> Violacao:
    """No modo "avisar" a violação só é registrada: nada sai da fala. `modo_musica` substitui o de settings para
    as regras da F3 (o `modo` de `corrigir`)."""
    campo = MODO_POR_REGRA.get(violacao.regra, "validacao_musica_modo")
    modo = modo_musica if modo_musica is not None and campo == "validacao_musica_modo" else modo_da_regra(
        violacao.regra)
    if violacao.remediacao == "remover_frase" and modo != "corrigir":
        return dataclasses.replace(violacao, remediacao="avisar")
    return violacao


def para_reescrita(violacoes: Iterable[Violacao]) -> list[Violacao]:
    """V1: só as violações de regras no modo "corrigir" entram na reescrita única."""
    return [v for v in violacoes if modo_da_regra(v.regra) == "corrigir"]


def validar(fala: str, ctx: "ContextoEmissao", fase: Literal["pre", "final"],
            checagens: Iterable[Checagem] | None = None) -> list[Violacao]:
    """Roda as checagens registradas. Uma checagem que quebra não derruba a fala: registra e segue."""
    violacoes: list[Violacao] = []
    for checagem in (CHECAGENS_POS_GERACAO if checagens is None else checagens):
        try:
            violacoes += checagem(fala, ctx) or []
        except Exception:
            logger.warning("live_validacao_checagem_falhou fase=%s checagem=%s", fase,
                           getattr(checagem, "__name__", checagem), exc_info=True)
    return violacoes


# ---------------------------------------------------------------------------------------------------------
# Remediação
# ---------------------------------------------------------------------------------------------------------

_LIGACOES_ARTISTA_RE = re.compile(r"^(?:com|de|do|da|na voz de)\s", re.IGNORECASE)

# Como cada regra divide a frase em orações para tirar só a da violação. A música (F3) corta só por vírgula; a
# participação (F4) também corta em "e (também) para" e leva junto a oração relativa do nome tirado ("que
# escreveu agora"): "Um abraço para Cida e também para a Dona Firmina, que escreveu" mantém a Cida.
_CORTE_ORACAO = {
    "padrao": (re.compile(r",\s+"), _LIGACOES_ARTISTA_RE),
    "participacao": (re.compile(r",\s+|\s+(?=e\s+(?:também\s+)?(?:para|pra)\s)", re.IGNORECASE),
                     re.compile(r"^(?:com|de|do|da|na voz de|que|quem)\s", re.IGNORECASE)),
}
_REGRAS_CORTE_PARTICIPACAO = ("pedido_nao_selecionado", "ouvinte_nao_autorizado", "participacao_simulada")


def _sem_clausula(frase: str, trecho: str, preservar: list[str], regra: str = "") -> str | None:
    """Tira só a oração com o trecho (e o artista ligado a ela) quando a frase também tem um termo preservado
    (título confirmado, nome do ouvinte) fora dela. None quando não dá."""
    divisor, continuacao = _CORTE_ORACAO["participacao" if regra in _REGRAS_CORTE_PARTICIPACAO else "padrao"]
    final = frase[-1] if frase and frase[-1] in ".!?…" else "."
    clausulas = divisor.split(frase.rstrip(".!?… "))
    alvo = _norm(trecho)
    indice = next((i for i, c in enumerate(clausulas) if alvo and f" {alvo} " in f" {_norm(c)} "), None)
    if indice is None or indice == 0:
        return None
    fim = indice + 1
    while fim < len(clausulas) and continuacao.match(clausulas[fim]):
        fim += 1
    resto = clausulas[:indice] + clausulas[fim:]
    texto = re.sub(r"\s+e(?: depois)?$", "", ", ".join(resto)).strip()
    if not texto or not any(f" {_norm(p)} " in f" {_norm(texto)} " for p in preservar if _norm(p)):
        return None
    return texto + final


def remover_frases(fala: str, violacoes: Iterable[Violacao], preservar: Iterable[str] = ()) -> str:
    """Extrativo: tira as frases com violação (remediação "remover_frase"). Frase que também tem um termo
    preservado perde só a oração da violação, quando isso basta; senão sai inteira (a regra editorial vale
    mais que manter o nome). Nunca reescreve palavra."""
    preservar = [p for p in preservar if p]
    alvos = [v for v in violacoes if v.remediacao == "remover_frase" and v.trecho]
    if not alvos:
        return fala
    ficam = []
    for frase in frases(fala):
        das_violacoes = [v for v in alvos if v.trecho.strip() and (v.trecho.strip() in frase or frase in v.trecho)]
        if not das_violacoes:
            ficam.append(frase)
            continue
        reduzida = frase
        for violacao in das_violacoes:
            if reduzida is None:
                break
            reduzida = _sem_clausula(reduzida, violacao.ref_id or violacao.trecho, preservar, violacao.regra)
        if reduzida:
            ficam.append(reduzida)
    return " ".join(ficam)


def fala_reserva_neutra(ctx: "ContextoEmissao", wpm: float | None = None) -> str:
    """Reorientação de quem acabou de sintonizar: repetição permitida, sem prometer conteúdo. A mais longa que
    cabe no máximo do orçamento aplicado, no ritmo `wpm` (padrão: o da voz para este bloco)."""
    nomes = {"radio": (getattr(ctx.account, "nome_radio", "") or "").strip(),
             "programa": (ctx.programa.nome or "").strip()}
    opcoes = [m.format(**nomes) for m in CONFIG_VALIDACAO["reserva_neutra"]
              if all(nomes[c] for c in re.findall(r"\{(\w+)\}", m))] or [CONFIG_VALIDACAO["reserva_neutra"][-1]
                                                                       .format(**nomes)]
    if ctx.orcamento.aplicar:
        wpm = wpm or ctx.wpm_fala
        cabem = [o for o in opcoes if estimar_duracao_s(o, wpm) <= ctx.orcamento.max_s]
        return cabem[0] if cabem else min(opcoes, key=len)
    return opcoes[0]


def abaixo_do_minimo(fala: str, ctx: "ContextoEmissao", wpm: float, fracao: float = 1.0) -> bool:
    """Fala com orçamento aplicado que ficou abaixo do mínimo do tipo."""
    orcamento = ctx.orcamento
    return bool(fala.strip()) and orcamento.aplicar and \
        estimar_duracao_s(fala, wpm) < orcamento.min_s * fracao


def fragmento(fala: str, ctx: "ContextoEmissao", wpm: float, fracao: float, so_musica: bool) -> bool:
    """O que o encurtamento ou o validador deixaram não vai ao ar: abaixo do mínimo do tipo e com algo melhor no
    lugar (a música que vem em seguida, ou a reorientação neutra quando ela é mais longa que o que sobrou)."""
    if not abaixo_do_minimo(fala, ctx, wpm, fracao):
        return False
    return so_musica or estimar_duracao_s(fala_reserva_neutra(ctx, wpm), wpm) > estimar_duracao_s(fala, wpm)


@dataclasses.dataclass
class ResultadoValidacao:
    fala: str
    falas_bloco: list
    violacoes: list[Violacao]
    acao: Acao = "nenhuma"
    finais: list[Violacao] = dataclasses.field(default_factory=list)   # só as da fala final (V2)


def corrigir(fala: str, falas_bloco: list, ctx: "ContextoEmissao", *, preservar: Iterable[str], modo: str,
             so_musica_se_vazia: bool, alterada: bool, wpm: float, fracao_minimo: float = 1.0,
             violacoes_pre: Iterable[Violacao] = ()) -> ResultadoValidacao:
    """V2: checagens na fala final e remediação. `alterada`: o encurtamento (momento B) mexeu no texto, o que
    liga a regra do fragmento abaixo do mínimo. `so_musica_se_vazia`: depois da fala vem música e não há pedido
    a reconhecer, então fala vazia vira só música."""
    preservar = list(preservar)
    # Modo por regra (F4, D12): a regra em "avisar" só registra. O fragmento abaixo do mínimo segue `modo`.
    violacoes = [com_modo(v, modo) for v in validar(fala, ctx, "final")]
    pre = list(violacoes_pre)
    acao: Acao = "reescrita" if pre and not violacoes else "nenhuma"
    if any(v.remediacao == "remover_frase" for v in violacoes):
        if falas_bloco:
            linhas = []
            for linha in falas_bloco:
                texto = remover_frases(linha.texto, violacoes, preservar)
                if texto.strip():
                    linhas.append(linha.model_copy(update={"texto": texto}))
            nova_lista, nova = linhas, " ".join(item.texto for item in linhas)
        else:
            nova_lista, nova = falas_bloco, remover_frases(fala, violacoes, preservar)
        if nova != fala:
            acao, alterada = "mencao_removida", True
            fala, falas_bloco = nova, nova_lista
        if not fala.strip():
            fala, falas_bloco = ("", []) if so_musica_se_vazia else (fala_reserva_neutra(ctx, wpm), [])
            acao = "fala_removida" if so_musica_se_vazia else "fala_neutra"
    if alterada and acao not in ("fala_neutra", "fala_removida") and not falas_bloco \
            and fragmento(fala, ctx, wpm, fracao_minimo, so_musica_se_vazia):
        violacoes.append(Violacao("fala_abaixo_do_minimo", fala.strip()[:120], remediacao="fala_inteira"))
        if modo == "corrigir":
            fala = "" if so_musica_se_vazia else fala_reserva_neutra(ctx, wpm)
            acao = "fala_removida" if so_musica_se_vazia else "fala_neutra"
    return ResultadoValidacao(fala=fala, falas_bloco=falas_bloco, violacoes=pre + violacoes, acao=acao,
                              finais=list(violacoes))
