"""Parâmetros por modelo, tarifas dos modelos 5.5 e modelo mais barato para falas curtas (configurável)."""
from types import SimpleNamespace

import pytest

from app.config.settings import settings
from app.live import geracao
from app.llm import client as llm
from app.llm import economia


@pytest.mark.parametrize("modelo,esperado", [
    ("claude-haiku-4-5", {}),
    ("claude-opus-5", {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}),
    ("claude-sonnet-5", {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}),
    ("claude-haiku-5-5", {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}),
    ("claude-opus-5-5", {"output_config": {"effort": "low"}}),  # thinking disabled dá 400 no Opus 5.5
    ("claude-sonnet-5-5", {"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}}),
])
def test_parametros_por_modelo(modelo, esperado):
    assert llm.parametros_modelo(modelo, "low") == esperado


def test_tarifas_e_coeficientes_dos_modelos_55():
    assert settings.ia_tarifas_llm["claude-opus-5-5"] == [4, 20]
    assert settings.ia_tarifas_llm["claude-sonnet-5-5"] == [2, 10]
    assert settings.ia_tarifas_llm["claude-haiku-5-5"] == [0.10, 0.50]
    assert settings.ia_coef_cache_leitura["claude-sonnet-5-5"] == 0.05


def _chamar_com_uso(monkeypatch, modelo, uso, caplog):
    def responder(**kwargs):
        return SimpleNamespace(stop_reason="end_turn", id="r1", content=[SimpleNamespace(type="text", text="ok")],
                               usage=SimpleNamespace(**uso))

    monkeypatch.setattr(llm._client.messages, "create", responder)
    monkeypatch.setattr(economia, "reservar", lambda *a, **k: object())
    monkeypatch.setattr(economia, "concluir", lambda *a, **k: None)
    with caplog.at_level("INFO", logger="radialista.llm.custos"):
        assert llm.gerar_resposta("Regras", "Pedido", model=modelo) == "ok"
    return [r.getMessage() for r in caplog.records if "llm_consumo" in r.getMessage()][-1]


def test_custo_da_leitura_de_cache_usa_o_coeficiente_do_modelo(monkeypatch, caplog):
    uso = dict(input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=10_000)
    sonnet55 = _chamar_com_uso(monkeypatch, "claude-sonnet-5-5", uso, caplog)
    # (2 × (1000 + 0,05 × 10000) + 10 × 100) / 1e6 = 0,004
    assert "usd=0.004000" in sonnet55
    sonnet5 = _chamar_com_uso(monkeypatch, "claude-sonnet-5", uso, caplog)
    # (2 × (1000 + 0,1 × 10000) + 10 × 100) / 1e6 = 0,005
    assert "usd=0.005000" in sonnet5


def _ctx(categoria):
    return SimpleNamespace(categoria=categoria, multi_voz=False)


class _Portas:
    def __init__(self):
        self.chamadas = []

    def gerar_resposta(self, system, mensagem, **kwargs):
        self.chamadas.append(kwargs)
        return "Fala pronta."


def test_modelo_barato_so_nas_falas_curtas_e_so_quando_configurado(monkeypatch):
    monkeypatch.setattr(settings, "llm_model_falas_curtas", "")
    portas = _Portas()
    geracao._gerar_falas_bloco(_ctx("musica"), "m", "s", portas)
    assert portas.chamadas == [{}]  # desligado: chamada idêntica à de sempre

    monkeypatch.setattr(settings, "llm_model_falas_curtas", "claude-sonnet-5-5")
    portas = _Portas()
    geracao._gerar_falas_bloco(_ctx("musica"), "m", "s", portas)
    geracao._gerar_falas_bloco(_ctx("comentario"), "m", "s", portas)
    assert portas.chamadas == [{"model": "claude-sonnet-5-5"}, {}]  # comentário segue no modelo principal
