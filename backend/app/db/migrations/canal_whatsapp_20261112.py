"""Migração aditiva 20261112_01. Tabelas novas e índices, preservando o histórico legado."""
from sqlalchemy import inspect, text
from app.db.database import Base
from app.models import canal_whatsapp

VERSAO = "20261112_01"


def aplicar(engine):
    existentes = set(inspect(engine).get_table_names())
    alterou = False
    nomes = {valor.__tablename__ for valor in vars(canal_whatsapp).values()
             if isinstance(valor, type) and issubclass(valor, Base) and valor is not Base}
    for tabela in Base.metadata.sorted_tables:
        if tabela.name not in nomes:
            continue
        if tabela.name not in existentes:
            tabela.create(engine, checkfirst=True)
            alterou = True
        if engine.dialect.name == "postgresql" and tabela.name in (
            "blocos_reproduzidos", "discussoes_programa", "contribuicoes_ouvintes",
        ):
            coluna = next(c for c in inspect(engine).get_columns(tabela.name) if c["name"] == "programa_id")
            if not coluna["nullable"]:
                with engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{tabela.name}" ALTER COLUMN programa_id DROP NOT NULL'))
                alterou = True
        for indice in tabela.indexes:
            antes = {i["name"] for i in inspect(engine).get_indexes(tabela.name)}
            indice.create(engine, checkfirst=True)
            alterou = alterou or indice.name not in antes
    return alterou
