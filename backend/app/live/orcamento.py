"""Orçamento de duração da fala: fórmula única de estimativa, ritmo padrão e encurtamento (F2).

Usado pelo relógio (F1), por /proxima e /tts e pelo simulador da F0. Puro: não lê banco nem Redis
(a calibração por voz fica em app.live.ritmo_voz). Os números (ritmo, pausas, tolerâncias) são
hipóteses de projeto e ficam em app.config.settings (`fala_*`). Desenho em
docs/melhoria-radio/f2/auditoria.md (§4.2 e §4.3).

Cadeia do ritmo (`wpm_para` em app.live.ritmo_voz): calibração da voz → padrão do modelo
(`wpm_padrao(modelo)`) → padrão geral (`wpm_padrao()`).
"""
import math
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Literal

from app.config.settings import settings
from app.live.formato import ORCAMENTOS, _tipo_fala, contar_palavras, musical_companhia, orcamento_fala
from app.numeros import normalizar_texto_fala

Fonte = Literal["relogio", "formato", "observacao"]
Situacao = Literal["dentro", "tolerancia", "fora", "acima_do_teto"]
# O que a F2 fez com o texto da fala: nada, a reescrita única do LLM por orçamento, encurtamento por
# frases, corte (só no bloco de música sem pedido: fica só a música) ou nada possível (vai acima do teto).
Ajuste = Literal["nenhum", "reescrita", "encurtada", "cortada", "acima_do_teto"]

# Pausa longa pedida pelo prompt ("......") e a tag que o TTS recebe no lugar dela
# (app.tts.client._PAUSA_TROCA_ASSUNTO).
_PAUSA_RE = re.compile(r"\.{4,}|\[\s*pause\s*\]", re.IGNORECASE)
_FRONTEIRA_FRASE_RE = re.compile(r"(?<=[.!?…])\s+")

# Orçamento por formato: (mínimo s, máximo s, máximo de palavras ou None = pelo ritmo). O musical é
# construído a partir de formato.ORCAMENTOS (sem copiar números). O padrão só observa: 15 a 30 s
# correspondem às "4 a 6 frases de rádio" do prompt atual (hipótese; a F6 troca pela unidade de fala
# do catálogo de formatos mantendo a assinatura de orcamento_para).
ORCAMENTOS_POR_FORMATO: dict[str, dict[str, tuple[float, float, int | None]]] = {
    "musical_companhia": {**ORCAMENTOS, "*": orcamento_fala("*")},
    "padrao": {"*": (15, 30, None)},
}
# Formatos cujo orçamento sem relógio é aplicado (reescrita e encurtamento). Os demais só medem.
FORMATOS_APLICADOS = frozenset({"musical_companhia"})


@dataclass(frozen=True)
class OrcamentoFala:
    min_s: float
    alvo_s: float
    max_s: float
    max_palavras: int | None   # teto do formato (vai ao prompt junto com o do ritmo); None = só pelo ritmo
    fonte: Fonte
    aplicar: bool              # False = só mede e registra (formato padrão sem relógio)

    @property
    def cabe(self) -> bool:
        return self.max_s >= self.min_s


# --- estimativa ---------------------------------------------------------------------------------

def contar_pausas(texto: str) -> int:
    return len(_PAUSA_RE.findall(texto or ""))


def palavras_faladas(texto: str) -> int:
    """Palavras que o TTS fala: tags fora, pausas como separador e números por extenso (sem
    pronúncias, que exigem o banco)."""
    return contar_palavras(normalizar_texto_fala(_PAUSA_RE.sub(" ", texto or "")))


def estimar_duracao_s(texto: str, wpm: float) -> float:
    """Segundos de fala de `texto` a `wpm` palavras por minuto, mais as pausas explícitas."""
    if wpm <= 0:
        raise ValueError("wpm deve ser maior que zero")
    return palavras_faladas(texto) / wpm * 60 + contar_pausas(texto) * settings.fala_pausa_explicita_s


def wpm_padrao(modelo: str | None = None) -> float:
    """Ritmo sem calibração: o padrão do modelo de voz, senão o padrão geral."""
    return float(settings.fala_wpm_padrao_por_modelo.get(modelo or "", settings.fala_wpm_padrao))


def wpm_observado(palavras: int, duracao_s: float, pausas: int = 0, pausa_s: float | None = None) -> float | None:
    """Ritmo de uma amostra medida, sem as pausas explícitas. None para amostra curta ou fora da faixa
    plausível (áudio truncado, mp3 de teste, silêncio)."""
    pausa_s = settings.fala_pausa_explicita_s if pausa_s is None else pausa_s
    fala_s = (duracao_s or 0.0) - pausas * pausa_s
    if palavras < settings.fala_calibracao_min_palavras or fala_s < settings.fala_calibracao_min_segundos:
        return None
    wpm = palavras / fala_s * 60
    minimo, maximo = settings.fala_calibracao_wpm_faixa
    return wpm if minimo <= wpm <= maximo else None


# --- orçamento ----------------------------------------------------------------------------------

def formato_do_programa(programa) -> str:
    return "musical_companhia" if musical_companhia(programa) else "padrao"


def _do_formato(formato: str, tipo: str, primeira: bool) -> tuple[float, float, int | None]:
    tabela = ORCAMENTOS_POR_FORMATO.get(formato, ORCAMENTOS_POR_FORMATO["padrao"])
    chave = _tipo_fala(tipo)
    if chave == "abertura" and not primeira:
        chave = "retomada"
    return tabela.get(chave, tabela["*"])


def orcamento_para(formato: str, tipo: str, primeira: bool, teto_relogio_s: float | None = None, *,
                   minimo_relogio_s: float | None = None) -> OrcamentoFala:
    """Orçamento da fala. Sem relógio, o do formato (aplicado só no musical). Com o teto do relógio
    (backtiming da F1), o máximo é o menor entre ele e o do formato aplicado, e o orçamento vale em
    qualquer formato; o mínimo é o do relógio quando informado."""
    minimo, maximo, palavras = _do_formato(formato, tipo, primeira)
    alvo = (minimo + maximo) / 2
    if teto_relogio_s is None:
        aplicar = formato in FORMATOS_APLICADOS
        return OrcamentoFala(minimo, alvo, maximo, palavras, "formato" if aplicar else "observacao", aplicar)
    if formato in FORMATOS_APLICADOS:
        maximo = min(maximo, teto_relogio_s)
    else:
        maximo, palavras = teto_relogio_s, None
    if minimo_relogio_s is not None:
        minimo = minimo_relogio_s
    alvo = min((minimo + maximo) / 2 if formato not in FORMATOS_APLICADOS else alvo, maximo)
    return OrcamentoFala(minimo, alvo, maximo, palavras, "relogio", True)


def palavras_max(orcamento: OrcamentoFala, wpm: float, pausas: int = 0) -> int:
    """Palavras que cabem no máximo a `wpm`, descontadas as pausas, limitadas pelo teto do formato."""
    pelo_ritmo = max(1, math.floor((orcamento.max_s - pausas * settings.fala_pausa_explicita_s) * wpm / 60))
    return min(pelo_ritmo, orcamento.max_palavras) if orcamento.max_palavras is not None else pelo_ritmo


def com_maximo(orcamento: OrcamentoFala, max_s: float) -> OrcamentoFala:
    return replace(orcamento, max_s=max_s, alvo_s=min(orcamento.alvo_s, max_s))


def acima_da_tolerancia(segundos: float, orcamento: OrcamentoFala) -> bool:
    """A fala pede ajuste (reescrita ou encurtamento): orçamento aplicado e acima de máximo + tolerância."""
    return orcamento.aplicar and avaliar_duracao(segundos, orcamento) in ("fora", "acima_do_teto")


def avaliar_duracao(segundos: float, orcamento: OrcamentoFala) -> Situacao:
    """dentro (≤ máximo), tolerancia (≤ máximo + tolerância), fora (≤ máximo + teto) ou acima_do_teto."""
    maximo = orcamento.max_s
    if segundos <= maximo:
        return "dentro"
    if segundos <= maximo * (1 + settings.fala_tolerancia_orcamento) + 1e-9:
        return "tolerancia"
    if segundos <= maximo * (1 + settings.fala_teto_orcamento) + 1e-9:
        return "fora"
    return "acima_do_teto"


# --- encurtamento (extrativo, sem LLM) ----------------------------------------------------------

def _normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _contem(frase: str, termos: list[str]) -> bool:
    alvo = f" {_normalizar(frase)} "
    return any(t and f" {t} " in alvo for t in termos)


def frases(texto: str) -> list[str]:
    return [f.strip() for f in _FRONTEIRA_FRASE_RE.split((texto or "").strip()) if f.strip()]


def encurtar_por_frases(texto: str, max_palavras: int, preservar: Iterable[str] = (), *,
                        manter: Callable[[str], bool] | None = None, manter_ultima: bool = False) -> str | None:
    """Tira frases inteiras do fim até caber em `max_palavras` (palavras faladas). Mantém a ordem, as
    frases com algum termo de `preservar` (nome do ouvinte, título confirmado), as aceitas por
    `manter` (atribuição da notícia) e, com `manter_ultima`, a última (despedida). Nunca corta uma frase
    no meio nem devolve texto vazio: sem jeito de caber, None."""
    partes = frases(texto)
    if not partes:
        return None
    termos = [_normalizar(t) for t in preservar if _normalizar(t)]
    obrigatoria = [_contem(f, termos) or bool(manter and manter(f)) for f in partes]
    if manter_ultima:
        obrigatoria[-1] = True
    tamanhos = [palavras_faladas(f) for f in partes]
    mantidas = list(range(len(partes)))
    total = sum(tamanhos)
    for indice in reversed(range(len(partes))):
        if total <= max_palavras:
            break
        if obrigatoria[indice] or len(mantidas) == 1:
            continue
        mantidas.remove(indice)
        total -= tamanhos[indice]
    if total > max_palavras:
        return None
    return " ".join(partes[i] for i in mantidas)


def cortar_linhas_dialogo(falas: list[str], duracoes_s: list[float], max_s: float, pausa_s: float,
                          preservar: Iterable[str] = ()) -> int:
    """Quantas linhas do diálogo ficam (sempre um prefixo, para os índices de falas e áudios seguirem
    alinhados): tira linhas do fim até caber em `max_s`, com pelo menos 2 linhas e sem passar da última
    linha com termo preservado (o pedido do ouvinte)."""
    termos = [_normalizar(t) for t in preservar if _normalizar(t)]
    ficam = len(falas)

    def total(n: int) -> float:
        return sum(duracoes_s[:n]) + pausa_s * max(0, n - 1)

    while ficam > 2 and total(ficam) > max_s and not _contem(falas[ficam - 1], termos):
        ficam -= 1
    return ficam


def ajustar_ao_orcamento(texto: str, orcamento: OrcamentoFala, wpm: float, *, preservar: Iterable[str] = (),
                         manter: Callable[[str], bool] | None = None, manter_ultima: bool = False,
                         pode_cortar: bool = False) -> tuple[str, Ajuste]:
    """Depois da reescrita única (ou quando ela já foi usada por outro motivo): se a estimativa ainda passa
    de máximo + tolerância, encurta por frases; sem frase que caiba, corta a fala só quando `pode_cortar`
    (bloco de música com faixa e sem pedido: fica só a música) e senão mantém o texto (nunca silêncio)."""
    if not texto.strip() or not acima_da_tolerancia(estimar_duracao_s(texto, wpm), orcamento):
        return texto, "nenhum"
    curto = encurtar_por_frases(texto, palavras_max(orcamento, wpm, contar_pausas(texto)), preservar,
                                manter=manter, manter_ultima=manter_ultima)
    if curto is not None:
        return curto, "encurtada"
    return ("", "cortada") if pode_cortar else (texto, "acima_do_teto")


def encurtar_pela_medida(texto: str, orcamento: OrcamentoFala, medida_s: float, *, preservar: Iterable[str] = (),
                         manter: Callable[[str], bool] | None = None, manter_ultima: bool = False) -> str | None:
    """Encurtamento depois do TTS: o ritmo é o do próprio áudio medido (melhor previsão para a mesma voz e
    o mesmo texto). None quando nada cabe ou o áudio não dá um ritmo plausível."""
    pausas = contar_pausas(texto)
    fala_s = medida_s - pausas * settings.fala_pausa_explicita_s
    if fala_s <= 0:
        return None
    wpm_medido = palavras_faladas(texto) / fala_s * 60
    if wpm_medido <= 0:
        return None
    curto = encurtar_por_frases(texto, palavras_max(orcamento, wpm_medido, pausas), preservar, manter=manter,
                                manter_ultima=manter_ultima)
    return curto if curto is not None and curto != texto.strip() else None
