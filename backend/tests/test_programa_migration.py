from sqlalchemy import create_engine, inspect, text


def test_migracao_preserva_programa_existente_e_pode_rodar_duas_vezes(monkeypatch):
    from app.main import garantir_colunas_programa
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE programas (id INTEGER PRIMARY KEY, nome VARCHAR)"))
        conn.execute(text("INSERT INTO programas (id, nome) VALUES (1, 'Programa existente')"))
    monkeypatch.setattr("app.main.engine", engine)
    garantir_colunas_programa()
    garantir_colunas_programa()
    assert "perfil_programacao" in {c["name"] for c in inspect(engine).get_columns("programas")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT nome, perfil_programacao FROM programas")).one() == ("Programa existente", "padrao")
    engine.dispose()
