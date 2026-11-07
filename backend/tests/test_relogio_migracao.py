"""Migração aditiva da coluna programas.relogio_hora (app/db/migrations/relogio_20261107.py)."""

from sqlalchemy import create_engine, inspect, text


def test_migracao_relogio_preserva_linha_pode_rodar_duas_vezes_e_nasce_nula():
    from app.db.migrations.relogio_20261107 import VERSAO, aplicar

    engine = create_engine("sqlite://")
    assert aplicar(engine) is False  # sem a tabela, não faz nada
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE programas (id INTEGER PRIMARY KEY, nome VARCHAR)"))
        conn.execute(text("INSERT INTO programas (id, nome) VALUES (1, 'Programa existente')"))
    assert aplicar(engine) is True
    assert aplicar(engine) is False
    assert "relogio_hora" in {c["name"] for c in inspect(engine).get_columns("programas")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT nome, relogio_hora FROM programas")).one() == ("Programa existente", None)
    assert VERSAO == "20261107_01"
    engine.dispose()


def test_startup_chama_a_migracao_depois_das_colunas_do_programa():
    import inspect as inspecao

    from app import main

    fonte = inspecao.getsource(main.criar_tabelas)
    assert fonte.index("garantir_colunas_programa()") < fonte.index("aplicar_relogio(engine)")
    assert fonte.index("Base.metadata.create_all") < fonte.index("aplicar_relogio(engine)")
