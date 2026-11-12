"""Migração aditiva 20261112_01: tabela promessas_no_ar (promessas feitas no ar, F4).

A existência da tabela é o próprio estado da migração: sem tabela de controle. Idempotente; não altera
nenhuma tabela existente.
"""
from sqlalchemy import inspect

from app.models.promessa_no_ar import PromessaNoAr

VERSAO = "20261112_01"


def aplicar(engine) -> bool:
    """Cria a tabela (e os índices) se ela não existir. Devolve True quando alterou o banco."""
    if PromessaNoAr.__tablename__ in inspect(engine).get_table_names():
        return False
    PromessaNoAr.__table__.create(engine, checkfirst=True)
    return True
