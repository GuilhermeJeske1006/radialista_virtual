"""Conjunto de geração da humanização (H0; docs/humanizacao/h0/auditoria.md §5.2 e §6, itens 4 e 9).

60 entradas, 10 por tipo, cada uma nos dois tons (DH0-1): 120 casos. O conjunto ainda não tem executor (H3: ao vivo, uma
fala por entrada; H6: adaptador de scripts/conversa_teste.py). Aqui se confere o formato: cada entrada, em cada tom,
vira uma fixture válida do simulador (`FixturePrograma`), e uma delas passa por uma hora fake sem rede (fumaça).
"""

import collections
import json
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
CONJUNTO = BACKEND.parent / "docs" / "benchmarks" / "2026-11-23-humanizacao" / "casos.json"
DIR_PROGRAMAS = BACKEND / "tests" / "fixtures" / "programas"

TIPOS = ("recado", "pedido_musica", "aniversario", "clima_transito", "patrocinio_lido", "whatsapp")
POR_TIPO = 10
TONS = ["formal", "informal"]
PERFIS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
TELEFONE_RE = re.compile(r"^55000000030\d{2}$")
# Chave do WhatsApp que não é campo de FixturePrograma: a mesma do roteiro.json lido por scripts/conversa_teste.py.
CHAVES_FORA_DA_FIXTURE = {"mensagens_ouvinte"}
# Dicionários da fixture mesclados chave a chave (o resto substitui).
MESCLA_RASA = ("programa", "conta")


@pytest.fixture(scope="module")
def conjunto():
    return json.loads(CONJUNTO.read_text(encoding="utf-8"))


def _mesclar(base: dict, camada: dict) -> dict:
    resultado = dict(base)
    for chave, valor in camada.items():
        if chave in CHAVES_FORA_DA_FIXTURE:
            continue
        if chave in MESCLA_RASA:
            resultado[chave] = {**resultado.get(chave, {}), **valor}
        else:
            resultado[chave] = valor
    return resultado


def _fixture_do_caso(conjunto: dict, caso: dict, tom: str) -> dict:
    """Fixture do formato com a persona do tom, a `entrada` e o `por_tom[tom]` por cima (regras.mescla)."""
    base = json.loads((DIR_PROGRAMAS / f"{caso['formato']}.json").read_text(encoding="utf-8"))
    persona = conjunto["regras"]["tons"][tom]["persona"]
    dados = _mesclar(base, {"programa": {"persona": persona}})
    dados = _mesclar(dados, caso["entrada"])
    return _mesclar(dados, (caso.get("por_tom") or {}).get(tom) or {})


def _pedidos(caso: dict) -> list[dict]:
    camadas = [caso["entrada"], *(caso.get("por_tom") or {}).values()]
    return [p for camada in camadas for p in camada.get("pedidos") or []]


def test_esquema_e_contagens(conjunto):
    assert {"versao", "fonte", "regras", "casos"} == set(conjunto)
    regras = conjunto["regras"]
    assert {"tipos", "canais", "tons", "mescla", "esperado", "dimensoes", "executor", "observacao"} <= set(regras)
    assert tuple(regras["tipos"]) == TIPOS
    casos = conjunto["casos"]
    assert len(casos) == len(TIPOS) * POR_TIPO
    assert collections.Counter(c["tipo"] for c in casos) == {t: POR_TIPO for t in TIPOS}
    assert len({c["id"] for c in casos}) == len(casos)
    chaves = {"id", "tipo", "canal", "formato", "bloco", "tons", "entrada", "por_tom", "especificos", "criterio",
              "dimensoes"}
    for caso in casos:
        assert chaves <= set(caso) <= chaves | {"musica_indisponivel"}, caso["id"]
        assert caso["formato"] in PERFIS, caso["id"]
        assert caso["canal"] == regras["canais"][caso["tipo"]], caso["id"]
        assert caso["criterio"].strip(), caso["id"]
        assert "soa_como_pessoa" in caso["dimensoes"], caso["id"]
        assert set(caso["dimensoes"]) <= set(regras["dimensoes"]), caso["id"]
    assert {c["formato"] for c in casos} == set(PERFIS)


def test_telefones_unicos_e_ficticios(conjunto):
    telefones = [p["telefone"] for caso in conjunto["casos"] for p in _pedidos(caso)]
    assert telefones
    assert all(TELEFONE_RE.match(t) for t in telefones), telefones
    assert len(telefones) == len(set(telefones))


def test_tons_sao_os_dois_e_a_persona_e_valida(conjunto):
    from app.live.persona import persona_ou_none

    tons = conjunto["regras"]["tons"]
    assert list(tons) == TONS
    # DH0-2: formalidade 4 (formal) e 2 (informal), nas fronteiras da D2.
    assert persona_ou_none(tons["formal"]["persona"]).formalidade == 4
    assert persona_ou_none(tons["informal"]["persona"]).formalidade == 2
    for caso in conjunto["casos"]:
        assert caso["tons"] == TONS, caso["id"]
        assert set(caso["por_tom"]) <= set(TONS), caso["id"]


def test_cada_entrada_em_cada_tom_vira_fixture_do_simulador(conjunto):
    from app.live.persona import persona_ou_none
    from app.models.programa import Programa
    from scripts.simulacao.fixtures import FixturePrograma

    colunas = set(Programa.__table__.columns.keys())
    validados = 0
    for caso in conjunto["casos"]:
        for camada in [caso["entrada"], *caso["por_tom"].values()]:
            assert set(camada) - CHAVES_FORA_DA_FIXTURE <= set(FixturePrograma.model_fields), caso["id"]
        for tom in caso["tons"]:
            fixture = FixturePrograma.model_validate(_fixture_do_caso(conjunto, caso, tom))
            assert set(fixture.programa) <= colunas, (caso["id"], set(fixture.programa) - colunas)
            persona = persona_ou_none(fixture.programa["persona"])
            assert persona.formalidade == conjunto["regras"]["tons"][tom]["persona"]["formalidade"]
            validados += 1
    assert validados == 2 * len(TIPOS) * POR_TIPO


def test_pedido_de_musica_resolve_no_catalogo_do_formato(conjunto):
    from scripts.simulacao.fixtures import carregar_catalogo, carregar_fixture

    indisponiveis = 0
    for caso in (c for c in conjunto["casos"] if c["tipo"] == "pedido_musica"):
        catalogo = carregar_catalogo(carregar_fixture(caso["formato"]).catalogo)
        pedidos = [p for p in _pedidos(caso) if p["tipo"] == "musica"]
        assert pedidos, caso["id"]
        for pedido in pedidos:
            faixa = next((f for f in catalogo.faixas if f.titulo == pedido["musica_query"]), None)
            assert faixa is not None, (caso["id"], pedido["musica_query"])
            assert caso.get("musica_indisponivel", False) is faixa.indisponivel, caso["id"]
        indisponiveis += bool(caso.get("musica_indisponivel"))
    # Duas entradas pedem faixa indisponível, para exercitar a substituição.
    assert indisponiveis == 2


def test_recado_e_aniversario_sao_abraco_de_recado_comum(conjunto):
    for caso in (c for c in conjunto["casos"] if c["tipo"] in ("recado", "aniversario")):
        pedidos = _pedidos(caso)
        assert pedidos and all(p["tipo"] == "abraco" and p["natureza"] == "recado_comum" for p in pedidos), caso["id"]
        assert caso["bloco"] == "chamada_ouvinte", caso["id"]


def test_clima_e_transito_vem_como_dado_verificavel(conjunto):
    for caso in (c for c in conjunto["casos"] if c["tipo"] == "clima_transito"):
        entrada = caso["entrada"]
        transito = [n for n in entrada.get("noticias") or [] if n["categoria"] == "transito"]
        assert entrada.get("clima") or transito, caso["id"]
        # Sem cidade, o backend não busca clima; sem dose de notícia, a notícia não entra no bloco (padrão da F5).
        if entrada.get("clima"):
            assert entrada["conta"]["cidade"], caso["id"]
        if transito:
            assert entrada["programa"]["dose_noticia"] != "nenhuma", caso["id"]


def test_patrocinio_tem_um_texto_por_tom(conjunto):
    for caso in (c for c in conjunto["casos"] if c["tipo"] == "patrocinio_lido"):
        textos = []
        for tom in TONS:
            patrocinadores = caso["por_tom"][tom]["patrocinadores"]
            assert len(patrocinadores) == 1 and patrocinadores[0]["tipo_conteudo"] == "texto", caso["id"]
            assert caso["bloco"] == f"patrocinador:@{patrocinadores[0]['chave']}", caso["id"]
            textos.append(patrocinadores[0]["texto"])
        assert textos[0] != textos[1], caso["id"]


def test_whatsapp_tem_mensagem_do_ouvinte_por_tom(conjunto):
    for caso in (c for c in conjunto["casos"] if c["tipo"] == "whatsapp"):
        assert caso["canal"] == "whatsapp"
        for tom in TONS:
            mensagens = caso["por_tom"][tom]["mensagens_ouvinte"]
            assert mensagens and all(isinstance(m, str) and m.strip() for m in mensagens), caso["id"]
        assert caso["por_tom"]["formal"]["mensagens_ouvinte"] != caso["por_tom"]["informal"]["mensagens_ouvinte"]


def test_especificos_estao_na_entrada(conjunto):
    """`especificos`: o dado concreto que a fala precisa citar (cita_especifico) vem da própria entrada."""
    for caso in conjunto["casos"]:
        assert caso["especificos"], caso["id"]
        fonte = json.dumps([caso["entrada"], caso["por_tom"]], ensure_ascii=False)
        for especifico in caso["especificos"]:
            assert especifico in fonte, (caso["id"], especifico)


def test_fumaca_uma_entrada_no_simulador_sem_rede(conjunto):
    from scripts.simular_hora import simular
    from scripts.simulacao.fixtures import Pedido, carregar_fixture

    caso = next(c for c in conjunto["casos"] if c["id"] == "recado-01")
    assert caso["formato"] == "popular_sertanejo"
    extras = [Pedido(**p) for p in caso["entrada"]["pedidos"]]
    resultado = simular("popular_sertanejo", pedidos_extra=extras)
    base = len(carregar_fixture("popular_sertanejo").pedidos)
    assert resultado.resumo["pedidos"]["recebidos"] == base + len(extras) == 5
    assert resultado.resumo["tentativas_rede"] == 0 and resultado.resumo["erros_http"] == 0
