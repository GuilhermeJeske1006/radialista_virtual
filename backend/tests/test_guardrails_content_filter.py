from app.guardrails.content_filter import TERMOS_SEMPRE_BLOQUEADOS, contem_topico_proibido
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
