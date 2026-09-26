"""Migração aditiva 20260925_01. Não transfere contratos nem reprecifica histórico."""
from sqlalchemy import text
from app.models.consumo_flex import TarifaIA, ContaConsumo, UsoIA, FaturaConsumo, EventoCobranca

VERSAO = '20260925_01'


def aplicar(engine):
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE IF NOT EXISTS migracoes_consumo (versao VARCHAR(40) PRIMARY KEY)'))
        if conn.execute(text('SELECT versao FROM migracoes_consumo WHERE versao=:v'), {'v':VERSAO}).first():
            return
        for modelo in (TarifaIA, ContaConsumo, UsoIA, FaturaConsumo, EventoCobranca):
            modelo.__table__.create(conn, checkfirst=True)
        conn.execute(text('INSERT INTO migracoes_consumo (versao) VALUES (:v)'), {'v':VERSAO})
