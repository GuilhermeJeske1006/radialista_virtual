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
