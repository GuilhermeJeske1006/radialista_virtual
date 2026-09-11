import datetime

import pytest
from freezegun import freeze_time

from app.models.noticia import Noticia
from app.models.noticia_historico import NoticiaHistorico
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local, dentro de um programa 10:00-14:00


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Principal",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        estrutura_blocos=["noticia"],
        ia_pode_adicionar_blocos=False,
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(radio_config)
    db_session.refresh(programa)
    return radio_config, programa


def _url_proxima(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


def _criar_noticia(db_session, account, **kwargs):
    base = dict(
        account_id=account.id,
        fonte_nome="Defesa Civil",
        fonte_tipo="oficial",
        titulo="Rua São Paulo interditada apos obra na rede de agua",
        resumo="Trecho de 300 metros fechado desde a manha.",
        url="https://exemplo.com/materia",
        url_hash="hash-fixo-router",
        publicado_em=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        categoria="transito",
        cidade="Blumenau",
        score=90.0,
        ativa=True,
        detalhes={"servico": "Desvio pela Antonio da Veiga"},
    )
    base.update(kwargs)
    noticia = Noticia(**base)
    db_session.add(noticia)
    db_session.commit()
    db_session.refresh(noticia)
    return noticia


@freeze_time(AGORA_UTC)
def test_bloco_noticia_usa_pauta_do_banco_em_vez_de_pesquisar_noticias(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    _criar_noticia(db_session, account)

    def _nao_deveria_pesquisar(*args, **kwargs):
        raise AssertionError("Com pauta real disponível, não deveria cair pra pesquisar_noticias")
    monkeypatch.setattr("app.live.router.pesquisar_noticias", _nao_deveria_pesquisar)

    prompts = []
    fala = "Segundo a Defesa Civil, a Rua São Paulo segue interditada até as seis da tarde."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or fala)

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert "PAUTA DESTE BLOCO" in prompts[0]
    assert "Fonte: Defesa Civil" in prompts[0]
    assert "REDAÇÃO DE NOTÍCIA" in prompts[0]
    assert resposta.json()["fala"] == fala

    historico = db_session.query(NoticiaHistorico).filter_by(programa_id=programa.id).all()
    assert len(historico) == 1
    assert historico[0].angulo == "fato"


@freeze_time(AGORA_UTC)
def test_fala_com_frase_proibida_dispara_retry_unico(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    _criar_noticia(db_session, account)

    respostas = iter([
        "Fico só no que está confirmado, sem especular sobre causa ou desfecho.",
        "Segundo a Defesa Civil, a Rua São Paulo segue interditada até as seis da tarde.",
    ])
    chamadas = []
    def _gerar(system, msg):
        chamadas.append(system)
        return next(respostas)
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerar)

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert len(chamadas) == 2
    assert "usou a construção proibida" in chamadas[1]
    assert resposta.json()["fala"] == "Segundo a Defesa Civil, a Rua São Paulo segue interditada até as seis da tarde."


@freeze_time(AGORA_UTC)
def test_fala_sem_atribuicao_dispara_retry(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    _criar_noticia(db_session, account)

    respostas = iter([
        "A Rua São Paulo segue interditada até as seis da tarde.",
        "Segundo a Defesa Civil, a Rua São Paulo segue interditada até as seis da tarde.",
    ])
    chamadas = []
    def _gerar(system, msg):
        chamadas.append(system)
        return next(respostas)
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerar)

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert len(chamadas) == 2
    assert "não atribuiu a informação a nenhuma fonte" in chamadas[1]


@freeze_time(AGORA_UTC)
def test_bloco_escalada_le_varias_manchetes_e_registra_historico_de_cada(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["escalada"]
    db_session.commit()
    for i in range(3):
        _criar_noticia(db_session, account, titulo=f"Manchete {i}", url=f"https://exemplo.com/{i}", url_hash=f"hash-escalada-{i}", score=90 - i)

    prompts = []
    fala = "Rua interditada. Falta de água em bairro. Show na praça central."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or fala)

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "escalada"
    assert "PAUTA DESTA ESCALADA" in prompts[0]
    assert "Manchete 0" in prompts[0] and "Manchete 1" in prompts[0] and "Manchete 2" in prompts[0]

    historico = db_session.query(NoticiaHistorico).filter_by(programa_id=programa.id).all()
    assert len(historico) == 3


@freeze_time(AGORA_UTC)
def test_bloco_giro_so_atualiza_noticia_ja_ao_ar_no_programa(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    ja_ao_ar = _criar_noticia(db_session, account)
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=ja_ao_ar.id, angulo="fato", fala="Fala original sobre a rua."))
    _criar_noticia(db_session, account, titulo="Inédita, nunca foi ao ar", url="https://exemplo.com/inedita", url_hash="hash-inedita")
    programa.estrutura_blocos = ["giro"]
    db_session.commit()

    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Atualizando: a rua segue interditada.")

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert "PAUTA DESTE GIRO" in prompts[0]
    assert "Rua São Paulo interditada" in prompts[0]
    assert "Inédita, nunca foi ao ar" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_bloco_plantao_sem_score_suficiente_nao_vira_plantao(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    from app.news.pauta import LIMIAR_SCORE_PLANTAO

    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["plantao"]
    programa.pode_pesquisar = False
    db_session.commit()
    _criar_noticia(db_session, account, score=LIMIAR_SCORE_PLANTAO - 10)

    def _pesquisar_sem_resultado(*a, **k):
        from app.llm.noticias import PesquisaNoticias
        return PesquisaNoticias(status="indisponivel")
    monkeypatch.setattr("app.live.router.pesquisar_noticias", _pesquisar_sem_resultado)

    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar.")

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert "PAUTA DESTE BLOCO" not in prompts[0]
    # A prosódia base do bloco "plantao" (ver _PROSODIA_BLOCO) sempre aparece -- o que não pode
    # aparecer sem pauta real é a instrução extra afirmando que ESTA notícia é urgente/impactante.
    assert "esta notícia tem urgência" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_bloco_plantao_com_score_suficiente_usa_a_pauta(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    from app.news.pauta import LIMIAR_SCORE_PLANTAO

    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["plantao"]
    db_session.commit()
    _criar_noticia(db_session, account, score=LIMIAR_SCORE_PLANTAO + 5)

    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Segundo a Defesa Civil, a rua segue interditada.")

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert "PAUTA DESTE BLOCO" in prompts[0]
    assert "PLANTÃO" in prompts[0]


@freeze_time(AGORA_UTC)
def test_dose_noticia_nenhuma_desativa_bloco_de_noticia(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    programa.dose_noticia = "nenhuma"
    db_session.commit()
    _criar_noticia(db_session, account)

    def _nao_deveria_buscar_pauta(*a, **k):
        raise AssertionError("dose_noticia='nenhuma' não deveria nem consultar a pauta")
    monkeypatch.setattr("app.live.router.proxima_noticia", _nao_deveria_buscar_pauta)
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *a, **k: None)
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Seguimos no ar.")

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "musica"


@freeze_time(AGORA_UTC)
def test_correcao_pendente_tem_prioridade_sobre_pauta_normal(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    noticia = _criar_noticia(db_session, account)
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo="fato", fala="Fala original sobre a rua."))
    db_session.commit()
    noticia.retificada = True
    noticia.texto_retificacao = "Na verdade a rua foi liberada às 14h, mais cedo do que informado."
    db_session.commit()
    _criar_noticia(db_session, account, titulo="Outra pauta qualquer", url="https://exemplo.com/outra", url_hash="hash-outra", score=99)

    prompts = []
    fala = "Corrigindo uma informação que a gente deu há pouco: a rua foi liberada às 14h."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or fala)

    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert "CORREÇÃO PENDENTE" in prompts[0]
    assert "Na verdade a rua foi liberada às 14h" in prompts[0]

    historico = db_session.query(NoticiaHistorico).filter_by(programa_id=programa.id, noticia_id=noticia.id).all()
    assert any(h.angulo == "correcao" for h in historico)
