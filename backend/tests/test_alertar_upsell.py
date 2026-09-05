import datetime

import pytest
from sqlalchemy.orm import sessionmaker

import app.billing.alertar_upsell as alertar_upsell_module
from app.auth.security import hash_senha
from app.billing.limites import mes_referencia_atual
from app.models.account import Account
from app.models.interaction_log import InteractionLog
from app.models.notificacao import Notificacao
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.usuario import Usuario


@pytest.fixture(autouse=True)
def _sessionlocal_de_teste(db_session, monkeypatch):
    # mesmo motivo do test_alertar_desconexao.py: o script usa SessionLocal proprio, fora do
    # ciclo de request/get_db do FastAPI -- aponta pro mesmo engine sqlite em memoria da suite.
    fabrica = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr(alertar_upsell_module, "SessionLocal", fabrica)


def _conta_consolidada_com_admin(db_session, **kwargs) -> Account:
    account = Account(wuzapi_token="tok-1", **kwargs)
    db_session.add(account)
    db_session.flush()
    db_session.add(
        Usuario(nome="Admin", email="admin@example.com", senha_hash=hash_senha("senha12345"), account_id=account.id, role="admin")
    )
    rc = RadioConfig(account_id=account.id, ativo=True, voz_id="voz-1")
    db_session.add(rc)
    db_session.flush()
    db_session.add(
        Programa(
            radio_config_id=rc.id,
            nome="Manha",
            horario_inicio=datetime.time(8, 0),
            horario_fim=datetime.time(10, 0),
            ativo=True,
        )
    )
    db_session.commit()
    db_session.refresh(account)
    return account


def test_conta_sem_sinal_nao_envia_nada(db_session):
    _conta_consolidada_com_admin(db_session, plano="growth", plano_status="ativo", agentes_extras=5)
    assert alertar_upsell_module.verificar_gatilhos_upsell() == 0
    assert db_session.query(Notificacao).count() == 0


def test_conta_nao_consolidada_ignora_mesmo_com_uso_alto(db_session):
    # sem WhatsApp conectado -- ainda em onboarding, upsell aqui seria ruido.
    account = Account(plano="starter", plano_status="ativo")
    db_session.add(account)
    db_session.commit()
    assert alertar_upsell_module.verificar_gatilhos_upsell() == 0


def test_agentes_cheio_envia_notificacao_e_email(db_session, monkeypatch):
    account = _conta_consolidada_com_admin(db_session, plano="starter", plano_status="ativo")
    account_id = account.id

    enviados = []
    import app.notificacoes.service as notificacoes_service

    monkeypatch.setattr(
        notificacoes_service,
        "enviar_email_notificacao",
        lambda email, nome, titulo, mensagem: enviados.append(email) or True,
    )

    assert alertar_upsell_module.verificar_gatilhos_upsell() == 1

    notificacao = db_session.query(Notificacao).filter_by(tipo="upsell").first()
    assert notificacao is not None
    assert notificacao.titulo == "Seus radialistas bateram o limite do plano"
    assert enviados == ["admin@example.com"]

    db_session.expire_all()
    atualizada = db_session.get(Account, account_id)
    assert atualizada.upsell_alerta_tipo == "agentes_cheio"
    assert atualizada.upsell_alerta_mes == mes_referencia_atual()


def test_nao_reenvia_mesmo_sinal_no_mesmo_mes(db_session, monkeypatch):
    account = _conta_consolidada_com_admin(
        db_session,
        plano="starter",
        plano_status="ativo",
        upsell_alerta_tipo="agentes_cheio",
        upsell_alerta_mes=mes_referencia_atual(),
    )

    import app.notificacoes.service as notificacoes_service

    enviados = []
    monkeypatch.setattr(
        notificacoes_service,
        "enviar_email_notificacao",
        lambda email, nome, titulo, mensagem: enviados.append(email) or True,
    )

    assert alertar_upsell_module.verificar_gatilhos_upsell() == 0
    assert db_session.query(Notificacao).filter_by(tipo="upsell").count() == 0
    assert enviados == []


def test_sinal_some_destrava_o_alerta(db_session):
    account = _conta_consolidada_com_admin(
        db_session,
        plano="growth",
        plano_status="ativo",
        agentes_extras=5,
        upsell_alerta_tipo="mensagens_quase_estourando",
        upsell_alerta_mes=mes_referencia_atual(),
    )
    account_id = account.id

    assert alertar_upsell_module.verificar_gatilhos_upsell() == 0

    db_session.expire_all()
    atualizada = db_session.get(Account, account_id)
    assert atualizada.upsell_alerta_tipo is None
    assert atualizada.upsell_alerta_mes is None


def test_alerta_leve_nao_manda_email(db_session, monkeypatch):
    from app.planos import limites_do_plano

    account = _conta_consolidada_com_admin(db_session, plano="growth", plano_status="ativo", agentes_extras=5)
    rc = db_session.query(RadioConfig).filter_by(account_id=account.id).first()
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

    import app.notificacoes.service as notificacoes_service

    enviados = []
    monkeypatch.setattr(
        notificacoes_service,
        "enviar_email_notificacao",
        lambda email, nome, titulo, mensagem: enviados.append(email) or True,
    )

    assert alertar_upsell_module.verificar_gatilhos_upsell() == 1
    assert enviados == []
    notificacao = db_session.query(Notificacao).filter_by(tipo="upsell").first()
    assert notificacao.titulo == "Seu plano esta perto do limite de mensagens"


def test_ignora_conta_trial(db_session):
    db_session.add(Account(wuzapi_token="tok-1", plano="starter", plano_status="trial"))
    db_session.commit()
    assert alertar_upsell_module.verificar_gatilhos_upsell() == 0
