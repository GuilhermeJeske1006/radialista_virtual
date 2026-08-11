from types import SimpleNamespace

from app.llm import client as llm_client


def _block(texto):
    return SimpleNamespace(type="text", text=texto)


def test_gerar_resposta_devolve_texto_do_primeiro_bloco(monkeypatch):
    resposta_fake = SimpleNamespace(stop_reason="end_turn", content=[_block("Oi, tudo bem?")])
    monkeypatch.setattr(
        llm_client._client.messages, "create", lambda **kwargs: resposta_fake
    )
    assert llm_client.gerar_resposta("system", "user") == "Oi, tudo bem?"


def test_gerar_resposta_com_refusal_devolve_mensagem_padrao(monkeypatch):
    resposta_fake = SimpleNamespace(stop_reason="refusal", content=[])
    monkeypatch.setattr(llm_client._client.messages, "create", lambda **kwargs: resposta_fake)
    resultado = llm_client.gerar_resposta("system", "user")
    assert "nao posso responder" in resultado.lower() or "não posso responder" in resultado.lower()


def test_gerar_resposta_sem_bloco_de_texto_devolve_fallback(monkeypatch):
    resposta_fake = SimpleNamespace(stop_reason="end_turn", content=[])
    monkeypatch.setattr(llm_client._client.messages, "create", lambda **kwargs: resposta_fake)
    resultado = llm_client.gerar_resposta("system", "user")
    assert "tenta de novo" in resultado.lower()


def test_gerar_classificacao_devolve_texto(monkeypatch):
    resposta_fake = SimpleNamespace(content=[_block("musica")])
    monkeypatch.setattr(llm_client._client.messages, "create", lambda **kwargs: resposta_fake)
    assert llm_client.gerar_classificacao("system", "user") == "musica"


def test_gerar_classificacao_sem_bloco_devolve_string_vazia(monkeypatch):
    resposta_fake = SimpleNamespace(content=[])
    monkeypatch.setattr(llm_client._client.messages, "create", lambda **kwargs: resposta_fake)
    assert llm_client.gerar_classificacao("system", "user") == ""


def test_gerar_configuracao_com_refusal_devolve_string_vazia(monkeypatch):
    resposta_fake = SimpleNamespace(stop_reason="refusal", content=[])
    monkeypatch.setattr(llm_client._client.messages, "create", lambda **kwargs: resposta_fake)
    assert llm_client.gerar_configuracao("system", "user") == ""


def test_classificar_categoria_bloco_reconhece_categoria_valida(monkeypatch):
    monkeypatch.setattr(llm_client, "gerar_classificacao", lambda system, user: "musica")
    assert llm_client.classificar_categoria_bloco("Musica Vaneira") == "musica"


def test_classificar_categoria_bloco_cai_em_outro_por_padrao(monkeypatch):
    monkeypatch.setattr(llm_client, "gerar_classificacao", lambda system, user: "nada disso")
    assert llm_client.classificar_categoria_bloco("bloco esquisito") == "outro"


def test_classificar_categoria_bloco_excecao_cai_em_outro(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha")

    monkeypatch.setattr(llm_client, "gerar_classificacao", _levanta)
    assert llm_client.classificar_categoria_bloco("qualquer coisa") == "outro"


def test_classificar_tom_fala_reconhece_tom_valido(monkeypatch):
    monkeypatch.setattr(llm_client, "gerar_classificacao", lambda system, user: "energico")
    assert llm_client.classificar_tom_fala("vamos la!", "abertura") == "energico"


def test_classificar_tom_fala_cai_em_neutro_por_padrao(monkeypatch):
    monkeypatch.setattr(llm_client, "gerar_classificacao", lambda system, user: "resposta esquisita")
    assert llm_client.classificar_tom_fala("...", None) == "neutro"


def test_classificar_tom_fala_excecao_cai_em_neutro(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha")

    monkeypatch.setattr(llm_client, "gerar_classificacao", _levanta)
    assert llm_client.classificar_tom_fala("texto", "comentario") == "neutro"


def test_resumir_contexto_musica_devolve_resumo(monkeypatch):
    monkeypatch.setattr(
        llm_client, "gerar_classificacao", lambda system, user: "Fala sobre saudade do interior, lancada em 1998."
    )
    resultado = llm_client.resumir_contexto_musica("Musica X", "Artista Y", "descricao real", ["sertanejo"], "1998")
    assert resultado == "Fala sobre saudade do interior, lancada em 1998."


def test_resumir_contexto_musica_insuficiente_devolve_vazio(monkeypatch):
    monkeypatch.setattr(llm_client, "gerar_classificacao", lambda system, user: "insuficiente")
    resultado = llm_client.resumir_contexto_musica("Musica X", "Artista Y", "", [], None)
    assert resultado == ""


def test_resumir_contexto_musica_excecao_devolve_vazio(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha")

    monkeypatch.setattr(llm_client, "gerar_classificacao", _levanta)
    resultado = llm_client.resumir_contexto_musica("Musica X", "Artista Y", "descricao", [], None)
    assert resultado == ""
