"""Validador pós-geração pela rota POST /proxima (F3, I1, I2, I5 e o fragmento da auditoria §6).

Mesmo padrão de tests/test_live_router_duracao.py: freeze_time, fakeredis do conftest e dublês por nome em
app.live.router.
"""

import datetime
import io

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 em São Paulo, dentro de um programa 10:00-14:00
FAIXA = MusicaEncontrada(video_id="f1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200)


def _mp3(segundos: float) -> bytes:
    from pydub import AudioSegment

    buffer = io.BytesIO()
    AudioSegment.silent(duration=int(segundos * 1000)).export(buffer, format="mp3")
    return buffer.getvalue()


@pytest.fixture()
def programa(db_session, account, monkeypatch):
    account.nome_radio = "Rádio Teste"
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=[], ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    monkeypatch.setattr("app.live.router.buscar_musica", lambda query, **kw: FAIXA)
    return radialista, programa


def _gerador(prompts: list, *respostas: str):
    def gerar(system, mensagem):
        prompts.append(system)
        return respostas[min(len(prompts), len(respostas)) - 1]
    return gerar


def _post(client, account, auth_headers, radialista, programa, **corpo):
    corpo.setdefault("incluir_audio", False)
    resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima", json=corpo,
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@freeze_time(AGORA_UTC)
def test_i1_musical_anuncia_outra_faixa_reescreve_e_depois_remove(client, account, auth_headers, programa,
                                                                   db_session, monkeypatch):
    radialista, prog = programa
    prog.perfil_programacao = "musical_companhia"
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Joana", tipo="musica",
                              mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta"))
    db_session.commit()
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(
        prompts, "A Joana pediu, e toca agora Varanda de Pedra, com Trio Ventania.",
        "A Joana pediu, e agora vem Varanda de Pedra."))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["retomada: oi"])
    assert len(prompts) == 2
    assert "Você citou 'Varanda de Pedra', que não vai tocar. A única faixa confirmada é 'Estrada Aberta' de " \
           "'Banda Horizonte'; não cite outra." in prompts[1]
    # Sem a oração da faixa errada sobra "A Joana pediu.", um fragmento abaixo do mínimo: entra a reorientação
    # neutra e a faixa do pedido toca em seguida.
    assert dados["fala"] == "Você está no Tarde Viva, na Rádio Teste."
    assert dados["video_id"] == "f1"
    assert dados["validacao_fala"]["acao"] == "fala_neutra"
    assert [v["regra"] for v in dados["validacao_fala"]["violacoes"]] == \
        ["musica_nao_confirmada", "musica_nao_confirmada", "fala_abaixo_do_minimo"]


@freeze_time(AGORA_UTC)
def test_i1_reescrita_que_corrige_fica_registrada(client, account, auth_headers, programa, db_session,
                                                  monkeypatch):
    radialista, prog = programa
    prog.perfil_programacao = "musical_companhia"
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Joana", tipo="musica",
                              mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta"))
    db_session.commit()
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(
        prompts, "A Joana pediu, e toca agora Varanda de Pedra.", "A Joana pediu Estrada Aberta, com Banda Horizonte."))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["retomada: oi"])
    assert len(prompts) == 2
    assert dados["fala"] == "A Joana pediu Estrada Aberta, com Banda Horizonte."
    assert dados["validacao_fala"]["acao"] == "reescrita"


@freeze_time(AGORA_UTC)
def test_modo_avisar_so_registra(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.perfil_programacao = "musical_companhia"
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Joana", tipo="musica",
                              mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta"))
    db_session.commit()
    monkeypatch.setattr("app.live.router.settings.validacao_musica_modo", "avisar")
    prompts: list[str] = []
    fala = "A Joana pediu, e toca agora Varanda de Pedra."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, fala))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["retomada: oi"])
    assert len(prompts) == 1
    assert dados["fala"] == fala
    assert dados["validacao_fala"]["acao"] == "nenhuma"
    assert dados["validacao_fala"]["violacoes"][0]["ref_id"] == "Varanda de Pedra"


@freeze_time(AGORA_UTC)
def test_i2_comentario_que_cita_musica_inexistente_vira_reserva(client, account, auth_headers, programa,
                                                                 db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    db_session.commit()
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Lembrei de Musica Inexistente.")
    monkeypatch.setattr("app.live.router.extrair_musicas_citadas",
                        lambda fala, ja_tocadas=None: ["Musica Inexistente"])
    monkeypatch.setattr("app.live.router.buscar_musica", lambda query, **kw: None)
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert dados["musicas"] == [] and dados["video_id"] is None
    assert dados["fala"] == "Você está no Tarde Viva, na Rádio Teste."
    assert dados["validacao_fala"]["acao"] == "fala_neutra"
    assert dados["validacao_fala"]["violacoes"][0]["ref_id"] == "Musica Inexistente"


@freeze_time(AGORA_UTC)
def test_i4_citada_que_toca_nao_e_violacao(client, account, auth_headers, programa, monkeypatch):
    radialista, prog = programa
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda system, msg: "Agora vem Estrada Aberta, com Banda Horizonte, e depois Outra Citada.")
    monkeypatch.setattr("app.live.router.buscar_musica", lambda query, **kw: MusicaEncontrada(
        video_id="c1", titulo="Outra Citada", canal="Banda Y") if "Outra Citada" in query else FAIXA)
    monkeypatch.setattr("app.live.router.extrair_musicas_citadas",
                        lambda fala, ja_tocadas=None: ["Banda Y - Outra Citada"])
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", lambda *a, **k: None)
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["abertura: oi"])
    assert [m["video_id"] for m in dados["musicas"]] == ["f1", "c1"]
    assert dados["validacao_fala"] is None
    assert dados["fala"].endswith("e depois Outra Citada.")


@freeze_time(AGORA_UTC)
def test_i5_musica_duracao_e_repeticao_juntas_ainda_no_maximo_dois_llm_e_duas_sinteses(
    client, account, auth_headers, programa, db_session, monkeypatch
):
    from app.live.router import _registrar_fala_gerada

    radialista, prog = programa
    prog.perfil_programacao = "musical_companhia"
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Joana", tipo="musica",
                              mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta"))
    db_session.commit()
    longa = ("A Joana pediu e toca agora Varanda de Pedra, com Trio Ventania, numa tarde bonita de sol. "
             "Que alegria receber o recado dela aqui na rádio, que bom ter você por perto nesta hora.")
    _registrar_fala_gerada(prog.id, "musica", longa)
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, longa))
    sinteses: list[str] = []
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio",
                        lambda texto, *a, **k: sinteses.append(texto) or _mp3(25.0))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["retomada: oi"],
                  incluir_audio=True)
    assert len(prompts) == 2
    revisao = prompts[1]
    assert "ficou muito parecida" in revisao and "Reescreva com no máximo" in revisao \
        and "Você citou 'Varanda de Pedra'" in revisao
    assert len(sinteses) <= 2
    assert "Varanda de Pedra" not in dados["fala"]


@freeze_time(AGORA_UTC)
def test_fragmento_do_encurtamento_pelo_audio_nao_vai_ao_ar(client, account, auth_headers, programa, db_session,
                                                            monkeypatch):
    """Achado do juiz da F2: o momento C deixou "Rádio." (0,4 s). Agora vira a reorientação neutra."""
    radialista, prog = programa
    prog.perfil_programacao = "musical_companhia"
    db_session.commit()
    fala = "Rádio. Você está com a gente nesta tarde de muita música boa e companhia para o seu dia inteiro."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    sinteses: list[str] = []
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    duracoes = iter([40.0, 3.0])
    monkeypatch.setattr("app.live.router.sintetizar_audio",
                        lambda texto, *a, **k: sinteses.append(texto) or _mp3(next(duracoes)))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=6, historico=["musica: anterior"],
                  incluir_audio=True)
    # A reorientação mais longa que cabe no máximo (12 s) no ritmo medido do próprio áudio.
    assert sinteses == [fala, "Você está na Rádio Teste."]
    assert dados["fala"] == "Você está na Rádio Teste."
    assert dados["audio_status"] == "pronto"
    assert dados["validacao_fala"] == {"acao": "fala_neutra", "violacoes": [
        {"regra": "fala_abaixo_do_minimo", "trecho": "Rádio.", "ref_id": ""}]}


@freeze_time(AGORA_UTC)
def test_campos_atuais_iguais_e_validacao_opcional(client, account, auth_headers, programa, monkeypatch):
    """I9: sem violação, a resposta não ganha nada além do campo nulo."""
    radialista, prog = programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: "Agora vem Estrada Aberta, com Banda Horizonte.")
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["abertura: oi"])
    assert dados["validacao_fala"] is None
    assert dados["fala"] == "Agora vem Estrada Aberta, com Banda Horizonte."


_LEMBRANCA = ("Essa lembrança me leva para as tardes de domingo na casa da minha avó, com café passado na hora "
              "e o rádio ligado na cozinha. Fica com a gente.")


@freeze_time("2026-11-10 15:12:20")
def test_i3_citada_descartada_pelo_relogio_nao_fica_registrada_e_sai_da_fala(client, account, auth_headers,
                                                                             programa, db_session, monkeypatch):
    from app.config.redis_client import redis_client
    from app.live import relogio as r
    from app.models.musica_historico import MusicaHistorico
    from app.models.patrocinador import Patrocinador

    radialista, prog = programa
    patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                   tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                      for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
    db_session.add_all(patrocinadores)
    db_session.flush()
    prog.horario_inicio, prog.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
    prog.estrutura_blocos = ["comentario", *[f"patrocinador:{p.id}" for p in patrocinadores]]
    prog.relogio_hora = r.PRESETS["A"].model_dump()
    db_session.commit()
    instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    r.marcar_executada(prog.id, r.ocorrencia_em(prog, radialista.timezone, instante), "0:0:fala:abertura", "0:40")

    faixas = {"Estrada Aberta": MusicaEncontrada(video_id="e1", titulo="Estrada Aberta", canal="Banda A",
                                                 duracao_segundos=400),
              "Moinho Grande": MusicaEncontrada(video_id="m1", titulo="Moinho Grande", canal="Banda B",
                                                duracao_segundos=400)}
    monkeypatch.setattr("app.live.router.buscar_musica",
                        lambda query, **kw: next((f for t, f in faixas.items() if t in query), None))
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", lambda *a, **k: None)
    monkeypatch.setattr("app.live.router.extrair_musicas_citadas",
                        lambda fala, ja_tocadas=None: ["Banda A - Estrada Aberta", "Banda B - Moinho Grande"])
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda *a: "Lembrei de Estrada Aberta, e também de Moinho Grande. " + _LEMBRANCA)
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=3, historico=["musica: anterior"],
                  inicio_previsto="2026-11-10T12:12:30-03:00")
    assert dados["tipo"] == "comentario" and dados["relogio"]["acao"] == "fala"
    assert [m["video_id"] for m in dados["musicas"]] == ["e1"]
    assert dados["fala"] == "Lembrei de Estrada Aberta. " + _LEMBRANCA
    assert [v["ref_id"] for v in dados["validacao_fala"]["violacoes"]] == ["Moinho Grande"]
    assert redis_client.smembers(f"musicas_tocadas:ids:{prog.id}") == {"e1"}
    assert [m.video_id for m in db_session.query(MusicaHistorico).all()] == ["e1"]
