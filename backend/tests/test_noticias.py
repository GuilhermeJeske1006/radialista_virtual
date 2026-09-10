import datetime
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from app.config.redis_client import redis_client
from app.llm import noticias

AGORA = datetime.datetime(2026, 9, 10, 12, tzinfo=datetime.timezone.utc)
URL = "https://jornal.example.com/cidade/obra"


def _resposta(url=URL, citado=True):
    citacoes = [NS(type="web_search_result_location", url=url, title="Jornal da Cidade")] if citado else []
    return NS(stop_reason="end_turn", content=[
        NS(type="text", text="Vou pesquisar agora.", citations=[]),
        NS(type="web_search_tool_result", content=[NS(url=url)]),
        NS(type="text", text="Em 10/09/2026, a prefeitura anunciou uma nova escola.", citations=citacoes),
    ])


@pytest.fixture()
def configuracao():
    return NS(
        id=7, nome="Jornal da manhã", pode_pesquisar=True,
        fontes_noticias=["https://jornal.example.com/cidade"], fontes_pesquisa=["outro.example.com"],
        tipos_noticias=["educação"], topicos_permitidos=["notícias locais"],
        topicos_proibidos=["fofoca"], instrucoes_pesquisa="Priorize serviços públicos",
    ), NS(id=3, cidade="Guabiruba, SC")


def test_busca_real_recebe_ferramenta_fontes_data_e_cidade(configuracao, monkeypatch):
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    pesquisa = noticias.pesquisar_noticias(*configuracao, agora=AGORA, assunto="educação")
    args = chamada.call_args.kwargs
    assert args["tools"] == [{
        "type": "web_search_20250305", "name": "web_search", "max_uses": 3,
        "allowed_domains": ["jornal.example.com"],
    }]
    pauta = json.loads(args["messages"][0]["content"])
    assert pauta["agora"] == AGORA.isoformat()
    assert pauta["cidade"] == "Guabiruba, SC"
    assert pauta["assunto"] == "educação"
    assert pesquisa.status == "ok"
    assert pesquisa.fontes[0].url == URL
    assert "Vou pesquisar" not in pesquisa.texto


def test_desabilitada_nao_chama_api(configuracao, monkeypatch):
    configuracao[0].pode_pesquisar = False
    chamada = Mock(side_effect=AssertionError("não pesquisar"))
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    assert noticias.pesquisar_noticias(*configuracao, agora=AGORA).status == "desabilitada"
    chamada.assert_not_called()


@pytest.mark.parametrize("resposta", [
    _resposta(citado=False),
    _resposta(url="https://jornal.example.com.evil.org/noticia"),
    NS(stop_reason="end_turn", content=[_resposta().content[-1]]),
])
def test_sem_citacao_resultado_ou_dominio_permitido_nao_gera_noticia(configuracao, monkeypatch, resposta):
    monkeypatch.setattr(noticias._client.messages, "create", Mock(return_value=resposta))
    pesquisa = noticias.pesquisar_noticias(*configuracao, agora=AGORA)
    assert pesquisa.status == "sem_resultados"
    assert pesquisa.texto == ""
    assert pesquisa.fontes == []


def test_www_configurado_ou_citado_nao_perde_match_de_dominio(configuracao, monkeypatch):
    # Fonte cadastrada sem "www.", materia citada com "www." (e vice-versa em outro teste
    # seria simetrico) -- sao o mesmo veiculo, nao pode virar sem_resultados por causa disso.
    url_com_www = "https://www.jornal.example.com/cidade/obra"
    chamada = Mock(return_value=_resposta(url=url_com_www))
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    pesquisa = noticias.pesquisar_noticias(*configuracao, agora=AGORA)
    assert pesquisa.status == "ok"
    assert pesquisa.fontes[0].url == url_com_www


def test_cache_reutiliza_busca_e_mudanca_editorial_invalida(configuracao, monkeypatch):
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    for _ in range(2):
        assert noticias.pesquisar_noticias(*configuracao, agora=AGORA).status == "ok"
    assert chamada.call_count == 1
    assert redis_client.ttl(redis_client.keys("noticias:*")[0]) == 300
    configuracao[0].topicos_proibidos = ["educação"]
    noticias.pesquisar_noticias(*configuracao, agora=AGORA)
    assert chamada.call_count == 2


def test_cache_isolado_por_conta_e_dia(configuracao, monkeypatch):
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    noticias.pesquisar_noticias(*configuracao, agora=AGORA)
    configuracao[1].id = 9
    noticias.pesquisar_noticias(*configuracao, agora=AGORA)
    noticias.pesquisar_noticias(*configuracao, agora=AGORA + datetime.timedelta(days=1))
    assert chamada.call_count == 3


def test_falha_de_rede_faz_fallback_e_cache_curto(configuracao, monkeypatch):
    chamada = Mock(side_effect=TimeoutError())
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    for _ in range(2):
        pesquisa = noticias.pesquisar_noticias(*configuracao, agora=AGORA)
        assert pesquisa.status == "indisponivel"
        assert "Não há notícias verificadas" in noticias.contexto_noticias(pesquisa)
    assert chamada.call_count == 1
    assert redis_client.ttl(redis_client.keys("noticias:*")[0]) == 60


def test_erro_da_ferramenta_em_http_200(configuracao, monkeypatch):
    resposta = NS(stop_reason="end_turn", content=[
        NS(type="web_search_tool_result", content=NS(error_code="unavailable")),
    ])
    monkeypatch.setattr(noticias._client.messages, "create", Mock(return_value=resposta))
    assert noticias.pesquisar_noticias(*configuracao, agora=AGORA).status == "indisponivel"


def test_pause_turn_continua_preservando_resultados(configuracao, monkeypatch):
    resposta = _resposta()
    parcial = NS(stop_reason="pause_turn", content=resposta.content[:2])
    final = NS(stop_reason="end_turn", content=resposta.content[2:])
    chamada = Mock(side_effect=[parcial, final])
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    pesquisa = noticias.pesquisar_noticias(*configuracao, agora=AGORA)
    assert pesquisa.status == "ok"
    assert chamada.call_count == 2
    assert chamada.call_args.kwargs["messages"][1]["content"] is parcial.content


@pytest.mark.parametrize("motivo", ["max_tokens", "refusal", "pause_turn"])
def test_resposta_incompleta_nao_vira_noticia(configuracao, monkeypatch, motivo):
    resposta = _resposta()
    resposta.stop_reason = motivo
    chamada = Mock(return_value=resposta)
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    assert noticias.pesquisar_noticias(*configuracao, agora=AGORA).status == "indisponivel"
    assert chamada.call_count <= 2


def test_sem_fontes_usa_busca_publica_com_pauta(configuracao, monkeypatch):
    configuracao[0].fontes_noticias = []
    configuracao[0].fontes_pesquisa = []
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(noticias._client.messages, "create", chamada)
    assert noticias.pesquisar_noticias(*configuracao, agora=AGORA).status == "ok"
    assert "allowed_domains" not in chamada.call_args.kwargs["tools"][0]


def test_falha_redis_nao_interrompe_pesquisa(configuracao, monkeypatch):
    monkeypatch.setattr(noticias.redis_client, "get", Mock(side_effect=ConnectionError()))
    monkeypatch.setattr(noticias.redis_client, "set", Mock(side_effect=ConnectionError()))
    monkeypatch.setattr(noticias._client.messages, "create", Mock(return_value=_resposta()))
    assert noticias.pesquisar_noticias(*configuracao, agora=AGORA).status == "ok"
