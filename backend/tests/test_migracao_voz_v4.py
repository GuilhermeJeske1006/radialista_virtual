"""Migração única das escolhas com Eleven v3 para a combinação v4 equivalente (app/db/migrations/voz_v4_20261123.py).

Escuta às cegas em docs/benchmarks/2026-11-23-entrega-voz: v4 com as mesmas vozes soou mais natural que o v3.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.consumo_flex import ContaConsumo, TarifaIA

ESCOLHAS_ANTES = {
    "1": {"texto": "claude-opus-5", "voz": "eleven_v3", "combinacao": "premium", "programa_id": 1},
    "radialista:2": {"texto": "claude-sonnet-5", "voz": "eleven_v3", "combinacao": "equilibrada"},
    "3": {"texto": "claude-haiku-4-5", "voz": "eleven_v3", "combinacao": "voz_premium", "programa_id": 3},
    # Escolha sem combinação (PUT /billing/modelos) também troca o modelo de voz.
    "4": {"texto": "claude-opus-5", "voz": "eleven_v3", "programa_id": 4},
    # Outros modelos de voz e escolha sem voz ficam como estão.
    "5": {"texto": "claude-sonnet-5", "voz": "eleven_flash_v2_5", "combinacao": "agil", "programa_id": 5},
    "whatsapp": {"texto": "claude-haiku-4-5", "voz": None, "programa_id": None},
}


def _banco(com_tarifa_v4=True):
    engine = create_engine("sqlite://")
    TarifaIA.__table__.create(engine)
    ContaConsumo.__table__.create(engine)
    with Session(engine) as db:
        if com_tarifa_v4:
            db.add(TarifaIA(id="v4", tipo="tts", provedor="elevenlabs", modelo="eleven_v4", versao="1",
                            unidades={"caracteres": {"preco": "0.10", "divisor": "1000"}}, cambio="5.5"))
        db.add(ContaConsumo(account_id=7, limite=0, exposicao=0, modelos=dict(ESCOLHAS_ANTES)))
        db.add(ContaConsumo(account_id=8, limite=0, exposicao=0, modelos={}))
        db.commit()
    return engine


def _modelos(engine, account_id=7):
    with Session(engine) as db:
        return db.get(ContaConsumo, account_id).modelos


def test_escolhas_v3_vao_para_a_combinacao_v4_equivalente_uma_vez():
    from app.db.migrations.voz_v4_20261123 import VERSAO, aplicar

    engine = _banco()
    assert aplicar(engine) is True
    modelos = _modelos(engine)
    assert modelos["1"] == {"texto": "claude-opus-5", "voz": "eleven_v4", "combinacao": "premium_v4", "programa_id": 1}
    assert modelos["radialista:2"]["voz"] == "eleven_v4" and modelos["radialista:2"]["combinacao"] == "equilibrada_v4"
    assert modelos["3"]["combinacao"] == "voz_premium_v4"
    assert modelos["4"] == {"texto": "claude-opus-5", "voz": "eleven_v4", "programa_id": 4}
    assert modelos["5"] == ESCOLHAS_ANTES["5"] and modelos["whatsapp"] == ESCOLHAS_ANTES["whatsapp"]
    assert _modelos(engine, 8) == {}

    # Roda uma vez só: quem voltar para o v3 depois não é migrado de novo no próximo startup.
    with Session(engine) as db:
        conta = db.get(ContaConsumo, 7)
        conta.modelos = {**conta.modelos, "1": ESCOLHAS_ANTES["1"]}
        db.commit()
    assert aplicar(engine) is False
    assert _modelos(engine)["1"] == ESCOLHAS_ANTES["1"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT versao FROM migracoes_consumo")).scalars().all() == [VERSAO]
    engine.dispose()


def test_sem_tarifa_do_v4_nao_migra_e_tenta_no_proximo_startup():
    """Sem tarifa vigente do v4 a síntese seria recusada (app.billing.flex.tarifa_atual): melhor ficar no v3."""
    from app.db.migrations.voz_v4_20261123 import aplicar

    engine = _banco(com_tarifa_v4=False)
    assert aplicar(engine) is False
    assert _modelos(engine) == ESCOLHAS_ANTES
    with Session(engine) as db:
        db.add(TarifaIA(id="v4", tipo="tts", provedor="elevenlabs", modelo="eleven_v4", versao="1",
                        unidades={"caracteres": {"preco": "0.10", "divisor": "1000"}}, cambio="5.5"))
        db.commit()
    assert aplicar(engine) is True
    assert _modelos(engine)["1"]["voz"] == "eleven_v4"
    engine.dispose()


def test_banco_novo_sem_tabelas_nao_quebra():
    from app.db.migrations.voz_v4_20261123 import aplicar

    engine = create_engine("sqlite://")
    assert aplicar(engine) is False
    engine.dispose()


def test_startup_migra_depois_de_criar_as_tabelas():
    import inspect as inspecao

    from app import main

    fonte = inspecao.getsource(main.criar_tabelas)
    assert fonte.index("Base.metadata.create_all") < fonte.index("aplicar_voz_v4(engine)")
