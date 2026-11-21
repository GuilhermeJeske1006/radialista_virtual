import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest
from redis.exceptions import ConnectionError

from app.guardrails import provedores as p


@pytest.fixture(autouse=True)
def limites(monkeypatch):
    monkeypatch.setattr(p.settings, "ia_fila_espera_s", 2)
    monkeypatch.setattr(p.settings, "ia_limites_provedores", {
        "tts": {"concorrencia": 3}, "llm": {"concorrencia": 2, "rpm": 60, "entrada": 1000, "saida": 1000},
        "stt": {"concorrencia": 1}, "music": {"concorrencia": 1}})
    monkeypatch.setattr(p.settings, "ia_limites_por_pool", {})


def test_pico_de_30_radios_respeita_concorrencia_e_libera_todas_as_vagas():
    ativos = pico = 0
    trava = threading.Lock()

    def radio(_):
        def gerar(restante):
            nonlocal ativos, pico
            assert restante > 0
            with trava:
                ativos += 1
                pico = max(pico, ativos)
            time.sleep(.015)
            with trava:
                ativos -= 1
            return SimpleNamespace(status_code=200)
        return p.executar("tts", "v3", gerar, timeout_s=4)

    with ThreadPoolExecutor(max_workers=30) as executor:
        respostas = list(executor.map(radio, range(30)))
    estado = json.loads(p.redis_client.get(p._chave("tts")))
    assert len(respostas) == 30
    assert pico == 3
    assert estado["ativos"] == estado["fila"] == {}


def test_falha_e_close_de_stream_liberam_lease():
    with pytest.raises(RuntimeError):
        with p.vaga("tts", prazo=p.prazo_operacao(1)):
            raise RuntimeError("socket caiu")
    assert json.loads(p.redis_client.get(p._chave("tts")))["ativos"] == {}


def test_recupera_lease_de_worker_morto_e_remove_fila_abandonada():
    chave = p._chave("tts")
    p.redis_client.set(chave, json.dumps({"ativos": {"morto": {"expira": 0}},
                                          "fila": {"morto": {"expira": 0}}}))
    with p.vaga("tts", prazo=p.prazo_operacao(1)):
        estado = json.loads(p.redis_client.get(chave))
        assert len(estado["ativos"]) == 1
        assert "morto" not in estado["fila"]


def test_tokens_reconciliam_uso_real_sem_consumir_cache_read():
    resposta = SimpleNamespace(usage=SimpleNamespace(input_tokens=20, output_tokens=5,
                               cache_creation_input_tokens=10, cache_read_input_tokens=500))
    p.executar("llm", "modelo", lambda _: resposta, timeout_s=1, entrada=200, saida=100)
    estado = json.loads(p.redis_client.get(p._chave("llm:modelo")))
    assert 970 <= estado["entrada"] < 971
    assert 995 <= estado["saida"] < 996
    assert 59 <= estado["rpm"] < 60


def test_429_devolve_reserva_de_tokens_para_a_retentativa():
    respostas = iter([SimpleNamespace(status_code=429, headers={"retry-after": "0"}),
                      SimpleNamespace(status_code=200, usage=SimpleNamespace(input_tokens=900, output_tokens=500))])
    assert p.executar("llm", "modelo", lambda _: next(respostas), timeout_s=1,
                      entrada=1000, saida=800).status_code == 200


def test_texto_acima_do_bucket_nao_chama_provedor():
    with pytest.raises(p.CapacidadeIndisponivel):
        p.executar("llm", "modelo", lambda _: pytest.fail("chamada indevida"), timeout_s=1, entrada=1001)


def test_limites_de_modelos_compartilhados_e_credenciais():
    assert p.nome_pool("llm", "claude-opus-4-6-20260205") == p.nome_pool("llm", "claude-opus-4-7")
    assert p.nome_pool("llm", "claude-haiku-4-5-20251001") == "llm:claude-haiku-4-5"
    assert p.nome_pool("tts", "eleven_v3") == p.nome_pool("tts", "eleven_flash_v2_5")
    assert p._chave("tts") != p._chave("llm:modelo")


def test_redis_fora_nao_dispara_chamadas_pagas(monkeypatch):
    monkeypatch.setattr(p, "_agora", lambda: (_ for _ in ()).throw(ConnectionError("fora")))
    with pytest.raises(p.CapacidadeIndisponivel):
        p.executar("tts", "v3", lambda _: pytest.fail("chamada indevida"), timeout_s=1)


def test_retry_after_longo_publica_cooldown_sem_esperar_nem_repetir():
    chamadas = []
    resposta = SimpleNamespace(status_code=429, headers={"retry-after": "120"})
    assert p.executar("tts", "v3", lambda _: chamadas.append(1) or resposta, timeout_s=1) is resposta
    assert chamadas == [1]
    estado = json.loads(p.redis_client.get(p._chave("tts")))
    assert estado["pausa_ate"] > p._agora() + 118
    assert estado["ativos"] == {}


def test_timeout_ambiguo_nao_repete_post():
    chamadas = []
    def falhar(_):
        chamadas.append(1)
        raise httpx.ReadTimeout("pode ter sido cobrado")
    with pytest.raises(httpx.ReadTimeout):
        p.executar("tts", "v3", falhar, timeout_s=1)
    assert chamadas == [1]


def test_cota_financeira_nao_e_retentada():
    resposta = httpx.Response(429, json={"error": {"details": {"error_code": "enforced_spend_limit_reached"}}})
    assert not p.espera_retentativa("llm", "modelo", resposta, 1, p.prazo_operacao(5), 3)


def test_retry_after_data_e_milisegundos():
    from email.utils import formatdate
    assert 19 <= p._retry_after({"retry-after": formatdate(time.time() + 20, usegmt=True)}) <= 20
    assert p._retry_after({"retry-after-ms": "1500"}) == 1.5
    assert p._retry_after({"retry-after": "nan"}) is None
    assert p._retry_after({"retry-after-ms": "inf"}) is None
    assert p._retry_after({"retry-after": "inválido"}) is None


def test_fila_cheia_e_prazo_curto_nao_disparam_chamada(monkeypatch):
    monkeypatch.setattr(p.settings, "ia_fila_max", 0)
    with pytest.raises(p.CapacidadeIndisponivel):
        p.executar("tts", "v3", lambda _: pytest.fail("não deve chamar"), timeout_s=.01)
    assert json.loads(p.redis_client.get(p._chave("tts")))["fila"] == {}


def test_fila_prioriza_ao_vivo_sobre_background():
    agora = p._agora()
    chave = p._chave("tts")
    p.redis_client.set(chave, json.dumps({"fila": {"background": {
        "prioridade": 2, "ordem": agora - 1, "expira": agora + 10}}}))
    with p.contexto_capacidade(prioridade=0):
        with p.vaga("tts", prazo=p.prazo_operacao(.5)):
            assert "background" in json.loads(p.redis_client.get(chave))["fila"]


def test_estado_expoe_metricas_sem_credenciais():
    p.executar("tts", "v3", lambda _: SimpleNamespace(status_code=200), timeout_s=1)
    resultado = p.estado_provedores()
    tts = next(x for x in resultado["provedores"] if x["pool"] == "tts")
    assert tts["ultimos_15_minutos"]["sucessos"] == 1
    assert tts["ativos"] == 0
    assert p.settings.anthropic_api_key not in json.dumps(resultado)


def test_capacidade_restrita_a_administracao_do_sistema(client, account, auth_headers, db_session):
    from app.auth.security import criar_token
    from app.models.super_admin import SuperAdmin
    assert client.get("/admin/ia/capacidade").status_code == 401
    assert client.get("/admin/ia/capacidade", headers=auth_headers(account.id)).status_code == 401
    admin = SuperAdmin(email="root@teste.com", senha_hash="nao-usada-neste-teste")
    db_session.add(admin)
    db_session.commit()
    resposta = client.get("/admin/ia/capacidade", headers={"Authorization": f"Bearer {criar_token(admin.id, tipo='super_admin')}"})
    assert resposta.status_code == 200
    assert resposta.json()["redis_disponivel"]


def test_headers_publicados_pelo_provedor_aparecem_na_administracao():
    p.executar("tts", "v3", lambda _: SimpleNamespace(status_code=200,
               headers={"maximum-concurrent-requests": "5", "xi-api-key": "nao-expor"}), timeout_s=1)
    tts = next(x for x in p.estado_provedores()["provedores"] if x["pool"] == "tts")
    assert tts["observado"] == {"maximum-concurrent-requests": 5}


def test_retentativa_de_excecao_do_sdk_anthropic():
    from anthropic import RateLimitError
    resposta = httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("POST", "https://teste/messages"))
    chamadas = []
    def chamar(_):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RateLimitError("ocupado", response=resposta, body={})
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=30, output_tokens=5))
    assert p.executar("llm", "modelo", chamar, timeout_s=1, entrada=100, saida=100).usage.output_tokens == 5
    assert chamadas == [1, 1]


def test_imagem_grande_nao_conta_base64_como_tokens_textuais():
    from app.llm.economia import _entrada_para_capacidade
    dados = {"messages": [{"content": [{"type": "image", "source": {"type": "base64", "data": "A" * 100_000}},
                                         {"type": "text", "text": "Descreva"}]}]}
    assert _entrada_para_capacidade(dados) < 10_000
    assert len(dados["messages"][0]["content"][0]["source"]["data"]) == 100_000
