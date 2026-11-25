import datetime
import hashlib
import hmac
import json
import os
import threading
import uuid
import asyncio
from types import SimpleNamespace
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from freezegun import freeze_time

from app.config.settings import settings
from app.db.database import Base
from app.models.account import Account
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.canal_whatsapp import (EntradaWhatsapp, EnvioWhatsapp, BlocoReproduzido,
    DiscussaoPrograma, ContribuicaoOuvinte)
from app.models.conversa_ouvinte import ConversaOuvinte
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.whatsapp.atendimento import ocorrencia
from app.whatsapp.eventos import registrar, depois
from app.whatsapp.locks import bloquear_conversa
from app.whatsapp.transmissao import contexto_publico, evento_player, EventoPlayer
from app.whatsapp.worker import persistir, processar_entrada, processar_envio


@pytest.fixture
def canal(db_session, account_factory, monkeypatch):
    a = account_factory(email="canal@radio.test", atendimento_ouvinte_ativo=True,
                        wuzapi_token="token-test", wuzapi_hmac_key="hmac-test")
    r = RadioConfig(account_id=a.id, nome_locutor="Ana", timezone="America/Sao_Paulo", resposta_automatica_whatsapp=True)
    db_session.add(r)
    db_session.flush()
    p = Programa(radio_config_id=r.id, nome="Programa do dia", horario_inicio=datetime.time(0), horario_fim=datetime.time(23, 59, 59))
    db_session.add(p)
    db_session.commit()
    monkeypatch.setattr(settings, "whatsapp_debounce_s", 0)
    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", lambda *args: {"acao": "conversar", "pergunta": "Que bom receber seu recado!"})
    monkeypatch.setattr("app.guardrails.content_filter.avaliar_adequacao_programa", lambda *args: (True, ""))
    monkeypatch.setattr("app.whatsapp.atendimento.enviar_mensagem", lambda *args: "saida-provedor")
    return a, r, p


def entrada(db, canal, mid="m1", texto="O que vocês acham?", **kwargs):
    a, r, p = canal
    payload = {"event": {"Info": {"ID": mid}, "Message": {}}}
    valores = ("55119999", "Carla", texto, kwargs.get("audio"), None, "image/jpeg", None, None,
               kwargs.get("from_me", False), f"radio:{a.id}:{mid}")
    persistir(db, a, r, p, valores, payload)
    return db.query(EntradaWhatsapp).filter_by(chave=valores[-1]).one()


def test_webhook_confirma_sem_esperar_debounce_ou_chamar_stt(client, db_session, canal, monkeypatch):
    a, _, _ = canal
    monkeypatch.setattr(settings, "whatsapp_worker_ativo", True)
    monkeypatch.setattr("app.whatsapp.webhook.transcrever_audio", lambda *args: pytest.fail("STT no webhook"))
    payload = {"token": a.wuzapi_token, "event": {"Info": {"ID": "audio1", "Chat": "55119999@s.whatsapp.net"},
        "Message": {"audioMessage": {"mimetype": "audio/ogg"}}}, "base64": "audio-test"}
    raw = json.dumps(payload).encode()
    headers = {"x-hmac-signature": hmac.new(a.wuzapi_hmac_key.encode(), raw, hashlib.sha256).hexdigest()}
    primeira = client.post("/webhook/whatsapp", content=raw, headers=headers)
    segunda = client.post("/webhook/whatsapp", content=raw, headers=headers)
    assert primeira.json()["status"] == "recebido"
    assert segunda.json()["motivo"] == "duplicada"
    assert db_session.query(EntradaWhatsapp).count() == 1
    assert db_session.query(ConversaOuvinte).one().nome == "Carla" or db_session.query(ConversaOuvinte).one().telefone == "55119999"


def test_recupera_apos_commit_de_entrada_e_resposta_atomica(db_session, canal):
    i = entrada(db_session, canal)
    assert db_session.query(InteractionLog).count() == 0
    assert processar_entrada(db_session, i.id)
    envio = db_session.query(EnvioWhatsapp).one()
    log = db_session.query(InteractionLog).one()
    assert envio.texto == log.resposta_pendente
    assert envio.estado == "pendente" and log.resposta is None
    assert not processar_entrada(db_session, i.id)
    assert processar_envio(db_session, envio.id)
    assert envio.provider_id == "saida-provedor"
    assert log.resposta and envio.estado == "aceito_pelo_provedor"
    assert not processar_envio(db_session, envio.id)


def test_agrupa_bolhas_persistidas_sem_duplicar_efeito(db_session, canal):
    i = entrada(db_session, canal, texto="Quero mandar")
    entrada(db_session, canal, mid="m2", texto="um recado")
    processar_entrada(db_session, i.id)
    assert db_session.query(InteractionLog).one().mensagem_usuario == "Quero mandar\num recado"
    assert db_session.query(EntradaWhatsapp).filter_by(estado="processada").count() == 2
    assert db_session.query(EnvioWhatsapp).count() == 1


def test_bolhas_nao_atravessam_ocorrencias_na_meia_noite(db_session, canal):
    with freeze_time("2026-11-12 02:59:50"):
        antiga = entrada(db_session, canal, texto="Mensagem do programa anterior")
    with freeze_time("2026-11-12 03:00:01"):
        nova = entrada(db_session, canal, mid="nova-ocorrencia", texto="Mensagem do programa novo")
        processar_entrada(db_session, antiga.id)
        processar_entrada(db_session, nova.id)
    itens = db_session.query(InteractionLog).order_by(InteractionLog.id).all()
    assert len(itens) == 2
    assert itens[0].status == "fora_horario"
    assert itens[0].mensagem_usuario == "Mensagem do programa anterior"
    assert itens[1].mensagem_usuario == "Mensagem do programa novo"


def test_checkpoint_de_midia_sobrevive_falha_do_agente(db_session, canal, monkeypatch):
    i = entrada(db_session, canal, texto=None, audio="audio")
    chamadas = []
    monkeypatch.setattr("app.stt.client.stt_habilitado", lambda: True)
    monkeypatch.setattr("app.stt.client.transcrever_audio", lambda *args: chamadas.append(1) or "Texto transcrito")
    import app.whatsapp.atendimento as atendimento
    original = atendimento._atender
    monkeypatch.setattr(atendimento, "_atender", lambda *args: (_ for _ in ()).throw(RuntimeError("falha")))
    with pytest.raises(RuntimeError):
        processar_entrada(db_session, i.id)
    db_session.rollback()
    db_session.refresh(i)
    assert i.estado == "pendente" and i.payload == {} and i.texto == "Texto transcrito"
    monkeypatch.setattr(atendimento, "_atender", original)
    processar_entrada(db_session, i.id)
    assert chamadas == [1]


def test_timeout_de_envio_persiste_incerto_sem_repetir(db_session, canal, monkeypatch):
    i = entrada(db_session, canal)
    processar_entrada(db_session, i.id)
    envio = db_session.query(EnvioWhatsapp).one()
    chamadas = []
    def falhar(*args):
        chamadas.append(1)
        raise httpx.ReadTimeout("timeout depois do POST")
    monkeypatch.setattr("app.whatsapp.atendimento.enviar_mensagem", falhar)
    processar_envio(db_session, envio.id)
    assert envio.estado == "incerto"
    assert not processar_envio(db_session, envio.id)
    assert chamadas == [1]


def test_assumir_conversa_pausa_resposta_ja_enfileirada(client, db_session, canal, auth_headers):
    i = entrada(db_session, canal)
    processar_entrada(db_session, i.id)
    c = db_session.query(ConversaOuvinte).one()
    assert client.patch(f"/ouvintes/conversas/{c.id}", headers=auth_headers(c.account_id), json={"humano": True}).status_code == 200
    envio = db_session.query(EnvioWhatsapp).one()
    processar_envio(db_session, envio.id)
    assert envio.estado == "pausado"


def test_encaminhamento_confirma_uma_vez_e_pausa_respostas_seguintes(db_session, canal, monkeypatch):
    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", lambda *args: {"acao": "humano"})
    i = entrada(db_session, canal, texto="Preciso falar com a equipe")
    processar_entrada(db_session, i.id)
    envio = db_session.query(EnvioWhatsapp).one()
    processar_envio(db_session, envio.id)
    assert envio.estado == "aceito_pelo_provedor"
    outra = entrada(db_session, canal, mid="continuacao", texto="Vou aguardar")
    processar_entrada(db_session, outra.id)
    assert db_session.query(EnvioWhatsapp).count() == 1
    assert db_session.query(InteractionLog).order_by(InteractionLog.id.desc()).first().status == "aguardando_humano"


def test_confirmacao_legada_f4_notifica_programa_validado_sem_duplicar(client, db_session, canal, auth_headers):
    from app.models.fila_ao_vivo import FilaAoVivo
    from app.models.canal_whatsapp import PreferenciasCanal
    a, r, p = canal
    pedido = FilaAoVivo(radio_config_id=r.id, programa_id=None, telefone="55119999", nome="Carla",
        tipo="musica", mensagem_usuario="Meu pedido legado", estado="selecionado", selecao_token="legado-f4")
    db_session.add(pedido)
    db_session.add(PreferenciasCanal(account_id=a.id, notificar_resultado=True))
    db_session.commit()
    corpo = {"token": pedido.selecao_token, "programa_id": p.id, "resultado": "executado"}
    url = f"/ouvintes/pedidos/{pedido.id}/reproducao"
    for _ in range(2):
        resposta = client.post(url, headers=auth_headers(a.id), json=corpo)
        assert resposta.status_code == 200 and resposta.json()["estado"] == "executado"
    assert db_session.query(EnvioWhatsapp).count() == 1
    assert p.nome in db_session.query(EnvioWhatsapp).one().texto


def test_eco_por_id_nao_pausa_agente_e_texto_manual_igual_pausa(db_session, canal):
    i = entrada(db_session, canal)
    processar_entrada(db_session, i.id)
    envio = db_session.query(EnvioWhatsapp).one()
    processar_envio(db_session, envio.id)
    eco = entrada(db_session, canal, mid="saida-provedor", texto=envio.texto, from_me=True)
    processar_entrada(db_session, eco.id)
    c = db_session.query(ConversaOuvinte).one()
    assert not c.humano
    manual = entrada(db_session, canal, mid="manual-id", texto=envio.texto, from_me=True)
    processar_entrada(db_session, manual.id)
    db_session.refresh(c)
    assert c.humano


def test_historico_inclui_resposta_sem_depender_de_eco_e_isola_contas(client, db_session, canal, auth_headers, account_factory):
    i = entrada(db_session, canal)
    processar_entrada(db_session, i.id)
    processar_envio(db_session, db_session.query(EnvioWhatsapp).one().id)
    c = db_session.query(ConversaOuvinte).one()
    dados = client.get(f"/ouvintes/conversas/{c.id}/mensagens", headers=auth_headers(c.account_id)).json()
    assert [m["origem"] for m in dados["mensagens"]] == ["ouvinte", "radio"]
    assert dados["mensagens"][1]["texto"] == "Que bom receber seu recado!"
    outro = account_factory(email="outra@canal.test")
    assert client.get(f"/ouvintes/conversas/{c.id}/mensagens", headers=auth_headers(outro.id)).status_code == 404


def test_eco_sincrono_nao_duplica_bolha_nem_pausa_agente(client, db_session, canal, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_worker_ativo", False)
    i = entrada(db_session, canal)
    processar_entrada(db_session, i.id)
    processar_envio(db_session, db_session.query(EnvioWhatsapp).one().id)
    a, _, _ = canal
    payload = {"token": a.wuzapi_token, "event": {"Info": {"ID": "saida-provedor", "Chat": "55119999@s.whatsapp.net", "FromMe": True},
        "Message": {"conversation": "Que bom receber seu recado!"}}}
    raw = json.dumps(payload).encode()
    assinatura = hmac.new(a.wuzapi_hmac_key.encode(), raw, hashlib.sha256).hexdigest()
    resposta = client.post("/webhook/whatsapp", content=raw, headers={"x-hmac-signature": assinatura})
    assert resposta.json()["motivo"] == "eco"
    assert db_session.query(InteractionLog).count() == 1
    assert not db_session.query(ConversaOuvinte).one().humano


def test_envio_manual_idempotente_e_exige_assumir(client, db_session, canal, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_worker_ativo", True)
    entrada(db_session, canal)
    c = db_session.query(ConversaOuvinte).one()
    path = f"/ouvintes/conversas/{c.id}/mensagens"
    dados = {"texto": "Olá, aqui é a equipe", "chave": "mensagem-cliente-123"}
    headers = auth_headers(c.account_id)
    assert client.post(path, headers=headers, json=dados).status_code == 409
    client.patch(f"/ouvintes/conversas/{c.id}", headers=headers, json={"humano": True})
    primeira = client.post(path, headers=headers, json=dados)
    segunda = client.post(path, headers=headers, json=dados)
    assert primeira.status_code == 200 and primeira.json() == segunda.json()
    assert db_session.query(EnvioWhatsapp).count() == 1
    assert client.post(path, headers=headers, json={**dados, "texto": "Outra"}).status_code == 409


def test_dois_operadores_nao_disputam_o_mesmo_atendimento(client, db_session, canal, auth_headers, monkeypatch):
    from app.models.usuario import Usuario
    from app.auth.security import criar_token
    monkeypatch.setattr(settings, "whatsapp_worker_ativo", True)
    entrada(db_session, canal)
    c = db_session.query(ConversaOuvinte).one()
    headers = auth_headers(c.account_id)
    segundo = Usuario(account_id=c.account_id, nome="Bruno", email="bruno@equipe.test", senha_hash="teste", role="membro")
    db_session.add(segundo)
    db_session.commit()
    outro = {"Authorization": f"Bearer {criar_token(segundo.id)}"}
    assert client.patch(f"/ouvintes/conversas/{c.id}", headers=headers, json={"humano": True}).status_code == 200
    assert client.patch(f"/ouvintes/conversas/{c.id}", headers=outro, json={"humano": True}).status_code == 409
    assert client.post(f"/ouvintes/conversas/{c.id}/mensagens", headers=outro,
        json={"texto": "Resposta concorrente", "chave": "operador-segundo-1"}).status_code == 409
    assert client.get(f"/ouvintes/conversas/{c.id}/mensagens", headers=outro).json()["conversa"]["pode_responder"] is False


def test_leituras_por_operador_nao_marcam_mensagens_futuras(client, db_session, canal, auth_headers):
    i = entrada(db_session, canal)
    processar_entrada(db_session, i.id)
    c = db_session.query(ConversaOuvinte).one()
    headers = auth_headers(c.account_id)
    dados = client.get("/ouvintes/central?modo=nao_lidas", headers=headers)
    assert dados.status_code == 200 and dados.json()["conversas"][0]["nao_lidas"] == 1
    log = db_session.query(InteractionLog).one()
    client.post(f"/ouvintes/conversas/{c.id}/leitura", headers=headers, json={"ultimo_log_id": log.id})
    assert client.get("/ouvintes/central?modo=nao_lidas", headers=headers).json()["conversas"] == []


def bloco(db, canal):
    a, r, p = canal
    b = BlocoReproduzido(account_id=a.id, programa_id=p.id, ocorrencia=ocorrencia(p, r.timezone), token="token-bloco",
        tipo="comentario", fala="Qual música marcou sua infância?", assunto={"titulo": "Memória musical", "pergunta": "Qual música marcou sua infância?"})
    db.add(b)
    db.commit()
    return b


def confirmar_bloco(db, canal, b, estado, player="player-teste-1"):
    return evento_player(b.id, EventoPlayer(token=b.token, player_id=player, estado=estado), canal[0], db)


def test_preparo_nao_vira_contexto_e_outro_player_nao_confirma(db_session, canal):
    b = bloco(db_session, canal)
    assert contexto_publico(db_session, canal[0].id, canal[2].id) is None
    confirmar_bloco(db_session, canal, b, "reproduzindo")
    with pytest.raises(HTTPException):
        confirmar_bloco(db_session, canal, b, "concluido", player="player-teste-2")
    db_session.rollback()
    confirmar_bloco(db_session, canal, b, "concluido")
    publico = contexto_publico(db_session, canal[0].id, canal[2].id)
    assert publico["pergunta"] == "Qual música marcou sua infância?"
    confirmar_bloco(db_session, canal, b, "concluido")
    assert db_session.query(DiscussaoPrograma).count() == 1


def test_bloco_falho_nao_publica_pergunta(db_session, canal):
    b = bloco(db_session, canal)
    confirmar_bloco(db_session, canal, b, "reproduzindo")
    confirmar_bloco(db_session, canal, b, "falhou")
    assert contexto_publico(db_session, canal[0].id, canal[2].id) is None


def test_ciclo_pergunta_resposta_revisao_pauta(client, db_session, canal, auth_headers, monkeypatch):
    b = bloco(db_session, canal)
    confirmar_bloco(db_session, canal, b, "reproduzindo")
    confirmar_bloco(db_session, canal, b, "concluido")
    contextos = []
    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", lambda texto, hist, pend: contextos.append(pend) or {"acao": "conversar", "pergunta": "Que lembrança boa!"})
    i = entrada(db_session, canal, texto="Oceano marcou minha infância")
    processar_entrada(db_session, i.id)
    assert contextos[0]["contexto_publico"]["pergunta"] == "Qual música marcou sua infância?"
    c = db_session.query(ConversaOuvinte).one()
    log = db_session.query(InteractionLog).one()
    headers = auth_headers(c.account_id)
    dados = {"log_id": log.id, "programa_id": canal[2].id, "discussao_id": db_session.query(DiscussaoPrograma).one().id}
    proposta = client.post(f"/ouvintes/conversas/{c.id}/contribuicoes", headers=headers, json=dados)
    assert proposta.status_code == 200
    id_ = proposta.json()["id"]
    assert db_session.query(Assunto).count() == 0
    assert client.patch(f"/ouvintes/contribuicoes/{id_}", headers=headers, json={"acao": "aprovar"}).status_code == 422
    revisao = {"acao": "aprovar", "autorizacao_confirmada": True, "titulo": "Memória musical da audiência", "texto_autorizado": "Uma ouvinte lembra de Oceano na infância"}
    assert client.patch(f"/ouvintes/contribuicoes/{id_}", headers=headers, json=revisao).status_code == 200
    assert db_session.query(Assunto).one().gancho == revisao["texto_autorizado"]
    assert db_session.query(ContribuicaoOuvinte).one().estado == "aprovada"
    from app.topics.pauta_conversa import proximo_assunto, montar_pauta_assunto
    from app.dados.fontes import de_assunto
    escolhido = proximo_assunto(db_session, canal[2])
    assert escolhido.eixo == "reacao"
    assert escolhido.repertorio["familia"] == "participacao"
    assert de_assunto(escolhido).detalhes["pergunta_origem"] == b.assunto["pergunta"]
    assert "exclusivamente o relato autorizado" in montar_pauta_assunto(escolhido)
    publico = BlocoReproduzido(account_id=canal[0].id, programa_id=canal[2].id,
        ocorrencia=b.ocorrencia, token="contribuicao-no-ar", tipo="comentario",
        fala=revisao["texto_autorizado"], assunto_id=db_session.query(Assunto).one().id, assunto={})
    db_session.add(publico)
    db_session.commit()
    confirmar_bloco(db_session, canal, publico, "reproduzindo")
    confirmar_bloco(db_session, canal, publico, "concluido")
    assert db_session.query(ContribuicaoOuvinte).one().estado == "utilizada"
    contexto = client.get(f"/ouvintes/conversas/{c.id}/contexto", headers=headers).json()
    assert contexto["contribuicoes"][0]["estado"] == "utilizada"
    assert contexto["publico"]["fala_confirmada"] == revisao["texto_autorizado"]
    # A autorização não atravessa a troca de ocorrência, mesmo antes do vencimento da pauta.
    contribuicao = db_session.query(ContribuicaoOuvinte).one()
    contribuicao.ocorrencia = "outra-ocorrencia"
    db_session.commit()
    assert proximo_assunto(db_session, canal[2]) is None


def test_resposta_clara_cria_candidata_sem_publicar_e_limita_por_ouvinte(db_session, canal, monkeypatch):
    b = bloco(db_session, canal)
    confirmar_bloco(db_session, canal, b, "reproduzindo")
    confirmar_bloco(db_session, canal, b, "concluido")
    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", lambda *args: {
        "acao": "conversar", "pergunta": "Obrigado pela lembrança", "responde_discussao": True})
    i = entrada(db_session, canal, texto="Oceano marcou minha infância")
    processar_entrada(db_session, i.id)
    segunda = entrada(db_session, canal, mid="m2", texto="Eu escutava com minha mãe")
    processar_entrada(db_session, segunda.id)
    assert db_session.query(ContribuicaoOuvinte).count() == 1
    assert db_session.query(ContribuicaoOuvinte).one().estado == "aguardando_revisao"
    assert db_session.query(Assunto).count() == 0


def test_eventos_nao_vazam_entre_contas_e_rollback_nao_publica(db_session, canal, account_factory):
    a, _, _ = canal
    outro = account_factory(email="eventos@outra.test")
    registrar(db_session, a.id, "teste", valor=1)
    db_session.commit()
    registrar(db_session, outro.id, "secreto", valor=2)
    db_session.rollback()
    assert [e["tipo"] for e in depois(db_session, a.id, 0)] == ["teste"]
    assert depois(db_session, outro.id, 0) == []


def test_fixar_repetido_e_descarte_persistente(client, db_session, canal, auth_headers):
    a, _, p = canal
    assunto = Assunto(account_id=a.id, origem="noticia", titulo="Chuva", gancho="chuva", tags=["chuva"])
    db_session.add(assunto)
    db_session.flush()
    ap = AssuntoPrograma(assunto_id=assunto.id, programa_id=p.id, score=5)
    db_session.add(ap)
    db_session.commit()
    headers = auth_headers(a.id)
    path = f"/topics/programas/{p.id}/pauta/{ap.id}"
    primeira = client.post(path + "/fixar", headers=headers).json()
    segunda = client.post(path + "/fixar", headers=headers).json()
    assert primeira["score"] == segunda["score"]
    client.delete(path, headers=headers)
    from app.topics.matcher import _candidatos_nao_casados
    assert _candidatos_nao_casados(db_session, p, a) == []


def test_worker_limita_tentativas_e_preserva_falha_para_operador(db_session, canal, monkeypatch):
    from app.whatsapp.worker import executar_rodada
    i = entrada(db_session, canal)
    monkeypatch.setattr(settings, "whatsapp_tentativas_max", 2)
    monkeypatch.setattr("app.whatsapp.atendimento._atender", lambda *args: (_ for _ in ()).throw(RuntimeError("falha")))
    # O worker real abre uma sessão por tarefa. Reusar a sessão da fixture após
    # rollback permite ao SQLite reciclar IDs dentro do mesmo identity map.
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    executar_rodada(factory)
    db_session.refresh(i)
    assert i.estado == "pendente" and i.tentativas == 1
    i.disponivel_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    db_session.commit()
    executar_rodada(factory)
    db_session.refresh(i)
    assert i.estado == "falhou" and i.tentativas == 2 and i.erro == "RuntimeError"


def test_redis_indisponivel_adia_sem_esgotar_tentativas(db_session, canal, monkeypatch):
    from redis import ConnectionError
    from app.whatsapp.worker import executar_rodada
    i = entrada(db_session, canal)
    monkeypatch.setattr("app.guardrails.rate_limiter.dentro_do_limite", lambda *args: (_ for _ in ()).throw(ConnectionError("offline")))
    executar_rodada(sessionmaker(bind=db_session.get_bind(), autoflush=False))
    db_session.refresh(i)
    assert i.estado == "pendente" and i.tentativas == 0


def test_resposta_citada_so_recupera_mensagem_do_mesmo_contato(db_session, canal, monkeypatch):
    i = entrada(db_session, canal, texto="Qual artista?")
    processar_entrada(db_session, i.id)
    envio = db_session.query(EnvioWhatsapp).one()
    processar_envio(db_session, envio.id)
    citada = entrada(db_session, canal, mid="m2", texto="Esse mesmo")
    citada.citada_id = "saida-provedor"
    db_session.commit()
    referencias = []
    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", lambda texto, hist, pend: referencias.append(pend["resposta_citada"]) or {"acao": "conversar", "pergunta": "Entendi"})
    processar_entrada(db_session, citada.id)
    assert referencias[0]["texto"] == envio.texto


def test_memoria_privada_exige_fontes_validas_e_expira(db_session, canal, monkeypatch):
    from app.whatsapp.memoria import atualizar, obter
    from app.models.canal_whatsapp import MemoriaConversa
    a, r, _ = canal
    c = ConversaOuvinte(account_id=a.id, telefone="55119999")
    db_session.add(c)
    for _ in range(8):
        db_session.add(InteractionLog(radio_config_id=r.id, telefone=c.telefone, mensagem_usuario="Gosto de MPB", status="guardado"))
    db_session.commit()
    monkeypatch.setattr("app.llm.client.gerar_classificacao", lambda *args: json.dumps({"resumo": "Gosta de MPB", "fontes": [99999]}))
    assert not atualizar(db_session, c)
    ids = [i.id for i in db_session.query(InteractionLog).all()]
    monkeypatch.setattr("app.llm.client.gerar_classificacao", lambda *args: json.dumps({"resumo": "Declarou gostar de MPB", "fontes": ids}))
    assert atualizar(db_session, c)
    assert obter(db_session, c)["fontes"] == ids
    m = db_session.get(MemoriaConversa, c.id)
    m.atualizado_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)
    db_session.commit()
    assert obter(db_session, c) is None


def test_sse_faz_replay_e_libera_conexao_ao_fechar(db_session, canal, auth_headers, monkeypatch):
    import app.whatsapp.central as central
    from app.models.usuario import Usuario
    from app.models.canal_whatsapp import ConexaoEventos
    a, _, _ = canal
    headers = auth_headers(a.id)
    usuario = db_session.query(Usuario).filter_by(account_id=a.id).first()
    registrar(db_session, a.id, "primeiro")
    registrar(db_session, a.id, "segundo")
    db_session.commit()
    async def conectado():
        return False
    request = SimpleNamespace(headers={"authorization": headers["Authorization"], "last-event-id": "1"},
                              cookies={}, is_disconnected=conectado)
    monkeypatch.setattr(central, "SessionLocal", lambda: nullcontext(db_session))
    async def consumir():
        response = await central.eventos(request, 0, usuario, db_session)
        assert db_session.query(ConexaoEventos).count() == 1
        evento = await response.body_iterator.__anext__()
        assert '"tipo": "segundo"' in evento and "id: 2" in evento
        await response.body_iterator.aclose()
        assert db_session.query(ConexaoEventos).count() == 0
    asyncio.run(consumir())


def test_excluir_programa_preserva_evidencias_do_canal(client, db_session, canal, auth_headers):
    b = bloco(db_session, canal)
    confirmar_bloco(db_session, canal, b, "reproduzindo")
    confirmar_bloco(db_session, canal, b, "concluido")
    i = entrada(db_session, canal)
    resposta = client.delete(f"/config/programas/{canal[2].id}", headers=auth_headers(canal[0].id))
    assert resposta.status_code == 204
    db_session.refresh(i)
    db_session.refresh(b)
    assert i.programa_id is None and i.estado == "expirada"
    assert b.programa_id is None and b.fala
    assert db_session.query(DiscussaoPrograma).one().estado == "encerrada"


def test_migracao_canal_e_aditiva_e_idempotente(db_session, canal):
    from app.db.migrations.canal_whatsapp_20261112 import aplicar
    from sqlalchemy import inspect
    i = entrada(db_session, canal)
    assert not aplicar(db_session.get_bind())
    assert not aplicar(db_session.get_bind())
    assert db_session.get(EntradaWhatsapp, i.id).texto
    indices = {i["name"] for i in inspect(db_session.get_bind()).get_indexes("whatsapp_entradas")}
    assert "ix_whatsapp_entrada_trabalho" in indices


def test_postgres_dois_workers_nao_duplicam_atendimento(postgres, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_debounce_s", 0)
    monkeypatch.setattr("app.whatsapp.atendimento.interpretar", lambda *args: {"acao": "conversar", "pergunta": "Recebi seu recado"})
    monkeypatch.setattr("app.guardrails.content_filter.avaliar_adequacao_programa", lambda *args: (True, ""))
    with postgres() as db:
        a = Account(nome_radio="Teste", atendimento_ouvinte_ativo=True, wuzapi_token="teste")
        db.add(a)
        db.flush()
        r = RadioConfig(account_id=a.id, timezone="America/Sao_Paulo", resposta_automatica_whatsapp=True)
        db.add(r)
        db.flush()
        p = Programa(radio_config_id=r.id, nome="Teste", horario_inicio=datetime.time(0), horario_fim=datetime.time(23, 59, 59))
        db.add(p)
        db.commit()
        i = entrada(db, (a, r, p))
        item_id = i.id
    barreira = threading.Barrier(2)
    def executar(_):
        with postgres() as db:
            barreira.wait(timeout=5)
            try:
                processar_entrada(db, item_id)
            except HTTPException as exc:
                assert exc.status_code == 503
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(executar, [1, 2]))
    with postgres() as db:
        assert db.query(InteractionLog).count() == 1
        assert db.query(EnvioWhatsapp).count() == 1


@pytest.fixture
def postgres():
    url = os.environ.get("WHATSAPP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina WHATSAPP_TEST_DATABASE_URL para PostgreSQL de teste isolado")
    engine = create_engine(url)
    schema = "whatsapp_test_" + uuid.uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    teste = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(teste)
    try:
        yield sessionmaker(bind=teste, expire_on_commit=False)
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_postgres_trava_sobrevive_commit_e_bloqueia_outro_worker(postgres):
    with postgres() as primeiro, postgres() as segundo:
        with bloquear_conversa(1, "55119999", primeiro):
            primeiro.commit()
            with pytest.raises(HTTPException):
                with bloquear_conversa(1, "55119999", segundo):
                    pytest.fail("Dois workers adquiriram a mesma conversa")
        with bloquear_conversa(1, "55119999", segundo):
            segundo.commit()


def test_postgres_eventos_concorrentes_tem_ordem_de_commit(postgres):
    with postgres() as db:
        a = Account(nome_radio="Teste")
        db.add(a)
        db.commit()
        aid = a.id
    barreira = threading.Barrier(2)
    def gravar(numero):
        with postgres() as db:
            barreira.wait(timeout=5)
            evento = registrar(db, aid, "teste", numero=numero)
            db.commit()
            return evento.sequencia
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(gravar, [1, 2]))
    assert sorted(resultados) == [1, 2]
    with postgres() as db:
        assert [e["id"] for e in depois(db, aid, 0)] == [1, 2]
