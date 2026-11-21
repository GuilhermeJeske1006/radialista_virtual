"""Caracterização do formato antes do catálogo (F6, C2 a C5 da auditoria §8).

Gravada no código anterior ao catálogo de formatos (`app.live.formatos`): o booleano `musical_companhia` e as
constantes de `app.live.formato` decidem roteiro, relógio, orçamento e a linha da estrutura no prompt. O commit
que troca o booleano pelo catálogo não pode mudar uma linha destes retratos.

- C2: `_tipo_proximo_bloco` (router) e `tipo_na_posicao` (roteiro puro) nas posições 0 a 20, e `roteiro_base`
  das vinhetas;
- C3: `planejar` nos presets A, B e C, padrão e musical, a cada 7 s da hora;
- C4: `orcamento_para` para `padrao` e `musical_companhia` em todos os tipos, primeira ou não, com e sem teto;
- C5: `montar_system_prompt` do musical com `ia_pode_adicionar_blocos=True` segue a estrutura estritamente.

Regravar só com `ATUALIZAR_GOLDEN=1` e diff revisado (o mesmo padrão dos goldens da F3).
"""

import dataclasses
import datetime
import json
import os
import pathlib
import random
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.live import relogio as r

DIR_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "caracterizacao_formatos"
ATUALIZAR = os.environ.get("ATUALIZAR_GOLDEN") == "1"
SP = ZoneInfo("America/Sao_Paulo")
PERFIS = ("padrao", "musical_companhia")


def _conferir(nome: str, retrato) -> None:
    retrato = json.loads(json.dumps(retrato, ensure_ascii=False))
    caminho = DIR_GOLDEN / f"{nome}.json"
    if ATUALIZAR or not caminho.exists():
        if not ATUALIZAR:
            pytest.fail(f"golden ausente: {caminho.name} (rode com ATUALIZAR_GOLDEN=1)")
        DIR_GOLDEN.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(retrato, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return
    assert retrato == json.loads(caminho.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------------
# C2: roteiro sem relógio
# ---------------------------------------------------------------------------------------------------------

ESTRUTURAS = {
    "vazia": [],
    "personalizada": ["musica", "comentario", "Música Sertaneja", "chamada_ouvinte", "noticia"],
    "abertura_e_encerramento_no_meio": ["musica", "abertura", "comentario", "encerramento", "musica", "noticia"],
    "vinheta_e_patrocinador": ["vinheta:3", "abertura", "musica", "patrocinador:7", "abertura", "comentario",
                               "identificacao", "retomada"],
    "quadro_customizado": ["Abertura", "musica", "Quadro da Receita", "musica", "chamada_ouvinte", "  "],
}
ULTIMAS = (None, "musica", "patrocinador", "comentario")
POSICOES = range(21)


def _programa_roteiro(estrutura, perfil, ia):
    return SimpleNamespace(id=1, estrutura_blocos=list(estrutura), perfil_programacao=perfil,
                           ia_pode_adicionar_blocos=ia, quadros_fixos={})


@pytest.fixture
def _sem_llm_de_categoria(monkeypatch):
    # Bloco customizado sem prefixo conhecido ("Quadro da Receita") iria ao LLM de classificação.
    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", lambda tipo: "comentario")


def test_c2_tipo_proximo_bloco_do_router(monkeypatch, _sem_llm_de_categoria):
    from app.live.router import _tipo_proximo_bloco

    retrato = {}
    for nome, estrutura in ESTRUTURAS.items():
        for perfil in PERFIS:
            for ia in (False, True):
                for ultima in ULTIMAS:
                    # O comentário extra de ia_pode_adicionar_blocos sorteia: semente fixa por combinação.
                    rng = random.Random(f"{nome}:{perfil}:{ia}:{ultima}")
                    sorteios: list[float] = []

                    def sortear(rng=rng, sorteios=sorteios):
                        valor = rng.random()
                        sorteios.append(round(valor, 6))
                        return valor

                    monkeypatch.setattr("app.live.router.random.random", sortear)
                    programa = _programa_roteiro(estrutura, perfil, ia)
                    tipos = [_tipo_proximo_bloco(programa, posicao, ultima) for posicao in POSICOES]
                    retrato[f"{nome}|{perfil}|ia={int(ia)}|ultima={ultima}"] = {"tipos": tipos,
                                                                                "sorteios": len(sorteios)}
    _conferir("roteiro_router", retrato)


def test_c2_tipo_na_posicao_do_roteiro(monkeypatch, _sem_llm_de_categoria):
    from app.live.roteiro import tipo_na_posicao
    from app.live.router import _categoria_bloco

    def proibido(*_a, **_k):
        raise AssertionError("tipo_na_posicao não sorteia")

    monkeypatch.setattr(random, "random", proibido)
    retrato = {}
    for nome, estrutura in ESTRUTURAS.items():
        for perfil in PERFIS:
            for ia in (False, True):
                programa = _programa_roteiro(estrutura, perfil, ia)
                retrato[f"{nome}|{perfil}|ia={int(ia)}"] = [
                    tipo_na_posicao(programa, posicao, _categoria_bloco) for posicao in POSICOES]
    _conferir("roteiro_puro", retrato)


def test_c2_roteiro_base_das_vinhetas():
    from app.vinhetas.estrutura import roteiro_base

    retrato = {perfil: roteiro_base(SimpleNamespace(perfil_programacao=perfil)) for perfil in PERFIS}
    retrato["sem_campo"] = roteiro_base(SimpleNamespace())
    _conferir("roteiro_base_vinhetas", retrato)


# ---------------------------------------------------------------------------------------------------------
# C3: relógio
# ---------------------------------------------------------------------------------------------------------

PECAS = {
    "patrocinio": r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),), tem_fonte_noticia=True),
    "completo": r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0), r.Peca(6, 20.0)), vinheta_encerramento_s=3.0,
                                   vinhetas_passagem=(r.Peca(9, 6.0),), tem_fonte_noticia=True,
                                   quadros=("Quadro da Receita",)),
}
EXECUTADAS = {"nada": (), "abertura": ("0:0:fala:abertura",)}


def _programa_relogio():
    return SimpleNamespace(id=1, horario_inicio=datetime.time(14, 0), horario_fim=datetime.time(15, 0),
                           dias_semana=[], data_especifica=None, feriados_municipais=[], relogio_hora=None)


def _resumo_plano(plano) -> list | None:
    if plano is None:
        return None
    orcamento = list(plano.orcamento_s) if plano.orcamento_s is not None else None
    return [plano.acao, plano.tipo_bloco, orcamento, plano.palavras_max, _resumo_plano(plano.alternativa)]


def _planejar(preset, musical, pecas, executadas, segundo, **extra):
    instante = datetime.datetime(2026, 11, 10, 14, 0, tzinfo=SP) + datetime.timedelta(seconds=segundo)
    return r.planejar(_programa_relogio(), r.PRESETS[preset], "America/Sao_Paulo", instante, formato_musical=musical,
                      ultima_categoria="musica", ja_encerrou=False, executadas=set(EXECUTADAS[executadas]),
                      pecas=PECAS[pecas], **extra)


def grade_do_relogio(planejar=_planejar) -> dict:
    """(acao, tipo_bloco, orcamento_s, palavras_max) do plano e da alternativa a cada 7 s, guardando só as
    mudanças (segundo em que o retrato muda). `planejar` é trocável para o teste do formato (U7)."""
    retrato = {}
    for preset in ("A", "B", "C"):
        for musical in (False, True):
            for pecas in PECAS:
                for executadas in EXECUTADAS:
                    mudancas, anterior = [], object()
                    for segundo in range(0, 3620, 7):
                        atual = _resumo_plano(planejar(preset, musical, pecas, executadas, segundo))
                        if atual != anterior:
                            mudancas.append([segundo, atual])
                            anterior = atual
                    retrato[f"{preset}|{'musical' if musical else 'padrao'}|{pecas}|{executadas}"] = mudancas
    return retrato


def test_c3_planejar_nos_presets_a_cada_7_segundos():
    _conferir("relogio_planos", grade_do_relogio())


# ---------------------------------------------------------------------------------------------------------
# C4: orçamento
# ---------------------------------------------------------------------------------------------------------

TIPOS_ORCAMENTO = (
    "abertura", "Abertura", "retomada", "identificacao", "  Identificação ", "musica", "Música Sertaneja",
    "encerramento", "comentario", "noticia", "escalada", "servico", "chamada_ouvinte", "Quadro da Receita",
    "patrocinador", "vinheta:3", "",
)
TETOS = (("sem_teto", None, None), ("teto_4", 4, None), ("teto_14", 14, None), ("teto_35", 35, None),
         ("teto_14_min_6", 14, 6), ("teto_35_min_20", 35, 20))


def tabela_de_orcamento(perfis=PERFIS) -> dict:
    from app.live.orcamento import orcamento_para

    retrato = {}
    for perfil in perfis:
        for tipo in TIPOS_ORCAMENTO:
            for primeira in (False, True):
                for nome, teto, minimo in TETOS:
                    orcamento = orcamento_para(perfil, tipo, primeira, teto, minimo_relogio_s=minimo)
                    retrato[f"{perfil}|{tipo}|{int(primeira)}|{nome}"] = dataclasses.asdict(orcamento)
    return retrato


def test_c4_orcamento_para_tabela_completa():
    _conferir("orcamento_para", tabela_de_orcamento())


# ---------------------------------------------------------------------------------------------------------
# C5: estrutura de blocos no system prompt (também usado pelo WhatsApp)
# ---------------------------------------------------------------------------------------------------------

@pytest.fixture
def _sem_clima_real(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)


def _system(perfil, ia):
    from app.llm.prompt_builder import montar_system_prompt
    from app.models.account import Account
    from app.models.programa import Programa
    from app.models.radio_config import RadioConfig

    programa = Programa(nome="Tarde Serena", tom="calmo", topicos_permitidos=[], topicos_proibidos=[],
                        generos_musicais=[], musicas_permitidas=[], musicas_bloqueadas=[],
                        criterios_busca_musicas="", assuntos_ao_vivo=[], tipos_noticias=[], fontes_noticias=[],
                        pode_pesquisar=False, fontes_pesquisa=[], instrucoes_pesquisa="",
                        estrutura_blocos=["abertura", "musica", "identificacao"], ia_pode_adicionar_blocos=ia,
                        descricao="", perfil_programacao=perfil)
    return montar_system_prompt(Account(nome_radio="Rádio Serra Clara"),
                                RadioConfig(nome_locutor="Caio Ventania", personalidade="",
                                            timezone="America/Sao_Paulo"), programa)


@freeze_time("2026-08-10 15:00:00")
def test_c5_musical_com_ia_pode_adicionar_blocos_segue_estritamente(_sem_clima_real):
    musical = _system("musical_companhia", True)
    assert "Estrutura de blocos do programa (siga estritamente, nessa ordem, sem adicionar blocos extras): " \
           "abertura -> musica -> identificacao." in musical
    assert "fique livre pra inserir blocos extras" not in musical
    padrao = _system("padrao", True)
    assert "fique livre pra inserir blocos extras" in padrao and "siga estritamente" not in padrao
    assert "siga estritamente" in _system("padrao", False)
    assert "siga estritamente" in _system("musical_companhia", False)
