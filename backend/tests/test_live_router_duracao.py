"""Duração real da fala em /proxima e /tts (F2 do plano de melhoria de rádio).

Desenho em docs/melhoria-radio/f2/auditoria.md (§4 e §6). Mesmo padrão de tests/test_live_router.py:
freeze_time, fakeredis do conftest e dublês por nome em app.live.router. A primeira parte caracteriza o
comportamento anterior à F2 (reescrita única, formato padrão sem orçamento e registros com o texto da
resposta) e foi escrita verde antes de mexer no router.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.noticia import Noticia
from app.models.noticia_historico import NoticiaHistorico
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 em São Paulo, dentro de um programa 10:00-14:00


def _url(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Programa Principal",
                        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0),
                        estrutura_blocos=[], ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


@pytest.fixture()
def sem_sorteio(monkeypatch):
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")


@pytest.fixture()
def programa_musical(radialista_e_programa, db_session, sem_sorteio):
    radialista, programa = radialista_e_programa
    programa.perfil_programacao = "musical_companhia"
    db_session.commit()
    return radialista, programa


def _gerador(prompts: list, *respostas: str):
    """gerar_resposta falso: devolve as respostas na ordem (a última se repete) e guarda os prompts."""
    def gerar(system, mensagem):
        prompts.append(system)
        return respostas[min(len(prompts), len(respostas)) - 1]
    return gerar


def _criar_noticia(db_session, account) -> Noticia:
    noticia = Noticia(
        account_id=account.id, fonte_nome="Defesa Civil", fonte_tipo="oficial",
        titulo="Rua das Acácias interditada para obra na rede de água",
        resumo="Trecho de trezentos metros fechado desde a manhã.", url="https://exemplo.invalid/materia",
        url_hash="hash-f2-duracao", publicado_em=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        categoria="transito", cidade="Vila Serena", score=90.0, ativa=True,
        detalhes={"servico": "Desvio pela avenida do Lago"},
    )
    db_session.add(noticia)
    db_session.commit()
    return noticia


# ---------------------------------------------------------------------------------------------
# Caracterização (verde antes da F2)
# ---------------------------------------------------------------------------------------------

_LONGA_MUSICAL = "Esta seleção acompanha a sua tarde com música boa. " * 10


@freeze_time(AGORA_UTC)
def test_reescrita_unica_combina_repeticao_e_orcamento(client, account, auth_headers, programa_musical,
                                                      monkeypatch):
    from app.live.router import _registrar_fala_gerada

    radialista, programa = programa_musical
    _registrar_fala_gerada(programa.id, "abertura", _LONGA_MUSICAL.strip())
    prompts: list[str] = []
    curta = "Seguimos juntos com a seleção da tarde."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, _LONGA_MUSICAL.strip(), curta))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200, r.text
    assert r.json()["tipo"] == "retomada"
    assert r.json()["fala"] == curta
    assert len(prompts) == 2
    assert "ficou muito parecida" in prompts[1]
    assert "Reescreva com no máximo 25 palavras" in prompts[1]


@freeze_time(AGORA_UTC)
def test_padrao_sem_relogio_nao_revisa_fala_longa(client, account, auth_headers, radialista_e_programa,
                                                  db_session, sem_sorteio, monkeypatch):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["comentario"]
    db_session.commit()
    longa = " ".join(f"palavra{i}" for i in range(119)) + " fim."
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, longa))
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 1, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200, r.text
    assert r.json()["tipo"] == "comentario"
    assert r.json()["fala"] == longa
    assert len(prompts) == 1


@freeze_time(AGORA_UTC)
@pytest.mark.parametrize("caminho", ["comentario", "noticia", "abertura"])
def test_registros_usam_fala_da_resposta(caminho, client, account, auth_headers, radialista_e_programa, db_session,
                                         sem_sorteio, monkeypatch):
    """Histórico de falas, tema, NoticiaHistorico e fio condutor gravam o texto que a resposta devolve."""
    from app.live.router import _historico_falas

    radialista, programa = radialista_e_programa
    temas, fios = [], []
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda pid, texto: temas.append(texto))
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda texto: fios.append(texto) or "")
    corpo = {"total_falas": 1, "historico": ["musica: faixa anterior"], "incluir_audio": False}
    if caminho == "noticia":
        programa.estrutura_blocos = ["noticia"]
        _criar_noticia(db_session, account)
        fala = "Segundo a Defesa Civil, a Rua das Acácias segue interditada até o fim da tarde."
    elif caminho == "abertura":
        programa.estrutura_blocos = ["abertura", "comentario"]
        corpo = {"total_falas": 0, "historico": [], "incluir_audio": False}
        fala = "Boa tarde! Começa agora o Programa Principal, com música e conversa boa."
    else:
        programa.estrutura_blocos = ["comentario"]
        fala = "Tem gente que organiza a semana no domingo à noite, e isso muda o humor da segunda."
    db_session.commit()
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id), json=corpo)
    assert r.status_code == 200, r.text
    resposta = r.json()
    assert resposta["fala"] == fala
    categoria = {"comentario": "comentario", "noticia": "noticia", "abertura": "abertura"}[caminho]
    assert _historico_falas(programa.id, categoria)[0] == resposta["fala"]
    if caminho in ("comentario", "noticia"):
        assert temas == [resposta["fala"]]
    if caminho == "noticia":
        historico = db_session.query(NoticiaHistorico).filter_by(programa_id=programa.id).all()
        assert [h.fala for h in historico] == [resposta["fala"]]
    if caminho == "abertura":
        assert fios == [resposta["fala"]]


@freeze_time(AGORA_UTC)
def test_musica_sem_pedido_no_musical_continua_sem_llm(client, account, auth_headers, programa_musical,
                                                       monkeypatch):
    radialista, programa = programa_musical
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: pytest.fail("não gerar fala"))
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *_: MusicaEncontrada(
        video_id="faixa123", titulo="Clássico", canal="Artista", duracao_segundos=240))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 2, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200
    assert r.json()["fala"] == ""
    assert r.json()["video_id"] == "faixa123"
