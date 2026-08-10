import json

from app.llm.intent import classificar_intencao
from app.models.radio_config import RadioConfig


def _config():
    return RadioConfig(nome_locutor="Ze do Radio", timezone="America/Sao_Paulo")


def test_classifica_pedido_de_musica(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "musica", "musica_query": "Legiao Urbana"}),
    )
    acao, musica_query = classificar_intencao(_config(), "toca uma musica da legiao urbana")
    assert acao == "musica"
    assert musica_query == "Legiao Urbana"


def test_classifica_pedido_de_abraco(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "abraco", "musica_query": None}),
    )
    acao, musica_query = classificar_intencao(_config(), "manda um alo pra mim")
    assert acao == "abraco"
    assert musica_query is None


def test_classifica_como_guardar_por_padrao(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "guardar", "musica_query": None}),
    )
    acao, musica_query = classificar_intencao(_config(), "vocês são ótimos")
    assert acao == "guardar"
    assert musica_query is None


def test_resposta_com_acao_invalida_cai_no_fallback_guardar(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "dancar", "musica_query": None}),
    )
    acao, musica_query = classificar_intencao(_config(), "oi")
    assert acao == "guardar"
    assert musica_query is None


def test_resposta_nao_json_cai_no_fallback_guardar(monkeypatch):
    monkeypatch.setattr("app.llm.intent.gerar_classificacao", lambda system, user: "isso nao e json")
    acao, musica_query = classificar_intencao(_config(), "oi")
    assert acao == "guardar"
    assert musica_query is None


def test_excecao_no_llm_cai_no_fallback_guardar(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha de rede")

    monkeypatch.setattr("app.llm.intent.gerar_classificacao", _levanta)
    acao, musica_query = classificar_intencao(_config(), "oi")
    assert acao == "guardar"
    assert musica_query is None


def test_musica_query_vazia_vira_none(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "musica", "musica_query": ""}),
    )
    acao, musica_query = classificar_intencao(_config(), "toca algo ai")
    assert acao == "musica"
    assert musica_query is None
