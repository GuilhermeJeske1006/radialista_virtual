import datetime
import hashlib
import hmac
import json

import pytest
from freezegun import freeze_time

from app.models.fila_ao_vivo import FilaAoVivo
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

# Mesma janela usada em test_guardrails_schedule.py: 2026-08-10 15:00 UTC ==
# 2026-08-10 12:00 America/Sao_Paulo (segunda-feira), dentro do programa 10:00-14:00.
AGORA_UTC = "2026-08-10 15:00:00"


@pytest.fixture(autouse=True)
def _sem_espera_debounce(monkeypatch):
    """O webhook espera _DEBOUNCE_SEGUNDOS (6s) de silencio antes de agir --
    sem isso cada teste que chega a esse ponto do fluxo levaria 6s de verdade."""
    import asyncio

    async def _sleep_imediato(segundos):
        return None

    monkeypatch.setattr(asyncio, "sleep", _sleep_imediato)


@pytest.fixture()
def conta_no_ar(db_session, account_factory):
    account = account_factory(
        email="radio@a.com", wuzapi_token="wuzapi-token-1", wuzapi_user_id="user-123"
    )
    radio_config = RadioConfig(account_id=account.id, ativo=True, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Principal",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        limite_mensagens_hora=1000,
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(account)
    db_session.refresh(radio_config)
    return account, radio_config, programa


def _payload(
    user_id="user-123",
    texto="ola, tudo bem?",
    telefone="5511999999999@s.whatsapp.net",
    from_me=False,
    message_id="msg-1",
    push_name="Fulano",
    audio=False,
):
    info = {"Chat": telefone, "FromMe": from_me, "ID": message_id, "PushName": push_name}
    mensagem = {"audioMessage": {"url": "https://example.com/audio.ogg"}} if audio else {"conversation": texto}
    payload = {"userID": user_id, "event": {"Info": info, "Message": mensagem}}
    if audio:
        payload["base64"] = "ZmFrZS1hdWRpby1ieXRlcw=="
    return payload


def _post_webhook(client, payload, headers=None):
    return client.post(
        "/webhook/whatsapp", content=json.dumps(payload).encode(), headers=headers or {}
    )


@freeze_time(AGORA_UTC)
def test_conta_desconhecida_e_ignorada(client):
    resposta = _post_webhook(client, _payload(user_id="user-desconhecido"))
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}


@freeze_time(AGORA_UTC)
def test_payload_sem_texto_nem_userid_e_ignorado(client):
    resposta = client.post("/webhook/whatsapp", content=json.dumps({"foo": "bar"}).encode())
    assert resposta.json() == {"status": "ignorado"}


@freeze_time(AGORA_UTC)
def test_mensagem_from_me_apenas_registra_log(client, conta_no_ar, db_session):
    account, radio_config, _ = conta_no_ar
    resposta = _post_webhook(client, _payload(from_me=True, message_id="msg-radio-1"))
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "origem": "radio"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-radio-1").first()
    assert log is not None
    assert log.origem == "radio"
    assert log.status == "enviada"


@freeze_time(AGORA_UTC)
def test_mensagem_duplicada_e_ignorada(client, conta_no_ar):
    _post_webhook(client, _payload(message_id="msg-dup", texto="oi"))
    resposta = _post_webhook(client, _payload(message_id="msg-dup", texto="oi"))
    assert resposta.json() == {"status": "ignorado", "motivo": "duplicada"}


@freeze_time(AGORA_UTC)
def test_audio_sem_stt_configurado_e_bloqueado(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.stt_habilitado", lambda: False)
    resposta = _post_webhook(client, _payload(audio=True, message_id="msg-audio-1"))
    assert resposta.json() == {"status": "ignorado", "motivo": "audio_sem_stt"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-audio-1").first()
    assert log.status == "bloqueado_audio_sem_stt"


@freeze_time(AGORA_UTC)
def test_audio_transcrito_segue_fluxo_normal(client, conta_no_ar, monkeypatch):
    monkeypatch.setattr("app.whatsapp.webhook.stt_habilitado", lambda: True)
    monkeypatch.setattr("app.whatsapp.webhook.transcrever_audio", lambda audio_b64: "toca uma musica")
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("musica", "Legiao Urbana")
    )
    resposta = _post_webhook(client, _payload(audio=True, message_id="msg-audio-2"))
    assert resposta.json() == {"status": "ok", "acao": "musica"}


@freeze_time(AGORA_UTC)
def test_falha_na_transcricao_e_registrada(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.stt_habilitado", lambda: True)

    def _falha(audio_b64):
        raise RuntimeError("falha na api")

    monkeypatch.setattr("app.whatsapp.webhook.transcrever_audio", _falha)
    resposta = _post_webhook(client, _payload(audio=True, message_id="msg-audio-3"))
    assert resposta.json() == {"status": "ignorado", "motivo": "falha_transcricao"}


@freeze_time(AGORA_UTC)
def test_limite_de_plano_excedido_bloqueia(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.limite_mensagens_efetivo", lambda db, account: 0)
    resposta = _post_webhook(client, _payload(message_id="msg-limite-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "limite_plano"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-limite-1").first()
    assert log.status == "bloqueado_plano"


def test_fora_do_horario_bloqueia(client, conta_no_ar, db_session):
    with freeze_time("2026-08-10 22:00:00"):  # fora da janela 10h-14h local
        resposta = _post_webhook(client, _payload(message_id="msg-horario-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "horario"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-horario-1").first()
    assert log.status == "bloqueado_horario"


@freeze_time(AGORA_UTC)
def test_rate_limit_por_telefone_bloqueia(client, conta_no_ar, db_session):
    account, radio_config, programa = conta_no_ar
    programa.limite_mensagens_hora = 0
    db_session.commit()

    resposta = _post_webhook(client, _payload(message_id="msg-rl-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "rate_limit"}


@freeze_time(AGORA_UTC)
def test_conteudo_proibido_bloqueia(client, conta_no_ar, db_session):
    resposta = _post_webhook(client, _payload(texto="quero comprar uma arma", message_id="msg-cf-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "conteudo"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-cf-1").first()
    assert log.status == "bloqueado_conteudo"


@freeze_time(AGORA_UTC)
def test_pedido_de_musica_entra_na_fila(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao",
        lambda config, programa, texto: ("musica", "Legiao Urbana"),
    )
    resposta = _post_webhook(client, _payload(texto="toca legiao urbana", message_id="msg-mus-1"))
    assert resposta.json() == {"status": "ok", "acao": "musica"}

    pedido = db_session.query(FilaAoVivo).filter_by(tipo="musica").first()
    assert pedido is not None
    assert pedido.musica_query == "Legiao Urbana"


@freeze_time(AGORA_UTC)
def test_pedido_de_abraco_entra_na_fila(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("abraco", None))
    resposta = _post_webhook(client, _payload(texto="manda um alo pra mim", message_id="msg-ab-1"))
    assert resposta.json() == {"status": "ok", "acao": "abraco"}

    pedido = db_session.query(FilaAoVivo).filter_by(tipo="abraco").first()
    assert pedido is not None


@freeze_time(AGORA_UTC)
def test_mensagem_sem_pedido_so_fica_registrada(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None))
    resposta = _post_webhook(client, _payload(texto="voces sao otimos", message_id="msg-gd-1"))
    assert resposta.json() == {"status": "ok", "acao": "guardar"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-gd-1").first()
    assert log.status == "guardado"
    assert db_session.query(FilaAoVivo).count() == 0


@freeze_time(AGORA_UTC)
def test_assinatura_hmac_valida_processa_normalmente(client, conta_no_ar, db_session, monkeypatch):
    account, _, _ = conta_no_ar
    account.wuzapi_hmac_key = "chave-secreta"
    db_session.commit()
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None))

    corpo = json.dumps(_payload(texto="oi", message_id="msg-hmac-ok")).encode()
    assinatura = hmac.new(b"chave-secreta", corpo, hashlib.sha256).hexdigest()

    resposta = client.post(
        "/webhook/whatsapp", content=corpo, headers={"x-hmac-signature": assinatura}
    )
    assert resposta.json() == {"status": "ok", "acao": "guardar"}


@freeze_time(AGORA_UTC)
def test_assinatura_hmac_invalida_e_ignorada(client, conta_no_ar, db_session):
    account, _, _ = conta_no_ar
    account.wuzapi_hmac_key = "chave-secreta"
    db_session.commit()

    corpo = json.dumps(_payload(texto="oi", message_id="msg-hmac-bad")).encode()
    resposta = client.post(
        "/webhook/whatsapp", content=corpo, headers={"x-hmac-signature": "assinatura-forjada"}
    )
    assert resposta.json() == {"status": "ignorado", "motivo": "assinatura_invalida"}


@freeze_time(AGORA_UTC)
def test_status_broadcast_e_ignorado(client, conta_no_ar):
    payload = _payload(telefone="status@broadcast", message_id="msg-status-1")
    resposta = _post_webhook(client, payload)
    assert resposta.json() == {"status": "ignorado"}
