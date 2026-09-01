import httpx
import pytest
from sqlalchemy.orm import sessionmaker

import app.onboarding.alertar_desconexao as alertar_desconexao_module
from app.models.account import Account
from app.models.notificacao import Notificacao
from app.models.usuario import Usuario


@pytest.fixture(autouse=True)
def _sessionlocal_de_teste(db_session, monkeypatch):
    # o script usa SessionLocal proprio (fora do ciclo de request/get_db do FastAPI) --
    # aponta pro mesmo engine sqlite em memoria do db_session da suite.
    fabrica = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr(alertar_desconexao_module, "SessionLocal", fabrica)


def _conta_com_admin(db_session, **kwargs) -> Account:
    from app.auth.security import hash_senha

    account = Account(wuzapi_token="tok-1", **kwargs)
    db_session.add(account)
    db_session.flush()
    db_session.add(
        Usuario(nome="Admin", email="admin@example.com", senha_hash=hash_senha("senha12345"), account_id=account.id, role="admin")
    )
    db_session.commit()
    db_session.refresh(account)
    return account


def test_ignora_conta_sem_wuzapi_token(db_session, monkeypatch):
    db_session.add(Account(wuzapi_token=None))
    db_session.commit()

    chamadas = []
    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", lambda token: chamadas.append(token))

    assert alertar_desconexao_module.verificar_desconexoes() == 0
    assert chamadas == []


def test_sessao_conectada_nao_envia_alerta(db_session, monkeypatch):
    _conta_com_admin(db_session)
    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", lambda token: {"data": {"loggedIn": True}})

    enviados = []
    monkeypatch.setattr(
        alertar_desconexao_module, "enviar_email_alerta_desconexao", lambda email, nome: enviados.append(email)
    )

    assert alertar_desconexao_module.verificar_desconexoes() == 0
    assert enviados == []


def test_sessao_desconectada_envia_alerta_e_marca_flag(db_session, monkeypatch):
    account = _conta_com_admin(db_session)
    account_id = account.id
    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", lambda token: {"data": {"loggedIn": False}})

    enviados = []
    monkeypatch.setattr(
        alertar_desconexao_module, "enviar_email_alerta_desconexao", lambda email, nome: enviados.append(email) or True
    )

    assert alertar_desconexao_module.verificar_desconexoes() == 1
    assert enviados == ["admin@example.com"]

    db_session.expire_all()
    atualizada = db_session.get(Account, account_id)
    assert atualizada.wuzapi_desconectado_alerta_enviado is True

    notificacao = db_session.query(Notificacao).filter_by(tipo="whatsapp").first()
    assert notificacao is not None
    assert notificacao.titulo == "WhatsApp desconectado"


def test_nao_reenvia_alerta_enquanto_continua_desconectada(db_session, monkeypatch):
    _conta_com_admin(db_session, wuzapi_desconectado_alerta_enviado=True)
    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", lambda token: {"data": {"loggedIn": False}})

    enviados = []
    monkeypatch.setattr(
        alertar_desconexao_module, "enviar_email_alerta_desconexao", lambda email, nome: enviados.append(email) or True
    )

    assert alertar_desconexao_module.verificar_desconexoes() == 0
    assert enviados == []


def test_reconexao_destrava_o_alerta(db_session, monkeypatch):
    account = _conta_com_admin(db_session, wuzapi_desconectado_alerta_enviado=True)
    account_id = account.id
    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", lambda token: {"data": {"loggedIn": True}})

    assert alertar_desconexao_module.verificar_desconexoes() == 0

    db_session.expire_all()
    atualizada = db_session.get(Account, account_id)
    assert atualizada.wuzapi_desconectado_alerta_enviado is False


def test_ignora_conta_sem_admin_ativo(db_session, monkeypatch):
    account = Account(wuzapi_token="tok-sem-admin")
    db_session.add(account)
    db_session.commit()
    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", lambda token: {"data": {"loggedIn": False}})

    enviados = []
    monkeypatch.setattr(
        alertar_desconexao_module, "enviar_email_alerta_desconexao", lambda email, nome: enviados.append(email) or True
    )

    assert alertar_desconexao_module.verificar_desconexoes() == 0
    assert enviados == []


def test_falha_ao_consultar_status_e_ignorada(db_session, monkeypatch):
    _conta_com_admin(db_session)

    def _falha(token):
        requisicao = httpx.Request("GET", "http://wuzapi.local/session/status")
        raise httpx.HTTPStatusError("erro", request=requisicao, response=httpx.Response(500, request=requisicao))

    monkeypatch.setattr(alertar_desconexao_module, "obter_status_sessao", _falha)

    assert alertar_desconexao_module.verificar_desconexoes() == 0
