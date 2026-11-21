"""Migração aditiva 20261107_01: coluna programas.relogio_hora (JSON, nula = sem relógio).

A existência da coluna é o próprio estado da migração: sem tabela de controle. Idempotente.
"""
from sqlalchemy import inspect, text

VERSAO = "20261107_01"


def aplicar(engine) -> bool:
    """Cria a coluna se a tabela existir e a coluna não. Devolve True quando alterou o banco."""
    inspector = inspect(engine)
    if "programas" not in inspector.get_table_names():
        return False
    if "relogio_hora" in {coluna["name"] for coluna in inspector.get_columns("programas")}:
        return False
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE programas ADD COLUMN relogio_hora JSON NULL"))
    return True
