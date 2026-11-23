from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.billing.combinacoes import catalogo, habilitadas
from app.config.settings import settings
from app.models.consumo_flex import TarifaIA
from scripts.publicar_tarifas_referencia import main, tarifas


@pytest.fixture
def publicar(db_session, monkeypatch):
    monkeypatch.setattr("app.db.database.engine", db_session.get_bind())
    monkeypatch.setattr("app.db.database.SessionLocal", sessionmaker(bind=db_session.get_bind()))
    monkeypatch.setattr("sys.argv", ["publicar_tarifas_referencia.py", "--ambiente-de-teste", "--somente-ausentes"])
    return main


def test_banco_novo_libera_catalogo_e_repeticao_nao_duplica(db_session, publicar):
    publicar()
    assert len(catalogo(db_session)["combinacoes"]) == len(habilitadas())
    ids = set(db_session.scalars(select(TarifaIA.id)))
    assert len(ids) == len(tarifas(settings))

    publicar()
    assert set(db_session.scalars(select(TarifaIA.id))) == ids


def test_preserva_tarifa_contratada_vigente(db_session, publicar):
    db_session.add(TarifaIA(
        id="contratada", tipo="llm", provedor="anthropic", modelo=settings.llm_model,
        versao="contrato", unidades={}, cambio="5", acrescimo="80",
        vigente_desde=datetime.now(timezone.utc) - timedelta(days=1),
    ))
    db_session.commit()

    publicar()

    assert list(db_session.scalars(select(TarifaIA.id).where(
        TarifaIA.tipo == "llm", TarifaIA.modelo == settings.llm_model
    ))) == ["contratada"]


@pytest.mark.parametrize("chave", ["sk_live_teste", "rk_live_teste"])
def test_recusa_chave_live_sem_publicar(db_session, publicar, monkeypatch, chave):
    monkeypatch.setattr(settings, "stripe_secret_key", chave)
    with pytest.raises(SystemExit, match="Recusado"):
        publicar()
    assert list(db_session.scalars(select(TarifaIA.id))) == []
