"""Migração aditiva 20261109_01: tabela ritmos_voz (ritmo observado por voz, F2).

A existência da tabela é o próprio estado da migração: sem tabela de controle. Idempotente; não altera
nenhuma tabela existente.
"""
from sqlalchemy import inspect

from app.models.perfil_voz import RitmoVoz

VERSAO = "20261109_01"


def aplicar(engine) -> bool:
    """Cria a tabela se ela não existir. Devolve True quando alterou o banco."""
    if RitmoVoz.__tablename__ in inspect(engine).get_table_names():
        return False
    RitmoVoz.__table__.create(engine, checkfirst=True)
    return True
