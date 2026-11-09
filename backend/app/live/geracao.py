"""Geração da fala do ao vivo (F3, passo 5): LLM, reescrita única e encurtamento antes do TTS (F2).

`gerar_fala(ctx, prompt, portas)` faz o que app/live/router.py::gerar_proxima_fala fazia entre o prompt e o
TTS, sem mudar a regra: uma chamada ao LLM (texto ou diálogo multivoz), no máximo uma reescrita com todos os
motivos juntos (repetição, duração estimada acima do orçamento — momento A —, redação de notícia e, desde a
F3, as checagens pós-geração da fase "pre") e o encurtamento por frases pela estimativa (momento B). Nunca uma
terceira chamada. O TTS (momento C), os registros e a resposta continuam no router.
"""

import dataclasses
import json
import logging
import re
from typing import Callable

from pydantic import BaseModel

from app.config.settings import settings
from app.live.formato import contar_palavras
from app.live.orcamento import (
    OrcamentoFala,
    acima_da_tolerancia,
    ajustar_ao_orcamento,
    cortar_linhas_dialogo,
    estimar_duracao_s,
)
from app.live.portas import PortasEmissao
from app.live.prompt_emissao import MotivosRevisao, PromptEmissao, prompt_revisao
from app.live.prompts import _CATEGORIAS_NOTICIA_LIKE
from app.llm.json_utils import extrair_json
from app.news.validacao import frase_proibida_em, tem_atribuicao
from app.util.texto import sem_acento as _sem_acento

logger = logging.getLogger("radialista.live")


class FalaItem(BaseModel):
    radio_config_id: int
    nome_locutor: str
    voz_id: str | None
    texto: str


_MARKDOWN_ENFASE = re.compile(r"(\*\*|\*|__|_|`)")
_ESPACO_ANTES_PONTUACAO = re.compile(r"\s+([,.;:!?])")
_ESPACOS_REPETIDOS = re.compile(r"[ \t]{2,}")
_DIGITO_SOLTO = re.compile(r"\d")


def _avisar_digito_solto(texto: str) -> None:
    """So' loga (nao reescreve) quando a fala gerada pelo LLM ainda tem algarismo -- o prompt
    instrui "escreva todo numero por extenso" (ver app.numeros.numero_por_extenso), mas isso e'
    so' uma instrucao de prompt, sem nenhum enforcement de codigo (diferente do texto de
    patrocinador, que roda substituir_valores_monetarios sempre, porque nunca passa pelo LLM).
    O sintetizador le algarismo errado em portugues com frequencia -- sem alerta aqui, um desvio
    do LLM so' aparece como reclamacao de "locucao estranha" depois, sem pista de onde nem
    quando. Nao reescreve automaticamente: o padrao de "e" entre grupos de numero por extenso
    (ver docstring de numero_por_extenso) muda dependendo do contexto gramatical da frase ao
    redor, um reescrita cega podia trocar um numero certo por um estranho.
    """
    if _DIGITO_SOLTO.search(texto):
        logger.warning("Fala gerada pelo LLM ainda tem algarismo (deveria estar por extenso): %r", texto)


def _limpar_fala(fala: str) -> str:
    """Remove artefatos que o LLM às vezes deixa escapar (aspas envolvendo a fala
    inteira, ênfase em markdown, espaço solto antes de pontuação) antes de mandar
    pro TTS -- o prompt pede pra não usar essas coisas, mas nada garantia isso.
    """
    texto = fala.strip()
    if len(texto) >= 2 and texto[0] in "\"'" and texto[-1] == texto[0]:
        texto = texto[1:-1].strip()
    texto = _MARKDOWN_ENFASE.sub("", texto)
    texto = _ESPACO_ANTES_PONTUACAO.sub(r"\1", texto)
    texto = _ESPACOS_REPETIDOS.sub(" ", texto)
    texto = texto.strip()
    _avisar_digito_solto(texto)
    return texto


# Sobreposicao de palavras (Jaccard) a partir da qual duas falas do mesmo tipo de bloco sao
# tratadas como repeticao. Falas muito curtas (menos que isso de palavras) nao entram na
# checagem -- sobreposicao alta em frase curta e normal, nao indica repeticao.
_LIMIAR_SIMILARIDADE_REPETICAO = 0.6
_MIN_PALAVRAS_SIMILARIDADE = 5

_PONTUACAO_RE = re.compile(r"[^\w\s]")


def _palavras_normalizadas(texto: str) -> set[str]:
    sem_acento = _sem_acento(texto.lower())
    sem_pontuacao = _PONTUACAO_RE.sub(" ", sem_acento)
    return {p for p in sem_pontuacao.split() if p}


def _fala_semelhante_no_historico(fala: str, historico_falas: list[str]) -> str | None:
    """Rede de seguranca em runtime: mesmo com as instrucoes de variacao no prompt, o LLM as
    vezes ainda produz uma fala quase igual a uma de varios blocos atras (janela enviada ao
    prompt so cobre as ultimas falas). Compara por sobreposicao de palavras contra o historico
    da sessao pro mesmo tipo de bloco; devolve a fala anterior que colidiu (pra citar no retry),
    ou None se nao achou repeticao.
    """
    palavras_fala = _palavras_normalizadas(fala)
    if len(palavras_fala) < _MIN_PALAVRAS_SIMILARIDADE:
        return None
    for anterior in historico_falas:
        palavras_anterior = _palavras_normalizadas(anterior)
        if len(palavras_anterior) < _MIN_PALAVRAS_SIMILARIDADE:
            continue
        uniao = palavras_fala | palavras_anterior
        if not uniao:
            continue
        similaridade = len(palavras_fala & palavras_anterior) / len(uniao)
        if similaridade >= _LIMIAR_SIMILARIDADE_REPETICAO:
            return anterior
    return None


_TAG_BLOCO_MUSICAS = re.compile(r"\[BLOCO_MUSICAS:\s*(\d)\]\s*$")


def _extrair_quantidade_musicas(fala: str) -> tuple[str, int]:
    """Le a tag opcional que o LLM deixa no fim da fala pra emendar mais musicas seguidas."""
    match = _TAG_BLOCO_MUSICAS.search(fala)
    if not match:
        return fala, 1
    quantidade = max(1, min(3, int(match.group(1))))
    return _TAG_BLOCO_MUSICAS.sub("", fala).rstrip(), quantidade


def _termos_preservados(pedidos: tuple, musicas: list) -> list[str]:
    """Nome do ouvinte e titulo confirmado: frases com eles nunca saem no encurtamento."""
    termos = [p.nome for p in pedidos if p is not None and (p.nome or "").strip()]
    return termos + [m.titulo for m in musicas if m.titulo]


def _linhas_que_cabem(falas_bloco: list[FalaItem], duracoes: list[float], orcamento: OrcamentoFala,
                      preservar: list[str], gatilho) -> int:
    """Quantas linhas do dialogo ficam: todas, salvo orcamento aplicado com o total (linhas + pausas entre
    elas, como o player toca) acima do `gatilho`; ai' retira linhas do fim ate' caber."""
    pausa = settings.fala_pausa_entre_linhas_s
    total = sum(duracoes) + pausa * max(0, len(duracoes) - 1)
    if not orcamento.aplicar or not gatilho(total, orcamento):
        return len(falas_bloco)
    return cortar_linhas_dialogo([f.texto for f in falas_bloco], duracoes, orcamento.max_s, pausa, preservar)


# Reserva quando o diálogo multivoz não volta em JSON válido: não trava o ao vivo.
_FALA_RESERVA_MULTIVOZ = "Seguimos no ar, ja volto com mais uma novidade."


@dataclasses.dataclass
class FalaGerada:
    falas_bloco: list[FalaItem]
    fala: str
    quantidade: int
    ajuste: str
    preservar: list[str]
    manter_frase: Callable[[str], bool] | None
    manter_ultima: bool
    pode_cortar: bool
    revisada: bool = False


def _gerar_falas_bloco(ctx, mensagem: str, system: str, portas: PortasEmissao) -> tuple[list[FalaItem], str]:
    if not ctx.multi_voz:
        return [], _limpar_fala(portas.gerar_resposta(system, mensagem))

    resposta_llm = portas.gerar_dialogo_multivoz(system, mensagem)
    try:
        linhas_dialogo = list((extrair_json(resposta_llm) if resposta_llm else {}).get("linhas") or [])
    except (json.JSONDecodeError, TypeError, AttributeError, ValueError):
        logger.warning("Resposta de dialogo multi-voz invalida: programa_id=%s", ctx.programa.id)
        linhas_dialogo = []

    roster_por_nome = {_sem_acento(p.radialista.nome_locutor.lower()): p for p in ctx.roster}
    falas: list[FalaItem] = []
    for linha in linhas_dialogo:
        texto_linha = _limpar_fala(str(linha.get("texto") or ""))
        if not texto_linha:
            continue
        participante = roster_por_nome.get(_sem_acento(str(linha.get("locutor") or "").lower()), ctx.roster[0])
        falas.append(FalaItem(
            radio_config_id=participante.radialista.id,
            nome_locutor=participante.radialista.nome_locutor,
            voz_id=participante.radialista.voz_id,
            texto=texto_linha,
        ))
    if falas:
        return falas, " ".join(item.texto for item in falas)
    # LLM nao retornou dialogo em JSON valido -- nao trava o ao vivo, segue com uma fala generica.
    return [], _FALA_RESERVA_MULTIVOZ


def gerar_fala(ctx, prompt: PromptEmissao, portas: PortasEmissao,
               checar_pre: Callable[[str], list[str]] | None = None) -> FalaGerada:
    """Gera a fala do bloco. `checar_pre(fala)` devolve instruções de reescrita das checagens pós-geração da
    fase "pre" (app.live.validacao_fala); elas entram como mais um motivo da MESMA reescrita única."""
    programa, tipo, categoria = ctx.programa, ctx.tipo, ctx.categoria
    orcamento, wpm_fala, limite_palavras = ctx.orcamento, ctx.wpm_fala, ctx.limite_palavras

    falas_bloco, fala = _gerar_falas_bloco(ctx, prompt.mensagem, prompt.system, portas)
    excedeu_orcamento = limite_palavras is not None and contar_palavras(fala) > limite_palavras
    # Momento A (F2): estimativa no ritmo calibrado da voz acima de maximo + tolerancia entra como mais um
    # motivo da MESMA reescrita unica -- nunca uma terceira chamada.
    estimada_inicial = estimar_duracao_s(fala, wpm_fala)
    excedeu_duracao = acima_da_tolerancia(estimada_inicial, orcamento)
    pauta, pesquisa = ctx.jornalismo.pauta, ctx.jornalismo.pesquisa
    # Atribuição só é checada quando há UM fato central na pauta -- escalada lista várias manchetes.
    falta_atribuicao = (
        categoria in _CATEGORIAS_NOTICIA_LIKE
        and categoria != "escalada"
        and (pauta is not None or (pesquisa is not None and pesquisa.status == "ok"))
        and not tem_atribuicao(fala)
    )
    motivos = MotivosRevisao(
        # Rede de seguranca: fala parecida com uma recente do mesmo tipo de bloco nesta sessao.
        fala_parecida=_fala_semelhante_no_historico(fala, list(ctx.memoria.falas_categoria)),
        excedeu_duracao=excedeu_duracao,
        estimada_s=estimada_inicial,
        revisar_orcamento=excedeu_orcamento or excedeu_duracao,
        # Locutor narrando a propria regra ("sem especular") em vez de noticiar.
        frase_proibida=frase_proibida_em(fala) if categoria in _CATEGORIAS_NOTICIA_LIKE else None,
        falta_atribuicao=falta_atribuicao,
        instrucoes_extras=tuple(checar_pre(fala)) if checar_pre is not None else (),
    )
    fala_ajuste = "nenhum"
    if motivos.algum:
        logger.info(
            "Revisando fala por repetição, duração ou redação de notícia: programa_id=%s tipo=%s", programa.id, tipo
        )
        if motivos.revisar_orcamento:
            fala_ajuste = "reescrita"
            if excedeu_duracao:
                logger.info("live_fala_revisada motivo=duracao request_id=%s programa_id=%s tipo=%s estimada_s=%s "
                            "max_s=%s wpm=%s", ctx.request_id, programa.id, tipo, round(estimada_inicial, 1),
                            orcamento.max_s, round(wpm_fala))
        if motivos.instrucoes_extras:
            logger.info("live_fala_revisada motivo=validacao request_id=%s programa_id=%s tipo=%s violacoes=%s",
                        ctx.request_id, programa.id, tipo, len(motivos.instrucoes_extras))
        falas_bloco, fala = _gerar_falas_bloco(ctx, prompt.mensagem, prompt_revisao(ctx, prompt, fala, motivos),
                                               portas)
        if limite_palavras is not None and contar_palavras(fala) > limite_palavras:
            logger.warning("live_orcamento_excedido programa_id=%s tipo=%s palavras=%s limite=%s",
                           programa.id, tipo, contar_palavras(fala), limite_palavras)
        if categoria in _CATEGORIAS_NOTICIA_LIKE and frase_proibida_em(fala):
            logger.warning("live_noticia_frase_proibida_apos_retry programa_id=%s tipo=%s", programa.id, tipo)
        if falta_atribuicao and not tem_atribuicao(fala):
            logger.warning("live_noticia_sem_atribuicao_apos_retry programa_id=%s tipo=%s", programa.id, tipo)

    quantidade = 1
    if categoria == "musica":
        fala, quantidade = _extrair_quantidade_musicas(fala)
        if ctx.formato_musical or ctx.tempo.plano is not None:
            quantidade = 1

    # Momento B (F2): depois da reescrita unica, se a estimativa ainda passa de maximo + tolerancia, encurta
    # por frases (extrativo, sem LLM) preservando o nome do ouvinte, a faixa confirmada, a atribuicao da
    # noticia e a despedida. Sem frase que caiba, so' o bloco de musica com faixa e sem pedido perde a fala
    # (fica so' a musica, regra 8); qualquer outro mantem o texto -- nunca silencio.
    confirmada = ctx.musica.confirmada
    pedido_musica = ctx.participacao.pedido_musica
    preservar = _termos_preservados((pedido_musica, ctx.participacao.pedido_ouvinte),
                                    [confirmada] if confirmada is not None else [])
    manter_frase = tem_atribuicao if categoria in _CATEGORIAS_NOTICIA_LIKE else None
    manter_ultima = categoria == "encerramento"
    pode_cortar = categoria == "musica" and confirmada is not None and pedido_musica is None
    if falas_bloco:
        ficam = _linhas_que_cabem(falas_bloco, [estimar_duracao_s(f.texto, wpm_fala) for f in falas_bloco],
                                  orcamento, preservar, acima_da_tolerancia)
        if ficam < len(falas_bloco):
            falas_bloco = falas_bloco[:ficam]
            fala, fala_ajuste = " ".join(item.texto for item in falas_bloco), "encurtada"
    else:
        fala, ajuste_b = ajustar_ao_orcamento(fala, orcamento, wpm_fala, preservar=preservar, manter=manter_frase,
                                              manter_ultima=manter_ultima, pode_cortar=pode_cortar)
        if ajuste_b != "nenhum":
            fala_ajuste = ajuste_b
            logger.info("live_fala_ajustada request_id=%s programa_id=%s tipo=%s ajuste=%s momento=estimativa",
                        ctx.request_id, programa.id, tipo, ajuste_b)
    return FalaGerada(falas_bloco=falas_bloco, fala=fala, quantidade=quantidade, ajuste=fala_ajuste,
                      preservar=preservar, manter_frase=manter_frase, manter_ultima=manter_ultima,
                      pode_cortar=pode_cortar, revisada=motivos.algum)
