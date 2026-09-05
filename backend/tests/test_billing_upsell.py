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


class TestCalcularSinalUpsell:
    def test_conta_nao_consolidada_sem_sinal(self, db_session, account_factory):
        account = account_factory(email="a@a.com", wuzapi_token=None, plano="starter")
        assert calcular_sinal_upsell(db_session, account) is None

    def test_agentes_no_limite_sinaliza_e_manda_email(self, db_session, account_factory):
        account, _ = _conta_consolidada(db_session, account_factory, plano="starter")
        # starter permite 1 agente -- o unico radio_config ja criado em _conta_consolidada preenche o limite.
        sinal = calcular_sinal_upsell(db_session, account)
        assert sinal is not None
        assert sinal.tipo == "agentes_cheio"
        assert sinal.enviar_email is True

    def test_agentes_extras_afastam_o_limite(self, db_session, account_factory):
        account, _ = _conta_consolidada(db_session, account_factory, plano="starter", agentes_extras=1)
        assert calcular_sinal_upsell(db_session, account) is None

    def test_mensagens_estourando_sinaliza_e_manda_email(self, db_session, account_factory):
        account, rc = _conta_consolidada(db_session, account_factory, plano="growth", agentes_extras=5)
        limite = limites_do_plano("growth").mensagens_mes
        for _ in range(limite):
            db_session.add(
                InteractionLog(
                    radio_config_id=rc.id,
                    telefone="5511999999999",
                    mensagem_usuario="oi",
                    status="respondido_whatsapp",
                    origem="ouvinte",
                    criado_em=datetime.datetime.now(datetime.timezone.utc),
                )
            )
        db_session.commit()

        sinal = calcular_sinal_upsell(db_session, account)
        assert sinal is not None
        assert sinal.tipo == "mensagens_estourou"
        assert sinal.enviar_email is True

    def test_mensagens_perto_do_limite_sinaliza_sem_email(self, db_session, account_factory):
        account, rc = _conta_consolidada(db_session, account_factory, plano="growth", agentes_extras=5)
        limite = limites_do_plano("growth").mensagens_mes
        quantidade = int(limite * 0.85)
        for _ in range(quantidade):
            db_session.add(
                InteractionLog(
                    radio_config_id=rc.id,
                    telefone="5511999999999",
                    mensagem_usuario="oi",
                    status="respondido_whatsapp",
                    origem="ouvinte",
                    criado_em=datetime.datetime.now(datetime.timezone.utc),
                )
            )
        db_session.commit()

        sinal = calcular_sinal_upsell(db_session, account)
        assert sinal is not None
        assert sinal.tipo == "mensagens_quase_estourando"
        assert sinal.enviar_email is False

    def test_uso_confortavel_sem_sinal(self, db_session, account_factory):
        account, _ = _conta_consolidada(db_session, account_factory, plano="growth", agentes_extras=5)
        assert calcular_sinal_upsell(db_session, account) is None

    def test_excedente_comprado_soma_no_limite_de_mensagens(self, db_session, account_factory):
        from app.billing.limites import mes_referencia_atual

        account, rc = _conta_consolidada(db_session, account_factory, plano="starter", agentes_extras=5)
        db_session.add(
            CompraExcedente(account_id=account.id, quantidade=5000, mes_referencia=mes_referencia_atual())
        )
        db_session.commit()

        # sem as 5000 extras o plano starter (2000) ja estaria zerado; com elas, uso 0 fica confortavel.
        assert calcular_sinal_upsell(db_session, account) is None
