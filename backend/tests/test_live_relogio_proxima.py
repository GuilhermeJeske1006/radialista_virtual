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


def _wpm_da_voz() -> float:
    """Ritmo sem calibração da voz do teste: o padrão do modelo do servidor (F2, app.live.ritmo_voz.wpm_para)."""
    from app.config.settings import settings
    from app.live.orcamento import wpm_padrao

    return wpm_padrao(settings.elevenlabs_model)


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


# ---------------------------------------------------------------------------------------------
# Integração com relógio (I1-I16)
# ---------------------------------------------------------------------------------------------

@pytest.fixture()
def com_relogio(radialista_e_programa, account, db_session, monkeypatch):
    from app.live.relogio import PRESETS

    radialista, programa = radialista_e_programa
    patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                   tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                      for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
    db_session.add_all(patrocinadores)
    db_session.flush()
    programa.horario_inicio, programa.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
    programa.ia_pode_adicionar_blocos = False
    programa.estrutura_blocos = ["comentario", *[f"patrocinador:{p.id}" for p in patrocinadores]]
    programa.relogio_hora = PRESETS["A"].model_dump()
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    return radialista, programa, patrocinadores


def _post(client, account, auth_headers, radialista, programa, **corpo):
    corpo.setdefault("incluir_audio", False)
    corpo.setdefault("historico", ["musica: faixa anterior"])
    corpo.setdefault("total_falas", 3)
    resposta = client.post(_url(radialista.id, programa.id), json=corpo, headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _marcar(programa, *chaves, radialista_tz="America/Sao_Paulo"):
    from app.live import relogio as r

    instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    r.marcar_executada(programa.id, r.ocorrencia_em(programa, radialista_tz, instante), *chaves)


def _prompts(monkeypatch, *respostas):
    prompts = []
    fila = list(respostas) or ["Seguimos juntos nesta tarde."]

    def gerar(system, msg):
        prompts.append(system)
        return fila[min(len(prompts), len(fila)) - 1]

    monkeypatch.setattr("app.live.router.gerar_resposta", gerar)
    return prompts


@freeze_time("2026-11-10 15:00:05")
def test_i1_i11_inicio_previsto_aceito_ecoado_e_cliente_antigo(client, account, auth_headers, com_relogio, monkeypatch):
    radialista, programa, _ = com_relogio
    _prompts(monkeypatch, "Boa tarde, começa agora o nosso programa com muita música.")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:00:10-03:00",
                  total_falas=0, historico=[])
    assert dados["tipo"] == "abertura"
    assert dados["relogio"]["preset"] == "A"
    assert dados["relogio"]["inicio_previsto_aceito"] is True
    assert dados["relogio"]["inicio_previsto"].startswith("2026-11-10T15:00:10")
    assert (dados["relogio"]["etapa"]["tipo"], dados["relogio"]["etapa"]["hard_time"]) == ("abertura", True)
    assert dados["duracao_alvo_segundos"] == [20, 40]

    antigo = _post(client, account, auth_headers, radialista, programa, total_falas=1)
    assert antigo["relogio"]["inicio_previsto_aceito"] is False
    assert antigo["relogio"]["inicio_previsto"].startswith("2026-11-10T15:00:05")


@freeze_time("2026-11-10 15:10:00")
def test_i2_sem_espaco_nao_chama_o_llm(client, account, auth_headers, com_relogio, monkeypatch):
    from unittest.mock import Mock

    radialista, programa, patrocinadores = com_relogio
    gerar = Mock(side_effect=AssertionError("sem espaço para fala"))
    monkeypatch.setattr("app.live.router.gerar_resposta", gerar)
    monkeypatch.setattr("app.live.router._selecionar_musica_para_bloco", lambda *a, **k: (MusicaEncontrada(
        video_id="f1", titulo="Faixa Curta", canal="Banda", duracao_segundos=200), "q"))
    _marcar(programa, "0:0:fala:abertura", "0:720")
    musica = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:10:00-03:00")
    assert (musica["tipo"], musica["fala"], musica["video_id"]) == ("musica", "", "f1")
    assert musica["relogio"]["acao"] == "musica"
    assert musica["duracao_prevista_s"] == 200

    _marcar(programa, "0:755:reserva", "0:755:preenchimento")
    adiantado = _post(client, account, auth_headers, radialista, programa,
                      inicio_previsto="2026-11-10T12:23:00-03:00")
    assert adiantado["tipo"] == "patrocinador" and adiantado["patrocinador_id"] == patrocinadores[0].id
    assert adiantado["relogio"]["acao"] == "adiantamento"
    assert adiantado["duracao_prevista_s"] == 30
    gerar.assert_not_called()


@freeze_time("2026-11-10 15:12:00")
def test_i3_pouco_espaco_reduz_o_orcamento(client, account, auth_headers, com_relogio, db_session, monkeypatch):
    from app.live.relogio import RelogioHora

    radialista, programa, _ = com_relogio
    eventos, inicio = [], 0
    for tipo, duracao, natureza, hard in (("abertura", 40, "obrigatorio", True), ("musica", 680, "ajustavel", False),
                                          ("link", 35, "ajustavel", False), ("intervalo", 180, "obrigatorio", True),
                                          ("musica", 2635, "ajustavel", False), ("passagem", 30, "obrigatorio", True)):
        eventos.append({"inicio_s": inicio, "duracao_s": duracao, "tipo": tipo, "natureza": natureza, "hard_time": hard})
        inicio += duracao
    programa.relogio_hora = RelogioHora.model_validate({"eventos": eventos}).model_dump()
    db_session.commit()
    _marcar(programa, "0:0:fala:abertura")
    prompts = _prompts(monkeypatch, "Uma dica rápida antes do intervalo.")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:12:17-03:00")
    assert (dados["tipo"], dados["duracao_alvo_segundos"]) == ("comentario", [10, 18])
    assert dados["relogio"]["acao"] == "fala_reduzida"
    assert f"Meta: 10 a 18 segundos, no máximo {int(18 * _wpm_da_voz() // 60)} palavras" in prompts[0]


@freeze_time("2026-11-10 15:52:00")  # 12:52: sem relógio, ainda faltariam 8 min
def test_i4_encerramento_decidido_pelo_horario_previsto(client, account, auth_headers, com_relogio, monkeypatch):
    radialista, programa, _ = com_relogio
    _prompts(monkeypatch, "Obrigado pela companhia nesta tarde.")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:59:35-03:00")
    assert dados["tipo"] == "encerramento"
    assert dados["duracao_alvo_segundos"] == [15, 25]
    assert dados["relogio"]["acao"] == "encerramento"


@freeze_time("2026-11-10 15:15:00")
def test_i5_debate_estourou_gera_fechamento_curto(client, account, auth_headers, com_relogio, db_session, monkeypatch):
    from app.live.relogio import PRESETS

    radialista, programa, _ = com_relogio
    programa.relogio_hora = PRESETS["C"].model_dump()
    db_session.commit()
    _marcar(programa, "0:0:fala:abertura")
    prompts = _prompts(monkeypatch, "Fica a dica: devagar se vai longe.")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:15:48-03:00",
                  historico=["comentario: falávamos de hábitos simples"])
    assert dados["relogio"]["acao"] == "fechamento_curto"
    assert dados["duracao_alvo_segundos"] == [6, 12]
    assert "Feche o assunto em andamento" in prompts[0]


@freeze_time("2026-11-10 15:12:00")
def test_i6_i15_revisao_por_orcamento_no_formato_padrao(client, account, auth_headers, com_relogio, monkeypatch):
    radialista, programa, _ = com_relogio
    _marcar(programa, "0:0:fala:abertura")
    curta = "Um assunto rápido entre as músicas desta tarde."
    prompts = _prompts(monkeypatch, "Uma conversa longa sobre a tarde. " * 20, curta)
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:12:00-03:00")
    assert (dados["tipo"], dados["fala"], dados["duracao_alvo_segundos"]) == ("comentario", curta, [10, 35])
    assert len(prompts) == 2
    assert f"Reescreva com no máximo {int(35 * _wpm_da_voz() // 60)} palavras" in prompts[1]
    assert "4 a 6 frases" not in prompts[0] and "em loop" not in prompts[0]
    assert "Não cite nem prometa música específica" in prompts[0]


@freeze_time("2026-11-10 15:10:00")
def test_i7_teto_de_musica_so_com_relogio_e_faixa_longa_nao_registrada(
    client, account, auth_headers, com_relogio, db_session, monkeypatch
):
    from app.live.router import _historico_musicas

    radialista, programa, _ = com_relogio
    _prompts(monkeypatch, "Você está na rádio, a tarde segue.")
    chamadas = []

    def selecionar(db, prog, rotulo=None, **kwargs):
        chamadas.append(kwargs)
        return MusicaEncontrada(video_id=f"longa{len(chamadas)}", titulo=f"Longa {len(chamadas)}", canal="Banda",
                                duracao_segundos=900), "q"

    monkeypatch.setattr("app.live.router._selecionar_musica_para_bloco", selecionar)
    _marcar(programa, "0:0:fala:abertura", "0:720")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:20:00-03:00")
    assert len(chamadas) == 3 and all(c["duracao_max_s"] == 243 for c in chamadas)
    assert chamadas[-1]["evitar_ids"] == {"longa1", "longa2", "longa3"}  # a rejeitada não volta
    assert _historico_musicas(programa.id)[0] == set()
    assert dados["video_id"] is None and dados["relogio"]["acao"] == "reserva"

    espiao = []
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco",
                        lambda db, prog, tipo=None, **kw: espiao.append(kw) or None)
    programa.relogio_hora = None
    programa.estrutura_blocos = ["musica"]
    db_session.commit()
    _post(client, account, auth_headers, radialista, programa)
    assert espiao == [{}]


@freeze_time("2026-11-10 15:24:00")
def test_i8_intervalo_toca_os_patrocinadores_e_segue(client, account, auth_headers, com_relogio, monkeypatch):
    radialista, programa, patrocinadores = com_relogio
    _prompts(monkeypatch, "E voltamos com você, mande sua mensagem.")
    tipos = []
    for previsto in ("12:24:00", "12:24:30", "12:24:50"):
        dados = _post(client, account, auth_headers, radialista, programa,
                      inicio_previsto=f"2026-11-10T{previsto}-03:00")
        tipos.append((dados["tipo"], dados.get("patrocinador_id"), dados["relogio"]["etapa"]["tipo"]))
    assert tipos == [("patrocinador", patrocinadores[0].id, "intervalo"),
                     ("patrocinador", patrocinadores[1].id, "intervalo"),
                     ("chamada_ouvinte", None, "retorno")]


@freeze_time("2026-11-10 15:00:00")
def test_i9_vinheta_de_abertura_e_depois_abertura_primeira(
    client, account, auth_headers, com_relogio, db_session, monkeypatch
):
    from app.live.router import _fio_condutor

    radialista, programa, _ = com_relogio
    programa.horario_fim = datetime.time(14, 0)
    vinheta = BibliotecaAudioItem(account_id=account.id, nome="Abertura", programa_id=programa.id, papel="abertura",
                                  texto="Rádio Teste.", audio_path="v/a.mp3", duracao_segundos=8, ativo=True)
    db_session.add(vinheta)
    db_session.commit()
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "será que hoje chove?")
    prompts = _prompts(monkeypatch, "Boa tarde! Será que hoje chove? Fica com a gente.")
    primeira = _post(client, account, auth_headers, radialista, programa, total_falas=0, historico=[],
                     inicio_previsto="2026-11-10T12:00:00-03:00")
    assert (primeira["tipo"], primeira["vinheta_id"], primeira["duracao_prevista_s"]) == ("vinheta", vinheta.id, 8)
    abertura = _post(client, account, auth_headers, radialista, programa, total_falas=1, historico=["vinheta: Rádio"],
                     inicio_previsto="2026-11-10T12:00:08-03:00")
    assert (abertura["tipo"], abertura["duracao_alvo_segundos"]) == ("abertura", [20, 32])
    assert "pequena pergunta ou expectativa" in prompts[0]
    assert _fio_condutor(programa.id) == "será que hoje chove?"
    with freeze_time("2026-11-10 16:00:00"):
        retomada = _post(client, account, auth_headers, radialista, programa,
                         inicio_previsto="2026-11-10T13:00:01-03:00")
    assert (retomada["tipo"], retomada["relogio"]["hora"]) == ("retomada", 1)


@freeze_time("2026-11-10 15:12:00")
def test_i12_horario_alem_de_30_min_e_ignorado(client, account, auth_headers, com_relogio, monkeypatch):
    radialista, programa, _ = com_relogio
    _prompts(monkeypatch, "Seguimos juntos.")
    _marcar(programa, "0:0:fala:abertura")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-11-10T12:43:00-03:00")
    assert dados["relogio"]["inicio_previsto_aceito"] is False
    assert dados["relogio"]["inicio_previsto"].startswith("2026-11-10T15:12:00")
    assert dados["relogio"]["etapa"]["tipo"] == "link"


@freeze_time(AGORA_UTC)
def test_i13_i14_duracao_prevista_em_todos_e_relogio_invalido_cai_no_caminho_atual(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["comentario"]
    programa.ia_pode_adicionar_blocos = False
    programa.relogio_hora = {"versao": 1, "eventos": [{"inicio_s": 0, "duracao_s": 10, "tipo": "musica",
                                                       "natureza": "ajustavel"}]}
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    _prompts(monkeypatch, "Uma duas três quatro cinco seis sete oito nove dez onze doze treze catorze quinze.")
    dados = _post(client, account, auth_headers, radialista, programa, inicio_previsto="2026-08-10T12:05:00-03:00")
    assert dados["tipo"] == "comentario" and dados["relogio"] is None
    assert dados["duracao_prevista_s"] == round(15 / _wpm_da_voz() * 60, 2)


def test_i16_prompt_mostra_a_hora_prevista(account, radialista_e_programa, monkeypatch):
    from app.llm.prompt_builder import montar_system_prompt

    radialista, programa = radialista_e_programa
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda *_: None)
    previsto = datetime.datetime(2026, 11, 10, 16, 45, tzinfo=datetime.timezone.utc)
    with freeze_time("2026-11-10 16:20:00"):
        assert "13:45" in montar_system_prompt(account, radialista, programa, agora=previsto)
        assert "13:20" in montar_system_prompt(account, radialista, programa)
