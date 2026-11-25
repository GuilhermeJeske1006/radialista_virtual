"""Encerramento pontual: reta final, zona de fechamento sem relógio, última música e encerramento elástico.

Desenho em docs/melhoria-radio/encerramento/auditoria.md. Os testes puros usam instante explícito; os de integração
passam pelo POST /proxima real com o horário congelado.
"""

import ast
import datetime
import pathlib
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.live import fechamento as f
from app.live import relogio as r
from app.live.formatos import resolver_formato
from app.live.music import MusicaEncontrada
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

SP = ZoneInfo("America/Sao_Paulo")
PADRAO = resolver_formato("padrao")
POPULAR = resolver_formato("popular_sertanejo")
MUSICAL = resolver_formato("musical_adulto")
SEM_PECAS = r.PecasDisponiveis()


def _programa(inicio=(14, 0), fim=(15, 0), **extra):
    campos = dict(id=1, nome="Tarde Viva", horario_inicio=datetime.time(*inicio), horario_fim=datetime.time(*fim),
                  dias_semana=[], data_especifica=None, feriados_municipais=[], relogio_hora=None, ativo=True)
    campos.update(extra)
    return SimpleNamespace(**campos)


def _em(dia, hora, minuto, segundo=0):
    return datetime.datetime(2026, 11, dia, hora, minuto, segundo, tzinfo=SP)


def _categoria(tipo):
    return r._categoria_simples(tipo)


def _fechar(programa, instante, tipo="comentario", formato=PADRAO, *, pecas=SEM_PECAS, executadas=(),
            ja_encerrou=False, chamado=None):
    def tipo_roteiro():
        if chamado is not None:
            chamado.append(tipo)
        return tipo
    return r.planejar_fechamento(programa, "America/Sao_Paulo", instante, tipo_roteiro=tipo_roteiro,
                                 categoria_de=_categoria, formato=formato, ultima_categoria="musica",
                                 ja_encerrou=ja_encerrou, executadas=set(executadas), pecas=pecas)


def test_modulo_fechamento_nao_importa_o_router():
    arvore = ast.parse((pathlib.Path(__file__).resolve().parents[1] / "app" / "live" / "fechamento.py").read_text())
    modulos = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom) and no.module}
    assert not any(m.startswith("app.live.router") for m in modulos)


# --- Zona de fechamento sem relógio (relogio.planejar_fechamento) ----------------------------------------

def test_fora_da_zona_nada_muda_e_o_roteiro_nem_e_sorteado():
    chamado = []
    assert _fechar(_programa(), _em(10, 14, 49, 59), chamado=chamado) is None
    assert chamado == []
    assert _fechar(_programa(), _em(10, 14, 52), ja_encerrou=True) is None
    assert _fechar(_programa(), _em(10, 13, 55)) is None   # antes do programa


def test_fala_na_zona_deixa_espaco_para_uma_musica():
    plano = _fechar(_programa(), _em(10, 14, 52))
    assert plano.fechamento_sem_relogio
    assert plano.tipo_bloco == "comentario"
    assert plano.etapa.evento.rotulo == "Reta final"
    assert plano.proximo_compromisso.tipo_efetivo == "encerramento"
    # 8 min até o fim, 7:15 até o encerramento: link de 10 a 35 s, sobra mais que uma música.
    assert plano.orcamento_s == (10, 35)
    assert plano.espaco_s - plano.orcamento_s[1] >= r.CONFIG_PADRAO.musica_duracao_min_s


def test_fala_sem_espaco_para_musica_depois_vira_janela_de_musica():
    # 14:56: 3:15 até o encerramento, menos que mínimo da fala + uma música.
    plano = _fechar(_programa(), _em(10, 14, 56))
    assert plano.acao == "musica"
    # O padrão apresenta a faixa: o teto desconta o máximo da fala do bloco de música (4 a 20 s).
    assert plano.orcamento_s == (4, 20) and not plano.musica_sem_fala
    assert plano.duracao_max_musica_s == 195 + r.CONFIG_PADRAO.folga_teto_s - 20
    assert plano.espaco_s == 195 - 20
    assert plano.sobra_proibida_s == (105, 200)
    assert plano.alternativa is not None and plano.alternativa.fechamento_sem_relogio


def test_musica_na_zona_mantem_a_fala_do_formato_que_apresenta_a_faixa():
    # 14:54: 5:15 (315 s) até o encerramento.
    popular = _fechar(_programa(), _em(10, 14, 54), tipo="musica", formato=POPULAR)
    assert popular.acao == "musica" and popular.musica_sem_fala is False
    assert popular.orcamento_s == (8, 25)
    assert popular.espaco_s == 315 - 25
    assert popular.duracao_max_musica_s == 315 + r.CONFIG_PADRAO.folga_teto_s - 25
    musical = _fechar(_programa(), _em(10, 14, 54), tipo="musica", formato=MUSICAL)
    assert musical.musica_sem_fala is True and musical.espaco_s == 315


def test_peca_do_roteiro_segue_com_folga_e_cede_lugar_perto_do_fim():
    assert _fechar(_programa(), _em(10, 14, 51), tipo="vinheta:3") is None
    perto = _fechar(_programa(), _em(10, 14, 56), tipo="patrocinador:4")
    assert perto is not None and perto.acao in ("musica", "reserva")


def test_sem_nada_que_caiba_reserva_e_depois_encerramento():
    plano = _fechar(_programa(), _em(10, 14, 58))
    assert (plano.acao, plano.tipo_bloco) == ("reserva", "identificacao")
    depois = _fechar(_programa(), _em(10, 14, 58, 15), executadas=(plano.chave_estado,))
    assert (depois.acao, depois.tipo_bloco) == ("reserva", "comentario")   # link de preenchimento (padrão)
    no_fim = _fechar(_programa(), _em(10, 14, 59, 20))
    assert no_fim.acao == "encerramento" and no_fim.fechamento_sem_relogio


def test_encerramento_elastico_ocupa_o_espaco_ate_o_fim():
    com_vinheta = r.PecasDisponiveis(vinheta_encerramento_s=9.0)
    plano = _fechar(_programa(), _em(10, 14, 59, 15), formato=MUSICAL, pecas=com_vinheta)
    assert plano.orcamento_s == (26, 36)        # 45 s − 9 s da vinheta; acima dos 10 a 18 s do musical
    adiantado = _fechar(_programa(), _em(10, 14, 58, 30), formato=MUSICAL, pecas=com_vinheta,
                        executadas=("0:3000:reserva",))   # etapa de música da zona começa às 14:50
    assert adiantado.acao == "encerramento"
    assert adiantado.orcamento_s == (50, 60)    # teto do encerramento elástico (encerramento_max_s)


def test_coerencia_aceita_o_encerramento_estendido_pelo_relogio():
    from app.live.formatos import FalaNoAr, avisos_da_fala

    def fora(duracao, teto):
        fala = FalaNoAr(bloco="encerramento", categoria="encerramento", texto="Obrigado.", duracao_s=duracao,
                        teto_s=teto)
        return [a.codigo for a in avisos_da_fala(MUSICAL, fala)] == ["fora_da_unidade"]

    assert fora(40, None)            # sem relógio: 40 s passa dos 10 a 18 s do musical
    assert not fora(40, 45)          # o relógio estendeu até 45 s
    assert fora(60, 45)              # passou do teto estendido (com a tolerância da unidade)
    assert fora(5, 45)               # abaixo do mínimo continua fora


def test_zona_limitada_a_metade_de_programa_curto():
    curto = _programa(inicio=(14, 0), fim=(14, 10))
    assert _fechar(curto, _em(10, 14, 4)) is None
    assert _fechar(curto, _em(10, 14, 6)) is not None
    ocorrencia = r.ocorrencia_em(_programa(), "America/Sao_Paulo", _em(10, 14, 30))
    assert (r.zona_fechamento_s(ocorrencia), r.reta_final_s(ocorrencia)) == (600, 900)
    meia_hora = r.ocorrencia_em(_programa(fim=(14, 30)), "America/Sao_Paulo", _em(10, 14, 10))
    assert (r.zona_fechamento_s(meia_hora), r.reta_final_s(meia_hora)) == (600, 600)


# --- Última música (relogio.marcar_ultima_musica) ---------------------------------------------------------

def test_ultima_musica_so_quando_nenhuma_outra_cabe_depois():
    plano = _fechar(_programa(), _em(10, 14, 54), tipo="musica", formato=MUSICAL)   # 315 s até o encerramento
    assert plano.sobra_proibida_s == (45, 200)
    assert r.marcar_ultima_musica(plano, plano.espaco_s - 15, MUSICAL).ultima_musica   # o encerramento absorve
    assert r.marcar_ultima_musica(plano, plano.espaco_s - 45, MUSICAL).ultima_musica
    assert not r.marcar_ultima_musica(plano, plano.espaco_s - 105, MUSICAL).ultima_musica   # cabe outra busca
    fala = _fechar(_programa(), _em(10, 14, 52))
    assert r.marcar_ultima_musica(fala, 240, PADRAO) is fala                  # bloco de fala: nada muda


def test_ultima_musica_no_relogio_libera_fala_curta_que_cabe_na_sobra():
    programa = _programa()
    relogio = r.PRESETS["A"]
    plano = r.planejar(programa, relogio, "America/Sao_Paulo", _em(10, 14, 55), formato=POPULAR,
                       ultima_categoria="musica", ja_encerrou=False,
                       executadas={"0:0:fala:abertura", "0:3180:patrocinador:5"},
                       pecas=r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),)))
    assert plano.acao == "musica" and plano.musica_sem_fala
    sobra = 12
    marcado = r.marcar_ultima_musica(plano, plano.espaco_s - sobra, POPULAR)
    assert marcado.ultima_musica and marcado.musica_sem_fala is False
    assert marcado.orcamento_s == (8, sobra + r.CONFIG_PADRAO.folga_teto_s)
    # Sobra menor que o mínimo da fala: continua só música, mas marcada como última.
    curta = r.marcar_ultima_musica(plano, plano.espaco_s - 2, POPULAR)
    assert curta.ultima_musica and curta.musica_sem_fala


# --- Reta final, volta e programa seguinte (app.live.fechamento) ------------------------------------------

def test_fase_do_bloco_reta_final_e_zona():
    programa = _programa()
    ocorrencia = r.ocorrencia_em(programa, "America/Sao_Paulo", _em(10, 14, 30))
    assert f.fase_do_bloco(ocorrencia, _em(10, 14, 44), []) is None
    reta = f.fase_do_bloco(ocorrencia, _em(10, 14, 46), ["comentario: tudo bem por aqui"])
    assert (reta.zona, reta.avisada, round(reta.segundos_para_fim)) == (False, False, 840)
    zona = f.fase_do_bloco(ocorrencia, _em(10, 14, 51), ["retomada: Reta final do Tarde Viva, fica com a gente"],
                           ultima_musica=True)
    assert (zona.zona, zona.avisada, zona.ultima_musica) == (True, True, True)


@pytest.mark.parametrize("linha, avisada", [
    ("retomada: Estamos nos últimos minutos do programa", True),
    ("comentario: E já estamos chegando ao fim da tarde de hoje", True),
    ("musica: Pra fechar, uma da Banda Horizonte", False),
    ("comentario: O final de semana promete", False),
])
def test_reta_final_avisada(linha, avisada):
    assert f.reta_final_avisada([linha]) is avisada


@pytest.mark.parametrize("hora, texto", [
    ((15, 0), "às quinze horas"), ((1, 0), "à uma hora"), ((12, 0), "ao meio-dia"), ((0, 0), "à meia-noite"),
    ((9, 30), "às nove e trinta"), ((22, 5), "às vinte e duas e cinco"),
])
def test_hora_por_extenso(hora, texto):
    assert f.hora_por_extenso(datetime.time(*hora)) == texto


def test_descrever_volta_pela_grade():
    terca = datetime.date(2026, 11, 10)
    assert f.descrever_volta(_programa(), terca, terca) == "amanhã, às catorze horas"
    assert f.descrever_volta(_programa(dias_semana=[0]), terca, terca) == "na segunda-feira, às catorze horas"
    assert f.descrever_volta(_programa(dias_semana=[1]), terca, terca) == "na próxima terça-feira, às catorze horas"
    assert f.descrever_volta(_programa(dias_semana=[5]), terca, terca) == "no sábado, às catorze horas"
    assert f.descrever_volta(_programa(data_especifica=terca), terca, terca) is None
    # Madrugada (22h às 6h): a ocorrência começou ontem e termina hoje; volta hoje à noite.
    assert f.descrever_volta(_programa(inicio=(22, 0), fim=(6, 0)), datetime.date(2026, 11, 9), terca) \
        == "hoje, às vinte e duas horas"


def test_programa_seguinte_na_grade():
    atual = _programa()
    fim = _em(10, 15, 0)
    grade = [atual, _programa(id=2, nome="Noite Sertaneja", inicio=(15, 0), fim=(17, 0)),
             _programa(id=3, nome="Fora de Hora", inicio=(15, 10), fim=(16, 0))]
    assert f.programa_seguinte(grade, atual, fim, "America/Sao_Paulo") == "Noite Sertaneja"
    grade[1].ativo = False
    assert f.programa_seguinte(grade, atual, fim, "America/Sao_Paulo") is None
    so_segunda = [_programa(id=4, nome="Segunda Viva", inicio=(15, 0), fim=(16, 0), dias_semana=[0])]
    assert f.programa_seguinte(so_segunda, atual, fim, "America/Sao_Paulo") is None   # 10/11 é terça


# --- Integração: POST /proxima e prompt ---------------------------------------------------------------------

@pytest.fixture()
def sem_relogio(db_session, account, monkeypatch):
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=[])
    db_session.add(programa)
    db_session.commit()
    sistemas = []
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda system, mensagem: sistemas.append(system) or "Seguimos juntos nesta tarde.")
    monkeypatch.setattr("app.live.router.buscar_musica", lambda q, **k: MusicaEncontrada(
        video_id="v1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200))
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *a: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    return radialista, programa, sistemas


def _proxima(client, account, auth_headers, radialista, programa, **corpo):
    resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima",
                           json={"incluir_audio": False, **corpo}, headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@freeze_time("2026-08-10 16:57:00")   # 13:57 local; o programa acaba às 14:00
def test_sem_relogio_encerramento_pelo_horario_previsto(client, account, auth_headers, sem_relogio):
    radialista, programa, _ = sem_relogio
    dados = _proxima(client, account, auth_headers, radialista, programa, total_falas=5,
                     historico=["comentario: oi"], inicio_previsto="2026-08-10T13:59:20-03:00")
    assert dados["tipo"] == "encerramento"
    assert dados["relogio"]["acao"] == "encerramento"
    assert dados["relogio"]["preset"] is None
    assert dados["duracao_alvo_segundos"] == [30, 40]     # 40 s até o fim, elástico


@freeze_time("2026-08-10 16:40:00")   # 13:40 local: longe da zona
def test_sem_relogio_longe_do_fim_nao_ganha_plano(client, account, auth_headers, sem_relogio):
    radialista, programa, sistemas = sem_relogio
    dados = _proxima(client, account, auth_headers, radialista, programa, total_falas=1,
                     historico=["comentario: oi"], inicio_previsto="2026-08-10T13:42:00-03:00")
    assert dados.get("relogio") is None
    assert sistemas and all("RETA FINAL: faltam" not in s for s in sistemas)


@freeze_time("2026-08-10 16:48:00")   # 13:48 local, bloco vai ao ar 13:49: reta final, ainda fora da zona
def test_prompt_da_reta_final_avisa_uma_vez(client, account, auth_headers, sem_relogio):
    radialista, programa, sistemas = sem_relogio
    programa.estrutura_blocos = ["comentario"]
    _proxima(client, account, auth_headers, radialista, programa, total_falas=4,
             historico=["comentario: oi"], inicio_previsto="2026-08-10T13:49:00-03:00")
    assert "RETA FINAL: faltam cerca de onze minutos para o fim do Tarde Viva" in sistemas[-1]
    assert "avise uma única vez" in sistemas[-1]
    assert "não diga que vai ler, responder ou tocar ainda neste programa" in sistemas[-1]
    _proxima(client, account, auth_headers, radialista, programa, total_falas=5,
             historico=["comentario: oi", "comentario: Reta final do Tarde Viva, fica com a gente"],
             inicio_previsto="2026-08-10T13:49:30-03:00")
    assert "não repita esse aviso" in sistemas[-1]


@freeze_time("2026-08-10 16:58:30")   # 13:58:30 local
def test_prompt_do_encerramento_com_volta_e_programa_seguinte(client, account, auth_headers, sem_relogio,
                                                               db_session):
    radialista, programa, sistemas = sem_relogio
    db_session.add(Programa(radio_config_id=radialista.id, nome="Noite Sertaneja",
                            horario_inicio=datetime.time(14, 0), horario_fim=datetime.time(16, 0),
                            estrutura_blocos=[]))
    db_session.commit()
    dados = _proxima(client, account, auth_headers, radialista, programa, total_falas=8,
                     historico=["musica: [Música(s) tocada(s) nesse bloco: Estrada Aberta - Banda Horizonte]"],
                     inicio_previsto="2026-08-10T13:59:20-03:00")
    assert dados["tipo"] == "encerramento"
    system = sistemas[-1]
    assert "O Tarde Viva volta amanhã, às dez horas" in system
    assert "a programação da rádio segue com Noite Sertaneja" in system
    assert "A música que acabou de tocar fechou o programa" in system
    # 40 s até o fim, elástico (30 a 40 s): faixa de palavras pelo ritmo da voz.
    assert "A despedida ocupa o tempo que falta até o fim do programa: escreva entre" in system


@freeze_time("2026-08-10 16:57:00")   # 13:57 local
def test_zona_sem_pergunta_nem_formato_de_comentario_e_link_que_retoma_o_programa(
    client, account, auth_headers, sem_relogio, monkeypatch
):
    radialista, programa, sistemas = sem_relogio
    programa.estrutura_blocos = ["comentario"]
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)
    convite = "Para este comentário, convide o ouvinte a responder pelo WhatsApp da rádio o que ele acha sobre o assunto."
    monkeypatch.setattr("app.live.router._proxima_variacao",
                        lambda programa_id, chave, opcoes: convite if chave == "formato_comentario" else opcoes[0])
    # 13:58:15 no ar: 60 s até o encerramento, nada cabe; a reserva (identificação) já foi.
    from app.config.redis_client import redis_client
    from app.live import relogio as rl
    ocorrencia = rl.ocorrencia_em(programa, "America/Sao_Paulo", datetime.datetime(2026, 8, 10, 16, 58, 15,
                                                                                    tzinfo=datetime.timezone.utc))
    rl.marcar_executada(programa.id, ocorrencia, "3:3000:reserva")
    dados = _proxima(client, account, auth_headers, radialista, programa, total_falas=9,
                     historico=["abertura: Tarde Viva, na rádio"], inicio_previsto="2026-08-10T13:58:15-03:00")
    redis_client.flushall()
    assert (dados["tipo"], dados["relogio"]["acao"]) == ("comentario", "reserva")
    system = sistemas[-1]
    assert convite not in system
    assert "não faça pergunta ao ouvinte nem convide a mandar pedido ou mensagem" in system
    assert "Esta é a última fala antes da despedida: não abra assunto novo" in system
