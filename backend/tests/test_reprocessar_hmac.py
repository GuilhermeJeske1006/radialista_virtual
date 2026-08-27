import httpx
import pytest
from sqlalchemy.orm import sessionmaker

import app.onboarding.reprocessar_hmac as reprocessar_hmac_module
from app.models.account import Account


@pytest.fixture(autouse=True)
def _sessionlocal_de_teste(db_session, monkeypatch):
    # o script usa SessionLocal proprio (fora do ciclo de request/get_db do FastAPI) --
    # aponta pro mesmo engine sqlite em memoria do db_session da suite.
    fabrica = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr(reprocessar_hmac_module, "SessionLocal", fabrica)


def test_ignora_conta_sem_wuzapi_token(db_session, monkeypatch):
    db_session.add(Account(wuzapi_token=None, wuzapi_hmac_key=None))
    db_session.commit()

    chamadas = []
    monkeypatch.setattr(
        reprocessar_hmac_module, "configurar_hmac", lambda token, chave: chamadas.append(token)
    )

    assert reprocessar_hmac_module.reprocessar_contas_sem_hmac() == 0
    assert chamadas == []


def test_ignora_conta_que_ja_tem_hmac(db_session, monkeypatch):
    db_session.add(Account(wuzapi_token="tok-1", wuzapi_hmac_key="ja-configurada"))
    db_session.commit()

    chamadas = []
    monkeypatch.setattr(
        reprocessar_hmac_module, "configurar_hmac", lambda token, chave: chamadas.append(token)
    )

    assert reprocessar_hmac_module.reprocessar_contas_sem_hmac() == 0
    assert chamadas == []


def test_configura_hmac_para_conta_pendente(db_session, monkeypatch):
    account = Account(wuzapi_token="tok-pendente", wuzapi_hmac_key=None)
    db_session.add(account)
    db_session.commit()
    account_id = account.id

    monkeypatch.setattr(reprocessar_hmac_module, "configurar_hmac", lambda token, chave: {})

    corrigidas = reprocessar_hmac_module.reprocessar_contas_sem_hmac()

    assert corrigidas == 1
    db_session.expire_all()
    atualizada = db_session.get(Account, account_id)
    assert atualizada.wuzapi_hmac_key is not None


def test_mantem_pendente_quando_wuzapi_falha(db_session, monkeypatch):
    account = Account(wuzapi_token="tok-com-falha", wuzapi_hmac_key=None)
    db_session.add(account)
    db_session.commit()
    account_id = account.id

    def _falha(token, chave):
        requisicao = httpx.Request("POST", "http://wuzapi.local/session/hmac/config")
        raise httpx.HTTPStatusError("erro", request=requisicao, response=httpx.Response(500, request=requisicao))

    monkeypatch.setattr(reprocessar_hmac_module, "configurar_hmac", _falha)

    corrigidas = reprocessar_hmac_module.reprocessar_contas_sem_hmac()

    assert corrigidas == 0
    db_session.expire_all()
    atualizada = db_session.get(Account, account_id)
    assert atualizada.wuzapi_hmac_key is None
