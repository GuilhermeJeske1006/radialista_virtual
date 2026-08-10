from app.guardrails.rate_limiter import dentro_do_limite


def test_primeira_mensagem_fica_dentro_do_limite():
    assert dentro_do_limite("token1", "5511999999999", limite_por_hora=3) is True


def test_mensagens_dentro_do_limite_passam():
    for _ in range(3):
        assert dentro_do_limite("token1", "5511999999999", limite_por_hora=3) is True


def test_mensagem_que_excede_limite_e_bloqueada():
    for _ in range(3):
        dentro_do_limite("token1", "5511999999999", limite_por_hora=3)
    assert dentro_do_limite("token1", "5511999999999", limite_por_hora=3) is False


def test_limite_e_por_telefone_e_por_token():
    for _ in range(3):
        dentro_do_limite("token1", "5511999999999", limite_por_hora=3)

    assert dentro_do_limite("token1", "5511888888888", limite_por_hora=3) is True
    assert dentro_do_limite("token2", "5511999999999", limite_por_hora=3) is True
