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
