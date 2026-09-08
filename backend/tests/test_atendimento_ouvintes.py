import datetime
import json
import httpx
import pytest
from freezegun import freeze_time

# Carrega schemas antes de congelar o relógio das fixtures.
from app.main import app  # noqa: F401
from app.models.conversa_ouvinte import ConversaOuvinte
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.whatsapp.atendimento import atender, ocorrencia, selecionar

pytestmark = pytest.mark.usefixtures("agora")


@pytest.fixture
def agora():
    with freeze_time("2026-08-10 15:00:00"):
        yield


@pytest.fixture
def contexto(db_session, account_factory, monkeypatch):
    a = account_factory(
        email="ouvintes@radio.com", atendimento_ouvinte_ativo=True, wuzapi_token="token"
    )
    r = RadioConfig(
        account_id=a.id,
        nome_locutor="Ana",
        timezone="America/Sao_Paulo",
        resposta_automatica_whatsapp=True,
    )
    db_session.add(r)
    db_session.flush()
    p = Programa(
        radio_config_id=r.id,
        nome="Tarde Boa",
        horario_inicio=datetime.time(10),
        horario_fim=datetime.time(14),
    )
    db_session.add(p)
    db_session.commit()
    monkeypatch.setattr(
        "app.whatsapp.atendimento.interpretar",
        lambda *args: {"acao": "musica", "musica_query": "Oceano - Djavan"},
    )
    monkeypatch.setattr("app.whatsapp.atendimento.enviar_mensagem", lambda *args: None)
    monkeypatch.setattr(
        "app.whatsapp.gestao.avaliar_adequacao_programa", lambda *args: (True, "")
    )
    return a, r, p


def receber(db, contexto, texto="Toca Oceano, estou saindo do plantão", mid="1"):
    a, r, p = contexto
    return atender(db, a, r, p, "55119999", "Carla", texto, mid)


def pedido_aprovado(db, contexto, telefone="55119999"):
    _, r, p = contexto
    pedido = FilaAoVivo(
        radio_config_id=r.id,
        programa_id=p.id,
        transmissao=ocorrencia(p, r.timezone),
        telefone=telefone,
        nome="Carla",
        tipo="abraco",
        mensagem_usuario="privado",
        texto_autorizado="Um abraço para Carla",
        estado="em_fila",
    )
    db.add(pedido)
    db.commit()
    return pedido


def test_pedido_salvo_antes_de_confirmar_e_privado_fora_da_fala(
    db_session, contexto, monkeypatch
):
    def enviar(*args):
        item = db_session.query(FilaAoVivo).one()
        assert item.programa_id == contexto[2].id
        assert item.estado == "aguardando_revisao"
        assert item.texto_autorizado == ""
        assert not item.atendido

    monkeypatch.setattr("app.whatsapp.atendimento.enviar_mensagem", enviar)
    receber(db_session, contexto)
    assert db_session.query(InteractionLog).one().status == "respondido_whatsapp"


def test_reentrega_e_pedido_repetido_nao_duplicam(db_session, contexto):
    receber(db_session, contexto)
    assert receber(db_session, contexto)["motivo"] == "duplicada"
    receber(db_session, contexto, mid="2")
    assert db_session.query(FilaAoVivo).count() == 1


def test_esclarecimento_recebe_historico_e_pendente(db_session, contexto, monkeypatch):
    monkeypatch.setattr(
        "app.whatsapp.atendimento.interpretar",
        lambda *args: {"acao": "musica", "pergunta": "Qual música?"},
    )
    receber(db_session, contexto, texto="Quero pedir uma música")

    def completar(texto, historico, pendente):
        assert historico[-1]["content"] == "Qual música?"
        assert pendente["acao"] == "musica"
        return {"acao": "musica", "musica_query": "Oceano"}

    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", completar)
    receber(db_session, contexto, texto="Oceano", mid="2")
    assert db_session.query(FilaAoVivo).one().musica_query == "Oceano"


def test_corrigir_e_cancelar_pedido(db_session, contexto, monkeypatch):
    receber(db_session, contexto)
    monkeypatch.setattr(
        "app.whatsapp.atendimento.interpretar",
        lambda *args: {"acao": "corrigir", "musica_query": "Flor de Lis"},
    )
    receber(db_session, contexto, mid="2")
    assert db_session.query(FilaAoVivo).one().musica_query == "Flor de Lis"
    monkeypatch.setattr(
        "app.whatsapp.atendimento.interpretar", lambda *args: {"acao": "cancelar"}
    )
    receber(db_session, contexto, mid="3")
    assert db_session.query(FilaAoVivo).one().estado == "cancelado"


def test_selecao_nao_significa_execucao_e_callback_idempotente(
    client, db_session, contexto, auth_headers
):
    a, r, p = contexto
    pedido = pedido_aprovado(db_session, contexto)
    assert selecionar(db_session, r, p, ("abraco",)).id == pedido.id
    assert not pedido.atendido
    assert selecionar(db_session, r, p, ("abraco",)) is None
    dados = {
        "token": pedido.selecao_token,
        "programa_id": p.id,
        "resultado": "executado",
    }
    for _ in range(2):
        res = client.post(
            f"/ouvintes/pedidos/{pedido.id}/reproducao",
            json=dados,
            headers=auth_headers(a.id),
        )
        assert res.status_code == 200
        assert res.json()["estado"] == "executado"
    db_session.refresh(pedido)
    assert pedido.atendido and pedido.atendido_em


@pytest.mark.parametrize("resultado", ["falhou", "interrompido"])
def test_player_falho_nao_marca_atendido(
    client, db_session, contexto, auth_headers, resultado
):
    a, r, p = contexto
    pedido = pedido_aprovado(db_session, contexto)
    selecionar(db_session, r, p, ("abraco",))
    res = client.post(
        f"/ouvintes/pedidos/{pedido.id}/reproducao",
        json={
            "token": pedido.selecao_token,
            "programa_id": p.id,
            "resultado": resultado,
        },
        headers=auth_headers(a.id),
    )
    assert res.json()["estado"] == "nao_atendido"
    assert not pedido.atendido


def test_callback_outro_tenant_e_token_invalido(
    client, db_session, contexto, account_factory, auth_headers
):
    a, r, p = contexto
    pedido = pedido_aprovado(db_session, contexto)
    selecionar(db_session, r, p, ("abraco",))
    outra = account_factory(email="outra@radio.com")
    url = f"/ouvintes/pedidos/{pedido.id}/reproducao"
    dados = {
        "token": pedido.selecao_token,
        "programa_id": p.id,
        "resultado": "executado",
    }
    assert (
        client.post(url, json=dados, headers=auth_headers(outra.id)).status_code == 404
    )
    dados["token"] = "invalido"
    assert client.post(url, json=dados, headers=auth_headers(a.id)).status_code == 409


def test_fila_nao_vaza_para_outro_programa_e_expira(db_session, contexto):
    _, r, p = contexto
    pedido = pedido_aprovado(db_session, contexto)
    outro = Programa(
        radio_config_id=r.id,
        nome="Outro",
        horario_inicio=datetime.time(10),
        horario_fim=datetime.time(14),
    )
    db_session.add(outro)
    db_session.commit()
    assert selecionar(db_session, r, outro, ("abraco",)) is None
    with freeze_time("2026-08-11 15:00:00"):
        assert selecionar(db_session, r, p, ("abraco",)) is None
    db_session.refresh(pedido)
    assert pedido.estado == "expirado"


def test_distribui_espaco_entre_ouvintes(db_session, contexto):
    _, r, p = contexto
    pedido_aprovado(db_session, contexto)
    selecionar(db_session, r, p, ("abraco",))
    pedido_aprovado(db_session, contexto)
    outro = pedido_aprovado(db_session, contexto, telefone="55228888")
    assert selecionar(db_session, r, p, ("abraco",)).id == outro.id


def test_aprovacao_exige_autorizacao_e_texto(
    client, db_session, contexto, auth_headers
):
    a, _, _ = contexto
    receber(db_session, contexto)
    pedido = db_session.query(FilaAoVivo).one()
    url = f"/ouvintes/pedidos/{pedido.id}"
    assert (
        client.patch(
            url,
            json={"acao": "aprovar", "texto_autorizado": "Um abraço"},
            headers=auth_headers(a.id),
        ).status_code
        == 422
    )
    res = client.patch(
        url,
        json={
            "acao": "aprovar",
            "texto_autorizado": "Carla pediu Oceano",
            "autorizacao_confirmada": True,
        },
        headers=auth_headers(a.id),
    )
    assert res.status_code == 200
    assert pedido.estado == "em_fila"


def test_bloqueio_musical_na_aprovacao(client, db_session, contexto, auth_headers):
    a, _, p = contexto
    p.musicas_bloqueadas = ["Djavan"]
    db_session.commit()
    receber(db_session, contexto)
    pedido = db_session.query(FilaAoVivo).one()
    res = client.patch(
        f"/ouvintes/pedidos/{pedido.id}",
        json={
            "acao": "aprovar",
            "texto_autorizado": "Carla pediu música",
            "autorizacao_confirmada": True,
        },
        headers=auth_headers(a.id),
    )
    assert res.status_code == 422


def test_humano_pausa_e_memoria_expira(
    client, db_session, contexto, auth_headers, monkeypatch
):
    a, _, _ = contexto
    receber(db_session, contexto)
    c = db_session.query(ConversaOuvinte).one()
    assert (
        client.patch(
            f"/ouvintes/conversas/{c.id}",
            json={"humano": True},
            headers=auth_headers(a.id),
        ).status_code
        == 200
    )

    def nao_chamar(*args):
        raise AssertionError("Agente não pode responder durante atendimento humano")

    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", nao_chamar)
    receber(db_session, contexto, mid="2")
    assert (
        db_session.query(InteractionLog).filter_by(wuzapi_message_id="2").one().status
        == "aguardando_humano"
    )
    with freeze_time("2026-08-12 15:00:00"):
        assert (
            client.get("/ouvintes/conversas", headers=auth_headers(a.id)).json()[0][
                "historico"
            ]
            == []
        )


def test_falha_envio_nao_perde_pedido_e_nao_finge_resposta(
    db_session, contexto, monkeypatch
):
    def falhar(*args):
        raise httpx.ReadTimeout("resultado desconhecido")

    monkeypatch.setattr("app.whatsapp.atendimento.enviar_mensagem", falhar)
    receber(db_session, contexto)
    log = db_session.query(InteractionLog).one()
    assert (
        log.status == "envio_incerto" and log.resposta is None and log.resposta_pendente
    )
    assert len(db_session.query(ConversaOuvinte).one().historico) == 1
    assert db_session.query(FilaAoVivo).count() == 1


def test_conexao_falha_repete_so_envio(db_session, contexto, monkeypatch):
    chamadas = []

    def enviar(*args):
        chamadas.append(args)
        if len(chamadas) == 1:
            raise httpx.ConnectError("sem conexão")

    monkeypatch.setattr("app.whatsapp.atendimento.enviar_mensagem", enviar)
    receber(db_session, contexto)
    assert len(chamadas) == 2
    assert db_session.query(FilaAoVivo).count() == 1
    assert db_session.query(InteractionLog).one().status == "respondido_whatsapp"


def test_lock_concorrente_nao_cria_pedido(db_session, contexto):
    from app.whatsapp.locks import bloquear_conversa
    from fastapi import HTTPException

    with bloquear_conversa(contexto[0].id, "55119999"):
        with pytest.raises(HTTPException) as erro:
            receber(db_session, contexto)
        assert erro.value.status_code == 503
    assert db_session.query(FilaAoVivo).count() == 0
    receber(db_session, contexto)
    assert db_session.query(FilaAoVivo).count() == 1


def test_inbox_agrupa_bolhas_e_reentrega_nao_repete(db_session, contexto, monkeypatch):
    from app.models.mensagem_ouvinte import MensagemOuvinte
    from app.whatsapp.inbox import processar

    a, r, p = contexto
    monkeypatch.setattr(
        "app.whatsapp.inbox.avaliar_adequacao_programa", lambda *args: (True, "")
    )
    for chave, texto in [("bolha1", "Quero pedir uma música"), ("bolha2", "Oceano")]:
        db_session.add(
            MensagemOuvinte(
                chave=chave,
                account_id=a.id,
                radio_config_id=r.id,
                programa_id=p.id,
                telefone="55119999",
                texto=texto,
            )
        )
    db_session.commit()
    processar(db_session, a, r, p, "55119999", "Carla", "bolha2")
    assert (
        db_session.query(FilaAoVivo).one().mensagem_usuario
        == "Quero pedir uma música\nOceano"
    )
    assert (
        processar(db_session, a, r, p, "55119999", "Carla", "bolha1")["motivo"]
        == "duplicada"
    )
    assert db_session.query(FilaAoVivo).count() == 1


def test_inbox_falha_antes_de_commit_permite_retry(db_session, contexto, monkeypatch):
    from app.models.mensagem_ouvinte import MensagemOuvinte
    from app.whatsapp.inbox import processar

    a, r, p = contexto
    item = MensagemOuvinte(
        chave="falha",
        account_id=a.id,
        radio_config_id=r.id,
        programa_id=p.id,
        telefone="55119999",
        texto="Oceano",
    )
    db_session.add(item)
    db_session.commit()
    monkeypatch.setattr(
        "app.whatsapp.inbox.avaliar_adequacao_programa", lambda *args: (True, "")
    )
    import app.whatsapp.inbox as inbox

    original = inbox._atender

    def falhar(*args):
        raise RuntimeError("falha antes de salvar")

    monkeypatch.setattr(inbox, "_atender", falhar)
    with pytest.raises(RuntimeError):
        processar(db_session, a, r, p, "55119999", "Carla", "falha")
    db_session.refresh(item)
    assert item.estado == "pendente"
    monkeypatch.setattr(inbox, "_atender", original)
    processar(db_session, a, r, p, "55119999", "Carla", "falha")
    assert db_session.query(FilaAoVivo).count() == 1


def test_webhook_novo_fluxo_isola_id_por_radio(
    client, db_session, contexto, account_factory, monkeypatch
):
    monkeypatch.setattr("app.whatsapp.webhook._DEBOUNCE_SEGUNDOS", 0)
    monkeypatch.setattr(
        "app.whatsapp.inbox.avaliar_adequacao_programa", lambda *args: (True, "")
    )
    a, r, p = contexto
    a.wuzapi_user_id = "radio1"
    outra = account_factory(
        email="segunda@radio.com",
        atendimento_ouvinte_ativo=True,
        wuzapi_token="token2",
        wuzapi_user_id="radio2",
    )
    r2 = RadioConfig(account_id=outra.id, ativo=True, timezone="America/Sao_Paulo")
    db_session.add(r2)
    db_session.flush()
    db_session.add(
        Programa(
            radio_config_id=r2.id,
            nome="Outra atração",
            horario_inicio=datetime.time(10),
            horario_fim=datetime.time(14),
        )
    )
    db_session.commit()
    for radio in ("radio1", "radio2"):
        payload = {
            "userID": radio,
            "event": {
                "Info": {
                    "Chat": "55119999@s.whatsapp.net",
                    "FromMe": False,
                    "ID": "mesmo-id",
                    "PushName": "Carla",
                },
                "Message": {"conversation": "Toca Oceano"},
            },
        }
        res = client.post("/webhook/whatsapp", content=json.dumps(payload))
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        assert (
            client.post("/webhook/whatsapp", content=json.dumps(payload)).json()[
                "motivo"
            ]
            == "duplicada"
        )
    assert db_session.query(FilaAoVivo).count() == 2
    assert db_session.query(ConversaOuvinte).count() == 2


def test_migracao_aditiva_preserva_historico_e_roda_duas_vezes(monkeypatch):
    from sqlalchemy import create_engine, text, inspect
    import app.main as main

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE fila_ao_vivo (id INTEGER PRIMARY KEY, atendido BOOLEAN NOT NULL, mensagem_usuario TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO fila_ao_vivo VALUES (1, 0, 'mensagem original'), (2, 1, 'histórico')"
            )
        )
    monkeypatch.setattr(main, "engine", engine)
    main.garantir_colunas_fila_ao_vivo()
    main.garantir_colunas_fila_ao_vivo()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT estado, mensagem_usuario FROM fila_ao_vivo ORDER BY id")
        ).all()
    assert rows == [
        ("aguardando_revisao", "mensagem original"),
        ("historico_legado", "histórico"),
    ]
    assert "programa_id" in {
        c["name"] for c in inspect(engine).get_columns("fila_ao_vivo")
    }
    engine.dispose()


def test_fala_nova_usa_apenas_conteudo_aprovado(
    client, db_session, contexto, auth_headers, monkeypatch
):
    a, r, p = contexto
    p.estrutura_blocos = ["chamada_ouvinte"]
    p.ia_pode_adicionar_blocos = False
    pedido = pedido_aprovado(db_session, contexto)
    pedido.mensagem_usuario = "Meu endereço privado é Rua Particular 123"
    pedido.texto_autorizado = "Carla pediu um abraço para a mãe"
    db_session.commit()
    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta",
        lambda prompt, msg: prompts.append(prompt)
        or "Carla, um abraço para você e sua mãe!",
    )
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *args: False)
    res = client.post(
        f"/live/{r.id}/programas/{p.id}/proxima",
        json={"historico": [], "total_falas": 1},
        headers=auth_headers(a.id),
    )
    assert res.status_code == 200
    assert res.json()["pedido_id"] == pedido.id
    assert "Rua Particular" not in prompts[0]
    assert pedido.texto_autorizado in prompts[0]
    assert "sem deduzir profissão" in prompts[0]
    assert not pedido.atendido


def test_aprovacao_respeita_perfil_musical(
    client, db_session, contexto, auth_headers, monkeypatch
):
    a, _, p = contexto
    p.generos_musicais = ["sertanejo"]
    db_session.commit()
    receber(db_session, contexto)
    pedido = db_session.query(FilaAoVivo).one()
    monkeypatch.setattr(
        "app.whatsapp.gestao.classificar_intencao",
        lambda *args: ("guardar", None, "pedido_musica"),
    )
    res = client.patch(
        f"/ouvintes/pedidos/{pedido.id}",
        json={
            "acao": "aprovar",
            "texto_autorizado": "Carla pediu Oceano",
            "autorizacao_confirmada": True,
        },
        headers=auth_headers(a.id),
    )
    assert res.status_code == 422
    assert pedido.estado == "aguardando_revisao"


def test_excluir_programa_preserva_pedido_sem_bloquear_fk(
    client, db_session, contexto, auth_headers
):
    from app.models.mensagem_ouvinte import MensagemOuvinte

    a, r, p = contexto
    pedido = pedido_aprovado(db_session, contexto)
    item = MensagemOuvinte(
        chave="exclusao",
        account_id=a.id,
        radio_config_id=r.id,
        programa_id=p.id,
        telefone="55119999",
        texto="recado",
    )
    db_session.add(item)
    db_session.commit()
    res = client.delete(f"/config/programas/{p.id}", headers=auth_headers(a.id))
    assert res.status_code == 204
    db_session.refresh(pedido)
    db_session.refresh(item)
    assert pedido.programa_id is None and pedido.estado == "nao_atendido"
    assert item.programa_id is None and item.estado == "expirada"
