import datetime
import json

import pytest
from freezegun import freeze_time

from app.live import prewarm
from app.live.router import LiveProgramResponse
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

TZ = "America/Sao_Paulo"

# 2026-08-10 15:00 UTC == 2026-08-10 12:00 America/Sao_Paulo, uma segunda-feira.
AGORA_UTC = "2026-08-10 15:00:00"


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone=TZ)
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Principal",
        horario_inicio=datetime.time(12, 1, 30),
        horario_fim=datetime.time(14, 0),
        ativo=True,
        estrutura_blocos=[],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(radio_config)
    db_session.refresh(programa)
    return radio_config, programa


def _resposta_fake(fala="E ai, bom dia!", falas=None):
    return LiveProgramResponse(
        tipo="abertura",
        fala=fala,
        criado_em=datetime.datetime.now(datetime.timezone.utc),
        programa_atual="Programa Principal",
        falas=falas,
    )


def test_preparar_programa_grava_cache_no_redis(monkeypatch, db_session, account, radialista_e_programa):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        prewarm, "gerar_proxima_fala",
        lambda radialista_id, programa_id, dados, account, db: _resposta_fake(),
    )

    prewarm.preparar_programa(db_session, account, radio_config, programa)

    bruto = prewarm.redis_client.get(prewarm._chave_cache(programa.id))
    assert bruto is not None
    payload = json.loads(bruto)
    assert payload["fala"] == "E ai, bom dia!"
    assert payload["tipo"] == "abertura"


def test_consumir_preparo_antecipado_e_uso_unico(monkeypatch, db_session, account, radialista_e_programa):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        prewarm, "gerar_proxima_fala",
        lambda radialista_id, programa_id, dados, account, db: _resposta_fake(),
    )
    prewarm.preparar_programa(db_session, account, radio_config, programa)

    primeiro = prewarm.consumir_preparo_antecipado(programa.id)
    segundo = prewarm.consumir_preparo_antecipado(programa.id)

    assert primeiro is not None and primeiro["fala"] == "E ai, bom dia!"
    assert segundo is None


@freeze_time(AGORA_UTC)
def test_executar_tick_prepara_uma_vez_dentro_da_janela(monkeypatch, db_session, account, radialista_e_programa):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(prewarm, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    chamadas = []
    monkeypatch.setattr(
        prewarm, "preparar_programa",
        lambda db, acc, radialista, prog: chamadas.append(prog.id),
    )

    prewarm.executar_tick()
    prewarm.executar_tick()  # segunda rodada no mesmo segundo -- dedupe deve barrar

    assert chamadas == [programa.id]


@freeze_time(AGORA_UTC)
def test_executar_tick_fora_da_janela_nao_prepara(monkeypatch, db_session, account, radialista_e_programa):
    radio_config, programa = radialista_e_programa
    programa.horario_inicio = datetime.time(18, 0)  # 6h no futuro, fora da janela de 90s
    db_session.commit()

    monkeypatch.setattr(prewarm, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    chamadas = []
    monkeypatch.setattr(
        prewarm, "preparar_programa",
        lambda db, acc, radialista, prog: chamadas.append(prog.id),
    )

    prewarm.executar_tick()

    assert chamadas == []
