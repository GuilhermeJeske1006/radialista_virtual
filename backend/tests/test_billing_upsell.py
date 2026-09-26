from app.billing.upsell import calcular_sinal_upsell


def test_limite_financeiro_proximo_avisa_sem_oferta_de_pacotes(db_session, account):
    from app.models.consumo_flex import ContaConsumo
    db_session.add(ContaConsumo(account_id=account.id, limite=10000000, exposicao=9000000))
    db_session.commit()
    sinal = calcular_sinal_upsell(db_session, account)
    assert sinal.tipo == 'limite_financeiro'
    assert sinal.enviar_email is False


def test_sem_exposicao_nao_oferece_upgrade(db_session, account):
    assert calcular_sinal_upsell(db_session, account) is None
