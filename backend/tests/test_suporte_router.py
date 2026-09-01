def test_chat_responde_usando_llm(client, account, auth_headers, monkeypatch):
    capturado = {}

    def _gerar(system_prompt, historico):
        capturado["system_prompt"] = system_prompt
        capturado["historico"] = historico
        return "Pra conectar o WhatsApp, vai em Conta > WhatsApp e escaneia o QR code."

    monkeypatch.setattr("app.suporte.router.gerar_resposta_chat", _gerar)

    resposta = client.post(
        "/suporte/chat",
        json={"mensagem": "como conecto o whatsapp?", "historico": []},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert "WhatsApp" in resposta.json()["resposta"]
    assert capturado["historico"][-1] == {"role": "user", "content": "como conecto o whatsapp?"}


def test_chat_envia_historico_recente_pro_llm(client, account, auth_headers, monkeypatch):
    capturado = {}

    def _gerar(system_prompt, historico):
        capturado["historico"] = historico
        return "ok"

    monkeypatch.setattr("app.suporte.router.gerar_resposta_chat", _gerar)

    resposta = client.post(
        "/suporte/chat",
        json={
            "mensagem": "e quanto custa?",
            "historico": [
                {"role": "user", "content": "quero saber dos planos"},
                {"role": "assistant", "content": "temos Starter, Growth e Professional"},
            ],
        },
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert len(capturado["historico"]) == 3
    assert capturado["historico"][0]["content"] == "quero saber dos planos"


def test_chat_exige_autenticacao(client):
    resposta = client.post("/suporte/chat", json={"mensagem": "oi", "historico": []})
    assert resposta.status_code == 401


def test_chat_falha_do_llm_devolve_502(client, account, auth_headers, monkeypatch):
    def _falha(system_prompt, historico):
        raise RuntimeError("timeout")

    monkeypatch.setattr("app.suporte.router.gerar_resposta_chat", _falha)

    resposta = client.post(
        "/suporte/chat",
        json={"mensagem": "oi", "historico": []},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 502


def test_chat_respeita_rate_limit(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr("app.suporte.router.gerar_resposta_chat", lambda system_prompt, historico: "ok")
    monkeypatch.setattr("app.suporte.router.limite_excedido", lambda chave, limite, janela_segundos=60: True)

    resposta = client.post(
        "/suporte/chat",
        json={"mensagem": "oi", "historico": []},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 429
