import datetime

import pytest

from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics import reserva


@pytest.fixture()
def programa(db_session, account):
    account.cidade = "Blumenau"
    db_session.commit()
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Sertanejo da Manha",
        horario_inicio=datetime.time(5, 0), horario_fim=datetime.time(8, 0),
        generos_musicais=["sertanejo"], tom="animado e proximo",
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def test_briefing_deriva_publico_quando_publico_alvo_vazio(db_session, account, programa):
    assert programa.publico_alvo == ""

    briefing = reserva.montar_briefing_publico(db_session, programa, account)

    assert "trabalhador" in briefing or "cedo" in briefing
    assert "sertanejo" in briefing
    assert "Blumenau" in briefing


def test_briefing_usa_publico_alvo_quando_preenchido(db_session, account, programa):
    programa.publico_alvo = "donas de casa entre 30 e 50 anos"
    db_session.commit()

    briefing = reserva.montar_briefing_publico(db_session, programa, account)

    assert briefing == "donas de casa entre 30 e 50 anos"


def test_gerar_reserva_semanal_grava_assuntos_e_casamento(db_session, account, programa, monkeypatch):
    resposta = (
        '[{"titulo": "Expressao regional", "gancho": "de onde vem esse jeito de falar", '
        '"tags": ["curiosidade"], "pergunta_ouvinte": ""}, '
        '{"titulo": "Pergunta do dia", "gancho": "qual musica marcou sua infancia", '
        '"tags": ["memoria"], "pergunta_ouvinte": "qual foi a primeira musica que voce aprendeu?"}]'
    )
    monkeypatch.setattr("app.topics.reserva.gerar_classificacao", lambda system, msg, **_: resposta)

    gravados = reserva.gerar_reserva_semanal(db_session, programa, account)

    assert gravados == 2
    assuntos = db_session.query(Assunto).filter_by(origem="reserva").all()
    assert len(assuntos) == 2
    assert all(a.validade_ate is None for a in assuntos)
    casamentos = db_session.query(AssuntoPrograma).filter_by(programa_id=programa.id).all()
    assert len(casamentos) == 2
    assert all(ap.eixos_sugeridos == [] for ap in casamentos)


def test_gerar_reserva_semanal_nao_regenera_dentro_da_janela(db_session, account, programa, monkeypatch):
    chamadas = []

    def _fake(system, msg, **_):
        chamadas.append(1)
        return '[{"titulo": "X", "gancho": "Y", "tags": [], "pergunta_ouvinte": ""}]'
    monkeypatch.setattr("app.topics.reserva.gerar_classificacao", _fake)

    reserva.gerar_reserva_semanal(db_session, programa, account)
    segunda = reserva.gerar_reserva_semanal(db_session, programa, account)

    assert segunda == 0
    assert len(chamadas) == 1


def test_gerar_reserva_semanal_com_forcar_ignora_marcador(db_session, account, programa, monkeypatch):
    monkeypatch.setattr(
        "app.topics.reserva.gerar_classificacao",
        lambda system, msg, **_: '[{"titulo": "X", "gancho": "Y", "tags": [], "pergunta_ouvinte": ""}]',
    )

    reserva.gerar_reserva_semanal(db_session, programa, account)
    segunda = reserva.gerar_reserva_semanal(db_session, programa, account, forcar=True)

    assert segunda == 1
