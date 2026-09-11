from app.topics.espelho import (
    ORIGENS_PERECIVEIS,
    ajustar_score,
    formatar_registro,
    parsear_registro,
)


def test_registro_compacto_faz_round_trip():
    bruto = formatar_registro(42, "fato", "noticia", "transito")
    registro = parsear_registro(bruto)
    assert registro is not None
    assert registro.assunto_id == 42
    assert registro.eixo == "fato"
    assert registro.origem == "noticia"
    assert registro.tag_principal == "transito"


def test_registro_sanitiza_pipe_nos_campos_livres():
    bruto = formatar_registro(1, "fato", "notic|ia", "tag|ruim")
    registro = parsear_registro(bruto)
    assert registro is not None
    assert "|" not in registro.origem
    assert "|" not in registro.tag_principal


def test_parsear_registro_invalido_devolve_none():
    assert parsear_registro("lixo-sem-formato") is None
    assert parsear_registro("1|2|3") is None


def test_quota_de_origem_penaliza_terceira_vez_seguida_da_mesma_origem():
    """Fase F: 2 assuntos seguidos da mesma origem ja' e' o limite -- um terceiro candidato da
    mesma origem que os dois ultimos usados deve sair penalizado (nao bloqueado)."""
    historico = [
        parsear_registro(formatar_registro(1, "fato", "noticia", "transito")),
        parsear_registro(formatar_registro(2, "impacto", "noticia", "clima")),
    ]
    score_mesma_origem = ajustar_score(5.0, origem="noticia", tag_principal="seguranca", historico=historico)
    score_origem_diferente = ajustar_score(5.0, origem="musica", tag_principal="memoria", historico=historico)

    assert score_mesma_origem < 5.0
    assert score_origem_diferente == 5.0


def test_tag_saturada_na_janela_penaliza():
    historico = [
        parsear_registro(formatar_registro(1, "fato", "noticia", "transito")),
        parsear_registro(formatar_registro(2, "impacto", "musica", "transito")),
        parsear_registro(formatar_registro(3, "memoria", "ouvinte", "transito")),
    ]
    score = ajustar_score(5.0, origem="reserva", tag_principal="transito", historico=historico)
    assert score < 5.0


def test_permanente_ganha_bonus_quando_quatro_pereciveis_seguidos():
    # Origens pereciveis ALTERNADAS (nao repete a mesma duas vezes seguidas) pra isolar a regra
    # de proporcao (Fase F, ultimos 4) da regra de "nao repita a mesma origem 2x seguidas" --
    # as duas sao independentes e um historico com 4x a mesma origem dispararia as duas juntas.
    historico = [
        parsear_registro(formatar_registro(1, "fato", "noticia", "tag1")),
        parsear_registro(formatar_registro(2, "impacto", "efemeride", "tag2")),
        parsear_registro(formatar_registro(3, "fato", "noticia", "tag3")),
        parsear_registro(formatar_registro(4, "impacto", "efemeride", "tag4")),
    ]
    assert all(r.origem in ORIGENS_PERECIVEIS for r in historico)

    score_permanente = ajustar_score(5.0, origem="musica", tag_principal="memoria", historico=historico)
    score_perecivel = ajustar_score(5.0, origem="noticia", tag_principal="outra", historico=historico)

    assert score_permanente > 5.0
    assert score_perecivel == 5.0
