import datetime

import pytest
from freezegun import freeze_time

from app.llm.prompt_builder import ParticipantePrograma, montar_system_prompt
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.tts.voices import VOZES_DISPONIVEIS


@pytest.fixture
def dois_programas(db_session, account):
    radialista = RadioConfig(account_id=account.id, nome_locutor="Caio", timezone="America/Sao_Paulo",
        voz_id=VOZES_DISPONIVEIS[0]["voz_id"], personalidade="Brincalhão, usa gírias em toda frase",
        tracos_marcantes=["Faz piada em todos os boletins"])
    db_session.add(radialista)
    db_session.flush()
    musical = Programa(radio_config_id=radialista.id, nome="Manhã musical", horario_inicio=datetime.time(8),
        horario_fim=datetime.time(9), estrutura_blocos=["comentario"], ia_pode_adicionar_blocos=False,
        persona={"formalidade": 1, "humor": 4, "girias": "frequentes", "orientacoes": "Conversa leve."})
    jornal = Programa(radio_config_id=radialista.id, nome="Jornal da manhã", horario_inicio=datetime.time(10),
        horario_fim=datetime.time(11), estrutura_blocos=["comentario"], ia_pode_adicionar_blocos=False,
        persona={"formalidade": 5, "humor": 1, "girias": "evitar", "orientacoes": "Boletins objetivos."})
    db_session.add_all([musical, jornal])
    db_session.commit()
    return radialista, musical, jornal


@freeze_time("2026-11-25 11:30:00")
def test_mesma_identidade_tem_estilos_independentes_tambem_no_whatsapp(account, dois_programas, monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda *args: None)
    radialista, musical, jornal = dois_programas
    original = radialista.personalidade, radialista.voz_id
    leve = montar_system_prompt(account, radialista, musical)
    serio = montar_system_prompt(account, radialista, jornal)

    assert "gírias naturais com mais frequência" in leve
    assert "Conversa leve." in leve and "Boletins objetivos." not in leve
    assert "Evite gírias" in serio
    assert "Boletins objetivos." in serio and "Conversa leve." not in serio
    assert radialista.personalidade not in serio
    assert radialista.tracos_marcantes[0] not in serio
    assert "Caio" in leve and "Caio" in serio
    assert (radialista.personalidade, radialista.voz_id) == original


def test_api_salva_estilo_de_um_programa_sem_alterar_outro_ou_a_voz(client, db_session, account, auth_headers, dois_programas):
    radialista, musical, jornal = dois_programas
    headers = auth_headers(account.id)
    voz = radialista.voz_id
    dados = client.get(f"/config/programas/{musical.id}", headers=headers).json()
    dados["persona"]["girias"] = "moderadas"
    dados["persona"]["orientacoes"] = "Use expressões regionais com moderação."
    salvo = client.put(f"/config/programas/{musical.id}", headers=headers, json=dados)
    assert salvo.status_code == 200
    assert salvo.json()["persona"]["girias"] == "moderadas"
    assert client.get(f"/config/programas/{jornal.id}", headers=headers).json()["persona"]["girias"] == "evitar"
    db_session.refresh(radialista)
    assert radialista.voz_id == voz
    assert radialista.personalidade == "Brincalhão, usa gírias em toda frase"


def test_ao_vivo_muda_estilo_e_sintetiza_com_a_mesma_voz(client, db_session, account, auth_headers, dois_programas, monkeypatch):
    radialista, musical, jornal = dois_programas
    prompts, vozes = [], []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or
                        "Tem música que a gente reconhece pelos primeiros acordes. A lembrança chega antes da voz.")
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *args: True)
    monkeypatch.setattr("app.live.router.parametros_sintese", lambda *args: {})
    monkeypatch.setattr("app.live.router.duracao_mp3_s", lambda *args: 10)
    monkeypatch.setattr("app.live.router._registrar_amostra_fala", lambda *args: None)
    monkeypatch.setattr("app.live.router.sintetizar_audio", lambda texto, voz, **kwargs: vozes.append(voz) or b"audio-teste")

    for programa, instante in [(musical, "2026-11-25 11:30:00"), (jornal, "2026-11-25 13:30:00")]:
        with freeze_time(instante):
            resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima",
                headers=auth_headers(account.id), json={"historico": [], "total_falas": 3, "incluir_audio": True})
            assert resposta.status_code == 200, resposta.text
            assert resposta.json()["audio_status"] == "pronto"
    assert vozes == [radialista.voz_id, radialista.voz_id]
    assert prompts[0].count("Jeito de falar neste programa:") == 1
    assert "gírias naturais com mais frequência" in prompts[0]
    assert "Evite gírias" in prompts[1]


@freeze_time("2026-11-25 11:30:00")
def test_comportamento_do_vinculo_funciona_com_um_unico_apresentador(client, db_session, account, auth_headers, dois_programas, monkeypatch):
    radialista, musical, _ = dois_programas
    musical.persona = None
    db_session.add(ProgramaRadialista(programa_id=musical.id, radio_config_id=radialista.id,
                                     comportamento="Condução sóbria e objetiva neste programa."))
    db_session.commit()
    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos com o programa.")
    resposta = client.post(f"/live/{radialista.id}/programas/{musical.id}/proxima",
        headers=auth_headers(account.id), json={"historico": [], "total_falas": 3})
    assert resposta.status_code == 200
    assert "Condução sóbria e objetiva neste programa." in prompts[0]
    assert radialista.personalidade not in prompts[0]
    assert '"linhas"' not in prompts[0]


def test_programa_em_dupla_aplica_estilo_sem_apagar_papeis(account, dois_programas, monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda *args: None)
    radialista, _, jornal = dois_programas
    convidado = RadioConfig(id=999, nome_locutor="Bia", personalidade="Muito brincalhona")
    prompt = montar_system_prompt(account, radialista, jornal, roster=[
        ParticipantePrograma(radialista, "Âncora", "Apresenta o fato e passa a palavra."),
        ParticipantePrograma(convidado, "Repórter", "Explica os detalhes apurados."),
    ])
    assert "Âncora" in prompt and "Repórter" in prompt
    assert "Explica os detalhes apurados." in prompt
    assert "Muito brincalhona" not in prompt
    assert "Evite gírias" in prompt
