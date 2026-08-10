from app.models.voz_clonada import VozClonada
from app.tts.voices import VOZES_DISPONIVEIS, voz_valida, voz_valida_para_conta


def test_voz_valida_aceita_voz_do_catalogo():
    assert voz_valida(VOZES_DISPONIVEIS[0]["voz_id"]) is True


def test_voz_valida_rejeita_voz_desconhecida():
    assert voz_valida("voz-que-nao-existe") is False


def test_voz_valida_para_conta_aceita_catalogo(db_session, account_factory):
    account = account_factory(email="a@a.com")
    assert voz_valida_para_conta(db_session, account.id, VOZES_DISPONIVEIS[0]["voz_id"]) is True


def test_voz_valida_para_conta_aceita_voz_clonada_da_propria_conta(db_session, account_factory):
    account = account_factory(email="a@a.com")
    db_session.add(VozClonada(account_id=account.id, nome="Minha voz", voz_id="voz-clonada-1"))
    db_session.commit()

    assert voz_valida_para_conta(db_session, account.id, "voz-clonada-1") is True


def test_voz_valida_para_conta_rejeita_voz_clonada_de_outra_conta(db_session, account_factory):
    dono = account_factory(email="dono@a.com")
    outro = account_factory(email="outro@a.com")
    db_session.add(VozClonada(account_id=dono.id, nome="Minha voz", voz_id="voz-clonada-1"))
    db_session.commit()

    assert voz_valida_para_conta(db_session, outro.id, "voz-clonada-1") is False


def test_voz_valida_para_conta_rejeita_voz_desconhecida(db_session, account_factory):
    account = account_factory(email="a@a.com")
    assert voz_valida_para_conta(db_session, account.id, "voz-inexistente") is False
