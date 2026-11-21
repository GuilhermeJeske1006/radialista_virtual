"""Redis com timeouts, disjuntor e falha aberta no estado de sessão do ao vivo (F3, U7 e I6 da auditoria §6)."""

import datetime

import pytest
import redis
from freezegun import freeze_time

from app.config import redis_client as modulo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

# Chaves de estado de sessão e cache do ao vivo (as que passam por redis_sessao).
PREFIXOS_SESSAO = ("rotacao:", "musicas_tocadas:", "falas_geradas:", "temas_comentados:", "ultimo_tom:",
                   "fio_condutor:", "cache:", "callback_", "clima_mencionado", "assuntos_", "fato_do_dia",
                   "relogio_cadeia:", "relogio_etapas:")


@pytest.fixture(autouse=True)
def _disjuntor_fechado():
    modulo.disjuntor.fechar()
    yield
    modulo.disjuntor.fechar()


@pytest.fixture()
def redis_fora(monkeypatch):
    """Todo comando de sessão do cliente cru levanta ConnectionError do redis (queda ou timeout)."""
    chamadas: list[tuple[str, str]] = []

    def quebrado(nome):
        def comando(*args, **kwargs):
            chamadas.append((nome, str(args[0]) if args else ""))
            raise redis.ConnectionError("redis fora")
        return comando

    for nome in modulo.PADROES_SESSAO:
        monkeypatch.setattr(modulo.redis_client, nome, quebrado(nome))
    return chamadas


def test_cliente_recebe_os_timeouts_da_configuracao(monkeypatch):
    from app.config.settings import settings

    recebidos = {}
    monkeypatch.setattr(modulo.redis, "from_url", lambda url, **kwargs: recebidos.update(url=url, **kwargs) or "c")
    assert modulo.criar_cliente("redis://exemplo:6379/0") == "c"
    assert recebidos == {
        "url": "redis://exemplo:6379/0", "decode_responses": True,
        "socket_connect_timeout": settings.redis_connect_timeout_s, "socket_timeout": settings.redis_socket_timeout_s,
        "health_check_interval": settings.redis_health_check_s,
    }
    assert (settings.redis_connect_timeout_s, settings.redis_socket_timeout_s) == (0.5, 1.0)


def test_seguro_devolve_o_padrao_e_o_disjuntor_poupa_o_socket(caplog):
    tentativas = []

    def falha():
        tentativas.append(1)
        raise redis.TimeoutError("lento")

    assert modulo.seguro(falha, "padrao", "get") == "padrao"
    assert not modulo.redis_disponivel()
    for _ in range(5):
        assert modulo.seguro(falha, [], "lrange") == []
    assert len(tentativas) == 1
    assert caplog.text.count("redis_indisponivel") == 1


def test_disjuntor_tenta_de_novo_depois_da_pausa():
    agora = [100.0]
    disjuntor = modulo.Disjuntor(pausa_s=lambda: 15, relogio=lambda: agora[0])
    disjuntor.falhou("get", redis.ConnectionError())
    assert disjuntor.aberto()
    agora[0] = 114.9
    assert disjuntor.aberto()
    agora[0] = 115.1
    assert not disjuntor.aberto()


def test_erro_que_nao_e_do_redis_continua_subindo():
    with pytest.raises(ValueError):
        modulo.seguro(lambda: (_ for _ in ()).throw(ValueError("bug")), None, "get")
    assert modulo.redis_disponivel()


def test_cliente_seguro_usa_padroes_neutros(redis_fora):
    sessao = modulo.redis_sessao
    assert sessao.get("x") is None
    assert (sessao.lrange("x", 0, -1), sessao.smembers("x"), sessao.hgetall("x"), sessao.incr("x")) == \
        ([], set(), {}, 1)
    assert len(redis_fora) == 1


@pytest.mark.parametrize("rota, corpo, esperado", [
    ("/auth/login", {"email": "a@b.com", "senha": "senha12345"}, 503),
    ("/auth/esqueci-senha", {"email": "a@b.com"}, 503),
])
def test_rate_limit_fecha_nas_rotas_publicas_de_autenticacao(client, monkeypatch, rota, corpo, esperado):
    def quebrado(*a, **k):
        raise redis.ConnectionError("redis fora")

    monkeypatch.setattr(modulo.redis_client, "incr", quebrado)
    assert client.post(rota, json=corpo).status_code == esperado


def test_rate_limit_abre_no_resto(monkeypatch):
    from app.guardrails.http_rate_limit import limite_excedido

    def quebrado(*a, **k):
        raise redis.ConnectionError("redis fora")

    monkeypatch.setattr(modulo.redis_client, "incr", quebrado)
    assert limite_excedido("live_proxima:1", limite=60) is False


@freeze_time("2026-08-10 15:00:00")
def test_proxima_e_tts_com_redis_fora(client, account, auth_headers, db_session, monkeypatch, redis_fora, caplog):
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=["comentario"],
                        ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or
                        "Seguimos juntos nesta tarde.")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    url = f"/live/{radialista.id}/programas/{programa.id}/proxima"
    corpo = {"incluir_audio": False, "total_falas": 3, "historico": ["musica: boa"]}

    primeira = client.post(url, json=corpo, headers=auth_headers(account.id))
    assert primeira.status_code == 200, primeira.text
    # Sem memória: rotação na primeira opção, sem tom anterior.
    assert "'toca com a gente'" in prompts[0]
    assert "A fala anterior saiu em tom" not in prompts[0]
    assert caplog.text.count("redis_indisponivel") == 1

    redis_fora.clear()
    segunda = client.post(url, json=corpo, headers=auth_headers(account.id))
    assert segunda.status_code == 200
    assert [c for c in redis_fora if c[1].startswith(PREFIXOS_SESSAO)] == []

    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz=None: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio_stream", lambda *a, **k: iter([b"mp3"]))
    tts = client.post(f"/live/{radialista.id}/tts", json={"texto": "Oi.", "tom": "neutro", "programa_id": programa.id},
                      headers=auth_headers(account.id))
    assert tts.status_code == 200
