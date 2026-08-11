import json

from app.llm.intent import classificar_intencao
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


def _config():
    return RadioConfig(nome_locutor="Ze do Radio", timezone="America/Sao_Paulo")


def _programa(generos_musicais=None, musicas_permitidas=None):
    return Programa(
        nome="Programa Teste",
        generos_musicais=generos_musicais or [],
        musicas_permitidas=musicas_permitidas or [],
    )


def test_classifica_pedido_de_musica(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "musica", "musica_query": "Legiao Urbana"}),
    )
    acao, musica_query = classificar_intencao(_config(), _programa(), "toca uma musica da legiao urbana")
    assert acao == "musica"
    assert musica_query == "Legiao Urbana"


def test_classifica_pedido_de_abraco(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "abraco", "musica_query": None}),
    )
    acao, musica_query = classificar_intencao(_config(), _programa(), "manda um alo pra mim")
    assert acao == "abraco"
    assert musica_query is None


def test_classifica_como_guardar_por_padrao(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "guardar", "musica_query": None}),
    )
    acao, musica_query = classificar_intencao(_config(), _programa(), "vocês são ótimos")
    assert acao == "guardar"
    assert musica_query is None


def test_resposta_com_acao_invalida_cai_no_fallback_guardar(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "dancar", "musica_query": None}),
    )
    acao, musica_query = classificar_intencao(_config(), _programa(), "oi")
    assert acao == "guardar"
    assert musica_query is None


def test_resposta_nao_json_cai_no_fallback_guardar(monkeypatch):
    monkeypatch.setattr("app.llm.intent.gerar_classificacao", lambda system, user: "isso nao e json")
    acao, musica_query = classificar_intencao(_config(), _programa(), "oi")
    assert acao == "guardar"
    assert musica_query is None


def test_excecao_no_llm_cai_no_fallback_guardar(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha de rede")

    monkeypatch.setattr("app.llm.intent.gerar_classificacao", _levanta)
    acao, musica_query = classificar_intencao(_config(), _programa(), "oi")
    assert acao == "guardar"
    assert musica_query is None


def test_musica_query_vazia_vira_none(monkeypatch):
    monkeypatch.setattr(
        "app.llm.intent.gerar_classificacao",
        lambda system, user: json.dumps({"acao": "musica", "musica_query": ""}),
    )
    acao, musica_query = classificar_intencao(_config(), _programa(), "toca algo ai")
    assert acao == "musica"
    assert musica_query is None


def test_estilos_permitidos_vao_pro_prompt_quando_programa_restringe(monkeypatch):
    prompts_capturados = {}

    def _fake(system, user):
        prompts_capturados["system"] = system
        return json.dumps({"acao": "musica", "musica_query": "Roberto Carlos"})

    monkeypatch.setattr("app.llm.intent.gerar_classificacao", _fake)
    classificar_intencao(_config(), _programa(generos_musicais=["sertanejo", "forro"]), "toca sertanejo")
    assert "sertanejo" in prompts_capturados["system"]
    assert "forro" in prompts_capturados["system"]


def test_sem_restricao_configurada_prompt_nao_menciona_estilos(monkeypatch):
    prompts_capturados = {}

    def _fake(system, user):
        prompts_capturados["system"] = system
        return json.dumps({"acao": "musica", "musica_query": "qualquer coisa"})

    monkeypatch.setattr("app.llm.intent.gerar_classificacao", _fake)
    classificar_intencao(_config(), _programa(), "toca uma musica")
    assert "SO' toca musica dentro" not in prompts_capturados["system"]


def test_prompt_instrui_ignorar_mensagem_sem_nexo_ou_acidental(monkeypatch):
    prompts_capturados = {}

    def _fake(system, user):
        prompts_capturados["system"] = system
        return json.dumps({"acao": "guardar", "musica_query": None})

    monkeypatch.setattr("app.llm.intent.gerar_classificacao", _fake)
    classificar_intencao(_config(), _programa(), "kkjshdf musica alo??")
    assert "sem querer" in prompts_capturados["system"]
    assert "CONTEXTO" in prompts_capturados["system"]
