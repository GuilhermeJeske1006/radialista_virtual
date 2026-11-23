"""Bancada de simulação de uma hora de programa (F0 do plano de melhoria de rádio).

Desenho em docs/melhoria-radio/f0/auditoria.md §5 e §6. O simulador passa pelo POST /proxima real;
só LLM, TTS, música, notícia e clima são dublês. Nenhum teste aqui compara as_run byte a byte:
as frentes seguintes mudam o comportamento de propósito, então os testes conferem invariantes e
métricas.
"""

import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

from anthropic.resources.messages import Messages as _Messages

from app.live.formato import contar_palavras, orcamento_fala

_MESSAGES_CREATE_ORIGINAL = _Messages.create  # antes do autouse _sem_api_anthropic do conftest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
DIR_PROGRAMAS = BACKEND / "tests" / "fixtures" / "programas"
PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")

# As 14 chaves que a skill avaliar-locucao lê de cada evento.
CHAVES_SKILL = (
    "inicio", "fim", "tipo", "formato", "texto", "duracao_prevista_s", "duracao_medida_s",
    "orcamento_s", "musica_anunciada", "musica_tocada", "promessas_abertas", "promessas_fechadas",
    "pedido_id", "pedido_estado",
)


# ---------------------------------------------------------------------------------------------
# Simulações compartilhadas: cada perfil roda uma vez por módulo (modo fake, padrões do CLI).
# ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def simulacoes(tmp_path_factory):
    from scripts.simular_hora import simular

    resultados = {}
    for perfil in PERFIS:
        saida = tmp_path_factory.mktemp(f"sim_{perfil}")
        inicio = time.perf_counter()
        resultado = simular(perfil, saida=saida)
        resultados[perfil] = {
            "resultado": resultado,
            "saida": saida,
            "parede_s": time.perf_counter() - inicio,
        }
    return resultados


def _falas(as_run):
    return [e for e in as_run["eventos"] if e["tipo"] == "fala"]


# ---------------------------------------------------------------------------------------------
# Unitários
# ---------------------------------------------------------------------------------------------

def test_relogios_somam_3600_e_sao_continuos():
    from scripts.simulacao.fixtures import carregar_relogio

    hard_times_esperados = {
        "A": [0, 1440, 3180, 3570],
        "B": [0, 900, 1080, 2460, 3480],
        "C": [0, 960, 2460, 3480],
    }
    for relogio_id, esperados in hard_times_esperados.items():
        relogio = carregar_relogio(relogio_id)
        assert relogio.id == relogio_id
        assert relogio.hipotese is True
        inicio = 0
        for evento in relogio.eventos:
            assert evento.inicio_s == inicio, f"{relogio_id}: lacuna ou sobreposição em {evento.rotulo}"
            assert evento.duracao_s > 0
            inicio += evento.duracao_s
        assert inicio == 3600
        assert [e.inicio_s for e in relogio.eventos if e.hard_time] == esperados

    relogio_a = carregar_relogio("A")
    por_grupo = relogio_a.duracao_por_grupo()
    assert por_grupo == {"musica": 3015, "fala": 225, "intervalo": 360}


def test_fixtures_de_programa_validas():
    from app.live.music import _titulo_normalizado, titulo_ja_tocado
    from app.models.programa import Programa
    from scripts.simulacao.fixtures import FixturePrograma, Relogio, carregar_catalogo, carregar_relogio

    colunas_programa = set(Programa.__table__.columns.keys())
    arquivos = sorted(DIR_PROGRAMAS.glob("*.json"))
    assert {a.stem for a in arquivos} == set(PERFIS)

    for arquivo in arquivos:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        # O testador percorre o topo da pasta: nenhum arquivo ali pode ser um relógio.
        with pytest.raises(ValueError):
            Relogio.model_validate(dados)
        fixture = FixturePrograma.model_validate(dados)
        assert fixture.id == arquivo.stem

        carregar_relogio(fixture.relogio)
        assert set(fixture.programa) <= colunas_programa, set(fixture.programa) - colunas_programa
        assert fixture.programa.get("ia_pode_adicionar_blocos") is False
        assert fixture.conta.cidade == ""
        assert fixture.programa.get("dose_noticia") == "nenhuma"
        assert fixture.programa.get("pode_pesquisar") is False

        catalogo = carregar_catalogo(fixture.catalogo)
        assert len(catalogo.faixas) >= 30
        assert sum(f.duracao_tocada_s for f in catalogo.faixas if not f.indisponivel) >= 100 * 60
        rotulos = {f"{f.artista} - {f.titulo}" for f in catalogo.faixas}
        for permitida in fixture.programa.get("musicas_permitidas", []):
            assert permitida in rotulos, permitida

        # Títulos distintos não podem ser "a mesma música" para o backend (contenção de palavras).
        titulos = [f.titulo for f in catalogo.faixas]
        for i, titulo in enumerate(titulos):
            outros = {_titulo_normalizado(t) for j, t in enumerate(titulos) if j != i}
            assert not titulo_ja_tocado(titulo, outros), titulo

        papeis = {v.papel for v in fixture.vinhetas}
        chaves = {p.chave for p in fixture.patrocinadores}
        for bloco in fixture.programa.get("estrutura_blocos", []):
            if bloco.startswith("vinheta:@"):
                assert bloco.removeprefix("vinheta:@") in papeis
            if bloco.startswith("patrocinador:@"):
                assert bloco.removeprefix("patrocinador:@") in chaves


def test_linha_historico_igual_ao_painel():
    """Espelha linhaMusicasHistorico + map de prepararTexto (frontend-painel/hooks/useLiveEngine.ts:1241)."""
    from scripts.simulacao.emissao import linha_historico

    segmento = {"tipo": "musica", "fala": "Vem aí", "musicas": [
        {"titulo": "T", "canal": "C"}, {"titulo": "U", "canal": "D"},
    ]}
    assert linha_historico(segmento) == "musica: Vem aí [Música(s) tocada(s) nesse bloco: T - C, U - D]"
    assert linha_historico({"tipo": "abertura", "fala": "Oi", "musicas": []}) == "abertura: Oi"
    assert linha_historico({"tipo": "musica", "fala": "", "musicas": [{"titulo": "T", "canal": ""}]}) == (
        "musica:  [Música(s) tocada(s) nesse bloco: T]"
    )


def test_duble_llm_respeita_orcamento_tipo_e_faixa_confirmada():
    from scripts.simulacao.dubles import DubleLLM, EstadoChamada
    from scripts.simulacao.fixtures import carregar_catalogo, carregar_fixture

    musical = carregar_fixture("musical_adulto").model_copy(update={"injecoes": []})
    catalogo = carregar_catalogo(musical.catalogo)
    faixa = next(f for f in catalogo.faixas if not f.indisponivel)
    estado = EstadoChamada()
    duble = DubleLLM(musical, estado, wpm=145, semente=7)

    # Faixa confirmada chega pelo canal lateral: o prompt não precisa citar a música.
    estado.nova_chamada(bloco_n=4, total_falas=3)
    estado.registrar_faixa(faixa)
    texto = duble.gerar_resposta("prompt sem nome de música", "Tipo do próximo bloco: musica.\nHistórico:")
    assert faixa.titulo in texto and faixa.artista in texto
    assert contar_palavras(texto) <= orcamento_fala("musica")[2]

    # Orçamento do backend no formato musical: identificação cabe na meta em segundos.
    estado.nova_chamada(bloco_n=5, total_falas=4)
    texto = duble.gerar_resposta("prompt", "Tipo do próximo bloco: identificacao.\n")
    minimo, maximo, palavras = orcamento_fala("identificacao")
    assert contar_palavras(texto) <= palavras
    assert contar_palavras(texto) / 145 * 60 <= maximo

    # Revisão obedece ao limite pedido, mesmo menor que a meta.
    texto = duble.gerar_resposta("prompt\nReescreva com no máximo 6 palavras, preservando os fatos.",
                                 "Tipo do próximo bloco: identificacao.\n")
    assert contar_palavras(texto) <= 6

    # Sem faixa confirmada, a fala de música não anuncia nenhuma faixa do catálogo.
    estado.nova_chamada(bloco_n=6, total_falas=5)
    texto = duble.gerar_resposta("prompt", "Tipo do próximo bloco: musica.\n")
    assert not any(f.titulo in texto for f in catalogo.faixas)

    # Formato padrão: orçamento de referência da fixture.
    variedades = carregar_fixture("variedades_leves").model_copy(update={"injecoes": []})
    duble_padrao = DubleLLM(variedades, EstadoChamada(), wpm=145, semente=7)
    duble_padrao.estado.nova_chamada(bloco_n=2, total_falas=1)
    texto = duble_padrao.gerar_resposta("prompt", "Tipo do próximo bloco: comentario.\n")
    assert contar_palavras(texto) / 145 * 60 <= variedades.orcamento_para("comentario").max

    assert duble.contadores["tipo_reconhecido"] == 4
    duble.gerar_resposta("prompt", "mensagem sem o tipo")
    assert duble.contadores["tipo_nao_reconhecido"] == 1


def test_duble_musica_respeita_evitar_e_titulos_tocados():
    from app.live.music import _titulo_normalizado
    from scripts.simulacao.dubles import CatalogoSimulado, EstadoChamada
    from scripts.simulacao.fixtures import carregar_catalogo

    catalogo = carregar_catalogo("popular_sertanejo")
    disponiveis = [f for f in catalogo.faixas if not f.indisponivel]
    indisponivel = next(f for f in catalogo.faixas if f.indisponivel)
    estado = EstadoChamada()
    estado.nova_chamada(bloco_n=1, total_falas=0)
    musicas = CatalogoSimulado(catalogo, estado)

    primeira = musicas.buscar_musica("sucessos musica brasileira")
    assert primeira.video_id == disponiveis[0].video_id
    assert primeira.canal == disponiveis[0].artista
    assert estado.faixa.video_id == disponiveis[0].video_id

    segunda = musicas.buscar_musica("sucessos musica brasileira", evitar_video_ids={disponiveis[0].video_id})
    assert segunda.video_id == disponiveis[1].video_id

    tocados = {_titulo_normalizado(disponiveis[0].titulo), _titulo_normalizado(disponiveis[1].titulo)}
    terceira = musicas.buscar_musica("sertanejo musica", genero="sertanejo", titulos_tocados=tocados)
    assert terceira.video_id == disponiveis[2].video_id

    # Pedido pelo título: tokens da query no texto da faixa; faixa indisponível nunca volta.
    assert musicas.buscar_musica(disponiveis[5].titulo).video_id == disponiveis[5].video_id
    assert musicas.buscar_musica(indisponivel.titulo) is None
    assert musicas.resolver_musica_catalogada(None, indisponivel.titulo, indisponivel.artista) is None

    resolvida = musicas.resolver_musica_catalogada(None, disponiveis[3].titulo, disponiveis[3].artista)
    assert resolvida.video_id == disponiveis[3].video_id
    assert musicas.resolver_musica_catalogada(
        None, disponiveis[3].titulo, disponiveis[3].artista, evitar_video_ids={disponiveis[3].video_id},
    ) is None

    faixas = musicas.buscar_faixas_por_categoria("sertanejo", excluir_titulos=tocados)
    assert (disponiveis[0].artista, disponiveis[0].titulo) not in faixas
    assert faixas[0] == (disponiveis[2].artista, disponiveis[2].titulo)

    duracao = (resolvida.fim_segundos or resolvida.duracao_segundos) - resolvida.inicio_segundos
    assert duracao == disponiveis[3].duracao_tocada_s

    citadas = musicas.extrair_musicas_citadas(
        f"Lembrei de {disponiveis[4].titulo} e de {disponiveis[6].titulo}.",
        [f"{disponiveis[6].titulo} - {disponiveis[6].artista}"],
    )
    assert citadas == [f"{disponiveis[4].artista} - {disponiveis[4].titulo}"]


def test_banco_de_falas_respeita_regras_editoriais():
    """Falas originais do dublê: sem algarismo, sem promessa, sem pedido simulado, sem título do catálogo."""
    from scripts.simulacao import banco_falas
    from scripts.simulacao.fixtures import carregar_catalogo
    from scripts.simulacao.metricas import CONFIG_METRICAS, detectar_promessas, normalizar

    titulos = [normalizar(f.titulo) for perfil in PERFIS for f in carregar_catalogo(perfil).faixas]
    espacos = {"radio": "Rádio Teste", "programa": "Programa Teste", "locutor": "Locutor Teste", "titulo": "",
               "artista": "", "nome": "", "quadro": "Quadro Teste"}
    for modelo, partes in banco_falas.BANCO.items():
        for parte in ("aberturas", "ganchos", "fechamentos"):
            assert len(partes[parte]) >= 8, (modelo, parte)
        for frase in [f for lista in partes.values() for f in lista]:
            texto = frase.format(**espacos)
            assert not any(ch.isdigit() for ch in texto), frase
            assert detectar_promessas(texto, 0, 3600, 1) == [], frase
            normalizado = f" {normalizar(texto)} "
            if not modelo.startswith("musica_pedido"):
                for padrao in CONFIG_METRICAS["pedido_indevido"]["padroes"]:
                    assert f" {normalizar(padrao)} " not in normalizado, (modelo, frase)
            for titulo in titulos:
                assert f" {titulo} " not in normalizado, (modelo, frase, titulo)


def _as_run_artificial():
    def evento(n, bloco_n, tipo, inicio_s, fim_s, **extra):
        base = {
            "n": n, "bloco_n": bloco_n, "tipo": tipo, "bloco": extra.pop("bloco", tipo),
            "categoria": extra.pop("categoria", tipo), "formato": "musical_adulto",
            "inicio_s": inicio_s, "fim_s": fim_s, "pausa_antes_s": extra.pop("pausa_antes_s", 0.0),
            "texto": extra.pop("texto", ""), "duracao_prevista_s": fim_s - inicio_s, "duracao_medida_s": None,
            "orcamento_s": extra.pop("orcamento_s", None), "musicas_citadas": [],
            "musica_anunciada": extra.pop("musica_anunciada", []), "musica_tocada": extra.pop("musica_tocada", None),
            "musicas_bloco": [], "promessas_abertas": extra.pop("promessas_abertas", []),
            "promessas_fechadas": [], "pedido_id": None, "pedido_estado": None, "pedido_estado_final": None,
            "cortado": False,
        }
        base.update(extra)
        return base

    def orc(maximo):
        return {"min": 1, "max": maximo, "fonte": "backend"}

    eventos = [
        evento(1, 1, "fala", 0.0, 18.0, bloco="abertura", categoria="abertura",
               texto="Boa tarde, começa a Tarde Serena.", orcamento_s=orc(35)),
        evento(2, 2, "musica", 18.0, 200.0, bloco="musica", categoria="musica",
               musica_tocada="Rua das Acácias - Duo Estrada Velha"),
        evento(3, 3, "fala", 200.0, 212.0, bloco="retomada", categoria="abertura",
               texto="Você ouve a Rádio Serra Clara nesta tarde.", orcamento_s=orc(12),
               musica_anunciada=["Varanda de Pedra - Trio Ventania"], musica_tocada="Lua no Telhado - Coral Alto"),
        evento(4, 3, "musica", 212.0, 400.0, bloco="retomada", categoria="abertura",
               musica_tocada="Lua no Telhado - Coral Alto"),
        evento(5, 4, "fala", 400.0, 440.0, bloco="identificacao", categoria="abertura",
               texto="Você ouve a Rádio Serra Clara, e daqui a pouco tem novidade.", orcamento_s=orc(20),
               promessas_abertas=[{"id": "p1", "padrao": "daqui a pouco", "trecho": "daqui a pouco", "prazo_s": 900}]),
        evento(6, 5, "bloco_vazio", 450.0, 455.0, pausa_antes_s=2.0),
        evento(7, 6, "fala", 455.0, 470.0, bloco="chamada_ouvinte", categoria="chamada_ouvinte",
               texto="Você ouve a Marina Tavares, que pediu esta, toca agora.", orcamento_s=orc(60)),
        evento(8, 6, "musica", 470.0, 582.0, bloco="chamada_ouvinte", categoria="chamada_ouvinte",
               musica_tocada="Ponte de Madeira - Coral Alto"),
        evento(9, 7, "fala", 582.0, 600.0, bloco="encerramento", categoria="encerramento",
               texto="Obrigado pela companhia nesta tarde.", orcamento_s=orc(18)),
    ]
    relogio = {"id": "T", "eventos": [
        {"inicio_s": 0, "duracao_s": 60, "tipo": "abertura", "grupo": "fala", "hard_time": True,
         "corresponde_a": ["abertura"]},
        {"inicio_s": 60, "duracao_s": 240, "tipo": "musica", "grupo": "musica", "hard_time": False,
         "corresponde_a": []},
        {"inicio_s": 300, "duracao_s": 120, "tipo": "intervalo", "grupo": "intervalo", "hard_time": True,
         "corresponde_a": ["intervalo"]},
        {"inicio_s": 420, "duracao_s": 150, "tipo": "musica", "grupo": "musica", "hard_time": False,
         "corresponde_a": []},
        {"inicio_s": 570, "duracao_s": 30, "tipo": "passagem", "grupo": "fala", "hard_time": True,
         "corresponde_a": ["encerramento"]},
    ]}
    return {
        "versao": 1, "programa": "artificial", "formato": "musical_adulto", "modo": "fake",
        "inicio": "2026-11-10T14:00:00-03:00", "fim_programa": "2026-11-10T14:10:00-03:00",
        "duracao_programa_s": 600, "relogio": relogio,
        "ouvintes": {"fixture": ["Marina Tavares"], "inexistentes": []},
        "pedidos": [], "eventos": eventos,
    }


def test_metricas_em_as_run_artificial():
    from scripts.simulacao.metricas import calcular_metricas

    m = calcular_metricas(_as_run_artificial())
    assert m["anuncio_sem_confirmacao"] == 1
    assert m["promessa_vencida"] == 1
    assert m["pedido_indevido"] == 1
    assert m["silencio_s"] == pytest.approx(13.0)
    assert m["silencio_editorial_s"] == pytest.approx(2.0)
    assert m["fora_orcamento_pct"] == pytest.approx(20.0)
    assert m["estouro_max_pct"] == pytest.approx(100.0)
    assert m["atraso_hard_time_s"] == pytest.approx(12.0)
    assert m["hard_times_perdidos"] == 1
    assert [h["status"] for h in m["hard_times"]] == ["ok", "perdido", "atrasado"]
    assert m["abertura_repetida"] == 1
    assert m["tempo_fala_s"] == pytest.approx(103.0)
    assert m["tempo_musica_s"] == pytest.approx(482.0)
    assert m["tempo_outros_s"] == pytest.approx(5.0)
    # F7: o verificador de oralidade existe; a métrica é a soma dos avisos das falas do as_run (não mais None).
    from app.live.oralidade import avisos

    falas = [e for e in _as_run_artificial()["eventos"] if e.get("texto")]
    assert m["aviso_oralidade"] == sum(len(avisos(e["texto"])) for e in falas)
    # F8: repetição por estrutura sobre as mesmas falas (não mais None).
    from app.live.memoria import repeticao_estrutura

    assert m["repeticao_estrutura"] == repeticao_estrutura([e["texto"] for e in falas], 3)

    # Controle negativo: sem as violações, as contagens zeram.
    limpo = _as_run_artificial()
    limpo["eventos"] = [e for e in limpo["eventos"] if e["n"] not in (3, 5, 6, 7)]
    m_limpo = calcular_metricas(limpo)
    assert (m_limpo["anuncio_sem_confirmacao"], m_limpo["promessa_vencida"], m_limpo["pedido_indevido"]) == (0, 0, 0)
    assert m_limpo["abertura_repetida"] == 0


# ---------------------------------------------------------------------------------------------
# H0 (humanização da fala): métricas com o detector do backend, importado na hora
# ---------------------------------------------------------------------------------------------

CHAVES_HUMANIZACAO = ("vazamento_grave", "sinais_ia_media", "sinais_ia_p90", "bordao_repetido")


@pytest.fixture
def sem_detectores_h0(monkeypatch):
    """Estado da H0: app.live.sinais_ia (H1/H4) e memoria.bordoes_repetidos (H5) não existem."""
    from app.live import memoria

    monkeypatch.setitem(sys.modules, "app.live.sinais_ia", None)
    monkeypatch.delattr(memoria, "bordoes_repetidos", raising=False)


@pytest.fixture
def detectores_h0_duble(monkeypatch):
    """Detectores dublês no lugar dos que a H1, a H4 e a H5 vão criar: `vazamentos` acusa "[", `pontuar` devolve a nota
    de `notas` (0 para texto fora dela) e `bordoes_repetidos` guarda os argumentos e devolve `bordao`."""
    import types

    from app.live import memoria

    estado = {"notas": {}, "bordao": 0, "chamadas_bordao": [], "textos_pontuados": []}
    modulo = types.ModuleType("app.live.sinais_ia")

    def pontuar(texto):
        estado["textos_pontuados"].append(texto)
        return types.SimpleNamespace(nota=estado["notas"].get(texto, 0.0), violacoes=[])

    modulo.vazamentos = lambda texto: ["["] if "[" in texto else []
    modulo.pontuar = pontuar

    def bordoes_repetidos(falas, bordoes, *, janela_s, maximo):
        estado["chamadas_bordao"].append({"falas": falas, "bordoes": bordoes, "janela_s": janela_s, "maximo": maximo})
        return estado["bordao"]

    monkeypatch.setitem(sys.modules, "app.live.sinais_ia", modulo)
    monkeypatch.setattr(memoria, "bordoes_repetidos", bordoes_repetidos, raising=False)
    return estado


def test_metricas_humanizacao_sem_detector_valem_none(sem_detectores_h0):
    from scripts.simulacao.metricas import metricas_humanizacao

    as_run = _as_run_artificial()
    copia = json.loads(json.dumps(as_run))
    m = metricas_humanizacao(as_run, bordoes=["Rádio Serra Clara"])
    assert {k: m[k] for k in CHAVES_HUMANIZACAO} == dict.fromkeys(CHAVES_HUMANIZACAO)
    # n medido (fato 9 da auditoria): as falas com texto, mesmo sem detector.
    assert m["sinais_ia_falas"] == 5
    assert as_run == copia  # função pura: não anota o as-run


def test_metricas_humanizacao_com_detector_duble(detectores_h0_duble):
    from scripts.simulacao.metricas import metricas_humanizacao

    as_run = _as_run_artificial()
    falas = _falas(as_run)
    falas[1]["texto"] = "Um alô para [NOME DO OUVINTE], que ouve do trabalho."
    detectores_h0_duble["notas"] = {falas[0]["texto"]: 10.0, falas[1]["texto"]: 35.5, falas[3]["texto"]: 20.0}
    detectores_h0_duble["bordao"] = 2
    m = metricas_humanizacao(as_run, bordoes=["Rádio Serra Clara", ""])
    assert m["vazamento_grave"] == 1
    assert m["sinais_ia_media"] == pytest.approx(13.1)  # (10 + 35,5 + 0 + 20 + 0) / 5
    assert m["sinais_ia_p90"] == pytest.approx(35.5)    # posto ceil(0,9 x 5) = 5
    assert m["sinais_ia_falas"] == 5
    assert m["bordao_repetido"] == 2
    (chamada,) = detectores_h0_duble["chamadas_bordao"]
    assert chamada["falas"] == [(float(f["inicio_s"]), f["texto"]) for f in falas]
    assert chamada["bordoes"] == ["Rádio Serra Clara"]
    from scripts.simulacao.metricas import CONFIG_METRICAS

    assert (chamada["janela_s"], chamada["maximo"]) == (1800, 1) == (
        CONFIG_METRICAS["humanizacao"]["bordao"]["janela_s"], CONFIG_METRICAS["humanizacao"]["bordao"]["maximo"])


def test_metricas_humanizacao_ignoram_fala_vazia(detectores_h0_duble):
    from scripts.simulacao.metricas import metricas_humanizacao

    as_run = _as_run_artificial()
    falas = _falas(as_run)
    falas[0]["texto"] = "   "
    falas[2]["texto"] = ""
    m = metricas_humanizacao(as_run)
    assert m["sinais_ia_falas"] == 3
    assert "" not in detectores_h0_duble["textos_pontuados"] and "   " not in detectores_h0_duble["textos_pontuados"]
    assert len(detectores_h0_duble["chamadas_bordao"][0]["falas"]) == 3
    sem_falas = _as_run_artificial()
    sem_falas["eventos"] = [e for e in sem_falas["eventos"] if e["tipo"] != "fala"]
    vazio = metricas_humanizacao(sem_falas)
    assert (vazio["sinais_ia_media"], vazio["sinais_ia_p90"], vazio["vazamento_grave"], vazio["sinais_ia_falas"]) == (
        None, None, 0, 0)


def test_percentil_posto_mais_proximo():
    from scripts.simulacao.metricas import _percentil

    assert _percentil([], 90) is None
    assert _percentil([7.0], 90) == 7.0
    assert _percentil([float(v) for v in range(10, 0, -1)], 90) == 9.0  # posto ceil(0,9 x 10) = 9
    assert _percentil([float(v) for v in range(1, 21)], 90) == 18.0
    assert _percentil([1.0, 2.0, 3.0], 90) == 3.0


def test_metricas_humanizacao_detector_parcial(monkeypatch):
    """H1 pronta e H4 ainda não: o módulo existe só com `vazamentos`; a média fica None, o vazamento é contado."""
    import types

    from app.live import memoria
    from scripts.simulacao.metricas import metricas_humanizacao

    modulo = types.ModuleType("app.live.sinais_ia")
    modulo.vazamentos = lambda texto: []
    monkeypatch.setitem(sys.modules, "app.live.sinais_ia", modulo)
    monkeypatch.delattr(memoria, "bordoes_repetidos", raising=False)
    m = metricas_humanizacao(_as_run_artificial())
    assert m["vazamento_grave"] == 0
    assert (m["sinais_ia_media"], m["sinais_ia_p90"], m["bordao_repetido"]) == (None, None, None)


def test_detector_so_engole_a_falta_do_proprio_modulo(monkeypatch):
    import types

    from scripts.simulacao import metricas

    def import_quebrado(nome):
        raise ModuleNotFoundError("No module named 'dependencia_interna'", name="dependencia_interna")

    monkeypatch.setattr(metricas, "importlib", types.SimpleNamespace(import_module=import_quebrado))
    with pytest.raises(ModuleNotFoundError, match="dependencia_interna"):
        metricas._detector("app.live.sinais_ia", "vazamentos")
    with pytest.raises(ModuleNotFoundError):
        metricas.metricas_humanizacao(_as_run_artificial())

    def import_ausente(nome):
        raise ModuleNotFoundError(f"No module named '{nome}'", name=nome)

    monkeypatch.setattr(metricas, "importlib", types.SimpleNamespace(import_module=import_ausente))
    assert metricas._detector("app.live.sinais_ia", "vazamentos") is None


def test_duble_llm_injeta_as_frases_da_h0():
    from scripts.simulacao.dubles import DubleLLM, EstadoChamada
    from scripts.simulacao.fixtures import Injecao, carregar_fixture

    frases = {
        "vazamento": "Desculpe, mas não posso ajudar com isso.",
        "sinal_ia": "Vale ressaltar que a festa é um verdadeiro marco histórico.",
        "bordao": "A viola que acompanha o seu dia.",
    }
    injecoes = [Injecao(fala=n, tipo=tipo, frase=frase) for n, (tipo, frase) in enumerate(frases.items(), start=1)]
    fixture = carregar_fixture("popular_sertanejo").model_copy(update={"injecoes": injecoes})
    estado = EstadoChamada()
    duble = DubleLLM(fixture, estado, wpm=145, semente=7)
    for n, (tipo, frase) in enumerate(frases.items(), start=1):
        estado.nova_chamada(bloco_n=n, total_falas=n - 1)
        texto = duble.gerar_resposta("prompt", "Tipo do próximo bloco: comentario.\n")
        assert texto.endswith(frase), (tipo, texto)
        assert duble.contadores[f"injecao_{tipo}"] == 1
    # A revisão da mesma fala repete a frase, como as injeções da F6.
    texto = duble.gerar_resposta("prompt\nReescreva com no máximo 40 palavras, preservando os fatos.",
                                 "Tipo do próximo bloco: comentario.\n")
    assert texto.endswith(frases["bordao"]) and duble.contadores["injecao_bordao"] == 2


# ---------------------------------------------------------------------------------------------
# Integração (pelo /proxima real)
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("perfil", PERFIS)
def test_simulacao_fake_rapida_e_sem_rede(simulacoes, perfil):
    sim = simulacoes[perfil]
    resultado, saida = sim["resultado"], sim["saida"]
    assert sim["parede_s"] < 30
    assert resultado.resumo["tempo_execucao_s"] < 30
    assert resultado.resumo["tentativas_rede"] == 0
    assert resultado.resumo["erros_http"] == 0

    as_run = json.loads((saida / "as_run.json").read_text(encoding="utf-8"))
    resumo = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    assert as_run["programa"] == perfil
    assert resumo["config"]["modo"] == "fake"

    eventos = as_run["eventos"]
    assert len(eventos) > 10
    for evento in eventos:
        faltando = [c for c in CHAVES_SKILL if c not in evento]
        assert not faltando, (evento["n"], faltando)
        assert evento["tipo"] in ("fala", "musica", "vinheta", "patrocinador", "intervalo", "bloco_vazio", "erro")
    for anterior, seguinte in zip(eventos, eventos[1:]):
        assert anterior["fim_s"] <= seguinte["inicio_s"] + 1e-6
        assert anterior["bloco_n"] <= seguinte["bloco_n"]
    assert eventos[0]["inicio_s"] >= 0
    assert any(e["tipo"] == "musica" for e in eventos)
    assert _falas(as_run)


def test_determinismo_mesma_semente(simulacoes):
    from scripts.simular_hora import simular

    base = simulacoes["variedades_leves"]["resultado"]
    outra = simular("variedades_leves")
    assert outra.as_run == base.as_run
    assert _resumo_comparavel(base.resumo) == _resumo_comparavel(outra.resumo)


def _resumo_comparavel(resumo: dict) -> dict:
    """Sem o que não é da simulação: tempo de parede e o commit do git (um commit durante a suíte o muda)."""
    copia = {k: v for k, v in resumo.items() if k != "tempo_execucao_s"}
    copia["config"] = {k: v for k, v in resumo["config"].items() if k != "commit"}
    return copia


def test_simulacao_isolada_do_random_global():
    """Outra thread do processo usando o random global (como o flush de logs do Sentry, a cada ~5 s) não muda
    a simulação: o backend sorteia com o RNG próprio da simulação."""
    import random
    import threading

    from scripts.simular_hora import simular

    base = simular("musical_adulto", relogio_backend="fixture")
    parar = threading.Event()

    def ruido():
        while not parar.is_set():
            random.random()
            parar.wait(0.0005)

    concorrente = threading.Thread(target=ruido, daemon=True)
    concorrente.start()
    try:
        outra = simular("musical_adulto", relogio_backend="fixture")
    finally:
        parar.set()
        concorrente.join()
    assert outra.as_run == base.as_run
    assert _resumo_comparavel(outra.resumo) == _resumo_comparavel(base.resumo)


def test_fila_de_preparo_gera_dois_blocos_a_frente(simulacoes):
    as_run = simulacoes["popular_sertanejo"]["resultado"].as_run
    inicio_bloco = {}
    gerado_em = {}
    for evento in as_run["eventos"]:
        if evento["bloco_n"] not in inicio_bloco:
            inicio_bloco[evento["bloco_n"]] = evento["inicio_s"] - evento["pausa_antes_s"]
            gerado_em[evento["bloco_n"]] = evento["gerado_em_s"]
    blocos = sorted(inicio_bloco)
    assert gerado_em[blocos[0]] == pytest.approx(-90.0)
    assert gerado_em[blocos[1]] == pytest.approx(-90.0)
    conferidos = 0
    for k in blocos[2:]:
        if k - 2 in inicio_bloco:
            assert gerado_em[k] == pytest.approx(inicio_bloco[k - 2], abs=5.0), k
            conferidos += 1
    assert conferidos >= 5


def test_corte_agendado_trunca_no_horario_fim(simulacoes):
    resultado = simulacoes["musical_adulto"]["resultado"]
    eventos = resultado.as_run["eventos"]
    assert max(e["fim_s"] for e in eventos) <= 3601.0 + 1e-6
    assert any(e["cortado"] for e in eventos) or resultado.resumo["segundos_cortados"] > 0
    assert resultado.resumo["estouro_fim_programa_s"] <= 1.0 + 1e-6
    assert resultado.resumo["config"]["corte"] == "agendado"
    # O que não foi ao ar fica registrado com o instante de geração (insumo da F1).
    assert len(resultado.as_run["blocos_nao_tocados"]) == resultado.resumo["blocos_nao_tocados"]
    assert all(b["gerado_em_s"] <= 3601 for b in resultado.as_run["blocos_nao_tocados"])


def test_corte_manual_mede_estouro():
    from scripts.simular_hora import simular

    resultado = simular("musical_adulto", corte="manual")
    eventos = resultado.as_run["eventos"]
    assert not any(e["cortado"] for e in eventos)
    assert resultado.resumo["estouro_fim_programa_s"] > 0
    assert resultado.resumo["encerramento_no_ar"] is True
    assert _falas(resultado.as_run)[-1]["bloco"] == "encerramento"


def test_pedido_fluxo_novo_selecionado_vira_executado(simulacoes):
    resultado = simulacoes["popular_sertanejo"]["resultado"]
    executados = [
        e for e in resultado.as_run["eventos"]
        if e["tipo"] == "fala" and e["pedido_estado"] == "selecionado" and e["pedido_estado_final"] == "executado"
    ]
    assert executados
    pedidos = resultado.resumo["pedidos"]
    assert pedidos["executados"] >= 1
    assert pedidos["atendidos_antes_de_tocar"] == 0
    assert pedidos["recebidos"] == 4


def test_pedido_fluxo_legado_confirma_depois_de_tocar(simulacoes):
    """F4 (D1): o legado é selecionado com token e o player confirma a reprodução, como no fluxo novo. Antes ele
    era marcado atendido na seleção ("historico_legado") e contava como pedido indevido de propósito."""
    resultado = simulacoes["variedades_leves"]["resultado"]
    eventos = resultado.as_run["eventos"]
    legados = [e for e in eventos if e["pedido_estado"] == "selecionado"]
    assert legados and not any(e["pedido_estado"] == "historico_legado" for e in eventos)
    assert any(e["pedido_estado_final"] == "executado" for e in legados)
    assert resultado.resumo["pedidos"]["atendidos_antes_de_tocar"] == 0
    assert resultado.resumo["pedidos"]["executados"] >= 1


def test_injecoes_aparecem_nas_metricas(simulacoes):
    popular = simulacoes["popular_sertanejo"]["resultado"].resumo
    musical = simulacoes["musical_adulto"]["resultado"].resumo
    variedades = simulacoes["variedades_leves"]["resultado"].resumo

    # F4: a promessa injetada ("daqui a pouco tem mais recado") acontece e o validador do backend a tira (sem
    # chamada de ouvinte a até 4 posições) ou a registra para cumprir: nenhuma vence.
    assert popular["dubles"]["contadores"]["injecao_promessa"] >= 1
    assert popular["promessa_vencida"] == 0
    assert musical["chamadas_llm"]["total"] > musical["chamadas_llm"]["falas"]
    assert musical["chamadas_llm"]["revisoes"] >= 1
    # F3: a injeção de música não confirmada acontece e o validador do backend a tira da fala antes de ir ao ar.
    assert musical["dubles"]["contadores"]["injecao_cita_musica"] >= 1
    assert musical["anuncio_sem_confirmacao"] == 0
    assert musical["validacao_fala"]["regras"]["musica_nao_confirmada"] >= 1
    # Desde a F2 o formato padrão sem relógio só observa o orçamento (o backend não reescreve nem encurta):
    # o excesso injetado aparece nas falas em observação, relatadas à parte.
    assert variedades["orcamento_observacao"]["fora_pct"] > 0
    # F4: o ouvinte inventado ("Dona Firmina") é injetado e sai da fala antes de ir ao ar.
    assert variedades["dubles"]["contadores"]["injecao_cita_ouvinte"] >= 1
    assert variedades["ouvinte_inexistente"] == 0


@pytest.mark.parametrize("perfil", PERFIS)
def test_resumo_tem_as_metricas_de_humanizacao(simulacoes, perfil):
    """H0: as quatro chaves no topo do resumo.json, None enquanto o detector da frente dona não existir (H1, H4, H5)."""
    saida = simulacoes[perfil]["saida"]
    resumo = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    for chave in CHAVES_HUMANIZACAO:
        assert chave in resumo, chave
        assert resumo[chave] is None or isinstance(resumo[chave], (int, float)), (chave, resumo[chave])
    assert resumo["sinais_ia_falas"] == len(
        [e for e in simulacoes[perfil]["resultado"].as_run["eventos"] if e["tipo"] == "fala" and e["texto"].strip()])


def test_metricas_de_humanizacao_so_acrescentam_chaves(simulacoes, monkeypatch):
    """Caracterização (portão §7.4): sem as métricas da H0, o as-run e as chaves que já existiam são os mesmos."""
    from scripts.simulacao import metricas
    from scripts.simular_hora import simular

    base = simulacoes["popular_sertanejo"]["resultado"]
    monkeypatch.setattr(metricas, "metricas_humanizacao", lambda as_run, **_: {})
    sem_h0 = simular("popular_sertanejo")
    assert sem_h0.as_run == base.as_run
    novas = set(CHAVES_HUMANIZACAO) | {"sinais_ia_falas"}
    assert set(base.resumo) - set(sem_h0.resumo) == novas
    antigas = {k: v for k, v in _resumo_comparavel(base.resumo).items() if k not in novas}
    assert antigas == _resumo_comparavel(sem_h0.resumo)


def test_dubles_cobrem_alvos_existentes(simulacoes, db_session):
    import importlib

    from scripts.simulacao.dubles import ALVOS, aplicar_dubles
    from scripts.simulacao.fixtures import carregar_catalogo, carregar_fixture

    originais = {}
    for alvo in ALVOS:
        modulo = importlib.import_module(alvo.modulo)
        assert hasattr(modulo, alvo.nome), f"{alvo.modulo}.{alvo.nome} não existe mais"
        originais[(alvo.modulo, alvo.nome)] = getattr(modulo, alvo.nome)

    fixture = carregar_fixture("popular_sertanejo")
    with aplicar_dubles(fixture, carregar_catalogo(fixture.catalogo), modo="fake", sessao=db_session):
        for nome_modulo, modulo in list(sys.modules.items()):
            if not nome_modulo.startswith("app.") or modulo is None:
                continue
            for atributo, valor in list(vars(modulo).items()):
                for (origem, nome), original in originais.items():
                    if callable(original) and valor is original:
                        pytest.fail(f"{nome_modulo}.{atributo} ainda aponta para {origem}.{nome} original")

    for (origem, nome), original in originais.items():
        assert getattr(importlib.import_module(origem), nome) is original

    assert simulacoes["popular_sertanejo"]["resultado"].resumo["dubles"]["faixa_reconhecida_pct"] >= 95


def _rodar_cli(*args, tmp_path):
    env = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONHASHSEED": "0",
           "ANTHROPIC_API_KEY": "chave-falsa-do-teste", "ELEVENLABS_API_KEY": ""}
    return subprocess.run(
        [sys.executable, "scripts/simular_hora.py", *args, "--saida", str(tmp_path / "saida")],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120,
    )


@pytest.mark.parametrize("modo", ["llm", "completo"])
def test_modos_pagos_exigem_confirmacao(tmp_path, modo):
    processo = _rodar_cli("--programa", "musical_adulto", "--modo", modo, tmp_path=tmp_path)
    assert processo.returncode == 3, processo.stderr[-2000:]
    assert "estimativa" in processo.stdout
    assert "tentativas_rede=0" in processo.stdout
    assert "--confirmo-custo" in processo.stdout
    assert not (tmp_path / "saida" / "as_run.json").exists()


def test_cli_modo_fake_grava_saidas(tmp_path):
    processo = _rodar_cli("--programa", str(DIR_PROGRAMAS / "musical_adulto.json"), tmp_path=tmp_path)
    assert processo.returncode == 0, processo.stderr[-2000:]
    resumo = json.loads((tmp_path / "saida" / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["tentativas_rede"] == 0
    assert "musical_adulto" in processo.stdout
    # H0: a linha-resumo traz as métricas de humanização (None até a H1 e a H4).
    assert "vazamento_grave=" in processo.stdout and "sinais_ia_media=" in processo.stdout


def test_casos_de_avaliacao_cobrem_as_regras():
    caminho = BACKEND.parent / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    casos = dados["casos"]
    assert len(casos) >= 30
    assert len({c["id"] for c in casos}) == len(casos)
    chaves = {
        "anuncio_sem_confirmacao", "promessa_sem_evento", "pedido_indevido", "ouvinte_inexistente",
        "dado_sem_fonte", "dado_vencido", "avisos_oralidade_min", "excede_orcamento", "abertura_repetida",
    }
    # F6: avisos de coerência com o formato (app.live.formatos.AVISOS), rotulados só nos casos da F6.
    chaves_f6 = {"fora_da_unidade", "bloco_fora_do_formato", "convite_fora_da_politica", "tema_revisao", "reorientacao"}
    contexto_chaves = {
        "tocou", "proxima_confirmada", "pedidos", "promessas_pendentes", "eventos_agendados", "dados",
        "segundos_ate_hard_time", "orcamento_s",
    }
    assert set(dados["regras"]["esperado"]) == chaves | chaves_f6
    positivos = {c: 0 for c in chaves | chaves_f6}
    negativos = {c: 0 for c in chaves | chaves_f6}
    wpm = dados["regras"]["wpm_referencia"]
    for caso in casos:
        assert {"id", "formato", "bloco", "frentes", "dimensoes", "contexto", "criterio", "falas_rotuladas"} <= set(caso)
        assert caso["formato"] in PERFIS
        assert contexto_chaves <= set(caso["contexto"])
        for fala in caso["falas_rotuladas"]:
            assert set(fala["esperado"]) == (chaves | chaves_f6 if "F6" in caso["frentes"] else chaves), caso["id"]
            assert not any(ch.isdigit() for ch in fala["texto"]), caso["id"]
            for chave, valor in fala["esperado"].items():
                ativo = valor > 0 if chave == "avisos_oralidade_min" else bool(valor)
                (positivos if ativo else negativos)[chave] += 1
            orcamento = caso["contexto"]["orcamento_s"]
            if orcamento:
                excede = contar_palavras(fala["texto"]) / wpm * 60 > orcamento["max"]
                assert fala["esperado"]["excede_orcamento"] == excede, caso["id"]
    for chave in chaves | chaves_f6:
        assert positivos[chave] >= 1 and negativos[chave] >= 1, chave
    assert {c["formato"] for c in casos} == set(PERFIS)


# ---------------------------------------------------------------------------------------------
# F1: relógio no backend (S1, S2 de docs/melhoria-radio/f1/auditoria.md §6)
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("perfil, relogio", [
    ("musical_adulto", "A"), ("popular_sertanejo", "A"), ("variedades_leves", "C"), ("variedades_leves", "B"),
])
def test_relogio_hard_times_sem_atraso(perfil, relogio, tmp_path):
    from scripts.simular_hora import simular

    inicio = time.perf_counter()
    resultado = simular(perfil, relogio=relogio, relogio_backend="fixture", saida=tmp_path)
    assert time.perf_counter() - inicio < 30
    resumo, as_run = resultado.resumo, resultado.as_run
    assert resumo["tentativas_rede"] == 0 and resumo["erros_http"] == 0
    assert as_run["relogio_backend"]["preset"] == relogio
    for hard_time in resumo["hard_times"]:
        assert hard_time["status"] != "perdido", hard_time
        assert hard_time["atraso_s"] is None or hard_time["atraso_s"] <= 5, hard_time
    assert resumo["atraso_hard_time_s"] <= 5
    assert resumo["falas_abaixo_minimo"] == 0
    falas = _falas(as_run)
    assert falas and all(f["relogio"] is not None and f["orcamento_s"]["fonte"] == "relogio" for f in falas)
    assert all(f["orcamento_s"]["max"] >= f["orcamento_s"]["min"] for f in falas)
    assert resumo["encerramento_no_ar"] is True
    assert resumo["segundos_cortados"] == 0
    assert resumo["fim_antecipado_s"] <= 60
    # O painel encadeia o horário previsto com a duração prevista pelo backend: no modo fake, exata.
    for evento in as_run["eventos"]:
        assert evento["inicio_previsto_s"] is not None
        assert evento["inicio_s"] - evento["pausa_antes_s"] >= evento["inicio_previsto_s"] - 1.0


def test_sem_relogio_inicio_previsto_nao_muda_as_run():
    from scripts.simular_hora import simular

    novos = {"inicio_previsto_s", "duracao_prevista_backend_s", "relogio"}

    def limpo(as_run):
        return [{k: v for k, v in e.items() if k not in novos} for e in as_run["eventos"]]

    for perfil in PERFIS:
        com = simular(perfil, relogio_backend="nenhum", inicio_previsto=True).as_run
        sem = simular(perfil, relogio_backend="nenhum", inicio_previsto=False).as_run
        assert limpo(com) == limpo(sem), perfil
        assert all(e["relogio"] is None for e in com["eventos"])
        assert com["relogio_backend"] is None


def test_cli_relogio_backend_e_padrao_fixture(tmp_path):
    processo = _rodar_cli("--programa", "popular_sertanejo", tmp_path=tmp_path)
    assert processo.returncode == 0, processo.stderr[-2000:]
    resumo = json.loads((tmp_path / "saida" / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["config"]["relogio_backend"] == "fixture" and resumo["config"]["inicio_previsto"] is True
    assert "fim_antecipado_s=" in processo.stdout


def test_parse_resposta_anthropic_sob_freeze_time_apos_aquecer(monkeypatch):
    """Regressão: o freezegun trocava datetime.datetime e o SDK falhava ao montar
    Container.expires_at (PydanticSchemaGenerationError) no primeiro parse com relógio falso."""
    import datetime as dt

    import anthropic
    import httpx
    from freezegun import freeze_time

    import scripts.simular_hora as sh

    msg = {"id": "m", "type": "message", "role": "assistant", "model": "claude-opus-5",
           "content": [{"type": "text", "text": "oi"}], "stop_reason": "end_turn",
           "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
           "container": {"id": "c", "expires_at": "2026-11-23T10:00:00Z"}}
    cliente = anthropic.Anthropic(api_key="sk-teste", max_retries=0,
                                  http_client=httpx.Client(transport=httpx.MockTransport(
                                      lambda r: httpx.Response(200, json=msg))))
    import anthropic.resources.messages as rm

    # conftest troca Messages.create por um stub de rede; restaura o original só neste teste.
    monkeypatch.setattr(rm.Messages, "create", _MESSAGES_CREATE_ORIGINAL)
    sh._aquecer_schemas_anthropic()
    with freeze_time(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)):
        resposta = cliente.messages.create(model="claude-opus-5", max_tokens=8,
                                           messages=[{"role": "user", "content": "oi"}])
    assert resposta.content[0].text == "oi"
    assert resposta.container.id == "c"


def test_espiao_llm_registra_direcao_do_formato_no_canal_lateral():
    """Regressão: nos modos pagos o espião de gerar_resposta não registrava a instrução, e o item
    instrucao_no_prompt saía 0% mesmo com a direção do formato no system."""
    from scripts.simulacao.dubles import DubleLLM, EstadoChamada, _EspiaoTexto
    from scripts.simulacao.fixtures import carregar_fixture
    from app.live.formatos import resolver_formato

    musical = carregar_fixture("musical_adulto").model_copy(update={"injecoes": []})
    direcao = resolver_formato(musical.programa.get("perfil_programacao")).direcao_cabecalho
    estado = EstadoChamada()
    duble = DubleLLM(musical, estado, wpm=145, semente=7)
    espiao = _EspiaoTexto(lambda system_prompt, mensagem_usuario: "oi", "gerar_resposta", duble)

    estado.nova_chamada(bloco_n=1, total_falas=2)
    espiao(f"{direcao} resto do system", "Tipo do próximo bloco: musica.")
    espiao(f"{direcao} resto do system", "Tipo do próximo bloco: musica.")  # revisão: não recontar
    estado.nova_chamada(bloco_n=2, total_falas=2)
    espiao("system sem direção", "Tipo do próximo bloco: musica.")

    assert duble.instrucao() == {"blocos": 2, "com_formato": 1, "com_outro": 0}
