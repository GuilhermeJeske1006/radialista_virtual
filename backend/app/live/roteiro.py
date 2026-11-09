"""Decisão do bloco do ao vivo (F3): qual é o próximo bloco e se ele sai pronto (vinheta ou patrocinador).

Extraído de app/live/router.py::gerar_proxima_fala sem mudar a ordem das decisões: relógio da hora (F1) ou
estrutura de blocos, laço de vinhetas desativadas, patrocinador, notícia sem fonte que vira música e assunto
esgotado. As funções do router (classificação de bloco, relógio, banco) entram pelas portas
(app.live.portas), então este módulo não importa o router.
"""

import dataclasses
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.live.portas import PortasEmissao
from app.live.prompts import _CATEGORIAS_NOTICIA_LIKE
from app.live.relogio import ConfigRelogio, Plano

logger = logging.getLogger("radialista.live")

_PATROCINADOR_RE = re.compile(r"^patrocinador:(\d+)$")
_VINHETA_RE = re.compile(r"^vinheta:(\d+)$")

# Quantos minutos antes do horario_fim do programa a fala vira encerramento
# em vez de seguir o roteiro normal.
_LIMIAR_ENCERRAMENTO_MIN = 3


@dataclasses.dataclass(frozen=True)
class EntradaEmissao:
    """O que chega em POST /proxima, já com o programa, a voz e o ritmo resolvidos pelo router."""

    request_id: str
    db: Session
    account: Any
    radialista: Any
    programa: Any
    dados: Any                      # LiveProgramRequest
    total_falas: int
    formato_musical: bool
    voz_programa: Any
    ritmos_voz: Any                 # app.live.ritmo_voz.RitmosVoz
    cfg_relogio: ConfigRelogio


@dataclasses.dataclass(frozen=True)
class DecisaoBloco:
    tipo: str
    categoria: str
    plano: Plano | None
    preset_relogio: str | None
    inicio_previsto_aceito: bool
    primeira_fala: bool
    passos_roteiro: int
    ultima_categoria: str | None
    # "painel" (inicio_previsto aceito), "estimado" (painel antigo, cadeia no servidor) ou "agora".
    origem_instante: str = "agora"
    musica_relogio: Any = None      # MusicaEncontrada da etapa de música do relógio
    buscou_musica_relogio: bool = False
    assunto: Any = None             # AssuntoConversa do banco de assuntos (comentário)
    # Bloco pronto, sem LLM: o router serializa a resposta.
    vinheta: Any = None
    patrocinador: Any = None


def decidir_bloco(entrada: EntradaEmissao, portas: PortasEmissao) -> DecisaoBloco:
    db, account, radialista, programa = entrada.db, entrada.account, entrada.radialista, entrada.programa
    historico = entrada.dados.historico
    total_falas = entrada.total_falas
    ultima_categoria = portas.ultima_categoria_bloco(historico)
    ja_encerrou = any(linha.startswith("encerramento:") for linha in historico)
    # Relogio da hora (F1): com programa.relogio_hora, o tipo do bloco vem da etapa do relogio no horario
    # previsto de ir ao ar (dados.inicio_previsto), nao da posicao na estrutura_blocos.
    plano, inicio_previsto_aceito, preset_relogio, origem_instante = portas.planejar_relogio(
        db, account, radialista, programa, entrada.dados, formato_musical=entrada.formato_musical,
        ultima_categoria=ultima_categoria, ja_encerrou=ja_encerrou, cfg=entrada.cfg_relogio,
    )
    musica_relogio, buscou_musica_relogio = None, False
    if plano is not None:
        plano, musica_relogio, buscou_musica_relogio = portas.resolver_musica_do_relogio(
            db, radialista, programa, plano, account.atendimento_ouvinte_ativo,
        )
        tipo = plano.tipo_bloco
    else:
        perto_do_fim = portas.minutos_restantes(programa, radialista.timezone) <= _LIMIAR_ENCERRAMENTO_MIN
        if perto_do_fim and not ja_encerrou:
            # Estrutura do programa roda em loop ate' chegar perto do horario_fim -- daqui em diante, para o
            # loop e gera a fala de encerramento.
            tipo = "encerramento"
        else:
            tipo = portas.tipo_proximo_bloco(programa, total_falas, ultima_categoria)
    primeira_fala = plano.primeira if plano is not None else total_falas == 0
    comum = dict(plano=plano, preset_relogio=preset_relogio, inicio_previsto_aceito=inicio_previsto_aceito,
                 primeira_fala=primeira_fala, ultima_categoria=ultima_categoria, origem_instante=origem_instante)

    # Vinheta (tratada ANTES da categoria: "vinheta:12" nunca vai pra classificacao por LLM nem pro cache do
    # Redis). Conteudo fixo -- sem LLM. Vinheta desativada/sem conteudo pula pro proximo bloco do roteiro.
    passos_roteiro = 1
    while _VINHETA_RE.match(tipo):
        vinheta = portas.buscar_vinheta_ativa(db, account, tipo)
        texto_vinheta = ((vinheta.texto or "").strip() if vinheta is not None else "")
        if vinheta is not None and (vinheta.audio_path or texto_vinheta):
            return DecisaoBloco(tipo="vinheta", categoria="vinheta", passos_roteiro=passos_roteiro, vinheta=vinheta,
                                **comum)
        if plano is not None:
            tipo = "identificacao"  # peca do relogio indisponivel: identificacao curta no lugar
            break
        if passos_roteiro > len(programa.estrutura_blocos or []):
            tipo = "comentario"  # roteiro inteiro de vinhetas mortas -- nao trava o ao vivo
            break
        tipo = portas.tipo_proximo_bloco(programa, total_falas + passos_roteiro, ultima_categoria)
        passos_roteiro += 1

    if _PATROCINADOR_RE.match(tipo):
        patrocinador = portas.buscar_patrocinador_ativo(db, account, tipo)
        if patrocinador is not None:
            # Conteudo de patrocinador e fixo (contrato comercial) -- nunca passa pelo LLM.
            return DecisaoBloco(tipo="patrocinador", categoria="patrocinador", passos_roteiro=passos_roteiro,
                                patrocinador=patrocinador, **comum)
        tipo = "comentario"  # patrocinador excluido/desativado -- nao trava o ao vivo

    categoria = portas.categoria_bloco(tipo)
    if categoria in _CATEGORIAS_NOTICIA_LIKE and (
        getattr(programa, "dose_noticia", "jornalistica") == "nenhuma"
        or not (
            programa.pode_pesquisar or programa.tipos_noticias or programa.fontes_noticias
            or tipo in (programa.estrutura_blocos or [])
        )
    ):
        # Sem fonte de noticia configurada (ou dose_noticia="nenhuma"): nao arrisca fala vaga, toca musica.
        tipo = "musica"
        categoria = "musica"

    # Banco de assuntos: busca o proximo assunto ANTES de montar o resto do prompt, porque a cascata pode mudar
    # o tipo do bloco. So' vira musica quando o pipeline de assunto e' comprovadamente ativo pra este programa e
    # mesmo assim esgotou nesta sessao.
    assunto = None
    if categoria == "comentario":
        assunto = portas.proximo_assunto(db, programa)
        # Com relogio a etapa e' de fala: comentario livre em vez de virar musica fora do teto.
        if assunto is None and not programa.assuntos_ao_vivo and plano is None \
                and portas.pipeline_tem_estoque(db, programa.id):
            logger.warning("live_assunto_esgotado_vira_musica programa_id=%s", programa.id)
            tipo = "musica"
            categoria = "musica"

    return DecisaoBloco(tipo=tipo, categoria=categoria, passos_roteiro=passos_roteiro,
                        musica_relogio=musica_relogio, buscou_musica_relogio=buscou_musica_relogio, assunto=assunto,
                        **comum)
