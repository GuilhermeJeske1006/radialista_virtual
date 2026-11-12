import httpx

from app.weather import client as weather_client


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


def test_obter_clima_atual_sem_cidade_devolve_none():
    assert weather_client.obter_clima_atual("") is None
    assert weather_client.obter_clima_atual(None) is None


def test_obter_clima_atual_fluxo_completo(monkeypatch):
    respostas = [
        _FakeResponse({"results": [{"latitude": -30.0, "longitude": -51.2}]}),
        _FakeResponse({"current": {"temperature_2m": 23.4, "weather_code": 1}}),
    ]

    def _fake_get(url, **kwargs):
        return respostas.pop(0)

    monkeypatch.setattr(weather_client.httpx, "get", _fake_get)

    resultado = weather_client.obter_clima_atual("Porto Alegre")
    assert resultado == "23°C, predomínio de sol"


def test_obter_clima_atual_usa_cache_na_segunda_chamada(monkeypatch):
    chamadas = []

    def _fake_get(url, **kwargs):
        chamadas.append(url)
        if "geocoding" in url:
            return _FakeResponse({"results": [{"latitude": -30.0, "longitude": -51.2}]})
        return _FakeResponse({"current": {"temperature_2m": 20.0, "weather_code": 0}})

    monkeypatch.setattr(weather_client.httpx, "get", _fake_get)

    primeira = weather_client.obter_clima_atual("Porto Alegre")
    segunda = weather_client.obter_clima_atual("Porto Alegre")

    assert primeira == segunda == "20°C, céu limpo"
    assert len(chamadas) == 2  # so' a primeira chamada bateu na rede


def test_obter_clima_atual_cidade_nao_encontrada_devolve_none(monkeypatch):
    monkeypatch.setattr(weather_client.httpx, "get", lambda url, **kwargs: _FakeResponse({"results": []}))
    assert weather_client.obter_clima_atual("CidadeQueNaoExiste") is None


def test_obter_clima_atual_falha_de_rede_no_geocoding_devolve_none(monkeypatch):
    def _fake_get(url, **kwargs):
        raise httpx.ConnectError("falhou")

    monkeypatch.setattr(weather_client.httpx, "get", _fake_get)
    assert weather_client.obter_clima_atual("Porto Alegre") is None


def test_obter_clima_atual_falha_no_forecast_devolve_none(monkeypatch):
    respostas = [
        _FakeResponse({"results": [{"latitude": -30.0, "longitude": -51.2}]}),
    ]

    def _fake_get(url, **kwargs):
        if respostas:
            return respostas.pop(0)
        raise httpx.ConnectError("falhou")

    monkeypatch.setattr(weather_client.httpx, "get", _fake_get)
    assert weather_client.obter_clima_atual("Porto Alegre") is None


def test_obter_clima_atual_codigo_desconhecido_usa_descricao_generica(monkeypatch):
    respostas = [
        _FakeResponse({"results": [{"latitude": -30.0, "longitude": -51.2}]}),
        _FakeResponse({"current": {"temperature_2m": 25.0, "weather_code": 999}}),
    ]
    monkeypatch.setattr(weather_client.httpx, "get", lambda url, **kwargs: respostas.pop(0))
    resultado = weather_client.obter_clima_atual("Porto Alegre")
    assert resultado == "25°C, tempo variável"


# --- F5 (U5): leitura com horário, cache v2 e última leitura -------------------------------------------------

import datetime  # noqa: E402

from app.config.redis_client import redis_client  # noqa: E402
from app.dados.verificavel import CONFIG_DADOS  # noqa: E402


def _rede(respostas):
    def _fake_get(url, **kwargs):
        if "geocoding" in url:
            return _FakeResponse({"results": [{"latitude": -26.3, "longitude": -49.3}]})
        resposta = respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta
    return _fake_get


def test_leitura_tem_horario_da_observacao_em_utc(monkeypatch):
    monkeypatch.setattr(weather_client.httpx, "get", _rede([_FakeResponse({
        "utc_offset_seconds": -10800,
        "current": {"time": "2026-11-10T14:15", "temperature_2m": 26.4, "weather_code": 0}})]))
    leitura = weather_client.obter_leitura_clima("Campo Alegre")
    assert leitura.observado_em == datetime.datetime(2026, 11, 10, 17, 15, tzinfo=datetime.timezone.utc)
    assert (leitura.temperatura_c, leitura.codigo, leitura.descricao) == (26.4, 0, "céu limpo")
    assert leitura.cidade == "Campo Alegre" and leitura.ultima_leitura is False
    assert leitura.consultado_em.tzinfo is not None


def test_leitura_sem_time_usa_a_hora_da_consulta(monkeypatch):
    monkeypatch.setattr(weather_client.httpx, "get", _rede([_FakeResponse({
        "current": {"temperature_2m": 20.0, "weather_code": 3}})]))
    leitura = weather_client.obter_leitura_clima("Campo Alegre")
    assert leitura.observado_em == leitura.consultado_em


def test_leitura_usa_cache_v2_e_grava_a_ultima(monkeypatch):
    chamadas = []
    rede = _rede([_FakeResponse({"current": {"time": "2026-11-10T14:00", "temperature_2m": 22, "weather_code": 1}}),
                  ])

    def contar(url, **kwargs):
        chamadas.append(url)
        return rede(url, **kwargs)

    monkeypatch.setattr(weather_client.httpx, "get", contar)
    primeira = weather_client.obter_leitura_clima("Campo Alegre")
    segunda = weather_client.obter_leitura_clima("Campo Alegre")
    assert primeira == segunda and len(chamadas) == 2
    assert redis_client.ttl("weather:leitura:v2:campo alegre") <= CONFIG_DADOS.clima_cache_ttl_s
    assert 0 < redis_client.ttl("weather:ultima:campo alegre") <= CONFIG_DADOS.clima_ultima_leitura_ttl_s


def test_api_fora_devolve_a_ultima_leitura_com_o_horario(monkeypatch):
    monkeypatch.setattr(weather_client.httpx, "get", _rede([
        _FakeResponse({"utc_offset_seconds": -10800,
                       "current": {"time": "2026-11-10T12:00", "temperature_2m": 22, "weather_code": 0}}),
        httpx.ConnectError("caiu"), httpx.ConnectError("caiu de novo")]))
    original = weather_client.obter_leitura_clima("Campo Alegre")
    redis_client.delete("weather:leitura:v2:campo alegre")   # o cache de 30 min venceu
    ultima = weather_client.obter_leitura_clima("Campo Alegre")
    assert ultima.ultima_leitura is True
    assert ultima.observado_em == original.observado_em and ultima.temperatura_c == 22
    # O WhatsApp (obter_clima_atual) não usa a última leitura: sem horário para dizer, segue sem clima.
    assert weather_client.obter_clima_atual("Campo Alegre") is None


def test_sem_cidade_ou_sem_ultima_leitura_devolve_none(monkeypatch):
    assert weather_client.obter_leitura_clima("") is None and weather_client.obter_leitura_clima(None) is None
    monkeypatch.setattr(weather_client.httpx, "get", _rede([httpx.ConnectError("caiu")]))
    assert weather_client.obter_leitura_clima("Campo Alegre") is None


def test_redis_fora_nao_derruba_a_leitura(monkeypatch):
    import redis

    from app.config import redis_client as modulo

    def quebra(*args, **kwargs):
        raise redis.ConnectionError("redis fora")

    for nome in modulo.PADROES_SESSAO:
        monkeypatch.setattr(modulo.redis_client, nome, quebra)
    monkeypatch.setattr(weather_client.httpx, "get", _rede([_FakeResponse({
        "current": {"time": "2026-11-10T14:00", "temperature_2m": 22, "weather_code": 1}})]))
    try:
        assert weather_client.obter_leitura_clima("Campo Alegre").temperatura_c == 22
    finally:
        modulo.disjuntor.fechar()


def test_testes_nao_vao_a_rede_do_clima_por_padrao():
    """Fixture autouse _clima_sem_rede (tests/conftest.py): sem monkeypatch próprio, o Open-Meteo falha."""
    assert weather_client.obter_leitura_clima("Campo Alegre") is None
    assert weather_client.obter_clima_atual("Campo Alegre") is None
