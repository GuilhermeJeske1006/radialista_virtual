import datetime

import pytest

from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


@pytest.fixture()
def programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Programa",
        horario_inicio=datetime.time(6, 0), horario_fim=datetime.time(9, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def _casar(db_session, account, programa, *, score=5.0, titulo="Chuva forte"):
    assunto = Assunto(
        account_id=account.id, origem="noticia", titulo=titulo, gancho="gancho qualquer",
        fatos=["fato"], tags=["servico"], peso_base=5.0,
    )
    db_session.add(assunto)
    db_session.flush()
    ap = AssuntoPrograma(assunto_id=assunto.id, programa_id=programa.id, score=score, ponte="briefing", eixos_sugeridos=["fato"])
    db_session.add(ap)
    db_session.commit()
    return assunto, ap


def test_listar_pauta_do_dia(client, account, auth_headers, db_session, programa):
    _assunto, ap = _casar(db_session, account, programa)

    resposta = client.get(f"/topics/programas/{programa.id}/pauta", headers=auth_headers(account.id))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["id"] == ap.id
    assert corpo[0]["titulo"] == "Chuva forte"
    assert corpo[0]["ponte"] == "briefing"


def test_listar_pauta_ordena_por_score_desc(client, account, auth_headers, db_session, programa):
    _casar(db_session, account, programa, score=2.0, titulo="Baixo score")
    _casar(db_session, account, programa, score=9.0, titulo="Alto score")

    resposta = client.get(f"/topics/programas/{programa.id}/pauta", headers=auth_headers(account.id))

    titulos = [item["titulo"] for item in resposta.json()]
    assert titulos == ["Alto score", "Baixo score"]


def test_listar_pauta_de_outra_conta_nao_aparece(client, account, account_factory, auth_headers, db_session, programa):
    outra_conta = account_factory(email="outra@example.com")
    resposta = client.get(f"/topics/programas/{programa.id}/pauta", headers=auth_headers(outra_conta.id))

    assert resposta.status_code == 404


def test_fixar_assunto_aumenta_o_score(client, account, auth_headers, db_session, programa):
    _assunto, ap = _casar(db_session, account, programa, score=5.0)

    resposta = client.post(f"/topics/programas/{programa.id}/pauta/{ap.id}/fixar", headers=auth_headers(account.id))

    assert resposta.status_code == 200
    assert resposta.json()["score"] > 5.0

    db_session.refresh(ap)
    assert ap.score > 5.0


def test_descartar_assunto_remove_da_pauta(client, account, auth_headers, db_session, programa):
    _assunto, ap = _casar(db_session, account, programa)

    resposta = client.delete(f"/topics/programas/{programa.id}/pauta/{ap.id}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    listagem = client.get(f"/topics/programas/{programa.id}/pauta", headers=auth_headers(account.id))
    assert listagem.json() == []


def test_fixar_assunto_de_outro_programa_404(client, account, auth_headers, db_session, programa):
    outro_programa = Programa(
        radio_config_id=programa.radio_config_id, nome="Outro",
        horario_inicio=datetime.time(9, 0), horario_fim=datetime.time(12, 0),
    )
    db_session.add(outro_programa)
    db_session.commit()
    _assunto, ap = _casar(db_session, account, outro_programa)

    resposta = client.post(f"/topics/programas/{programa.id}/pauta/{ap.id}/fixar", headers=auth_headers(account.id))

    assert resposta.status_code == 404
