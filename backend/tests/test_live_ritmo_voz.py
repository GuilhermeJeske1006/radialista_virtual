"""Ritmo observado por voz (F2): tabela ritmos_voz, cadeia do wpm e orçamento pendente no Redis.

Desenho em docs/melhoria-radio/f2/auditoria.md (§4.4). Só agregados numéricos no banco; o Redis serve
para deduplicar amostras vindas do cache de TTS e para o orçamento que o /tts lê, e falha aberto.
"""

import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def cfg_ritmo(monkeypatch):
    from app.config.settings import settings

    for chave, valor in {
        "fala_wpm_padrao": 150.0,
        "fala_wpm_padrao_por_modelo": {"eleven_v3": 162.0},
        "fala_calibracao_min_amostras": 3,
        "fala_calibracao_max_amostras": 10,
        "fala_pausa_explicita_s": 1.2,
    }.items():
        monkeypatch.setattr(settings, chave, valor)
    return settings


def _voz(voz_id="voz-a", modelo="eleven_v3", perfil="atual"):
    from app.live.ritmo_voz import VozEfetiva

    return VozEfetiva(voz_id=voz_id, modelo=modelo, perfil=perfil)


def _linhas(db_session):
    from app.models.perfil_voz import RitmoVoz

    return {(r.voz_id, r.modelo, r.perfil, r.categoria): (r.amostras, r.palavras, r.segundos)
            for r in db_session.query(RitmoVoz).all()}


def test_registrar_amostra_cria_e_incrementa(db_session, cfg_ritmo):
    from app.live.ritmo_voz import registrar_amostra

    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0) is True
    assert _linhas(db_session) == {("voz-a", "eleven_v3", "atual", "comentario"): (1, 30.0, 12.0)}
    # Pausas saem dos segundos: 30 palavras em 13,2 s com uma pausa de 1,2 s = 12 s de fala.
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=13.2, pausas=1) is True
    assert _linhas(db_session) == {("voz-a", "eleven_v3", "atual", "comentario"): (2, 60.0, 24.0)}
    # Amostra ruim (curta demais) não entra.
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=5, duracao_s=2.0) is False
    assert _linhas(db_session)[("voz-a", "eleven_v3", "atual", "comentario")][0] == 2


def test_registrar_amostra_corta_somas_pela_metade_no_limite(db_session, cfg_ritmo):
    from app.live.ritmo_voz import registrar_amostra

    for _ in range(11):
        registrar_amostra(db_session, _voz(), "musica", palavras=20, duracao_s=10.0)
    amostras, palavras, segundos = _linhas(db_session)[("voz-a", "eleven_v3", "atual", "musica")]
    assert amostras == 5 and palavras == pytest.approx(110.0) and segundos == pytest.approx(55.0)
    assert palavras / segundos * 60 == pytest.approx(120.0)


def test_wpm_para_percorre_a_cadeia(db_session, cfg_ritmo):
    from app.live.ritmo_voz import carregar_ritmos, registrar_amostra, wpm_para

    voz = _voz()
    # Sem amostras: padrão do modelo; modelo sem padrão: padrão geral.
    assert wpm_para(db_session, voz, "comentario") == 162.0
    assert wpm_para(db_session, _voz(modelo="eleven_multilingual_v2"), "comentario") == 150.0
    # Duas amostras de comentário a 120 e uma de música a 180: a voz (3 amostras) já calibra; a categoria
    # comentário (2) ainda não, então cai no agregado da voz.
    registrar_amostra(db_session, voz, "comentario", palavras=24, duracao_s=12.0)
    registrar_amostra(db_session, voz, "comentario", palavras=24, duracao_s=12.0)
    registrar_amostra(db_session, voz, "musica", palavras=30, duracao_s=10.0)
    ritmos = carregar_ritmos(db_session, voz)
    assert ritmos.wpm("comentario") == pytest.approx(78 / 34 * 60)
    assert ritmos.fonte("comentario") == "voz"
    registrar_amostra(db_session, voz, "comentario", palavras=24, duracao_s=12.0)
    assert wpm_para(db_session, voz, "comentario") == pytest.approx(120.0)
    assert carregar_ritmos(db_session, voz).fonte("comentario") == "categoria"
    assert wpm_para(db_session, voz) == pytest.approx(102 / 46 * 60)
    # Outro perfil e outro modelo da mesma voz não se misturam.
    assert wpm_para(db_session, _voz(perfil="natural"), "comentario") == 162.0


def test_registrar_amostra_deduplica_pelo_audio(db_session, cfg_ritmo):
    from app.live.ritmo_voz import registrar_amostra

    audio = b"\xff\xfb mesmo audio vindo do cache"
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0, audio=audio) is True
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0, audio=audio) is False
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0, audio=b"outro") is True
    assert _linhas(db_session)[("voz-a", "eleven_v3", "atual", "comentario")][0] == 2


def test_registrar_amostra_funciona_sem_redis(db_session, cfg_ritmo, monkeypatch):
    from app.config.redis_client import redis_client
    from app.live.ritmo_voz import registrar_amostra

    def _sem_redis(*args, **kwargs):
        raise RedisError("fora do ar")

    monkeypatch.setattr(redis_client, "set", _sem_redis)
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0, audio=b"a") is True
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0, audio=b"a") is True
    assert _linhas(db_session)[("voz-a", "eleven_v3", "atual", "comentario")][0] == 2


def test_falha_no_banco_nao_propaga(db_session, cfg_ritmo, monkeypatch, caplog):
    from app.live.ritmo_voz import carregar_ritmos, registrar_amostra

    def _quebrado(*args, **kwargs):
        raise OperationalError("UPDATE ritmos_voz", {}, Exception("banco fora"))

    monkeypatch.setattr(db_session, "execute", _quebrado)
    monkeypatch.setattr(db_session, "query", _quebrado)
    assert registrar_amostra(db_session, _voz(), "comentario", palavras=30, duracao_s=12.0) is False
    assert carregar_ritmos(db_session, _voz()).wpm("comentario") == 162.0
    assert "ritmo_voz_falhou" in caplog.text


def test_voz_efetiva_so_le_o_banco(db_session, account, monkeypatch):
    """Modelo e perfil efetivos antes do TTS saem de ConfiguracaoVoz e da combinação da conta, sem
    consultar metadados na ElevenLabs (consultar_metadados pode ir à rede)."""
    from app.live.ritmo_voz import voz_efetiva
    from app.models.perfil_voz import ConfiguracaoVoz

    monkeypatch.setattr("app.tts.profiles.consultar_metadados", lambda *a, **k: pytest.fail("rede"))
    monkeypatch.setattr("app.tts.profiles.settings.elevenlabs_voice_id", "voz-padrao")
    monkeypatch.setattr("app.tts.profiles.settings.elevenlabs_model", "eleven_v3")
    assert voz_efetiva(db_session, account.id, None) == _voz("voz-padrao", "eleven_v3", "atual")
    db_session.add(ConfiguracaoVoz(account_id=account.id, voz_id="voz-b", modelo="eleven_v4", perfil="natural"))
    db_session.commit()
    assert voz_efetiva(db_session, account.id, "voz-b") == _voz("voz-b", "eleven_v4", "natural")


def test_orcamento_pendente_no_redis(monkeypatch):
    from app.config.redis_client import redis_client
    from app.live.ritmo_voz import guardar_orcamento_pendente, ler_orcamento_pendente

    guardar_orcamento_pendente(7, "Boa tarde.", {"max_s": 12, "fonte": "formato"})
    assert ler_orcamento_pendente(7, "Boa tarde.") == {"max_s": 12, "fonte": "formato"}
    assert ler_orcamento_pendente(7, "Outro texto.") is None
    assert 0 < redis_client.ttl(next(iter(redis_client.keys("fala_orcamento:7:*")))) <= 900

    def _sem_redis(*args, **kwargs):
        raise RedisError("fora do ar")

    monkeypatch.setattr(redis_client, "set", _sem_redis)
    monkeypatch.setattr(redis_client, "get", _sem_redis)
    guardar_orcamento_pendente(7, "Boa tarde.", {"max_s": 12})
    assert ler_orcamento_pendente(7, "Boa tarde.") is None


def test_migracao_ritmo_voz_idempotente():
    from app.db.migrations.ritmo_voz_20261109 import aplicar

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    assert aplicar(engine) is True
    assert aplicar(engine) is False
    colunas = {c["name"] for c in inspect(engine).get_columns("ritmos_voz")}
    assert {"voz_id", "modelo", "perfil", "categoria", "amostras", "palavras", "segundos"} <= colunas
    engine.dispose()
