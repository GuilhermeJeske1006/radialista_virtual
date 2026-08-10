import datetime

from app.billing.limites import (
    limite_agentes_efetivo,
    limite_mensagens_efetivo,
    limite_radialistas_por_programa,
    mensagens_extras_do_mes,
    mensagens_respondidas_no_mes,
    mes_referencia_atual,
)
from app.models.compra_excedente import CompraExcedente
from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig
from app.planos import limites_do_plano


def test_limite_agentes_efetivo_soma_extras(account_factory):
    account = account_factory(email="a@a.com", plano="starter", agentes_extras=2)
    assert limite_agentes_efetivo(account) == limites_do_plano("starter").agentes + 2


def test_limite_radialistas_por_programa_reflete_plano(account_factory):
    account = account_factory(email="a@a.com", plano="professional")
    assert limite_radialistas_por_programa(account) == limites_do_plano("professional").radialistas_por_programa


def test_mensagens_extras_do_mes_soma_compras_do_mes_atual(db_session, account_factory):
    account = account_factory(email="a@a.com")
    db_session.add(
        CompraExcedente(account_id=account.id, quantidade=1000, mes_referencia=mes_referencia_atual())
    )
    db_session.add(
        CompraExcedente(account_id=account.id, quantidade=2000, mes_referencia=mes_referencia_atual())
    )
    db_session.add(CompraExcedente(account_id=account.id, quantidade=5000, mes_referencia="2000-01"))
    db_session.commit()

    assert mensagens_extras_do_mes(db_session, account.id) == 3000


def test_mensagens_extras_do_mes_sem_compras_e_zero(db_session, account_factory):
    account = account_factory(email="a@a.com")
    assert mensagens_extras_do_mes(db_session, account.id) == 0


def test_limite_mensagens_efetivo_soma_extras(db_session, account_factory):
    account = account_factory(email="a@a.com", plano="starter")
    db_session.add(
        CompraExcedente(account_id=account.id, quantidade=1000, mes_referencia=mes_referencia_atual())
    )
    db_session.commit()

    esperado = limites_do_plano("starter").mensagens_mes + 1000
    assert limite_mensagens_efetivo(db_session, account) == esperado


def _log(radio_config_id, status, origem="ouvinte", criado_em=None):
    return InteractionLog(
        radio_config_id=radio_config_id,
        telefone="5511999999999",
        mensagem_usuario="oi",
        status=status,
        origem=origem,
        criado_em=criado_em or datetime.datetime.now(datetime.timezone.utc),
    )


def test_mensagens_respondidas_no_mes_conta_so_fila_musica_e_abraco(db_session, account_factory):
    account = account_factory(email="a@a.com")
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()

    db_session.add_all(
        [
            _log(radio_config.id, "fila_musica"),
            _log(radio_config.id, "fila_abraco"),
            _log(radio_config.id, "guardado"),
            _log(radio_config.id, "bloqueado_horario"),
            _log(radio_config.id, "fila_musica", origem="radio"),
        ]
    )
    db_session.commit()

    assert mensagens_respondidas_no_mes(db_session, account.id) == 2


def test_mensagens_respondidas_no_mes_ignora_mes_anterior(db_session, account_factory):
    account = account_factory(email="a@a.com")
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()

    mes_passado = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)
    db_session.add(_log(radio_config.id, "fila_musica", criado_em=mes_passado))
    db_session.commit()

    assert mensagens_respondidas_no_mes(db_session, account.id) == 0
