import json

from app.topics.derivador import derivar_ganchos


def test_derivador_devolve_insuficiente_e_nao_inventa_gancho(monkeypatch):
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda system, msg, **_: "insuficiente")
    assert derivar_ganchos("texto vago sem fato nenhum") == []


def test_derivador_extrai_ganchos_do_json(monkeypatch):
    resposta = (
        '[{"titulo": "Chuva e trabalho", "gancho": "quem trabalha na rua leva capa", '
        '"fatos": ["chuva forte a tarde"], "tags": ["servico", "trabalho"], "pergunta_ouvinte": ""}, '
        '{"titulo": "Chuva e mar", "gancho": "pesca afetada", "fatos": ["mar agitado"], '
        '"tags": ["praia"], "pergunta_ouvinte": "como ta o mar ai?"}]'
    )
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda system, msg, **_: resposta)

    ganchos = derivar_ganchos("Defesa Civil preve chuva forte a tarde")

    assert len(ganchos) == 2
    assert ganchos[0].titulo == "Chuva e trabalho"
    assert ganchos[0].tags == ["servico", "trabalho"]
    assert ganchos[1].pergunta_ouvinte == "como ta o mar ai?"


def test_derivador_ignora_item_sem_gancho_ou_titulo(monkeypatch):
    resposta = '[{"titulo": "", "gancho": "algo", "fatos": [], "tags": []}, {"titulo": "ok", "gancho": "", "fatos": []}]'
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda system, msg, **_: resposta)

    assert derivar_ganchos("qualquer coisa") == []


def test_derivador_json_invalido_devolve_lista_vazia(monkeypatch):
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda system, msg, **_: "isso nao e json")
    assert derivar_ganchos("qualquer coisa") == []


def test_derivador_falha_de_llm_nao_propaga_excecao(monkeypatch):
    def _explode(*a, **k):
        raise RuntimeError("timeout")
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", _explode)
    assert derivar_ganchos("qualquer coisa") == []


def test_derivador_separa_notas_editoriais_dos_fatos_da_fonte(monkeypatch):
    resposta = [{"titulo": "Biblioteca", "gancho": "Novo horário da biblioteca",
                 "fatos": ["Abre às oito"], "familia": "vida_pratica", "recorte": "Organizar uma visita",
                 "abordagens": ["Conveniência do novo horário", "Como encaixar uma visita no dia"],
                 "contextos": ["Programa da manhã"], "tags": ["cultura"]}]
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda *args, **kwargs: json.dumps(resposta))
    gancho = derivar_ganchos("A biblioteca abre às oito")[0]
    assert gancho.fatos == ["Abre às oito"]
    assert gancho.repertorio["abordagens"] == resposta[0]["abordagens"]


def test_derivador_tolera_tipos_incorretos_do_modelo(monkeypatch):
    resposta = [{"titulo": "Válido", "gancho": "Recorte", "tags": "texto", "fatos": "não é lista", "familia": []},
                {"titulo": ["inválido"], "gancho": "Recorte"}]
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda *args, **kwargs: json.dumps(resposta))
    ganchos = derivar_ganchos("Fonte")
    assert len(ganchos) == 1
    assert ganchos[0].fatos == []
    assert ganchos[0].tags == []
