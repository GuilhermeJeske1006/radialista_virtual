import datetime

import pytest
from freezegun import freeze_time

from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics import matcher

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local


@pytest.fixture()
def radio_config(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    return radio_config


@pytest.fixture()
def programa_no_ar(db_session, radio_config):
    programa = Programa(
        radio_config_id=radio_config.id, nome="No Ar Agora",
        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0),
        topicos_permitidos=["transito", "servico"],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def _criar_gancho(db_session, account, *, titulo="Chuva forte", tags=None, texto_bloqueado=""):
    assunto = Assunto(
        account_id=account.id, origem="noticia", titulo=titulo,
        gancho=f"{texto_bloqueado} quem trabalha na rua leva capa", fatos=["fato real"],
        tags=tags or ["transito", "servico"], peso_base=5.0,
    )
    db_session.add(assunto)
    db_session.commit()
    db_session.refresh(assunto)
    return assunto


@freeze_time(AGORA_UTC)
def test_matcher_so_roda_pra_programa_na_janela_de_exibicao(db_session, account, radio_config, programa_no_ar):
    programa_distante = Programa(
        radio_config_id=radio_config.id, nome="So a Noite",
        horario_inicio=datetime.time(22, 0), horario_fim=datetime.time(23, 0),
    )
    db_session.add(programa_distante)
    db_session.commit()

    programas = matcher._programas_na_janela(db_session, account)

    ids = {p.id for p in programas}
    assert programa_no_ar.id in ids
    assert programa_distante.id not in ids


@freeze_time(AGORA_UTC)
def test_matcher_descarta_gancho_em_topico_proibido(db_session, account, programa_no_ar, monkeypatch):
    programa_no_ar.topicos_proibidos = ["chuva"]
    db_session.commit()
    _criar_gancho(db_session, account, titulo="Chuva forte a tarde")

    def _nao_deveria_chamar(*a, **k):
        raise AssertionError("gancho bloqueado nao deveria chegar no LLM de casamento")
    monkeypatch.setattr("app.topics.matcher.gerar_classificacao", _nao_deveria_chamar)

    gravados = matcher.casar_programa(db_session, programa_no_ar, account)

    assert gravados == 0
    assert db_session.query(AssuntoPrograma).count() == 0


@freeze_time(AGORA_UTC)
def test_matcher_grava_ponte_e_eixos_devolvidos_pelo_llm(db_session, account, programa_no_ar, monkeypatch):
    assunto = _criar_gancho(db_session, account)
    resposta = f'[{{"id": {assunto.id}, "score": 8, "ponte": "publico trabalhador sai cedo", "eixos_sugeridos": ["fato", "servico"]}}]'
    monkeypatch.setattr("app.topics.matcher.gerar_classificacao", lambda system, msg, **_: resposta)

    gravados = matcher.casar_programa(db_session, programa_no_ar, account)

    assert gravados == 1
    ap = db_session.query(AssuntoPrograma).filter_by(assunto_id=assunto.id, programa_id=programa_no_ar.id).one()
    assert ap.score == 8.0
    assert ap.ponte == "publico trabalhador sai cedo"
    assert ap.eixos_sugeridos == ["fato", "servico"]


@freeze_time(AGORA_UTC)
def test_matcher_score_abaixo_do_limiar_nao_e_gravado(db_session, account, programa_no_ar, monkeypatch):
    assunto = _criar_gancho(db_session, account)
    resposta = f'[{{"id": {assunto.id}, "score": 1, "ponte": "", "eixos_sugeridos": []}}]'
    monkeypatch.setattr("app.topics.matcher.gerar_classificacao", lambda system, msg, **_: resposta)

    gravados = matcher.casar_programa(db_session, programa_no_ar, account)

    assert gravados == 0


@freeze_time(AGORA_UTC)
def test_matcher_nao_recasa_gancho_ja_casado(db_session, account, programa_no_ar, monkeypatch):
    assunto = _criar_gancho(db_session, account)
    chamadas = []
    resposta = f'[{{"id": {assunto.id}, "score": 8, "ponte": "x", "eixos_sugeridos": ["fato"]}}]'

    def _fake(system, msg, **_):
        chamadas.append(1)
        return resposta
    monkeypatch.setattr("app.topics.matcher.gerar_classificacao", _fake)

    matcher.casar_programa(db_session, programa_no_ar, account)
    gravados_segunda_vez = matcher.casar_programa(db_session, programa_no_ar, account)

    assert gravados_segunda_vez == 0
    assert len(chamadas) == 1


@freeze_time(AGORA_UTC)
def test_matcher_no_teto_diario_degrada_pra_score_por_tags(db_session, account, programa_no_ar, monkeypatch):
    from app.config.redis_client import redis_client

    assunto = _criar_gancho(db_session, account)
    redis_client.set(f"matcher_chamadas_haiku:{account.id}:{datetime.date.today().isoformat()}", matcher._TETO_CHAMADAS_HAIKU_POR_CONTA_DIA)

    def _nao_deveria_chamar(*a, **k):
        raise AssertionError("teto diario estourado nao deveria chamar o LLM")
    monkeypatch.setattr("app.topics.matcher.gerar_classificacao", _nao_deveria_chamar)

    gravados = matcher.casar_programa(db_session, programa_no_ar, account)

    assert gravados == 1
    ap = db_session.query(AssuntoPrograma).filter_by(assunto_id=assunto.id, programa_id=programa_no_ar.id).one()
    assert ap.ponte == ""
    assert ap.eixos_sugeridos == []


@freeze_time(AGORA_UTC)
def test_score_tags_bate_por_palavra_nao_por_frase_inteira(db_session, account, programa_no_ar):
    """Bug real achado testando o fluxo ao vivo (conta emailjeske@gmail.com): topicos_permitidos/
    assuntos_ao_vivo sao FRASES descritivas ("trânsito e chuva na região"), nao tags atomicas --
    comparar a frase inteira contra uma tag curta do gancho ("chuva") nunca batia por igualdade
    exata, e nenhum gancho de noticia/musica nunca casava com nenhum programa em producao."""
    programa_no_ar.topicos_permitidos = ["trânsito e chuva na região"]
    programa_no_ar.generos_musicais = []
    db_session.commit()
    gancho_chuva = _criar_gancho(db_session, account, titulo="Granizo na cidade", tags=["chuva", "seguranca"])

    tags_programa = matcher._tags_programa(programa_no_ar)
    score = matcher._score_tags(gancho_chuva, tags_programa)

    assert score >= matcher._LIMIAR_SCORE_TAGS


@freeze_time(AGORA_UTC)
def test_mesmo_gancho_gera_pontes_diferentes_em_programas_diferentes(db_session, account, radio_config, programa_no_ar, monkeypatch):
    outro_programa = Programa(
        radio_config_id=radio_config.id, nome="Sertanejo Manha",
        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0),
        topicos_permitidos=["transito", "servico"],
    )
    db_session.add(outro_programa)
    db_session.commit()

    assunto = _criar_gancho(db_session, account)

    def _fake(system, msg, **_):
        if "No Ar Agora" in msg:
            return f'[{{"id": {assunto.id}, "score": 8, "ponte": "ponte pro programa A", "eixos_sugeridos": ["fato"]}}]'
        return f'[{{"id": {assunto.id}, "score": 8, "ponte": "ponte pro programa B", "eixos_sugeridos": ["servico"]}}]'
    monkeypatch.setattr("app.topics.matcher.gerar_classificacao", _fake)

    matcher.casar_programa(db_session, programa_no_ar, account)
    matcher.casar_programa(db_session, outro_programa, account)

    ponte_a = db_session.query(AssuntoPrograma).filter_by(programa_id=programa_no_ar.id).one().ponte
    ponte_b = db_session.query(AssuntoPrograma).filter_by(programa_id=outro_programa.id).one().ponte
    assert ponte_a != ponte_b
