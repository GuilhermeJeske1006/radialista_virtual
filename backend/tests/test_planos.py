from app.planos import PLANO_PADRAO, PLANOS, limites_do_plano


def test_limites_do_plano_conhecido():
    limites = limites_do_plano("growth")
    assert limites.agentes == 3
    assert limites.clonagem_voz is True


def test_limites_do_plano_desconhecido_cai_no_padrao():
    assert limites_do_plano("plano-inexistente") == PLANOS[PLANO_PADRAO]


def test_starter_nao_tem_clonagem_de_voz():
    assert limites_do_plano("starter").clonagem_voz is False


def test_professional_tem_mais_agentes_que_growth():
    assert limites_do_plano("professional").agentes > limites_do_plano("growth").agentes
