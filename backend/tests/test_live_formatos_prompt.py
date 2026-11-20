"""Seção do formato no prompt do ao vivo (F6, commit 5 da auditoria §7; §6.9 e D10).

`_formato(ctx)` entra em `montar_prompt` só quando o formato não é `padrao`: programa, nome do formato, promessa e
público (quando preenchido), a linha "promessa prevalece", a política de participação, os temas que exigem revisão
humana e, nos blocos de retomada, identificação, retorno e quadro, a frase de reorientação. O `padrao` não ganha
nenhuma linha (os 31 goldens dele ficam idênticos).

`contexto(...)` monta um `ContextoEmissao` à mão (como tests/test_live_validacao_fala.py) e também serve ao
snapshot das instruções (tests/test_live_formatos_snapshot.py).
"""

import dataclasses
import datetime
from types import SimpleNamespace

import pytest

from app.live import formatos as f
from app.live.contexto import (
    Chamadas,
    ContextoEmissao,
    EstadoMusical,
    Jornalismo,
    Memoria,
    MusicaRef,
    Participacao,
    PedidoRef,
    Tempo,
    Variacoes,
)
from app.live.orcamento import orcamento_para, palavras_max
from app.live.prompt_emissao import _formato, montar_prompt

AGORA = datetime.datetime(2026, 8, 10, 15, 0, tzinfo=datetime.timezone.utc)
QUADRO = "Cantinho da Casa"
FAIXA = MusicaRef("Rua das Acácias", "Duo Estrada Velha", "v1")


def contexto(formato, tipo: str, *, primeira: bool = False, categoria: str | None = None, quadro: bool = False,
             pedido: bool = False, plano=None, ultima_categoria: str | None = None, publico: str = "",
             wpm: float = 150.0) -> ContextoEmissao:
    """Contexto mínimo e determinístico de um bloco (sem banco, Redis, sorteio nem rede)."""
    formato = f.resolver_formato(formato)
    categoria = categoria or ("comentario" if quadro else tipo)
    quadros = {QUADRO: ["organização de gavetas", "sobras na cozinha"]}
    programa = SimpleNamespace(id=1, nome="Tarde Serena", quadros_fixos=quadros, publico_alvo=publico,
                               estrutura_blocos=[], perfil_programacao=formato.id, tom="acolhedor")
    pedido_ref = PedidoRef(id=7, tipo="musica", nome="Joana", natureza="pedido_musica",
                           texto="Pediu Rua das Acácias para a mãe.", texto_autorizado="Pediu Rua das Acácias para a mãe.",
                           musica_query="Rua das Acácias", estado="selecionado", token="t") if pedido else None
    orcamento = orcamento_para(formato, tipo, primeira, quadro=quadro,
                               teto_relogio_s=plano.orcamento_s[1] if plano is not None else None,
                               minimo_relogio_s=plano.orcamento_s[0] if plano is not None else None)
    return ContextoEmissao(
        request_id="t", account=SimpleNamespace(nome_radio="Rádio Serra Clara", cidade="Vale Verde"),
        radialista=SimpleNamespace(nome_locutor="Caio Ventania", timezone="America/Sao_Paulo"),
        programa=programa, tipo=QUADRO if quadro else tipo, categoria=categoria, primeira_fala=primeira,
        total_falas=0 if primeira else 3, passos_roteiro=1, formato_musical=formato.comportamento.ciclo == "musical",
        multi_voz=False, roster=(), roteiro=formato.roteiro_padrao,
        categorias_roteiro=tuple(None for _ in formato.roteiro_padrao),
        tempo=Tempo(agora_local=AGORA, instante=AGORA, origem_instante="agora", plano=plano, preset_relogio=None,
                    inicio_previsto_aceito=False),
        musica=EstadoMusical(tocou=(), confirmada=FAIXA if categoria == "musica" else None, resolvido=True),
        participacao=Participacao(novo_atendimento=pedido, pedido_musica=pedido_ref, pedido_ouvinte=None,
                                  ouvinte_recorrente=None, ouvinte_recorrente_dias=None, pedido_recente=None),
        chamadas=Chamadas(fio_condutor=None),
        memoria=Memoria(historico=(), historico_prompt="Programa acabou de entrar no ar.",
                        ultima_categoria=ultima_categoria),
        variacoes=Variacoes(verbo_identificacao="aqui é a", quadro_fixo="organização de gavetas" if quadro else None),
        jornalismo=Jornalismo(), orcamento=orcamento, wpm_fala=wpm, categoria_voz="padrao",
        limite_palavras=palavras_max(orcamento, wpm) if orcamento.aplicar else None, prompt_base="",
        modelo_com_tags=False, formato=formato,
    )


def linhas_do_formato_no_system(ctx: ContextoEmissao) -> list[str]:
    """As linhas do formato no system: a seção `_formato` e a direção do formato (cabeçalho do catálogo)."""
    secao = set(_formato(ctx))
    cabecalho = ctx.formato.direcao_cabecalho
    return [linha for linha in montar_prompt(ctx).system.split("\n")
            if linha in secao or (cabecalho and linha.startswith(cabecalho))]


MUSICAL = f.FORMATOS["musical_adulto"]
PREVALECE = "A promessa do formato prevalece sobre o perfil do horário."
REORIENTA = "Reoriente quem acabou de chegar: nome do programa e da rádio em uma frase."


# ---------------------------------------------------------------------------------------------------------
# linhas_do_formato (puro, no catálogo)
# ---------------------------------------------------------------------------------------------------------

def test_linhas_do_musical_na_retomada():
    linhas = f.linhas_do_formato(MUSICAL, programa="Tarde Serena", tipo="retomada", primeira=False)
    assert linhas == [
        "Programa Tarde Serena, formato Musical adulto. Promessa: Acompanhar com curadoria.",
        PREVALECE,
        "Participação neste formato: Pedido real anunciado no bloco de música; sem pedido, nada: a música fala.",
        "Temas que exigem revisão humana neste formato: notícia grave ou tragédia, saúde e medicamento, política, "
        "religião; sem conteúdo aprovado, não trate deles.",
        REORIENTA,
    ]


@pytest.mark.parametrize("tipo, primeira, quadro, retorno, reorienta", [
    ("retomada", False, False, False, True),
    ("abertura", False, False, False, True),      # abertura fora da largada é retomada
    ("abertura", True, False, False, False),
    ("identificacao", False, False, False, True),
    ("Identificação", False, False, False, True),
    ("chamada_ouvinte", False, False, True, True),   # retorno do intervalo
    ("chamada_ouvinte", False, False, False, False),
    ("comentario", False, True, False, True),         # quadro fixo
    ("Quadro da Receita", False, False, False, False),  # o nome não faz quadro (§6.3)
    ("musica", False, False, False, False),
    ("encerramento", False, False, False, False),
])
def test_reorientacao_so_nos_papeis_do_catalogo(tipo, primeira, quadro, retorno, reorienta):
    linhas = f.linhas_do_formato(MUSICAL, programa="Tarde Serena", tipo=tipo, primeira=primeira, quadro=quadro,
                                 retorno=retorno)
    assert (REORIENTA in linhas) is reorienta
    assert set(f.PAPEIS_REORIENTACAO) == {"retomada", "identificacao", "retorno", "quadro"}


def test_publico_so_quando_preenchido():
    sem = f.linhas_do_formato(MUSICAL, programa="Tarde Serena", tipo="musica", primeira=False, publico="  ")
    com = f.linhas_do_formato(MUSICAL, programa="Tarde Serena", tipo="musica", primeira=False,
                              publico="adultos que trabalham em casa\nà tarde")
    assert "Público" not in sem[0]
    assert com[0] == ("Programa Tarde Serena, formato Musical adulto. Promessa: Acompanhar com curadoria. "
                      "Público: adultos que trabalham em casa à tarde.")
    assert com[1:] == sem[1:]


@pytest.mark.parametrize("valor", ["padrao", "", None, "hits"])
def test_padrao_nao_tem_secao(valor):
    assert f.linhas_do_formato(valor, programa="Tarde Viva", tipo="retomada", primeira=False) == []


def test_alias_e_canonico_dao_a_mesma_secao():
    kwargs = dict(programa="Tarde Serena", tipo="identificacao", primeira=False)
    assert f.linhas_do_formato("musical_companhia", **kwargs) == f.linhas_do_formato("musical_adulto", **kwargs)


# ---------------------------------------------------------------------------------------------------------
# _formato(ctx) em montar_prompt
# ---------------------------------------------------------------------------------------------------------

def test_secao_aparece_no_musical_antes_da_direcao():
    ctx = contexto(MUSICAL, "retomada")
    linhas = montar_prompt(ctx).system.split("\n")
    secao = _formato(ctx)
    assert secao and secao[1] == PREVALECE and secao[-1] == REORIENTA
    inicio = linhas.index(secao[0])
    assert linhas[inicio:inicio + len(secao)] == secao
    assert linhas[inicio + len(secao)].startswith(MUSICAL.direcao_cabecalho)


@pytest.mark.parametrize("tipo, quadro", [("retomada", False), ("comentario", False), ("musica", False),
                                          ("abertura", False), ("comentario", True)])
def test_secao_nunca_aparece_no_padrao(tipo, quadro):
    ctx = contexto("padrao", tipo, quadro=quadro)
    assert _formato(ctx) == []
    system = montar_prompt(ctx).system
    assert PREVALECE not in system and "Participação neste formato" not in system
    assert "Temas que exigem revisão humana" not in system and REORIENTA not in system


def test_publico_do_programa_entra_na_secao():
    ctx = contexto(MUSICAL, "musica", publico="quem trabalha em casa")
    assert _formato(ctx)[0].endswith("Público: quem trabalha em casa.")


def test_retorno_pelo_intervalo_anterior_ou_pela_etapa_do_relogio():
    assert REORIENTA in _formato(contexto(MUSICAL, "chamada_ouvinte", ultima_categoria="patrocinador"))
    assert REORIENTA not in _formato(contexto(MUSICAL, "chamada_ouvinte", ultima_categoria="musica"))
    etapa = SimpleNamespace(tipo_efetivo="retorno")
    plano = SimpleNamespace(etapa=etapa, orcamento_s=(10, 20), instrucao=None, instante=AGORA, palavras_max=40,
                            acao="fala")
    ctx = dataclasses.replace(contexto(MUSICAL, "chamada_ouvinte", ultima_categoria="musica"),
                              tempo=Tempo(agora_local=AGORA, instante=AGORA, origem_instante="agora", plano=plano,
                                          preset_relogio="A", inicio_previsto_aceito=True))
    assert REORIENTA in _formato(ctx)


def test_secao_sem_efeito_colateral_e_identica_em_chamadas_repetidas():
    ctx = contexto(MUSICAL, "identificacao")
    assert montar_prompt(ctx) == montar_prompt(ctx)
    assert linhas_do_formato_no_system(ctx) == [*_formato(ctx), linhas_do_formato_no_system(ctx)[-1]]


# ---------------------------------------------------------------------------------------------------------
# _duracao: direção do formato para todo formato com orçamento aplicado, com e sem relógio (commit 6)
# ---------------------------------------------------------------------------------------------------------

def _plano_link_de_a(formato):
    from zoneinfo import ZoneInfo

    from app.live import relogio as r

    programa = SimpleNamespace(id=1, horario_inicio=datetime.time(14, 0), horario_fim=datetime.time(15, 0),
                               dias_semana=[], data_especifica=None, feriados_municipais=[], relogio_hora=None)
    instante = datetime.datetime(2026, 11, 10, 14, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
    pecas = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),))
    return r.planejar(programa, r.PRESETS["A"], "America/Sao_Paulo", instante, formato=f.resolver_formato(formato),
                      ultima_categoria="musica", ja_encerrou=False, executadas={"0:0:fala:abertura"}, pecas=pecas)


@pytest.mark.parametrize("formato", ["popular_sertanejo", "variedades_leves"])
def test_duracao_dos_novos_usa_a_direcao_do_formato_com_e_sem_relogio(formato):
    from app.live.promessas import EventoAgendado
    from scripts.simulacao.dubles import META_BLOCO_RE

    catalogo = f.FORMATOS[formato]
    sem = montar_prompt(contexto(formato, "comentario")).system
    assert "A duração deve seguir a meta específica deste bloco." in sem and "4 a 6 frases" not in sem
    direcao = next(linha for linha in sem.split("\n") if linha.startswith(catalogo.direcao_cabecalho))
    unidade = catalogo.unidades["comentario"]
    assert META_BLOCO_RE.search(direcao).groups()[:2] == (str(unidade.min_s), str(unidade.max_s))

    plano = _plano_link_de_a(formato)
    com = montar_prompt(contexto(formato, plano.tipo_bloco, plano=plano)).system
    direcao = next(linha for linha in com.split("\n") if linha.startswith(catalogo.direcao_cabecalho))
    assert META_BLOCO_RE.search(direcao).groups()[:2] == tuple(str(v) for v in plano.orcamento_s)
    assert "A duração deve seguir a meta deste bloco. Meta:" not in com  # a instrução genérica do relógio sai

    agenda = (EventoAgendado(chave="roteiro:5", tipo="participacao", rotulo="Participação", posicao=5),)
    ctx = dataclasses.replace(contexto(formato, "comentario"),
                              chamadas=Chamadas(fio_condutor=None, agenda=agenda, posicao=3))
    linhas = montar_prompt(ctx).system.split("\n")
    indice = next(i for i, linha in enumerate(linhas) if linha.startswith(catalogo.direcao_cabecalho))
    assert linhas[indice + 1].startswith("Agenda confirmada adiante (só isto pode ser chamado como próximo): "
                                         "Participação")


def test_secao_dos_novos_no_prompt():
    popular = _formato(contexto("popular_sertanejo", "chamada_ouvinte", ultima_categoria="patrocinador"))
    assert popular[0] == ("Programa Tarde Serena, formato Popular/sertanejo. Promessa: Companhia e reconhecimento.")
    assert REORIENTA in popular  # retorno do intervalo
    variedades = _formato(contexto("variedades_leves", "comentario", quadro=True))
    assert variedades[0].startswith("Programa Tarde Serena, formato Variedades leves. Promessa: Ajudar na vida")
    assert REORIENTA in variedades  # quadro fixo
    assert REORIENTA not in _formato(contexto("variedades_leves", "comentario"))
