"""Registro de promessas no banco (F4): modelo, migração aditiva, repositório e exclusões.

U10, U11 e I14 da auditoria (docs/melhoria-radio/f4/auditoria.md §8). O SQLite dos testes não verifica FK:
a exclusão de programa e de radialista confere as linhas da tabela nova explicitamente.
"""

import datetime
import logging

from sqlalchemy import create_engine, inspect, text

from app.live import promessas as p
from app.live import promessas_repo as repo
from app.models.programa import Programa
from app.models.promessa_no_ar import PromessaNoAr
from app.models.radio_config import RadioConfig

OCORRENCIA = "20261110T150000Z"


def _cenario(db, account):
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo", nome_locutor="Marta Girassol")
    db.add(radialista)
    db.flush()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde em Casa", horario_inicio=datetime.time(12, 0),
                        horario_fim=datetime.time(13, 0), estrutura_blocos=[])
    db.add(programa)
    db.commit()
    return radialista, programa


def _item(texto="Daqui a pouco tem recado de ouvinte.", chave="etapa:0:1620"):
    promessa = p.detectar(texto)[0]
    evento = p.EventoAgendado(chave=chave, tipo="participacao", rotulo="Retorno",
                              inicio=datetime.datetime(2026, 11, 10, 15, 27, tzinfo=datetime.timezone.utc))
    return promessa, evento


# --- U10: repositório ----------------------------------------------------------------------------------

def test_u10_registro_idempotente_por_request_id_e_abertas_por_ocorrencia(db_session, account):
    _, programa = _cenario(db_session, account)
    novas = repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1", itens=[_item()])
    assert len(novas) == 1 and novas[0].estado == "aberta" and novas[0].evento_alvo == "etapa:0:1620"
    assert novas[0].eventos[0]["acao"] == "registrar"
    assert repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1", itens=[_item()]) == []
    repo.registrar(db_session, programa=programa, ocorrencia="outra", request_id="r2", itens=[_item()])
    assert [x.ocorrencia for x in repo.abertas(db_session, programa.id, OCORRENCIA)] == [OCORRENCIA]
    assert repo.obrigacoes(db_session, programa.id, OCORRENCIA) == frozenset({"0:1620"})
    ref = repo.para_ref(novas[0])
    assert ref.evento_alvo == "etapa:0:1620" and ref.tipo == "participacao" and ref.prazo is not None


def test_u10_resolver_com_trava_e_trilha(db_session, account, monkeypatch):
    _, programa = _cenario(db_session, account)
    promessa = repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1",
                              itens=[_item()])[0]
    from sqlalchemy.orm import Query

    travas = []
    original = Query.with_for_update

    def com_trava(self, *a, **k):
        travas.append(self.column_descriptions[0]["entity"])
        return original(self, *a, **k)

    monkeypatch.setattr(Query, "with_for_update", com_trava)
    resolvidas = repo.resolver(db_session, [promessa.id], "cancelada", "contingencia:conteudo_caiu",
                               contingencia="O Cantinho da Casa não entra hoje.")
    assert travas == [PromessaNoAr]
    assert [(r.estado, r.motivo, r.contingencia) for r in resolvidas] == [
        ("cancelada", "contingencia:conteudo_caiu", "O Cantinho da Casa não entra hoje.")]
    assert resolvidas[0].resolvida_em is not None
    assert [e["acao"] for e in resolvidas[0].eventos] == ["registrar", "cancelada"]
    # Já resolvida: não muda de novo (duas abas).
    assert repo.resolver(db_session, [promessa.id], "cumprida", "cumprida no bloco") == []


def test_u10_vencer_outra_ocorrencia_e_o_que_sobra(db_session, account):
    _, programa = _cenario(db_session, account)
    velha = repo.registrar(db_session, programa=programa, ocorrencia="ontem", request_id="r0", itens=[_item()])[0]
    atual = repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1", itens=[_item()])[0]
    assert [x.id for x in repo.vencer(db_session, programa.id, exceto_ocorrencia=OCORRENCIA)] == [velha.id]
    assert repo.vencer(db_session, programa.id, exceto_ocorrencia=OCORRENCIA) == []
    sobras = repo.vencer(db_session, programa.id, ocorrencia=OCORRENCIA, motivo="transmissao_encerrada")
    assert [(x.id, x.estado, x.motivo) for x in sobras] == [(atual.id, "vencida", "transmissao_encerrada")]


def test_u10_log_sem_nome_nem_trecho(db_session, account, caplog):
    _, programa = _cenario(db_session, account)
    caplog.set_level(logging.INFO)
    promessa = repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1",
                              itens=[_item("Daqui a pouco tem recado da Cida Morais.")])[0]
    repo.resolver(db_session, [promessa.id], "cumprida", "cumprida no bloco")
    assert "promessa_registrada" in caplog.text and "promessa_resolvida" in caplog.text
    assert "Cida" not in caplog.text and "recado" not in caplog.text


def test_u10_ocorrencia_sem_relogio_e_fora_da_grade():
    programa = Programa(id=3, nome="X", horario_inicio=datetime.time(12, 0), horario_fim=datetime.time(13, 0),
                        dias_semana=[], estrutura_blocos=[])
    dentro = datetime.datetime(2026, 11, 10, 15, 30, tzinfo=datetime.timezone.utc)
    assert repo.ocorrencia_chave(programa, "America/Sao_Paulo", dentro) == "20261110T150000Z"
    fora = datetime.datetime(2026, 11, 10, 22, 0, tzinfo=datetime.timezone.utc)
    assert repo.ocorrencia_chave(programa, "America/Sao_Paulo", fora) == "manual:2026-11-10"


# --- U11: migração ---------------------------------------------------------------------------------------

def test_u11_migracao_aditiva_idempotente_sem_tocar_outras_tabelas():
    from app.db.migrations.promessas_20261112 import VERSAO, aplicar

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE programas (id INTEGER PRIMARY KEY, nome VARCHAR)"))
        conn.execute(text("CREATE TABLE radio_configs (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO programas (id, nome) VALUES (1, 'Programa existente')"))
    antes = {t: [c["name"] for c in inspect(engine).get_columns(t)] for t in ("programas", "radio_configs")}
    assert aplicar(engine) is True
    assert aplicar(engine) is False
    tabelas = inspect(engine).get_table_names()
    assert "promessas_no_ar" in tabelas
    assert {t: [c["name"] for c in inspect(engine).get_columns(t)] for t in ("programas", "radio_configs")} == antes
    with engine.connect() as conn:
        assert conn.execute(text("SELECT nome FROM programas")).scalar() == "Programa existente"
    assert VERSAO == "20261112_01"
    engine.dispose()


def test_u11_startup_cria_dependencias_antes_da_migracao_de_promessas():
    # Regra atualizada: em banco novo a tabela `programas` (create_all) tem que existir antes da migração de
    # promessas, que tem FK para ela. Migração antes do create_all quebra com UndefinedTable (testado em Postgres 16
    # vazio: ordem antiga falha, ordem atual passa).
    import inspect as inspecao

    from app import main

    fonte = inspecao.getsource(main.criar_tabelas)
    assert fonte.index("Base.metadata.create_all") < fonte.index("aplicar_promessas(engine)")


# --- I14: exclusões apagam a tabela nova -----------------------------------------------------------------

def test_i14_excluir_programa_apaga_promessas(client, account, auth_headers, db_session):
    radialista, programa = _cenario(db_session, account)
    outro = Programa(radio_config_id=radialista.id, nome="Outro", horario_inicio=datetime.time(14, 0),
                     horario_fim=datetime.time(15, 0), estrutura_blocos=[])
    db_session.add(outro)
    db_session.commit()
    repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1", itens=[_item()])
    repo.registrar(db_session, programa=outro, ocorrencia=OCORRENCIA, request_id="r2", itens=[_item()])
    resposta = client.delete(f"/config/programas/{programa.id}", headers=auth_headers(account.id))
    assert resposta.status_code == 204
    db_session.expire_all()
    assert db_session.query(PromessaNoAr).filter_by(programa_id=programa.id).count() == 0
    assert db_session.query(PromessaNoAr).filter_by(programa_id=outro.id).count() == 1


def test_i14_excluir_radialista_apaga_promessas(client, account, auth_headers, db_session):
    radialista, programa = _cenario(db_session, account)
    repo.registrar(db_session, programa=programa, ocorrencia=OCORRENCIA, request_id="r1", itens=[_item()])
    resposta = client.delete(f"/config/radialistas/{radialista.id}", headers=auth_headers(account.id))
    assert resposta.status_code == 204
    db_session.expire_all()
    assert db_session.query(PromessaNoAr).count() == 0
