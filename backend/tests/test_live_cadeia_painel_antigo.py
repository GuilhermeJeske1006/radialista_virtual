"""Painel antigo sem inicio_previsto: horário estimado pela cadeia de blocos no servidor (F3, U6, I7 e I8)."""

import datetime

import pytest
import redis
from freezegun import freeze_time

from app.live import relogio as r
from app.live.music import MusicaEncontrada
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

UTC = datetime.timezone.utc
AGORA = datetime.datetime(2026, 11, 10, 15, 0, 30, tzinfo=UTC)
INICIO = datetime.datetime(2026, 11, 10, 15, 0, 0, tzinfo=UTC)


def _elo(duracao, vinheta=False):
    return r.EloCadeia(tipo="vinheta" if vinheta else "fala", vinheta=vinheta, duracao_s=duracao, gerado_em=0.0)


def _s(segundos):
    return datetime.timedelta(seconds=segundos)


# ---------------------------------------------------------------------------------------------
# U6: função pura
# ---------------------------------------------------------------------------------------------

def test_sem_elos_abre_no_inicio_ou_agora():
    antes = INICIO - _s(90)
    assert r.instante_sem_painel([], antes, INICIO) == INICIO
    assert r.instante_sem_painel([], AGORA, INICIO) == AGORA


def test_menos_elos_que_a_antecedencia_contam_do_inicio():
    antes = INICIO - _s(90)
    assert r.instante_sem_painel([_elo(30)], antes, INICIO) == INICIO + _s(30)


def test_com_a_antecedencia_cheia_se_reancora_em_agora():
    assert r.instante_sem_painel([_elo(30), _elo(200)], AGORA, INICIO) == AGORA + _s(230)
    assert r.instante_sem_painel([_elo(30), _elo(200), _elo(25)], AGORA, INICIO) == AGORA + _s(225)


def test_vinheta_nao_conta_na_antecedencia():
    # O bloco que acabou de começar é o penúltimo sem vinheta: a vinheta depois dele soma, mas não conta.
    assert r.instante_sem_painel([_elo(30), _elo(6, vinheta=True), _elo(200)], AGORA, INICIO) == AGORA + _s(236)
    assert r.instante_sem_painel([_elo(6, vinheta=True), _elo(30)], INICIO - _s(90), INICIO) == INICIO + _s(36)


def test_limite_superior_e_inferior():
    cfg = r.CONFIG_PADRAO
    assert r.instante_sem_painel([_elo(5000), _elo(5000)], AGORA, INICIO) == AGORA + _s(cfg.inicio_previsto_max_s)
    assert r.instante_sem_painel([_elo(0), _elo(0)], AGORA, INICIO) == AGORA


def test_cadeia_no_redis_e_redis_fora(monkeypatch):
    from app.config import redis_client as modulo

    ocorrencia = r.Ocorrencia(inicio=INICIO, fim=INICIO + _s(3600), data=INICIO.date())
    r.gravar_elo(1, ocorrencia, _elo(30))
    r.gravar_elo(1, ocorrencia, _elo(6, vinheta=True))
    assert r.ler_cadeia(1, ocorrencia) == [_elo(30), _elo(6, vinheta=True)]
    r.zerar_cadeia(1, ocorrencia)
    assert r.ler_cadeia(1, ocorrencia) == []

    def quebrado(*a, **k):
        raise redis.ConnectionError("fora")

    monkeypatch.setattr(modulo.redis_client, "lrange", quebrado)
    try:
        assert r.ler_cadeia(1, ocorrencia) == []
        assert r.instante_sem_painel(r.ler_cadeia(1, ocorrencia), AGORA, INICIO) == AGORA
    finally:
        modulo.disjuntor.fechar()


# ---------------------------------------------------------------------------------------------
# I7 e I8: pela rota
# ---------------------------------------------------------------------------------------------

@pytest.fixture()
def programa_relogio(db_session, account, monkeypatch):
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                   tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                      for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
    db_session.add_all(patrocinadores)
    db_session.flush()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(12, 0),
                        horario_fim=datetime.time(13, 0), ia_pode_adicionar_blocos=False,
                        estrutura_blocos=["comentario", *[f"patrocinador:{p.id}" for p in patrocinadores]],
                        relogio_hora=r.PRESETS["A"].model_dump())
    db_session.add(programa)
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: "Boa tarde, começa agora o nosso programa.")
    monkeypatch.setattr("app.live.router._selecionar_musica_para_bloco", lambda *a, **k: (MusicaEncontrada(
        video_id="f1", titulo="Faixa", canal="Banda", duracao_segundos=200), "q"))
    return radialista, programa


def _post(client, account, auth_headers, radialista, programa, **corpo):
    corpo.setdefault("incluir_audio", False)
    resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima", json=corpo,
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _linha(dados):
    return f"{dados['tipo']}: {dados['fala']}"


def _duracao(dados):
    return (dados.get("pausa_antes_ms") or 0) / 1000 + dados["duracao_prevista_s"]


def _instante(dados):
    return datetime.datetime.fromisoformat(dados["relogio"]["inicio_previsto"])


def test_i7_painel_antigo_encadeia_tres_pedidos(client, account, auth_headers, programa_relogio):
    radialista, programa = programa_relogio
    with freeze_time("2026-11-10 14:58:30") as relogio:     # 90 s antes do início (12:00 em São Paulo)
        b1 = _post(client, account, auth_headers, radialista, programa, total_falas=0, historico=[])
        assert b1["relogio"]["origem_instante"] == "estimado"
        assert b1["relogio"]["inicio_previsto_aceito"] is False
        assert _instante(b1) == INICIO                    # 12:00 em São Paulo
        b2 = _post(client, account, auth_headers, radialista, programa, total_falas=1, historico=[_linha(b1)])
        assert _instante(b2) == _instante(b1) + _s(_duracao(b1))
        relogio.move_to("2026-11-10 15:00:00")              # o bloco 1 começa a tocar: o painel gera o 3
        b3 = _post(client, account, auth_headers, radialista, programa, total_falas=2,
                   historico=[_linha(b1), _linha(b2)])
        assert _instante(b3) == datetime.datetime(2026, 11, 10, 15, 0, tzinfo=UTC) + _s(_duracao(b1) + _duracao(b2))
        com_campo = _post(client, account, auth_headers, radialista, programa, total_falas=3,
                          historico=[_linha(b1), _linha(b2), _linha(b3)],
                          inicio_previsto="2026-11-10T12:05:00-03:00")
        assert com_campo["relogio"]["origem_instante"] == "painel"


def test_i8_primeiro_bloco_do_preparo_antecipado_entra_na_cadeia(client, account, auth_headers, programa_relogio):
    """O prewarm manda inicio_previsto (o início agendado): grava o primeiro elo, e o painel antigo encadeia dele."""
    radialista, programa = programa_relogio
    with freeze_time("2026-11-10 14:59:00"):
        preparo = _post(client, account, auth_headers, radialista, programa, total_falas=0, historico=[],
                        inicio_previsto="2026-11-10T12:00:00-03:00")
        assert preparo["relogio"]["origem_instante"] == "painel"
        seguinte = _post(client, account, auth_headers, radialista, programa, total_falas=1,
                         historico=[_linha(preparo)])
        assert seguinte["relogio"]["origem_instante"] == "estimado"
        assert _instante(seguinte) == datetime.datetime(2026, 11, 10, 15, 0, tzinfo=UTC) + _s(_duracao(preparo))
