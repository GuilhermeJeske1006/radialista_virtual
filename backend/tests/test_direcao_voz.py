"""A energia da apresentação musical não deve se sobrepor à intenção editorial."""
from types import SimpleNamespace

import pytest

from app.live.direcao_voz import energia_do_programa, instrucao_energia, tom_musical
from app.tts.client import _preparar_sintese
from app.vinhetas.trilha import prompt_trilha_ia


def _programa(**kwargs):
    return SimpleNamespace(**{"perfil": "musical", "tom": "animado", "persona": None, **kwargs})


@pytest.mark.parametrize("categoria", ["abertura", "musica", "encerramento"])
def test_musical_tem_presenca_do_inicio_a_despedida(categoria):
    assert tom_musical(_programa(), categoria, "calmo") == "energico"
    assert "sorriso na voz" in instrucao_energia(_programa(), categoria)


@pytest.mark.parametrize("categoria,tom", [
    ("noticia", "calmo"), ("servico", "neutro"), ("chamada_ouvinte", "calmo"), ("plantao", "energico"),
])
def test_conteudo_editorial_e_reclamacao_preservam_a_direcao(categoria, tom):
    assert tom_musical(_programa(), categoria, tom) == tom
    assert instrucao_energia(_programa(), categoria) is None


@pytest.mark.parametrize("persona,tom,esperado", [
    ({"energia": 1}, "animado", "calmo"), ({"energia": 3}, "animado", "neutro"),
    ({"energia": 5}, "calmo", "energico"), (None, "calmo e acolhedor", "calmo"),
    (None, "informal e descontraído", "energico"),
])
def test_energia_configurada_tem_prioridade(persona, tom, esperado):
    programa = _programa(persona=persona, tom=tom)
    assert energia_do_programa(programa) == esperado
    assert tom_musical(programa, "musica", "energico") == esperado


def test_programa_jornalistico_nao_recebe_direcao_musical():
    assert tom_musical(_programa(perfil="jornalismo"), "abertura", "neutro") == "neutro"


def test_trilha_musical_animada_nao_vira_relaxante_a_noite():
    import datetime
    programa = _programa(horario_inicio=datetime.time(23), generos_musicais=["pop"])
    prompt = prompt_trilha_ia(programa)
    assert "high energy" in prompt and "punchy" in prompt
    assert "late-night" not in prompt and "calm" not in prompt


@pytest.mark.parametrize("modelo", ["eleven_v3", "eleven_v4", "eleven_v4_turbo", "eleven_flash_v2_5"])
def test_vinheta_recebe_direcao_energica_compativel_com_modelo(modelo):
    _, payload = _preparar_sintese("É música boa na Rádio Cidade!", "vinheta", "energico", False, None, modelo)
    if modelo == "eleven_flash_v2_5":
        assert payload["voice_settings"]["speed"] > 1.04
        assert "[" not in payload["text"]
    else:
        assert payload["text"].startswith("[excited]")
    if modelo.startswith("eleven_v4"):
        assert set(payload["voice_settings"]) == {"stability", "similarity_boost"}


@pytest.mark.parametrize("perfil", ["atual", "natural"])
@pytest.mark.parametrize("modelo", ["eleven_v4", "eleven_v4_turbo"])
def test_v4_nao_depende_de_controles_ignorados(modelo, perfil):
    _, payload = _preparar_sintese("Começa agora!", "abertura", "energico", False, None, modelo, perfil)
    assert set(payload["voice_settings"]) == {"stability", "similarity_boost"}
    if perfil == "natural":
        assert payload["text"] == "Começa agora!"
    else:
        assert payload["text"].startswith("[excited]")


def test_plantao_v4_nao_recebe_tag_de_comemoracao():
    _, payload = _preparar_sintese("Atenção para a informação.", "plantao", "energico", False, None, "eleven_v4")
    assert "[excited]" not in payload["text"]


def test_retomada_tem_a_mesma_direcao_vocal_da_apresentacao(monkeypatch):
    monkeypatch.setattr("app.tts.client.random.uniform", lambda *_: 0)
    _, payload = _preparar_sintese("Você está na Rádio Cidade!", "retomada", "energico", False, None, "eleven_v4")
    assert payload["text"].startswith("[excited]")
