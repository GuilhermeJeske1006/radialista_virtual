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
