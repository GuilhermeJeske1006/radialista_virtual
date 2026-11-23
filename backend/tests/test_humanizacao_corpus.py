"""Corpus determinístico de humanização da fala (H0; docs/humanizacao/h0/auditoria.md §5.1 e §6, item 3).

Só confere o esquema e os rótulos. Nenhum teste aqui chama `app.live.sinais_ia`: o detector é da H1 e da H4
(`tests/test_sinais_ia.py`), e os textos foram escritos antes de qualquer regex, para o rótulo não seguir o detector.
O único detector que já existe e é conferido aqui é o de repetição por estrutura da F8 (`app.live.memoria`).
"""

import ast
import collections
import json
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
CORPUS = BACKEND / "tests" / "fixtures" / "humanizacao" / "corpus.json"

GRUPOS = {"vazamento", "sinal", "nao_corrigir"}
CANAIS = {"ao_vivo", "whatsapp", "patrocinio"}
TONS = {"formal", "informal"}
ACOES = {"bloquear", "limpar", "reescrever", "pontuar", "normalizar", "nenhuma"}
# Algarismo: o ao vivo escreve número por extenso; só vazamento, patrocínio (texto cadastrado) e WhatsApp têm dígito.
CANAIS_COM_ALGARISMO = {"patrocinio", "whatsapp"}
MIN_POSITIVOS_SINAL = 5  # revocação de 0,8 da H4 aceita um erro em cinco
MIN_DENSOS = 5
# Composição da auditoria (§5.1): mínimos por categoria.
MIN_VAZAMENTO = {"placeholder": 10, "recusa": 6, "identidade_ia": 5, "data_corte": 5, "markdown": 8, "emoji": 5,
                 "url": 4}
CATEGORIAS_SINAL = {"atendimento", "importancia_inflada", "ressalva", "conectivo_redacao", "vocabulario_ia",
                    "evitar_e", "folheto", "paralelismo_negativo", "triade", "gerundio_final", "fechamento_resumo",
                    "atribuicao_vaga", "travessao"}
MIN_NAO_CORRIGIR = {"noticia_formal": 10, "conectivo_isolado": 5, "mistura_registro": 6, "reorientacao": 5,
                    "armadilha": 19}
ARMADILHAS = {
    "tag_v3_permitida", "nao_posso_deixar_de", "ia_como_assunto", "ultima_atualizacao_com_fonte", "jornada_literal",
    "cenario_literal", "representa_literal", "vale_a_pena", "importante_instrucao", "gerundio_legitimo",
    "fulano_coloquial", "triade_factual", "dominio_falado", "emoji_espelhado",
}
CHAVES_TEXTO = {"id", "grupo", "categorias", "canal", "tom", "texto", "trechos", "esperado"}
CHAVES_TEXTO_OPCIONAIS = {"armadilha", "contexto", "nota"}
CHAVES_SEQUENCIA = {"id", "categorias", "formato", "bordoes", "falas", "esperado"}
ESPERADO_SEQUENCIA = {"bordao_repetido", "repeticao_estrutura", "repeticao_proibida", "naturalidade_repetida"}
_TAG_RE = re.compile(r"\[([^\[\]]*)\]")


@pytest.fixture(scope="module")
def corpus():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _por_grupo(corpus, grupo):
    return [t for t in corpus["textos"] if t["grupo"] == grupo]


def _contagem_categorias(textos):
    return collections.Counter(c for t in textos for c in t["categorias"])


def test_esquema(corpus):
    assert {"versao", "fonte", "regras", "textos", "sequencias"} == set(corpus)
    assert corpus["versao"] == 1
    regras = corpus["regras"]
    assert {"grupos", "categorias", "categorias_sequencia", "armadilhas", "tags_v3_permitidas", "esperado", "bordao",
            "observacao"} <= set(regras)
    assert 140 <= len(corpus["textos"]) <= 170
    for texto in corpus["textos"]:
        assert CHAVES_TEXTO <= set(texto) <= CHAVES_TEXTO | CHAVES_TEXTO_OPCIONAIS, texto["id"]
        assert set(texto["esperado"]) == {"vazamento", "acima_do_limite"}, texto["id"]
        assert isinstance(texto["texto"], str) and texto["texto"].strip(), texto["id"]
        assert isinstance(texto["trechos"], list), texto["id"]
    for sequencia in corpus["sequencias"]:
        assert set(sequencia) <= CHAVES_SEQUENCIA | {"nota"}, sequencia["id"]
        assert CHAVES_SEQUENCIA <= set(sequencia), sequencia["id"]
        assert set(sequencia["esperado"]) == ESPERADO_SEQUENCIA, sequencia["id"]


def test_ids_unicos(corpus):
    ids = [t["id"] for t in corpus["textos"]] + [s["id"] for s in corpus["sequencias"]]
    assert len(ids) == len(set(ids))


def test_grupos_e_categorias_declarados(corpus):
    regras = corpus["regras"]
    assert set(regras["grupos"]) == GRUPOS
    for nome, categoria in regras["categorias"].items():
        assert categoria["grupo"] in GRUPOS, nome
        assert categoria["acao"] in ACOES, nome
        assert categoria["frente"], nome
    for texto in corpus["textos"]:
        assert texto["grupo"] in GRUPOS, texto["id"]
        assert texto["categorias"], texto["id"]
        for categoria in texto["categorias"]:
            assert categoria in regras["categorias"], (texto["id"], categoria)
            assert regras["categorias"][categoria]["grupo"] == texto["grupo"], (texto["id"], categoria)
    usadas = {c for t in corpus["textos"] for c in t["categorias"]}
    assert usadas == set(regras["categorias"])


def test_minimo_por_categoria(corpus):
    sinais = _contagem_categorias(_por_grupo(corpus, "sinal"))
    assert set(sinais) == CATEGORIAS_SINAL
    for categoria in CATEGORIAS_SINAL:
        assert sinais[categoria] >= MIN_POSITIVOS_SINAL, categoria
    vazamentos = _contagem_categorias(_por_grupo(corpus, "vazamento"))
    for categoria, minimo in MIN_VAZAMENTO.items():
        assert vazamentos[categoria] >= minimo, categoria


def test_nao_corrigir_tem_as_subcategorias_e_as_armadilhas(corpus):
    textos = _por_grupo(corpus, "nao_corrigir")
    contagem = _contagem_categorias(textos)
    for categoria, minimo in MIN_NAO_CORRIGIR.items():
        assert contagem[categoria] >= minimo, categoria
    declaradas = set(corpus["regras"]["armadilhas"])
    usadas = collections.Counter(t.get("armadilha") for t in textos if "armadilha" in t["categorias"])
    assert None not in usadas
    assert set(usadas) == declaradas
    assert ARMADILHAS <= declaradas
    # Só armadilha tem rótulo de armadilha.
    assert all("armadilha" not in t for t in corpus["textos"] if "armadilha" not in t["categorias"])
    emoji = [t for t in textos if t.get("armadilha") == "emoji_espelhado"]
    assert emoji and all(t["canal"] == "whatsapp" and t["contexto"]["ouvinte_usou_emoji"] is True for t in emoji)


def test_trechos_sao_parte_do_texto(corpus):
    for texto in corpus["textos"]:
        for trecho in texto["trechos"]:
            assert trecho and trecho in texto["texto"], (texto["id"], trecho)
        if texto["grupo"] in ("vazamento", "sinal") or "armadilha" in texto["categorias"]:
            assert texto["trechos"], texto["id"]


def test_regra_do_algarismo(corpus):
    for texto in corpus["textos"]:
        if texto["grupo"] != "vazamento" and texto["canal"] not in CANAIS_COM_ALGARISMO:
            assert not any(ch.isdigit() for ch in texto["texto"]), texto["id"]
    for sequencia in corpus["sequencias"]:
        for fala in sequencia["falas"]:
            assert not any(ch.isdigit() for ch in fala["texto"]), sequencia["id"]


def test_tags_v3_permitidas_so_em_nao_corrigir(corpus):
    from app.tts.client import _TAGS_V3_PERMITIDAS

    permitidas = set(corpus["regras"]["tags_v3_permitidas"])
    assert permitidas == set(_TAGS_V3_PERMITIDAS)
    com_tag = []
    for texto in corpus["textos"]:
        tags = [m.group(1).strip().lower() for m in _TAG_RE.finditer(texto["texto"])]
        if any(tag in permitidas for tag in tags):
            assert texto["grupo"] == "nao_corrigir", texto["id"]
            com_tag.append(texto["id"])
    assert len(com_tag) >= 2
    # Colchete minúsculo de uma palavra fora da lista é placeholder (fato 6 da auditoria): vazamento.
    minusculos = [t for t in corpus["textos"] if any(
        re.fullmatch(r"[a-z ]+", m.group(1)) and m.group(1) not in permitidas for m in _TAG_RE.finditer(t["texto"]))]
    assert minusculos and all(t["grupo"] == "vazamento" for t in minusculos)


def test_sinais_nao_repetem_o_burocratico_da_oralidade(corpus):
    """Achado 7: 'ademais', 'outrossim' e 'bem como' já são da F7 (oralidade.BUROCRATICO); o léxico novo não os conta
    de novo, então nenhum texto de sinal pode depender deles."""
    from app.live.oralidade import avisos

    for texto in _por_grupo(corpus, "sinal"):
        burocraticos = [a.trecho for a in avisos(texto["texto"]) if a.regra == "burocratico"]
        assert not burocraticos, (texto["id"], burocraticos)


def test_rotulos_esperados_por_grupo(corpus):
    densos = 0
    for texto in corpus["textos"]:
        esperado = texto["esperado"]
        if texto["grupo"] == "vazamento":
            assert esperado == {"vazamento": True, "acima_do_limite": None}, texto["id"]
        elif texto["grupo"] == "sinal":
            assert esperado["vazamento"] is False, texto["id"]
            # Pesos são da H4 (D5): sinal isolado não tem rótulo de limite; o denso (várias categorias) passa dele.
            assert esperado["acima_do_limite"] in (None, True), texto["id"]
            if esperado["acima_do_limite"] is True:
                assert len(texto["categorias"]) >= 3, texto["id"]
                densos += 1
            else:
                assert len(texto["categorias"]) == 1, texto["id"]
        else:
            assert esperado == {"vazamento": False, "acima_do_limite": False}, texto["id"]
            assert len(texto["categorias"]) == 1, texto["id"]
    assert densos >= MIN_DENSOS


def test_tons_e_canais_validos(corpus):
    for texto in corpus["textos"]:
        assert texto["canal"] in CANAIS, texto["id"]
        assert texto["tom"] in TONS, texto["id"]
    textos = corpus["textos"]
    assert {t["tom"] for t in textos} == TONS and {t["canal"] for t in textos} == CANAIS
    # Emoji no ar é vazamento; no WhatsApp a regra é outra (armadilha emoji_espelhado).
    assert all(t["canal"] == "ao_vivo" for t in textos if "emoji" in t["categorias"])
    assert all(t["canal"] == "patrocinio" for t in textos if "folheto" in t["categorias"])


def test_sequencias_e_detector_de_estrutura_da_f8(corpus):
    from app.live.formatos import ids_aceitos
    from app.live.memoria import repeticao_estrutura
    from scripts.simulacao.metricas import CONFIG_METRICAS

    seguidas = CONFIG_METRICAS["repeticao_estrutura"]["seguidas"]
    declaradas = set(corpus["regras"]["categorias_sequencia"])
    assert len(corpus["sequencias"]) >= 7
    for sequencia in corpus["sequencias"]:
        assert set(sequencia["categorias"]) <= declaradas, sequencia["id"]
        assert sequencia["formato"] in ids_aceitos(), sequencia["id"]
        inicios = [f["inicio_s"] for f in sequencia["falas"]]
        assert len(inicios) >= 2 and inicios == sorted(inicios), sequencia["id"]
        textos = [f["texto"] for f in sequencia["falas"]]
        esperado = sequencia["esperado"]
        assert esperado["repeticao_estrutura"] == repeticao_estrutura(textos, seguidas), sequencia["id"]
        for bordao in sequencia["bordoes"]:
            assert any(bordao.lower() in t.lower() for t in textos), (sequencia["id"], bordao)
        if esperado["bordao_repetido"]:
            assert sequencia["bordoes"], sequencia["id"]
    usadas = {c for s in corpus["sequencias"] for c in s["categorias"]}
    assert usadas == declaradas
    regra = corpus["regras"]["bordao"]
    assert (regra["janela_s"], regra["maximo"]) == (CONFIG_METRICAS["humanizacao"]["bordao"]["janela_s"],
                                                    CONFIG_METRICAS["humanizacao"]["bordao"]["maximo"])


def _strings_do_atendimento() -> list[str]:
    """Frases fixas de app/whatsapp/atendimento.py (constantes e partes fixas de f-string), pela árvore do código."""
    arvore = ast.parse((BACKEND / "app" / "whatsapp" / "atendimento.py").read_text(encoding="utf-8"))
    frases = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            frases += [p.strip() for p in re.split(r"[.;?]", no.value)]
    return [f for f in frases if len(f) >= 25 and " " in f]


def test_corpus_nao_copia_as_respostas_fixas_do_atendimento(corpus):
    """As respostas fixas do WhatsApp mudam na H6 (D7): a linha de base as cita por referência, não no corpus."""
    frases = _strings_do_atendimento()
    assert frases
    textos = [t["texto"] for t in corpus["textos"]] + [f["texto"] for s in corpus["sequencias"] for f in s["falas"]]
    for frase in frases:
        assert not any(frase in texto for texto in textos), frase
