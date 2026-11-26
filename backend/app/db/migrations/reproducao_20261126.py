"""Telemetria de reprodução aditiva; não reinterpreta o histórico existente."""
from sqlalchemy import inspect, text


def aplicar(engine):
    if "reproducao" in {c["name"] for c in inspect(engine).get_columns("blocos_reproduzidos")}:
        return False
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE blocos_reproduzidos ADD COLUMN reproducao JSON NOT NULL DEFAULT '{}'"))
    return True
