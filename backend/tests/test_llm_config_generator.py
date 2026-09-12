import json

import pytest

from app.llm.config_generator import (
    _montar_system_prompt_completo,
    _montar_system_prompt_persona,
    _montar_system_prompt_programa,
    gerar_configuracao_ia,
    gerar_programa_ia,
)
from app.tts.voices import VOZES_DISPONIVEIS


def _resposta_completa_valida():
    return json.dumps(
        {
            "radialista": {
                "nome_locutor": "Ze",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            "programa": {
                "nome": "Show da Tarde",
                "descricao": "programa animado",
                "dias_semana": [0, 1, 2, 3, 4],
                "horario_inicio": "14:00",
                "horario_fim": "18:00",
                "tom": "animado",
                "topicos_permitidos": ["musica"],
                "topicos_proibidos": [],
                "mensagem_saudacao": "oi",
                "mensagem_recusa": "nao posso falar disso",
                "limite_mensagens_hora": 100,
                "estrutura_blocos": ["abertura", "musica"],
                "ia_pode_adicionar_blocos": True,
                "generos_musicais": ["sertanejo"],
                "musicas_permitidas": [],
                "musicas_bloqueadas": [],
                "criterios_busca_musicas": "",
                "assuntos_ao_vivo": [],
                "tipos_noticias": [],
                "fontes_noticias": [],
                "pode_pesquisar": False,
                "fontes_pesquisa": [],
                "instrucoes_pesquisa": "",
            },
        }
    )


def _resposta_persona_valida():
    return json.dumps(json.loads(_resposta_completa_valida())["radialista"])


def _resposta_programa_valida():
    return json.dumps(json.loads(_resposta_completa_valida())["programa"])


def _mock_duas_chamadas(persona_json, programa_json):
    """gerar_configuracao_ia agora chama gerar_configuracao DUAS vezes (persona, depois
    programa -- ver Fase 3 do plano de melhoria) -- esse mock devolve uma resposta por chamada,
    na ordem certa."""
    respostas = iter([persona_json, programa_json])
    return lambda system, user: next(respostas)


def test_gerar_configuracao_ia_devolve_radialista_e_programa(monkeypatch):
    monkeypatch.setattr(
        "app.llm.config_generator.gerar_configuracao",
        _mock_duas_chamadas(_resposta_persona_valida(), _resposta_programa_valida()),
    )
    radialista, programa = gerar_configuracao_ia("radio sertaneja animada")
    assert radialista["nome_locutor"] == "Ze"
    assert programa["nome"] == "Show da Tarde"


def test_gerar_configuracao_ia_sem_resposta_levanta_value_error(monkeypatch):
    monkeypatch.setattr("app.llm.config_generator.gerar_configuracao", lambda system, user: "")
    with pytest.raises(ValueError):
        gerar_configuracao_ia("qualquer coisa")


def test_gerar_configuracao_ia_com_json_invalido_levanta_value_error(monkeypatch):
    monkeypatch.setattr(
        "app.llm.config_generator.gerar_configuracao", lambda system, user: "isso nao e json"
    )
    with pytest.raises(ValueError):
        gerar_configuracao_ia("qualquer coisa")


def test_gerar_configuracao_ia_com_voz_invalida_usa_voz_padrao(monkeypatch):
    persona = json.loads(_resposta_persona_valida())
    persona["voz_id"] = "voz-que-nao-existe"
    monkeypatch.setattr(
        "app.llm.config_generator.gerar_configuracao",
        _mock_duas_chamadas(json.dumps(persona), _resposta_programa_valida()),
    )
    radialista, _ = gerar_configuracao_ia("qualquer coisa")
    assert radialista["voz_id"] == VOZES_DISPONIVEIS[0]["voz_id"]


def test_gerar_configuracao_ia_sanitiza_topicos_sempre_bloqueados(monkeypatch):
    programa = json.loads(_resposta_programa_valida())
    programa["topicos_permitidos"] = ["musica", "arma"]
    programa["generos_musicais"] = ["sertanejo", "bomba"]
    monkeypatch.setattr(
        "app.llm.config_generator.gerar_configuracao",
        _mock_duas_chamadas(_resposta_persona_valida(), json.dumps(programa)),
    )
    _, programa_final = gerar_configuracao_ia("qualquer coisa")
    assert "arma" not in programa_final["topicos_permitidos"]
    assert "bomba" not in programa_final["generos_musicais"]
    assert "musica" in programa_final["topicos_permitidos"]


def test_gerar_programa_ia_devolve_programa_sanitizado(monkeypatch):
    dados_programa = json.loads(_resposta_completa_valida())["programa"]
    dados_programa["topicos_permitidos"] = ["musica", "droga ilicita"]
    monkeypatch.setattr(
        "app.llm.config_generator.gerar_configuracao", lambda system, user: json.dumps(dados_programa)
    )
    programa = gerar_programa_ia("radio animada", "Ze", "animado")
    assert programa["nome"] == "Show da Tarde"
    assert "droga ilicita" not in programa["topicos_permitidos"]


def test_gerar_programa_ia_sem_resposta_levanta_value_error(monkeypatch):
    monkeypatch.setattr("app.llm.config_generator.gerar_configuracao", lambda system, user: "")
    with pytest.raises(ValueError):
        gerar_programa_ia("qualquer coisa", "Ze", "")


def test_config_generator_injeta_contexto_do_tipo_no_prompt():
    prompt_sem_tipo = _montar_system_prompt_completo(None)
    prompt_com_tipo = _montar_system_prompt_completo("sertaneja")
    assert "sertanejo raiz" not in prompt_sem_tipo
    assert "sertanejo raiz" in prompt_com_tipo
    assert "Perfil da radio" in prompt_com_tipo


def test_config_generator_ignora_tipo_radio_invalido():
    prompt = _montar_system_prompt_completo("tipo-que-nao-existe")
    assert "Perfil da radio" not in prompt


def test_config_generator_programa_injeta_contexto_do_tipo_no_prompt():
    prompt = _montar_system_prompt_programa("Ze", "animado", "gospel")
    assert "gospel" in prompt.lower()
    assert "Perfil da radio" in prompt


def test_gerar_configuracao_ia_gera_persona_e_depois_programa_com_contexto_dela(monkeypatch):
    """Ver Fase 3 do plano de melhoria: a segunda chamada (programa) tem que receber a persona
    JA resolvida da primeira chamada como contexto, nao os dados crus do usuario de novo."""
    prompts_recebidos = []

    def _fake(system, user):
        prompts_recebidos.append(system)
        if len(prompts_recebidos) == 1:
            return _resposta_persona_valida()
        return _resposta_programa_valida()

    monkeypatch.setattr("app.llm.config_generator.gerar_configuracao", _fake)
    gerar_configuracao_ia("radio sertaneja animada")

    assert len(prompts_recebidos) == 2
    persona_prompt, programa_prompt = prompts_recebidos
    assert "persona" in persona_prompt.lower()
    assert "Ze" in programa_prompt  # nome_locutor gerado na 1a chamada, injetado na 2a


def test_montar_system_prompt_persona_marca_voz_ja_usada(monkeypatch):
    voz_em_uso = VOZES_DISPONIVEIS[0]["voz_id"]
    roster = [{"nome_locutor": "Outro", "personalidade": "x", "voz_id": voz_em_uso, "programas": []}]
    prompt = _montar_system_prompt_persona(roster_existente=roster)
    linha_voz = next(l for l in prompt.splitlines() if voz_em_uso in l)
    assert "ja usada" in linha_voz.lower()


def test_gerar_configuracao_ia_sem_descricao_usa_placeholder(monkeypatch):
    capturado = {}
    respostas = iter([_resposta_persona_valida(), _resposta_programa_valida()])

    def _fake(system, user):
        capturado["user"] = user
        return next(respostas)

    monkeypatch.setattr("app.llm.config_generator.gerar_configuracao", _fake)
    gerar_configuracao_ia("", tipo_radio="sertaneja")
    assert "tipo de radio" in capturado["user"].lower()
