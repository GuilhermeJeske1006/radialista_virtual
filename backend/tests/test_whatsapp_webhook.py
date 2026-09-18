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

# HMAC agora e' obrigatorio (ver auditoria item 1) -- conta_no_ar ja' nasce com essa chave
# configurada, e _post_webhook assina o corpo com ela por padrao, pra' cada teste que nao
# quer testar assinatura em si nao precisar se preocupar com isso.
_HMAC_CHAVE_PADRAO = "chave-secreta-teste"


@pytest.fixture(autouse=True)
def _sem_espera_debounce(monkeypatch):
    """O webhook espera _DEBOUNCE_SEGUNDOS (6s) de silencio antes de agir --
    sem isso cada teste que chega a esse ponto do fluxo levaria 6s de verdade."""
    import asyncio

    async def _sleep_imediato(segundos):
        return None

    monkeypatch.setattr(asyncio, "sleep", _sleep_imediato)


@pytest.fixture(autouse=True)
def _guardrail_llm_aprova_por_padrao(monkeypatch):
    """A segunda camada do guardrail (avaliar_adequacao_programa) chama o LLM de verdade --
    nos testes que nao exercitam ela especificamente, aprova por padrao pra nao depender de rede
    nem mascarar o teste original com falha de credencial (ver Frente V)."""
    monkeypatch.setattr(
        "app.whatsapp.webhook.avaliar_adequacao_programa", lambda texto, programa: (True, "")
    )
    monkeypatch.setattr(
        "app.whatsapp.webhook.avaliar_adequacao_ao_vivo", lambda texto, programa: (True, "")
    )


@pytest.fixture()
def conta_no_ar(db_session, account_factory):
    account = account_factory(
        email="radio@a.com", wuzapi_token="wuzapi-token-1", wuzapi_user_id="user-123",
        wuzapi_hmac_key=_HMAC_CHAVE_PADRAO,
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
    imagem=False,
):
    info = {"Chat": telefone, "FromMe": from_me, "ID": message_id, "PushName": push_name}
    if audio:
        mensagem = {"audioMessage": {"url": "https://example.com/audio.ogg"}}
    elif imagem:
        mensagem = {"imageMessage": {"url": "https://example.com/foto.jpg", "mimetype": "image/jpeg"}}
    else:
        mensagem = {"conversation": texto}
    payload = {"userID": user_id, "event": {"Info": info, "Message": mensagem}}
    if audio or imagem:
        payload["base64"] = "ZmFrZS1taWRpYS1ieXRlcw=="
    return payload


def _post_webhook(client, payload, headers=None, chave_hmac=_HMAC_CHAVE_PADRAO):
    corpo = json.dumps(payload).encode()
    headers = dict(headers or {})
    if chave_hmac and "x-hmac-signature" not in headers:
        headers["x-hmac-signature"] = hmac.new(chave_hmac.encode(), corpo, hashlib.sha256).hexdigest()
    return client.post("/webhook/whatsapp", content=corpo, headers=headers)


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
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("musica", "Legiao Urbana", "pedido_musica")
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
def test_imagem_descrita_segue_fluxo_normal(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.whatsapp.webhook.descrever_imagem", lambda imagem_b64, mime_type: "foto de uma pessoa sorrindo na praia"
    )
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None, "outro"))
    resposta = _post_webhook(client, _payload(imagem=True, message_id="msg-img-1"))
    assert resposta.json() == {"status": "ok", "acao": "guardar"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-img-1").first()
    assert log.mensagem_usuario == "foto de uma pessoa sorrindo na praia"


@freeze_time(AGORA_UTC)
def test_falha_ao_descrever_imagem_e_registrada(client, conta_no_ar, monkeypatch, db_session):
    def _falha(imagem_b64, mime_type):
        raise RuntimeError("falha na api")

    monkeypatch.setattr("app.whatsapp.webhook.descrever_imagem", _falha)
    resposta = _post_webhook(client, _payload(imagem=True, message_id="msg-img-2"))
    assert resposta.json() == {"status": "ignorado", "motivo": "falha_descricao_imagem"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-img-2").first()
    assert log.status == "falha_descricao_imagem"


@freeze_time(AGORA_UTC)
def test_limite_de_plano_excedido_bloqueia(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.limite_mensagens_efetivo", lambda db, account: 0)
    resposta = _post_webhook(client, _payload(message_id="msg-limite-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "limite_plano"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-limite-1").first()
    assert log.status == "bloqueado_plano"


@freeze_time(AGORA_UTC)
def test_limite_de_plano_bloqueia_audio_antes_de_transcrever(client, conta_no_ar, monkeypatch, db_session):
    """Item 2 da auditoria: STT e' pago -- com o plano ja' estourado, nao deve nem ser chamado."""
    chamadas = []
    monkeypatch.setattr("app.whatsapp.webhook.stt_habilitado", lambda: True)
    monkeypatch.setattr(
        "app.whatsapp.webhook.transcrever_audio", lambda audio_b64: chamadas.append(audio_b64) or "texto"
    )
    monkeypatch.setattr("app.whatsapp.webhook.limite_mensagens_efetivo", lambda db, account: 0)
    resposta = _post_webhook(client, _payload(audio=True, message_id="msg-limite-audio-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "limite_plano"}
    assert chamadas == []


@freeze_time(AGORA_UTC)
def test_limite_de_plano_bloqueia_imagem_antes_de_descrever(client, conta_no_ar, monkeypatch, db_session):
    """Mesma checagem do teste acima, mas pro outro custo pago (visao) -- ver item 2."""
    chamadas = []
    monkeypatch.setattr(
        "app.whatsapp.webhook.descrever_imagem", lambda imagem_b64, mime_type: chamadas.append(imagem_b64) or "texto"
    )
    monkeypatch.setattr("app.whatsapp.webhook.limite_mensagens_efetivo", lambda db, account: 0)
    resposta = _post_webhook(client, _payload(imagem=True, message_id="msg-limite-img-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "limite_plano"}
    assert chamadas == []


@freeze_time(AGORA_UTC)
def test_rate_limit_de_midia_por_telefone_bloqueia_antes_de_transcrever(client, conta_no_ar, monkeypatch, db_session):
    """Item 2 da auditoria: teto por telefone especifico pra' midia (STT/visao), independente
    do limite de plano da conta -- protege contra um unico ouvinte crescendo custo pago em
    sequencia."""
    from app.whatsapp.webhook import _LIMITE_MIDIA_POR_TELEFONE_HORA

    chamadas = []
    monkeypatch.setattr("app.whatsapp.webhook.stt_habilitado", lambda: True)
    monkeypatch.setattr(
        "app.whatsapp.webhook.transcrever_audio", lambda audio_b64: chamadas.append(audio_b64) or "texto"
    )
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None, "outro")
    )

    for i in range(_LIMITE_MIDIA_POR_TELEFONE_HORA):
        resposta = _post_webhook(client, _payload(audio=True, message_id=f"msg-rl-midia-{i}"))
        assert resposta.json().get("motivo") != "rate_limit_midia"

    chamadas.clear()
    resposta = _post_webhook(client, _payload(audio=True, message_id="msg-rl-midia-excedente"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "rate_limit_midia"}
    assert chamadas == []


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
def test_guardrail_llm_reprova_conteudo_bloqueia(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.whatsapp.webhook.avaliar_adequacao_programa",
        lambda texto, programa: (False, "fora do tom do programa"),
    )
    resposta = _post_webhook(client, _payload(texto="mensagem qualquer", message_id="msg-guardrail-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "conteudo"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-guardrail-1").first()
    assert log.status == "bloqueado_conteudo"


@freeze_time(AGORA_UTC)
def test_audio_reprovado_pelo_guardrail_de_ao_vivo_e_bloqueado(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.stt_habilitado", lambda: True)
    monkeypatch.setattr("app.whatsapp.webhook.transcrever_audio", lambda audio_b64: "toca uma musica")
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("musica", "Legiao Urbana", "pedido_musica")
    )
    monkeypatch.setattr(
        "app.whatsapp.webhook.avaliar_adequacao_ao_vivo",
        lambda texto, programa: (False, "transcricao incoerente, provavel ruido de fundo"),
    )
    resposta = _post_webhook(client, _payload(audio=True, message_id="msg-audio-guardrail-1"))
    assert resposta.json() == {"status": "bloqueado", "motivo": "audio_ao_vivo"}

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-audio-guardrail-1").first()
    assert log.status == "bloqueado_audio_ao_vivo"
    assert db_session.query(FilaAoVivo).count() == 0


@freeze_time(AGORA_UTC)
def test_texto_digitado_nao_passa_pelo_guardrail_de_ao_vivo(client, conta_no_ar, monkeypatch, db_session):
    """O guardrail extra (Frente U) e' so' pra audio -- mensagem de texto normal, mesmo indo
    pra fila, nunca deve chamar avaliar_adequacao_ao_vivo."""
    chamadas = []
    monkeypatch.setattr(
        "app.whatsapp.webhook.avaliar_adequacao_ao_vivo",
        lambda texto, programa: chamadas.append(texto) or (True, ""),
    )
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("musica", "Legiao Urbana", "pedido_musica")
    )
    resposta = _post_webhook(client, _payload(texto="toca legiao urbana", message_id="msg-texto-guardrail-1"))
    assert resposta.json() == {"status": "ok", "acao": "musica"}
    assert chamadas == []


@freeze_time(AGORA_UTC)
def test_pedido_de_sorteio_entra_na_fila(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("sorteio", None, "participacao_sorteio")
    )
    resposta = _post_webhook(client, _payload(texto="quero participar do sorteio", message_id="msg-sorteio-1"))
    assert resposta.json() == {"status": "ok", "acao": "sorteio"}

    pedido = db_session.query(FilaAoVivo).filter_by(tipo="sorteio").first()
    assert pedido is not None

    log = db_session.query(InteractionLog).filter_by(wuzapi_message_id="msg-sorteio-1").first()
    assert log.status == "fila_sorteio"


@freeze_time(AGORA_UTC)
def test_pedido_de_musica_entra_na_fila(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao",
        lambda config, programa, texto: ("musica", "Legiao Urbana", "pedido_musica"),
    )
    resposta = _post_webhook(client, _payload(texto="toca legiao urbana", message_id="msg-mus-1"))
    assert resposta.json() == {"status": "ok", "acao": "musica"}

    pedido = db_session.query(FilaAoVivo).filter_by(tipo="musica").first()
    assert pedido is not None
    assert pedido.musica_query == "Legiao Urbana"


@freeze_time(AGORA_UTC)
def test_pedido_de_abraco_entra_na_fila(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("abraco", None, "recado_comum"))
    resposta = _post_webhook(client, _payload(texto="manda um alo pra mim", message_id="msg-ab-1"))
    assert resposta.json() == {"status": "ok", "acao": "abraco"}

    pedido = db_session.query(FilaAoVivo).filter_by(tipo="abraco").first()
    assert pedido is not None
    assert pedido.natureza == "recado_comum"


@freeze_time(AGORA_UTC)
def test_mensagem_sem_pedido_so_fica_registrada(client, conta_no_ar, monkeypatch, db_session):
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None, "outro"))
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
    monkeypatch.setattr("app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None, "outro"))

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


@freeze_time(AGORA_UTC)
def test_limite_isolado_por_radio_sem_token_no_payload(client, conta_no_ar, account_factory, db_session):
    _, _, programa = conta_no_ar
    programa.limite_mensagens_hora = 1
    outra = account_factory(
        email="outra@radio.com", wuzapi_user_id="outra", wuzapi_token="outro-token",
        wuzapi_hmac_key=_HMAC_CHAVE_PADRAO,
    )
    config = RadioConfig(account_id=outra.id, ativo=True, timezone="America/Sao_Paulo")
    db_session.add(config)
    db_session.flush()
    db_session.add(Programa(radio_config_id=config.id, nome="Outro programa",
                            horario_inicio=datetime.time(10), horario_fim=datetime.time(14),
                            limite_mensagens_hora=1))
    db_session.commit()
    assert _post_webhook(client, _payload(message_id="primeira")).json()["status"] == "ok"
    assert _post_webhook(client, _payload(message_id="segunda")).json()["motivo"] == "rate_limit"
    assert _post_webhook(client, _payload(user_id="outra", message_id="terceira")).json()["status"] == "ok"


@freeze_time(AGORA_UTC)
def test_duplicada_tambem_exige_assinatura(client, conta_no_ar, db_session, monkeypatch):
    """Dedupe (por wuzapi_message_id) roda depois de autenticar a origem -- reenvio do mesmo
    id com uma chave HMAC que nao e' mais a atual da conta (rotacionada) tem que continuar
    rejeitado por assinatura invalida, nunca "cair" na checagem de duplicada."""
    monkeypatch.setattr(
        "app.whatsapp.webhook.classificar_intencao", lambda config, programa, texto: ("guardar", None, "outro")
    )
    account, _, _ = conta_no_ar
    corpo = json.dumps(_payload(message_id="reentrega")).encode()
    assinatura_original = hmac.new(_HMAC_CHAVE_PADRAO.encode(), corpo, hashlib.sha256).hexdigest()

    primeira = client.post("/webhook/whatsapp", content=corpo, headers={"x-hmac-signature": assinatura_original})
    assert primeira.json()["status"] == "ok"

    account.wuzapi_hmac_key = "chave-rotacionada"
    db_session.commit()

    segunda = client.post("/webhook/whatsapp", content=corpo, headers={"x-hmac-signature": assinatura_original})
    assert segunda.json() == {"status": "ignorado", "motivo": "assinatura_invalida"}


@freeze_time(AGORA_UTC)
def test_conta_sem_hmac_configurado_rejeita_mensagem_sem_verificar(client, account_factory, db_session):
    """Nucleo do item 1 da auditoria: conta sem wuzapi_hmac_key (onboarding antigo, ou que
    falhou ao configurar no WuzAPI) nao pode mais aceitar mensagem sem assinatura nenhuma --
    o "userID" do payload nao e' secreto, entao aceitar sem checar deixaria qualquer um forjar
    mensagem em nome dessa conta so' adivinhando um id sequencial."""
    from app.models.radio_config import RadioConfig
    from app.models.programa import Programa
    import datetime as dt

    account = account_factory(email="sem-hmac@a.com", wuzapi_token="tok-sem-hmac", wuzapi_user_id="user-sem-hmac")
    radio_config = RadioConfig(account_id=account.id, ativo=True, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    db_session.add(Programa(
        radio_config_id=radio_config.id, nome="Programa Principal",
        horario_inicio=dt.time(10, 0), horario_fim=dt.time(14, 0), limite_mensagens_hora=1000,
    ))
    db_session.commit()

    resposta = _post_webhook(client, _payload(user_id="user-sem-hmac", message_id="sem-hmac-1"), chave_hmac=None)
    assert resposta.json() == {"status": "ignorado", "motivo": "assinatura_invalida"}


def test_resposta_whatsapp_preserva_identidade_e_contexto(conta_no_ar, monkeypatch):
    from app.whatsapp.webhook import _gerar_e_enviar_resposta
    account, config, programa = conta_no_ar
    account.nome_radio = "Rádio Aurora"
    config.nome_locutor = "Ana"
    capturado = {}
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)
    def gerar(prompt, texto):
        capturado["prompt"] = prompt
        return "Olá!"
    monkeypatch.setattr("app.whatsapp.webhook.gerar_resposta", gerar)
    monkeypatch.setattr("app.whatsapp.webhook.enviar_mensagem", lambda *args: None)
    assert _gerar_e_enviar_resposta(account, config, programa, "5511999999999", "Oi") == "Olá!"
    for trecho in ("Rádio Aurora", "Ana", programa.nome, "conversa privada", "não prometa execução"):
        assert trecho in capturado["prompt"]
