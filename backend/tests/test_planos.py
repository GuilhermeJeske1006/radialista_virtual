from app.planos import PLANO_PADRAO, PLANOS, limites_do_plano, PRECO_POR_PLANO


def test_oferta_unica_flex():
    assert set(PLANOS) == {'flex'}
    assert PLANO_PADRAO == 'flex'
    assert PRECO_POR_PLANO['flex'] == 69.9
    assert limites_do_plano('flex').clonagem_voz


def test_identificador_antigo_nao_cria_outro_regime():
    assert limites_do_plano('starter') == limites_do_plano('flex')
    assert limites_do_plano('professional') == limites_do_plano('flex')
