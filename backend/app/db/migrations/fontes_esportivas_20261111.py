"""Completa o histórico e o controle de revisão das fontes esportivas existentes.

create_all cria tabelas novas, mas não acrescenta colunas às tabelas já existentes.
Migração aditiva e idempotente, preservando os dados e revisões já cadastrados.
"""

from sqlalchemy import inspect, text


def aplicar(engine) -> bool:
    inspector = inspect(engine)
    if not inspector.has_table("fontes_esportivas"):
        return False
    existentes = {coluna["name"] for coluna in inspector.get_columns("fontes_esportivas")}
    definicoes = {
        "historico": "JSON NOT NULL DEFAULT '[]'",
        "revisao": "INTEGER NOT NULL DEFAULT 1",
    }
    faltantes = {nome: definicao for nome, definicao in definicoes.items() if nome not in existentes}
    if not faltantes:
        return False
    with engine.begin() as conn:
        for nome, definicao in faltantes.items():
            conn.execute(text(f"ALTER TABLE fontes_esportivas ADD COLUMN {nome} {definicao}"))
    return True
