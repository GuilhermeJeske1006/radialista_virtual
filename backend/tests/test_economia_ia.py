from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace
import time

from fastapi import HTTPException
from freezegun import freeze_time
import pytest
from sqlalchemy import select

from app.billing import consumo_ia
from app.billing.contexto_ia import atual, contexto_conta, tarefa_com_contexto
from app.config.settings import settings
from app.llm import client as llm
from app.models.consumo_flex import ContaConsumo
from app.tts.cache import cache_audio


@dataclass
class Conta:
    id: int = 1
    plano: str = "starter"














def test_sem_conta_bloqueia_e_contexto_nao_vaza(monkeypatch):
    with contexto_conta(Conta()):
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(tarefa_com_contexto(lambda: atual.get().id)).result() == 1
    assert atual.get() is None
    monkeypatch.setattr(settings, "ia_orcamento_bloquear", True)
    with pytest.raises(HTTPException) as exc:
        consumo_ia.reservar("tts", "teste", 1)
    assert exc.value.status_code == 503





def test_llm_cache_classificacao_preserva_texto_e_separa_contas(monkeypatch):
    chamadas = []
    def responder(**kwargs):
        chamadas.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="calmo")])
    monkeypatch.setattr(llm._client.messages, "create", responder)
    with contexto_conta(Conta()):
        assert llm.gerar_classificacao(llm._TOM_SYSTEM_PROMPT, "texto") == "calmo"
        assert llm.gerar_classificacao(llm._TOM_SYSTEM_PROMPT, "texto") == "calmo"
    with contexto_conta(Conta(id=2)):
        assert llm.gerar_classificacao(llm._TOM_SYSTEM_PROMPT, "texto") == "calmo"
    assert len(chamadas) == 2


def test_sugestoes_criativas_nao_ficam_congeladas_no_cache(monkeypatch):
    musicas = iter(["Artista - Música A", "Artista - Música B"])
    monkeypatch.setattr(llm._client.messages, "create", lambda **kwargs: SimpleNamespace(
        stop_reason="end_turn", content=[SimpleNamespace(type="text", text=next(musicas))],
    ))
    assert llm.sugerir_musica_do_genero("pop") == "Artista - Música A"
    assert llm.sugerir_musica_do_genero("pop") == "Artista - Música B"


def test_cache_audio_concorrente_preserva_bytes():
    chamadas = []
    @cache_audio
    def sintetizar(texto, voice_id=None, modelo=None, formato="mp3", texto_anterior=None):
        chamadas.append(texto)
        time.sleep(.08)
        return b"audio-original-sem-alteracao"
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: sintetizar("Oi"), range(2)))
    assert resultados == [b"audio-original-sem-alteracao"] * 2
    assert len(chamadas) == 1


def test_cache_buffered_reutilizado_no_stream_e_invalida_parametros():
    chamadas = []
    @cache_audio
    def buffered(texto, voice_id=None, modelo=None, formato="mp3", texto_anterior=None):
        chamadas.append(1)
        return b"abc"
    @cache_audio
    def stream(texto, voice_id=None, modelo=None, formato="mp3", texto_anterior=None):
        raise AssertionError("não deveria chamar o provedor")
        yield b""
    assert buffered("Oi", voice_id="a") == b"abc"
    assert b"".join(stream("Oi", voice_id="a")) == b"abc"
    buffered("Oi", voice_id="b")
    buffered("Oi", voice_id="a", formato="pcm")
    buffered("Oi", voice_id="a", modelo="eleven_flash_v2_5")
    with contexto_conta(Conta()):
        buffered("Oi", voice_id="a")
    assert len(chamadas) == 5


def test_stream_interrompido_nao_cacheia_audio_parcial():
    chamadas = []
    @cache_audio
    def stream(texto):
        chamadas.append(1)
        yield b"inicio"
        yield b"fim"
    gerador = stream("Oi")
    assert next(gerador) == b"inicio"
    gerador.close()
    assert b"".join(stream("Oi")) == b"iniciofim"
    assert b"".join(stream("Oi")) == b"iniciofim"
    assert len(chamadas) == 2


def test_prompt_cache_nao_remove_nem_altera_instrucoes(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_cache", True)
    chamadas = []
    def responder(**kwargs):
        chamadas.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Olá!")])
    monkeypatch.setattr(llm._client.messages, "create", responder)
    assert llm.gerar_resposta("Regras importantes.\nFatos confirmados.", "Pedido") == "Olá!"
    assert chamadas[0]["system"][0]["text"] == "Regras importantes.\nFatos confirmados."
    assert chamadas[0]["messages"] == [{"role": "user", "content": "Pedido"}]


def test_middleware_preserva_conta_em_dependencia_sync_e_stream():
    from fastapi import Depends, FastAPI
    from fastapi.responses import StreamingResponse
    from fastapi.testclient import TestClient
    from app.billing.contexto_ia import ContextoIAMiddleware, identificar
    app = FastAPI()
    app.add_middleware(ContextoIAMiddleware)

    def identificar_conta(conta_id: int):
        identificar(Conta(id=conta_id))

    @app.get("/teste")
    def rota(_=Depends(identificar_conta)):
        def corpo():
            yield str(atual.get().id)
            yield str(atual.get().id)
        return StreamingResponse(corpo())

    with TestClient(app) as client:
        assert client.get("/teste?conta_id=7").text == "77"
        assert client.get("/teste?conta_id=8").text == "88"
    assert atual.get() is None





def test_regeracao_explicita_pode_ignorar_cache():
    chamadas = []
    @cache_audio
    def sintetizar(texto, reutilizar_audio=True):
        chamadas.append(texto)
        return str(len(chamadas)).encode()
    assert sintetizar("Oi") == b"1"
    assert sintetizar("Oi") == b"1"
    assert sintetizar("Oi", reutilizar_audio=False) == b"2"


def test_consumo_http_isola_contas_e_mostra_alerta(client, account_factory, auth_headers, db_session, monkeypatch):
    import datetime
    conta1 = account_factory(email="custo1@teste.com")
    conta2 = account_factory(email="custo2@teste.com")
    mes = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    monkeypatch.setattr(settings, "ia_orcamentos_brl", {"starter": 10})
    db_session.add(ContaConsumo(account_id=conta1.id, limite=10_000_000, exposicao=9_000_000))
    db_session.commit()
    primeira = client.get("/billing/consumo-ia", headers=auth_headers(conta1.id)).json()
    segunda = client.get("/billing/consumo-ia", headers=auth_headers(conta2.id)).json()
    assert primeira["aviso"] == "90_porcento"
    assert primeira["disponivel_brl"] == 1
    assert segunda["comprometido_brl"] == 0
    assert client.get("/billing/consumo-ia").status_code == 401


def test_conta_isenta_nao_mede_nem_bloqueia(monkeypatch):
    with contexto_conta(Conta()):
        assert atual.get().faturavel is True
    monkeypatch.setattr(settings, "ia_medicao_habilitada", True)
    monkeypatch.setattr(settings, "ia_orcamento_bloquear", True)
    with contexto_conta(SimpleNamespace(id=2, plano="flex", cobranca_isenta=True)):
        assert atual.get().faturavel is False
        assert consumo_ia.reservar("llm", "claude-opus-5", unidades_max={"entrada": 1}) is None


def test_identificar_conta_isenta_desliga_cobranca_da_request():
    from app.billing.contexto_ia import ContaIA, identificar

    for account, faturavel in ((SimpleNamespace(id=2, plano="flex", cobranca_isenta=True), False),
                               (SimpleNamespace(id=3, plano="flex", cobranca_isenta=False), True),
                               (Conta(id=4), True)):
        token = atual.set(ContaIA(funcionalidade="programa_ao_vivo"))
        try:
            identificar(account)
            assert atual.get().faturavel is faturavel
        finally:
            atual.reset(token)
