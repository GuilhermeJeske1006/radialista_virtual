
import pytest
from freezegun import freeze_time

from app.llm.prompt_builder import ParticipantePrograma, montar_system_prompt
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


@pytest.fixture(autouse=True)
def _sem_clima_real(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)


def _account(**kwargs):
    padrao = dict(nome_radio="Radio Teste")
    padrao.update(kwargs)
    return Account(**padrao)


def _radialista(**kwargs):
    padrao = dict(nome_locutor="Ze do Radio", personalidade="", timezone="America/Sao_Paulo")
    padrao.update(kwargs)
    return RadioConfig(**padrao)


def _programa(**kwargs):
    padrao = dict(
        nome="Programa Principal",
        tom="animado",
        topicos_permitidos=[],
        topicos_proibidos=[],
        generos_musicais=[],
        musicas_permitidas=[],
        musicas_bloqueadas=[],
        criterios_busca_musicas="",
        assuntos_ao_vivo=[],
        tipos_noticias=[],
        fontes_noticias=[],
        pode_pesquisar=False,
        fontes_pesquisa=[],
        instrucoes_pesquisa="",
        estrutura_blocos=[],
        ia_pode_adicionar_blocos=True,
        descricao="",
    )
    padrao.update(kwargs)
    return Programa(**padrao)


@freeze_time("2026-08-10 15:00:00")
def test_prompt_single_voz_inclui_nome_do_locutor_e_da_radio():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Ze do Radio" in prompt
    assert "Radio Teste" in prompt
    assert "Programa Principal" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_personalidade_quando_definida():
    radialista = _radialista(personalidade="animado e brincalhao")
    prompt = montar_system_prompt(_account(), radialista, _programa())
    assert "animado e brincalhao" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_multi_voz_lista_todos_os_participantes():
    dono = _radialista(nome_locutor="Ze")
    convidado = _radialista(nome_locutor="Maria")
    roster = [
        ParticipantePrograma(dono, "Apresentador principal", "sempre animado"),
        ParticipantePrograma(convidado, "Comentarista", "mais calma"),
    ]
    prompt = montar_system_prompt(_account(), dono, _programa(), roster=roster)
    assert "Ze" in prompt
    assert "Maria" in prompt
    assert '"linhas"' in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_com_um_unico_participante_no_roster_nao_e_multi_voz():
    dono = _radialista(nome_locutor="Ze")
    roster = [ParticipantePrograma(dono, "Apresentador principal", "")]
    prompt = montar_system_prompt(_account(), dono, _programa(), roster=roster)
    assert '"linhas"' not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_topicos_proibidos_quando_definidos():
    programa = _programa(topicos_proibidos=["politica", "religiao"])
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "politica, religiao" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_pesquisa_habilitada():
    programa = _programa(pode_pesquisar=True, fontes_pesquisa=["g1.com"])
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "Pesquisa externa habilitada" in prompt
    assert "g1.com" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_pesquisa_desabilitada_por_padrao():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Pesquisa externa desabilitada" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_estrutura_de_blocos_quando_ia_pode_adicionar():
    programa = _programa(estrutura_blocos=["abertura", "musica"], ia_pode_adicionar_blocos=True)
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "abertura -> musica" in prompt
    assert "fique livre pra inserir blocos extras" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_estrutura_de_blocos_estrita_quando_ia_nao_pode_adicionar():
    programa = _programa(estrutura_blocos=["abertura", "musica"], ia_pode_adicionar_blocos=False)
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "siga estritamente" in prompt
