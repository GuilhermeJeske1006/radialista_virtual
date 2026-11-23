"""Glossário de pronúncia (F9): validação, precedência rádio x voz, uso no texto, sugestões e síntese."""

import pytest

from app.models.perfil_voz import ConfiguracaoVoz
from app.numeros import normalizar_texto_fala
from app.tts.glossario import (
    MAX_CARACTERES_TERMO,
    mesclar_glossarios,
    normalizar_glossario,
    sugerir_termos,
)
from app.tts.profiles import parametros_sintese


def test_normalizar_descarta_vazios_e_remove_duplicata_sem_caixa():
    limpo = normalizar_glossario({" Kelly ": " Quéli ", "": "x", "Y": "", "kelly": "Outra"}, limite=10)
    assert limpo == {"Kelly": "Quéli"}


def test_normalizar_recusa_termo_longo_demais():
    with pytest.raises(ValueError):
        normalizar_glossario({"x" * (MAX_CARACTERES_TERMO + 1): "a"}, limite=10)


def test_normalizar_recusa_acima_do_limite():
    with pytest.raises(ValueError):
        normalizar_glossario({f"t{i}": f"p{i}" for i in range(4)}, limite=3)


def test_voz_sobrescreve_radio_na_mesma_chave_sem_diferenca_de_caixa():
    efetivo = mesclar_glossarios({"Kelly": "Quéli", "Vale": "Vále"}, {"kelly": "Quelí"})
    assert efetivo == {"Vale": "Vále", "kelly": "Quelí"}


def test_radio_vale_quando_a_voz_nao_tem_glossario():
    assert mesclar_glossarios({"Vale": "Vále"}, None) == {"Vale": "Vále"}
    assert mesclar_glossarios(None, {"Vale": "Vále"}) == {"Vale": "Vále"}


def test_glossario_efetivo_muda_o_texto_falado():
    efetivo = mesclar_glossarios({"Kelly": "Quéli"}, {"kelly": "Quelí"})
    assert normalizar_texto_fala("Oi, Kelly!", efetivo) == "Oi, Quelí!"


def test_sugestoes_pegam_siglas_e_nomes_com_w_y_k_ph():
    textos = ["Patrocinado pela CRAS e pela Wesley Auto.", "Show da Kelly e do Phelipe."]
    assert sugerir_termos(textos) == ["CRAS", "Wesley", "Kelly", "Phelipe"]  # "Show" é empréstimo comum, fica de fora


def test_sugestoes_ignoram_o_que_ja_esta_no_glossario():
    assert sugerir_termos(["CRAS e Kelly"], ja_cadastrados=["cras"]) == ["Kelly"]


def test_sugestoes_respeitam_o_limite_e_nao_repetem():
    assert sugerir_termos(["Kelly Kelly Kelly Wesley"], limite=1) == ["Kelly"]
    assert sugerir_termos(["Kelly Kelly"]) == ["Kelly"]


def test_sem_nome_estranho_nao_sugere_nada():
    assert sugerir_termos(["Bom dia, pessoal da rádio."]) == []


def test_parametros_de_sintese_usam_glossario_da_radio_e_da_voz(db_session, account, monkeypatch):
    monkeypatch.setattr("app.tts.profiles.obter_metadados_voz", lambda _: {"categoria": "professional"})
    account.glossario_pronuncia = {"Kelly": "Quéli", "Vale": "Vále"}
    db_session.add(ConfiguracaoVoz(account_id=account.id, voz_id="voz-g", pronuncias={"kelly": "Quelí"}))
    db_session.commit()
    assert parametros_sintese(db_session, account.id, "voz-g")["pronuncias"] == {"Vale": "Vále", "kelly": "Quelí"}


def test_voz_sem_configuracao_ainda_recebe_o_glossario_da_radio(db_session, account, monkeypatch):
    monkeypatch.setattr("app.tts.profiles.obter_metadados_voz", lambda _: {"categoria": "professional"})
    account.glossario_pronuncia = {"Vale": "Vále"}
    db_session.commit()
    assert parametros_sintese(db_session, account.id, "voz-sem-config")["pronuncias"] == {"Vale": "Vále"}


def test_api_da_radio_limpa_o_glossario_e_recusa_excesso():
    from pydantic import ValidationError

    from app.config.router import RadioContaRequest
    from app.tts.glossario import MAX_TERMOS_RADIO

    limpo = RadioContaRequest(glossario_pronuncia={" Kelly ": "Quéli", "": "x"})
    assert limpo.glossario_pronuncia == {"Kelly": "Quéli"}
    with pytest.raises(ValidationError):
        RadioContaRequest(glossario_pronuncia={f"t{i}": "p" for i in range(MAX_TERMOS_RADIO + 1)})


def test_api_sugere_termos_dos_textos_da_radio_sem_os_cadastrados(client, account, auth_headers, db_session):
    """Sugestões a partir do que a rádio já tem: nome, cidade, bairros, patrocinadores, radialistas e músicas."""
    import datetime

    from app.models.musica_historico import MusicaHistorico
    from app.models.patrocinador import Patrocinador
    from app.models.programa import Programa
    from app.models.radio_config import RadioConfig

    account.nome_radio = "Rádio Serra FM"
    account.conhecimento_local = {"bairros": ["Vila Kennedy"], "pontos_referencia": [], "eventos_recorrentes": [],
                                  "expressoes_regionais": [], "gentilico": ""}
    account.glossario_pronuncia = {"Wesley": "Uésli"}
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo", nome_locutor="Kelly")
    db_session.add_all([radio_config, Patrocinador(account_id=account.id, nome="Kiwi Calçados")])
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Tarde", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(12, 0), estrutura_blocos=[], musicas_permitidas=["Phelipe Lima"])
    db_session.add(programa)
    db_session.commit()
    db_session.add(MusicaHistorico(programa_id=programa.id, video_id="v1", titulo="Wesley Safadão - Camarote",
                                   canal="Wesley Safadão", query="camarote", query_normalizada="camarote",
                                   origem="ia"))
    db_session.commit()

    resposta = client.get("/config/radio/glossario/sugestoes", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    termos = resposta.json()["termos"]
    assert {"FM", "Kennedy", "Kiwi", "Kelly", "Phelipe"} <= set(termos)
    assert "Wesley" not in termos  # já está no glossário


def test_api_de_sugestoes_nao_mistura_contas(client, account, auth_headers, db_session):
    from app.models.account import Account
    from app.models.patrocinador import Patrocinador

    outra = Account(nome_radio="Outra")
    db_session.add(outra)
    db_session.commit()
    db_session.add(Patrocinador(account_id=outra.id, nome="Yakult Kids"))
    db_session.commit()
    termos = client.get("/config/radio/glossario/sugestoes", headers=auth_headers(account.id)).json()["termos"]
    assert "Yakult" not in termos and "Kids" not in termos
