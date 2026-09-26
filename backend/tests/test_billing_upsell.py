import datetime

from app.billing.consolidacao import marca_consolidada
from app.billing.upsell import calcular_sinal_upsell
from app.models.compra_excedente import CompraExcedente
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.planos import limites_do_plano


def _radio_config(db_session, account_id, *, ativo=True, voz_id="voz-1"):
    rc = RadioConfig(account_id=account_id, ativo=ativo, voz_id=voz_id)
    db_session.add(rc)
    db_session.commit()
    db_session.refresh(rc)
    return rc


def _programa(db_session, radio_config_id, *, ativo=True):
    programa = Programa(
        radio_config_id=radio_config_id,
        nome="Manha",
        horario_inicio=datetime.time(8, 0),
        horario_fim=datetime.time(10, 0),
        ativo=ativo,
    )
    db_session.add(programa)
    db_session.commit()
    return programa


def _conta_consolidada(db_session, account_factory, **kwargs):
    account = account_factory(email="a@a.com", wuzapi_token="tok-1", **kwargs)
    rc = _radio_config(db_session, account.id)
    _programa(db_session, rc.id)
    return account, rc


class TestMarcaConsolidada:
    def test_sem_whatsapp_nao_consolidada(self, db_session, account_factory):
        account = account_factory(email="a@a.com", wuzapi_token=None)
        _radio_config(db_session, account.id)
        assert marca_consolidada(db_session, account) is False

    def test_sem_radialista_pronto_nao_consolidada(self, db_session, account_factory):
        account = account_factory(email="a@a.com", wuzapi_token="tok-1")
        assert marca_consolidada(db_session, account) is False

    def test_radialista_sem_voz_nao_consolidada(self, db_session, account_factory):
        account = account_factory(email="a@a.com", wuzapi_token="tok-1")
        _radio_config(db_session, account.id, voz_id=None)
        assert marca_consolidada(db_session, account) is False

    def test_sem_programa_ativo_nao_consolidada(self, db_session, account_factory):
        account = account_factory(email="a@a.com", wuzapi_token="tok-1")
        rc = _radio_config(db_session, account.id)
        _programa(db_session, rc.id, ativo=False)
        assert marca_consolidada(db_session, account) is False

    def test_com_tudo_pronto_consolidada(self, db_session, account_factory):
        account, _ = _conta_consolidada(db_session, account_factory)
        assert marca_consolidada(db_session, account) is True


def test_limite_financeiro_proximo_avisa_sem_oferta_de_pacotes(db_session, account):
    from app.models.consumo_flex import ContaConsumo
    db_session.add(ContaConsumo(account_id=account.id, limite=10000000, exposicao=9000000))
    db_session.commit()
    sinal = calcular_sinal_upsell(db_session, account)
    assert sinal.tipo == 'limite_financeiro'
    assert sinal.enviar_email is False


def test_sem_exposicao_nao_oferece_upgrade(db_session, account):
    assert calcular_sinal_upsell(db_session, account) is None
