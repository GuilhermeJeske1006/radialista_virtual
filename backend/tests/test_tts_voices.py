from app.models.voz_clonada import VozClonada
from app.tts import voices as tts_voices
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


def test_listar_vozes_com_preview_enriquece_catalogo(monkeypatch):
    tts_voices._preview_cache.clear()
    monkeypatch.setattr(tts_voices, "obter_preview_url", lambda voz_id: f"https://preview/{voz_id}.mp3")

    vozes = tts_voices.listar_vozes_com_preview()

    assert len(vozes) == len(VOZES_DISPONIVEIS)
    assert all(v["preview_url"] == f"https://preview/{v['voz_id']}.mp3" for v in vozes)


def test_listar_vozes_com_preview_tolera_falha(monkeypatch):
    tts_voices._preview_cache.clear()
    monkeypatch.setattr(tts_voices, "obter_preview_url", lambda voz_id: None)

    vozes = tts_voices.listar_vozes_com_preview()

    assert all(v["preview_url"] is None for v in vozes)


def test_listar_vozes_com_preview_usa_cache_em_chamadas_seguintes(monkeypatch):
    tts_voices._preview_cache.clear()
    chamadas = []

    def _fake(voz_id):
        chamadas.append(voz_id)
        return f"https://preview/{voz_id}.mp3"

    monkeypatch.setattr(tts_voices, "obter_preview_url", _fake)

    tts_voices.listar_vozes_com_preview()
    tts_voices.listar_vozes_com_preview()

    assert len(chamadas) == len(VOZES_DISPONIVEIS)
