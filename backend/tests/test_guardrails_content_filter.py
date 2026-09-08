import json

from app.guardrails.content_filter import (
    TERMOS_SEMPRE_BLOQUEADOS,
    avaliar_adequacao_ao_vivo,
    avaliar_adequacao_programa,
    contem_topico_proibido,
)
from app.models.programa import Programa


def _programa(topicos_proibidos=None):
    return Programa(topicos_proibidos=topicos_proibidos or [])


def test_termo_sempre_bloqueado_e_detectado_mesmo_sem_configuracao():
    programa = _programa()
    assert contem_topico_proibido("quero comprar uma arma", programa) is True


def test_termo_configurado_pela_radio_e_detectado():
    programa = _programa(topicos_proibidos=["futebol"])
    assert contem_topico_proibido("vamos falar de futebol hoje", programa) is True


def test_texto_sem_termo_proibido_passa():
    programa = _programa(topicos_proibidos=["futebol"])
    assert contem_topico_proibido("qual a previsao do tempo?", programa) is False


def test_deteccao_e_case_insensitive():
    programa = _programa(topicos_proibidos=["Politica"])
    assert contem_topico_proibido("vamos falar de POLITICA agora", programa) is True


def test_todos_os_termos_sempre_bloqueados_sao_detectados():
    programa = _programa()
    for termo in TERMOS_SEMPRE_BLOQUEADOS:
        assert contem_topico_proibido(f"mensagem contendo {termo} no meio", programa) is True


def test_avaliar_adequacao_aprova_quando_llm_diz_adequado(monkeypatch):
    monkeypatch.setattr(
        "app.guardrails.content_filter.gerar_classificacao",
        lambda system, user: json.dumps({"adequado": True, "motivo": "cabe no tom do programa"}),
    )
    adequado, motivo = avaliar_adequacao_programa("mensagem qualquer", _programa())
    assert adequado is True
    assert motivo == "cabe no tom do programa"


def test_avaliar_adequacao_reprova_quando_llm_diz_inadequado(monkeypatch):
    monkeypatch.setattr(
        "app.guardrails.content_filter.gerar_classificacao",
        lambda system, user: json.dumps({"adequado": False, "motivo": "fora do tom do programa"}),
    )
    adequado, motivo = avaliar_adequacao_programa("mensagem qualquer", _programa())
    assert adequado is False
    assert motivo == "fora do tom do programa"


def test_avaliar_adequacao_falha_do_llm_cai_pro_lado_seguro(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha de rede")

    monkeypatch.setattr("app.guardrails.content_filter.gerar_classificacao", _levanta)
    adequado, motivo = avaliar_adequacao_programa("mensagem qualquer", _programa())
    assert adequado is False
    assert motivo == "falha_avaliacao_llm"


def test_avaliar_adequacao_resposta_nao_json_cai_pro_lado_seguro(monkeypatch):
    monkeypatch.setattr(
        "app.guardrails.content_filter.gerar_classificacao", lambda system, user: "isso nao e json"
    )
    adequado, motivo = avaliar_adequacao_programa("mensagem qualquer", _programa())
    assert adequado is False
    assert motivo == "falha_avaliacao_llm"


def test_avaliar_adequacao_ao_vivo_aprova_quando_llm_diz_apropriado(monkeypatch):
    monkeypatch.setattr(
        "app.guardrails.content_filter.gerar_classificacao",
        lambda system, user: json.dumps({"apropriado": True, "motivo": "transcricao clara"}),
    )
    apropriado, motivo = avaliar_adequacao_ao_vivo("toca uma musica", _programa())
    assert apropriado is True
    assert motivo == "transcricao clara"


def test_avaliar_adequacao_ao_vivo_reprova_quando_llm_diz_inapropriado(monkeypatch):
    monkeypatch.setattr(
        "app.guardrails.content_filter.gerar_classificacao",
        lambda system, user: json.dumps(
            {"apropriado": False, "motivo": "transcricao incoerente, provavel ruido de fundo"}
        ),
    )
    apropriado, motivo = avaliar_adequacao_ao_vivo("asdf asdf nao sei nao consigo", _programa())
    assert apropriado is False
    assert motivo == "transcricao incoerente, provavel ruido de fundo"


def test_avaliar_adequacao_ao_vivo_falha_do_llm_cai_pro_lado_seguro(monkeypatch):
    def _levanta(*args, **kwargs):
        raise RuntimeError("falha de rede")

    monkeypatch.setattr("app.guardrails.content_filter.gerar_classificacao", _levanta)
    apropriado, motivo = avaliar_adequacao_ao_vivo("mensagem qualquer", _programa())
    assert apropriado is False
    assert motivo == "falha_avaliacao_llm"
