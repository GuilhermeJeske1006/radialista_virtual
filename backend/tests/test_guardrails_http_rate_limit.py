from app.guardrails.http_rate_limit import limite_excedido


def test_nao_excede_dentro_do_limite():
    for _ in range(5):
        assert limite_excedido("chave1", limite=5) is False


def test_excede_apos_limite():
    for _ in range(5):
        limite_excedido("chave1", limite=5)
    assert limite_excedido("chave1", limite=5) is True


def test_chaves_diferentes_tem_contadores_independentes():
    for _ in range(5):
        limite_excedido("chave1", limite=5)
    assert limite_excedido("chave2", limite=5) is False
