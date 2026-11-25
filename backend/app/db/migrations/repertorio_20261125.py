"""Adiciona notas de repertório sem alterar os assuntos já cadastrados."""

from sqlalchemy import inspect, text


def aplicar(engine) -> bool:
    inspector = inspect(engine)
    if "assuntos" not in inspector.get_table_names():
        return False
    if "repertorio" in {c["name"] for c in inspector.get_columns("assuntos")}:
        return False
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE assuntos ADD COLUMN repertorio JSON NOT NULL DEFAULT '{}'"))
    return True
