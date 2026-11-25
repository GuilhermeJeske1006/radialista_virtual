"""Textos de prompt da F4 (§6.9 da auditoria, U13): regra de promessa, linha de agenda, música sem faixa, pedido
recente do legado e reserva do multivoz. O prompt só oferece o que está na agenda; o validador remove o resto.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig

FAIXA = MusicaEncontrada(video_id="f1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200)
REGRA = ("Não prometa conteúdo futuro ('daqui a pouco', 'depois do intervalo', 'já já', 'ainda hoje') fora da agenda "
         "informada.")


@pytest.fixture()
def programa(db_session, account, monkeypatch):
    account.nome_radio = "Rádio Teste"
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo", nome_locutor="Zé do Rádio")
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
    monkeypatch.setattr("app.live.router.extrair_musicas_citadas", lambda fala, ja_tocadas=None: [])
    return radialista, programa


def _system(client, account, auth_headers, radialista, prog, monkeypatch, resposta="Seguimos juntos nesta tarde.",
            multivoz=False, **corpo):
    prompts = []
    alvo = "app.live.router.gerar_dialogo_multivoz" if multivoz else "app.live.router.gerar_resposta"
    monkeypatch.setattr(alvo, lambda system, msg: prompts.append(system) or resposta)
    corpo.setdefault("incluir_audio", False)
    resposta_http = client.post(f"/live/{radialista.id}/programas/{prog.id}/proxima", json=corpo,
                                headers=auth_headers(account.id))
    assert resposta_http.status_code == 200, resposta_http.text
    return prompts[0] if prompts else "", resposta_http.json()


@freeze_time("2026-08-10 15:00:00")
def test_u13_regra_geral_e_agenda_sem_relogio(client, account, auth_headers, programa, monkeypatch):
    radialista, prog = programa
    system, _ = _system(client, account, auth_headers, radialista, prog, monkeypatch, total_falas=2,
                        historico=["abertura: oi"])
    assert REGRA in system
    # Roteiro padrão: a chamada de ouvinte vem adiante (posição 4).
    assert "Agenda confirmada adiante (só isto pode ser chamado como próximo): participação dos ouvintes mais " \
           "adiante neste programa." in system


@freeze_time("2026-08-10 15:00:00")
def test_u13_sem_agenda_nao_tem_linha_de_agenda(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario", "musica"]
    db_session.commit()
    system, _ = _system(client, account, auth_headers, radialista, prog, monkeypatch, total_falas=0, historico=[])
    assert REGRA in system and "Agenda confirmada adiante" not in system


def test_u13_relogio_troca_a_ultima_frase_pela_agenda(client, account, auth_headers, programa, db_session,
                                                      monkeypatch):
    from app.live import relogio as r

    radialista, prog = programa
    with freeze_time("2026-11-10 15:12:20"):
        patrocinador = Patrocinador(account_id=account.id, nome="Loja", texto="Loja, perto de você.", ativo=True,
                                    tipo_conteudo="audio", audio_path="p/l.mp3", duracao_segundos=30)
        db_session.add(patrocinador)
        db_session.flush()
        prog.horario_inicio, prog.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
        prog.estrutura_blocos = ["comentario", f"patrocinador:{patrocinador.id}"]
        prog.relogio_hora = r.PRESETS["A"].model_dump()
        db_session.commit()
        instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
        r.marcar_executada(prog.id, r.ocorrencia_em(prog, radialista.timezone, instante), "0:0:fala:abertura", "0:40")
        system, _ = _system(client, account, auth_headers, radialista, prog, monkeypatch, total_falas=3,
                            historico=["musica: oi"], inicio_previsto="2026-11-10T12:12:30-03:00")
    assert "Agenda confirmada adiante (só isto pode ser chamado como próximo): Retorno e participação em cerca de " \
           "14 minutos." in system
    assert "Não anuncie o que vem a seguir nem prometa conteúdo." not in system


@freeze_time("2026-08-10 16:59:20")  # 40 s antes do fim (14:00), já na etapa de encerramento
def test_u13_encerramento_sem_agenda_e_formato_musical_sem_retorno(client, account, auth_headers, programa,
                                                                  db_session, monkeypatch):
    radialista, prog = programa
    system, dados = _system(client, account, auth_headers, radialista, prog, monkeypatch, total_falas=9,
                            historico=["musica: oi"], resposta="Obrigado pela companhia, até amanhã.")
    assert dados["tipo"] == "encerramento" and "Agenda confirmada adiante" not in system
    prog.perfil_programacao = "musical_companhia"
    db_session.commit()
    from app.live.formato import direcao_musical

    assert "Não prometa retorno" in direcao_musical("encerramento")


@freeze_time("2026-08-10 15:00:00")
def test_u13_musica_sem_faixa_nao_chama_o_proximo_momento(client, account, auth_headers, programa, monkeypatch):
    radialista, prog = programa
    monkeypatch.setattr("app.live.router.buscar_musica", lambda query, **kw: None)
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *a, **kw: None)
    system, _ = _system(client, account, auth_headers, radialista, prog, monkeypatch, total_falas=1,
                        historico=["comentario: oi"])
    assert "chamada pro próximo momento do programa" not in system
    assert "transição curta e natural, sem prometer nada" in system


@freeze_time("2026-08-10 15:00:00")
def test_u13_pedido_recente_sem_prometer_atendimento(client, account, auth_headers, programa, db_session,
                                                     monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Rita Andrade", tipo="musica",
                              mensagem_usuario="toca Varanda Azul", musica_query="Varanda Azul",
                              criado_em=datetime.datetime.now(datetime.timezone.utc)))
    db_session.commit()
    system, _ = _system(client, account, auth_headers, radialista, prog, monkeypatch, total_falas=1,
                        historico=["musica: oi"])
    assert "Acabou de chegar uma mensagem nova no WhatsApp da rádio, de Rita Andrade" in system
    assert "vai ser atendido" not in system and "Varanda Azul" not in system
    assert "não diga que o pedido vai tocar nem quando ele vai ser lido" in system


@freeze_time("2026-08-10 15:00:00")
def test_u13_reserva_do_multivoz_e_neutra(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    convidada = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone=radialista.timezone)
    db_session.add(convidada)
    db_session.flush()
    db_session.add(ProgramaRadialista(programa_id=prog.id, radio_config_id=convidada.id, papel="Co-apresentadora"))
    db_session.commit()
    _, dados = _system(client, account, auth_headers, radialista, prog, monkeypatch, multivoz=True,
                       resposta="isto não é json", total_falas=1, historico=["musica: oi"])
    assert dados["fala"] == "Você está no Tarde Viva, na Rádio Teste."
    assert "volto" not in dados["fala"]
