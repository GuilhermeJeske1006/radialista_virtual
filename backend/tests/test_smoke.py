def test_health(client):
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_registro_e_login(client):
    resposta = client.post(
        "/auth/register",
        json={"nome": "Fulano", "email": "fulano@example.com", "senha": "senha12345"},
    )
    assert resposta.status_code == 200
    assert "access_token" in resposta.json()

    resposta = client.post(
        "/auth/login", json={"email": "fulano@example.com", "senha": "senha12345"}
    )
    assert resposta.status_code == 200
