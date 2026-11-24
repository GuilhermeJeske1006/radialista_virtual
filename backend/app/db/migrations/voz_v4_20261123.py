"""Migração de dados 20261123_01: escolhas com Eleven v3 passam para a combinação v4 equivalente.

Escuta às cegas em docs/benchmarks/2026-11-23-entrega-voz: com as mesmas vozes, o v4 teve nota 4,17 contra
2,17 do v3 (entonação, pronúncia e ritmo), pelo mesmo preço por caractere. Premium, Equilibrada e Voz Premium
viram as versões v4; escolha gravada sem combinação (PUT /billing/modelos) troca só o modelo de voz.

Roda uma vez (controle em migracoes_consumo, como app.db.migrations.consumo_20260925): quem voltar para o
v3 depois continua no v3. Sem tarifa vigente do v4 não migra nem marca, porque a síntese seria recusada
(app.billing.flex.tarifa_atual); tenta de novo no próximo startup.
"""
import logging

from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.billing.flex import tarifa_atual
from app.models.consumo_flex import ContaConsumo

VERSAO = "20261123_01_voz_v4"
COMBINACAO_V4 = {"premium": "premium_v4", "equilibrada": "equilibrada_v4", "voz_premium": "voz_premium_v4"}

logger = logging.getLogger("radialista.migracoes")


def _migrar(escolha):
    if not isinstance(escolha, dict) or escolha.get("voz") != "eleven_v3":
        return escolha
    nova = {**escolha, "voz": "eleven_v4"}
    if "combinacao" in escolha:
        nova["combinacao"] = COMBINACAO_V4.get(escolha["combinacao"], escolha["combinacao"])
    return nova


def aplicar(engine) -> bool:
    """Devolve True quando alterou o banco."""
    tabelas = inspect(engine).get_table_names()
    if ContaConsumo.__tablename__ not in tabelas or "tarifas_ia" not in tabelas:
        return False
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS migracoes_consumo (versao VARCHAR(40) PRIMARY KEY)"))
        if conn.execute(text("SELECT versao FROM migracoes_consumo WHERE versao=:v"), {"v": VERSAO}).first():
            return False
    with Session(engine) as db:
        try:
            tarifa_atual(db, "tts", "eleven_v4")
        except HTTPException:
            logger.warning("migracao %s adiada: sem tarifa vigente do eleven_v4", VERSAO)
            return False
        alteradas = 0
        for conta in db.scalars(select(ContaConsumo)):
            modelos = {chave: _migrar(escolha) for chave, escolha in (conta.modelos or {}).items()}
            if modelos != (conta.modelos or {}):
                conta.modelos = modelos
                alteradas += 1
        db.execute(text("INSERT INTO migracoes_consumo (versao) VALUES (:v)"), {"v": VERSAO})
        db.commit()
    logger.info("migracao %s: %s contas com escolha v3 passaram para v4", VERSAO, alteradas)
    return True
