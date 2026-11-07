"""Integração do relógio da hora com POST /live/{rid}/programas/{pid}/proxima (F1).

Desenho em docs/melhoria-radio/f1/auditoria.md (§5.6, §5.7 e §6). Mesmo padrão de
tests/test_live_router.py: freeze_time, fakeredis do conftest e dublês por nome em app.live.router.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.musica_historico import MusicaHistorico
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.tema_historico import TemaHistorico

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 em São Paulo, dentro de um programa 10:00-14:00


def _url(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Programa Principal",
                        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0), estrutura_blocos=[])
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


def _sem_campos_novos(dados: dict) -> dict:
    return {k: v for k, v in dados.items() if k not in ("criado_em", "duracao_prevista_s", "relogio")}


# ---------------------------------------------------------------------------------------------
# Caracterização: sem relógio, inicio_previsto não muda nada (escrito e verde antes da mudança)
# ---------------------------------------------------------------------------------------------

def _preparar_caminho(caminho, account, radialista, programa, db_session, monkeypatch):
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.random.randint", lambda a, b: a)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *_: "Seguimos juntos nesta tarde de música.")
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *_: MusicaEncontrada(
        video_id="faixa123", titulo="Clássico", canal="Artista", duracao_segundos=240,
    ))
    programa.ia_pode_adicionar_blocos = False
    corpo = {"total_falas": 1, "historico": ["musica: faixa anterior"], "incluir_audio": False}
    if caminho == "comentario":
        programa.estrutura_blocos = ["comentario"]
    elif caminho == "musica_musical":
        programa.perfil_programacao = "musical_companhia"
        corpo["total_falas"] = 2
    elif caminho == "vinheta":
        vinheta = BibliotecaAudioItem(account_id=account.id, nome="Vinheta", texto="Rádio Teste.", ativo=True,
                                      duracao_segundos=6)
        db_session.add(vinheta)
        db_session.flush()
        programa.estrutura_blocos = [f"vinheta:{vinheta.id}", "comentario"]
        corpo["total_falas"] = 0
    elif caminho == "patrocinador":
        patrocinador = Patrocinador(account_id=account.id, nome="Loja", texto="Loja Teste, perto de você.",
                                    ativo=True)
        db_session.add(patrocinador)
        db_session.flush()
        programa.estrutura_blocos = [f"patrocinador:{patrocinador.id}", "comentario"]
        corpo["total_falas"] = 0
    db_session.commit()
    return corpo


@pytest.mark.parametrize("caminho", ["comentario", "musica_musical", "encerramento", "vinheta", "patrocinador"])
def test_proxima_sem_relogio_ignora_inicio_previsto(
    caminho, client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    from app.config.redis_client import redis_client

    radialista, programa = radialista_e_programa
    agora = "2026-08-10 16:58:00" if caminho == "encerramento" else AGORA_UTC
    corpo = _preparar_caminho(caminho, account, radialista, programa, db_session, monkeypatch)
    respostas = []
    with freeze_time(agora):
        for extra in ({}, {"inicio_previsto": "2026-08-10T13:05:00-03:00"}):
            redis_client.flushall()
            db_session.query(MusicaHistorico).delete()
            db_session.query(TemaHistorico).delete()
            db_session.commit()
            resposta = client.post(_url(radialista.id, programa.id), json={**corpo, **extra},
                                   headers=auth_headers(account.id))
            assert resposta.status_code == 200, resposta.text
            respostas.append(resposta.json())
    assert _sem_campos_novos(respostas[0]) == _sem_campos_novos(respostas[1])
    esperado = {"comentario": "comentario", "musica_musical": "musica", "encerramento": "encerramento",
                "vinheta": "vinheta", "patrocinador": "patrocinador"}[caminho]
    assert respostas[0]["tipo"] == esperado
    assert respostas[1].get("relogio") is None
