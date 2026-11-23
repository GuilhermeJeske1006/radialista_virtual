"""Revisão humana de falas (F12): roteamento na /proxima, substituta neutra, decisão dentro do prazo."""

import datetime

import pytest
from freezegun import freeze_time

from app.live.revisao import FALAS_SUBSTITUTAS, RevisaoInvalida, decidir, prazo_para, substituta
from app.models.fala_em_revisao import FalaEmRevisao
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from tests.test_live_router import _url_proxima

AGORA = datetime.datetime(2026, 8, 10, 15, 0, tzinfo=datetime.timezone.utc)  # 12:00 local, programa 10-14
FALA_PROIBIDA = "Hoje a conversa é sobre a Operação Teste na cidade."


@pytest.fixture()
def programa_com_topico(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Programa Principal", horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0), estrutura_blocos=[], topicos_proibidos=["Operação Teste"],
    )
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


def test_prazo_e_vinte_minutos_depois_da_geracao():
    assert prazo_para(AGORA) == AGORA + datetime.timedelta(minutes=20)


def test_decisao_dentro_do_prazo_aprova_ou_rejeita():
    prazo = AGORA + datetime.timedelta(minutes=20)
    assert decidir("aguardando_revisao", prazo, AGORA, "aprovar") == "aprovada"
    assert decidir("aguardando_revisao", prazo, AGORA, "rejeitar") == "rejeitada"


def test_decisao_fora_do_prazo_recusada():
    prazo = AGORA + datetime.timedelta(minutes=20)
    with pytest.raises(RevisaoInvalida):
        decidir("aguardando_revisao", prazo, prazo + datetime.timedelta(seconds=1), "aprovar")


def test_fala_ja_decidida_nao_muda_de_novo():
    prazo = AGORA + datetime.timedelta(minutes=20)
    with pytest.raises(RevisaoInvalida):
        decidir("aprovada", prazo, AGORA, "rejeitar")


def test_acao_fora_do_contrato_levanta_valueerror():
    with pytest.raises(ValueError):
        decidir("aguardando_revisao", AGORA, AGORA, "publicar")


def test_substituta_nunca_vem_vazia_e_gira():
    assert all(substituta(i).strip() for i in range(10))
    assert substituta(0) == FALAS_SUBSTITUTAS[0]
    assert substituta(len(FALAS_SUBSTITUTAS)) == FALAS_SUBSTITUTAS[0]


@freeze_time("2026-08-10 15:00:00")
def test_topico_proibido_troca_fala_por_substituta_e_guarda_o_original(
    client, account, auth_headers, programa_com_topico, db_session, monkeypatch
):
    radio_config, programa = programa_com_topico
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: FALA_PROIBIDA)
    resposta = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": [], "total_falas": 0},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["fala"] in FALAS_SUBSTITUTAS
    linha = db_session.query(FalaEmRevisao).filter_by(programa_id=programa.id).one()
    assert linha.texto == FALA_PROIBIDA
    assert linha.estado == "bloqueado"
    assert linha.prazo_em is None


@freeze_time("2026-08-10 15:00:00")
def test_fala_bloqueada_nao_leva_o_audio_do_texto_original(
    client, account, auth_headers, programa_com_topico, db_session, monkeypatch
):
    """Com incluir_audio (caminho do preparo antecipado), o áudio sintetizado é do texto original. A resposta
    não pode carregar esse áudio junto com a substituta: o player tocaria a fala barrada."""
    from tests.test_live_validacao_proxima import _mp3

    radio_config, programa = programa_com_topico
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: FALA_PROIBIDA)
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    sinteses: list[str] = []
    monkeypatch.setattr("app.live.router.sintetizar_audio",
                        lambda texto, *a, **k: sinteses.append(texto) or _mp3(5.0))
    resposta = client.post(_url_proxima(radio_config.id, programa.id),
                           json={"historico": [], "total_falas": 0, "incluir_audio": True},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert sinteses, "o teste precisa passar pela síntese embutida"
    assert corpo["fala"] in FALAS_SUBSTITUTAS
    assert corpo["audio_base64"] is None
    assert corpo["audios_falas_base64"] is None
    assert corpo["audio_status"] == "pendente"  # o player sintetiza a substituta pelo /tts
    assert corpo["duracao_fala_s"] is None


@freeze_time("2026-08-10 15:00:00")
def test_fala_normal_segue_sem_revisao(client, account, auth_headers, programa_com_topico, db_session, monkeypatch):
    radio_config, programa = programa_com_topico
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Bom dia, pessoal da rádio.")
    resposta = client.post(_url_proxima(radio_config.id, programa.id), json={"historico": [], "total_falas": 0},
                           headers=auth_headers(account.id))
    assert resposta.json()["fala"] == "Bom dia, pessoal da rádio."
    assert db_session.query(FalaEmRevisao).filter_by(programa_id=programa.id).count() == 0


def test_api_lista_e_rejeita_fora_do_prazo(client, account, auth_headers, programa_com_topico, db_session):
    radio_config, programa = programa_com_topico
    linha = FalaEmRevisao(account_id=account.id, programa_id=programa.id, categoria="plantao", texto="x",
                          rota="revisao", motivo="revisao", estado="aguardando_revisao",
                          criado_em=AGORA, prazo_em=AGORA + datetime.timedelta(minutes=20))
    db_session.add(linha)
    db_session.commit()
    url = f"/config/programas/{programa.id}/falas-revisao"
    listada = client.get(f"{url}?estado=aguardando_revisao", headers=auth_headers(account.id)).json()
    assert [f["id"] for f in listada] == [linha.id]
    # Sem freeze_time o relógio real é de 2026+ (muito depois do prazo de 2026-08-10): recusa com 409.
    recusada = client.post(f"{url}/{linha.id}/aprovar", headers=auth_headers(account.id))
    assert recusada.status_code == 409


def test_api_fala_inexistente_404(client, account, auth_headers, programa_com_topico):
    _, programa = programa_com_topico
    resposta = client.post(f"/config/programas/{programa.id}/falas-revisao/999/rejeitar",
                           headers=auth_headers(account.id))
    assert resposta.status_code == 404
