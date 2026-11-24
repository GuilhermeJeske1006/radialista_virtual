"""Escolha de música pela duração: o relógio da hora fecha no tempo e o musical completa a sequência sem fala.

Antes, a escolha (Spotify, lista do admin, pedidos do público) não sabia a duração: o relógio só conferia depois da
busca no YouTube, em até três tentativas, e ficava com a mais longa quando nenhuma fechava o espaço (fim do musical 91 s
antes da hora na simulação). Ver docs/melhoria-radio/f6/pendencias.md, "Escolha de música pela duração".
"""
import datetime
from types import SimpleNamespace

import pytest

from app.config.redis_client import redis_client
from app.live.music import MusicaEncontrada
from app.models.musica import Musica
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


@pytest.fixture()
def programa(db_session, account):
    radio = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio)
    db_session.commit()
    programa = Programa(radio_config_id=radio.id, nome="Tarde", horario_inicio=datetime.time(10),
                        horario_fim=datetime.time(14), estrutura_blocos=[], musicas_permitidas=[],
                        generos_musicais=["Sertanejo"])
    db_session.add(programa)
    db_session.commit()
    redis_client.flushall()
    return programa


SPOTIFY = [("Duo A", "Longa"), ("Duo B", "Fecha"), ("Duo C", "Media"), ("Duo D", "Curta")]
DURACOES = {"Longa": 274, "Fecha": 360, "Media": 230, "Curta": 190}


def _spotify(monkeypatch, duracoes=DURACOES):
    escolhas = []
    monkeypatch.setattr("app.live.router.buscar_faixas_por_categoria", lambda genero, excluir_titulos=None: list(SPOTIFY))
    monkeypatch.setattr("app.live.router.duracoes_faixas", lambda faixas: [duracoes.get(t) for _, t in faixas])
    monkeypatch.setattr("app.live.router.escolher_faixa_do_programa",
                        lambda pool, contexto: escolhas.append([t for _, t in pool]) or 0)
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", lambda db, titulo, artista, **kw: MusicaEncontrada(
        video_id=titulo, titulo=titulo, canal=artista, duracao_segundos=DURACOES[titulo]))
    return escolhas


def _janela(espaco_s, sobra=(45, 200)):
    return SimpleNamespace(espaco_s=espaco_s, sobra_proibida_s=sobra, duracao_max_musica_s=int(espaco_s) + 3)


def test_relogio_escolhe_entre_as_faixas_que_fecham_o_espaco(db_session, programa, monkeypatch):
    """393 s até o encerramento: só a de 360 s fecha (sobra 33 s, dentro dos 45 s de adiantamento final). As outras
    deixam sobra que nada preenche; a escolha do LLM recebe só a que fecha."""
    from app.live.router import _selecionar_musica_que_cabe

    escolhas = _spotify(monkeypatch)
    musica, query = _selecionar_musica_que_cabe(db_session, programa, None, _janela(393))
    assert (musica.titulo, query) == ("Fecha", "Duo B - Fecha")
    assert escolhas == [["Fecha"]]


def test_sem_duracao_conhecida_a_escolha_e_a_de_antes(db_session, programa, monkeypatch):
    from app.live.router import _escolher_query_musica

    escolhas = _spotify(monkeypatch, duracoes={})
    _escolher_query_musica(db_session, programa, set(), set(), {}, custo_duracao=lambda d, outras: 0)
    assert sorted(escolhas[0]) == sorted(t for _, t in SPOTIFY)


def test_duracao_desconhecida_vem_antes_da_que_nao_fecha(db_session, programa, monkeypatch):
    """Sem nenhuma que feche, a de duração desconhecida ainda pode fechar; a que se sabe que não fecha fica por último."""
    from app.live.router import _escolher_query_musica

    escolhas = _spotify(monkeypatch, duracoes={"Longa": 274, "Media": 230, "Curta": 190})
    _escolher_query_musica(db_session, programa, set(), set(), {},
                           custo_duracao=lambda d, outras: 10)
    assert escolhas == [["Fecha"]]


@pytest.mark.parametrize("duracoes, custos, esperado", [
    # A duração não diferencia (todas as conhecidas servem): as desconhecidas seguem no sorteio, como antes.
    ([250, None, None], {250: 0}, [0, 1, 2]),
    # Fora da janela só o teto conta: a que passa do teto sai, as desconhecidas ficam.
    ([250, 400, None], {250: 0, 400: float("inf")}, [0, 2]),
    # Na janela a duração diferencia: ficam só as que fecham.
    ([250, 300, None], {250: 0, 300: 40}, [0]),
    ([250, 300, None], {250: 70, 300: 40}, [2]),
    ([250, 300], {250: 70, 300: 40}, [1]),
    ([None, None], {}, [0, 1]),
    ([500, 600], {500: float("inf"), 600: float("inf")}, [0, 1]),
])
def test_camadas_da_escolha_pela_duracao(duracoes, custos, esperado):
    from app.live.router import _melhores_pela_duracao

    assert _melhores_pela_duracao(duracoes, lambda d, outras: custos[d]) == esperado


def test_lista_do_admin_usa_a_duracao_do_catalogo(db_session, programa, monkeypatch):
    from app.live.router import _escolher_query_musica
    from app.live.song_service import buscar_ou_criar_musica

    programa.musicas_permitidas = ["Duo A - Longa", "Duo B - Fecha", "Pedido sem formato"]
    db_session.commit()
    for titulo, artista in (("Longa", "Duo A"), ("Fecha", "Duo B")):
        musica = buscar_ou_criar_musica(db_session, titulo, artista)
        musica.duracao_segundos, musica.youtube_video_id = DURACOES[titulo], f"yt-{titulo}"
    esquecida = buscar_ou_criar_musica(db_session, "Esquecida", "Duo E")
    esquecida.duracao_segundos = 360  # vídeo esquecido (esquecer_video_catalogado): a duração antiga não vale
    db_session.commit()
    from app.live.song_service import duracoes_catalogadas
    assert duracoes_catalogadas(db_session, [("Duo B", "Fecha"), ("Duo E", "Esquecida"), ("X", "Y")]) == [360, None, None]
    monkeypatch.setattr("app.live.router.duracoes_faixas", lambda faixas: [None] * len(faixas))
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", lambda *a, **kw: None)
    for _ in range(5):
        query, _, _ = _escolher_query_musica(db_session, programa, set(), set(), {},
                                             custo_duracao=lambda d, outras: 0 if d == 360 else 50)
        assert query == "Duo B - Fecha"
    assert db_session.query(Musica).count() == 3


def test_duracao_por_posicao_do_roteiro(programa):
    """Por posição, não "as últimas": bloco gerado de novo (painel cancelou o preparo) sobrescreve a mesma posição."""
    from app.live.router import _duracoes_nas_posicoes, _registrar_duracao_na_posicao

    _registrar_duracao_na_posicao(programa.id, 1, MusicaEncontrada(video_id="a", titulo="a", canal="x",
                                                                    duracao_segundos=250))
    _registrar_duracao_na_posicao(programa.id, 2, MusicaEncontrada(video_id="b", titulo="b", canal="x",
                                                                    duracao_segundos=280))
    _registrar_duracao_na_posicao(programa.id, 2, MusicaEncontrada(video_id="c", titulo="c", canal="x"))
    # Sem duração conhecida, a padrão do relógio (mesma conta do player).
    assert _duracoes_nas_posicoes(programa.id, [1, 2, 3]) == [250.0, 210.0, None]
    assert _duracoes_nas_posicoes(programa.id, []) == []


# ---------------------------------------------------------------------------------------------------------
# Musical sem relógio: a faixa que fecha a sequência completa os nove minutos sem fala
# ---------------------------------------------------------------------------------------------------------

def _entrada(programa, total_falas):
    from app.live.formatos import formato_do_programa

    return SimpleNamespace(programa=programa, total_falas=total_falas, formato=formato_do_programa(programa))


def _portas(duracoes):
    from app.live.router import _categoria_bloco

    # `duracoes`: da posição anterior para trás (a mais recente primeiro).
    def nas_posicoes(_pid, posicoes):
        return [duracoes[i] if i < len(duracoes) else None for i in range(len(posicoes))]

    return SimpleNamespace(categoria_bloco=_categoria_bloco, duracoes_nas_posicoes=nas_posicoes)


@pytest.mark.parametrize("total_falas, anteriores, esperado", [
    (2, [250], 540 - 250),  # segunda música do par (roteiro musica, musica, identificacao): completa a sequência
    (2, [560], None),       # a anterior já passou de nove minutos
    (1, [], None),          # primeira do par: a sequência continua no bloco seguinte
    (3, [250, 280], None),  # identificação: não é música
    (5, [270], 540 - 270),  # par seguinte (musica, musica, retomada)
    (2, [], None),          # posição anterior sem duração registrada: sem preferência
])
def test_falta_para_a_sequencia_musical(db_session, programa, total_falas, anteriores, esperado):
    from app.live.contexto import falta_sequencia_musical_s

    programa.perfil_programacao = "musical_companhia"
    db_session.commit()
    decisao = SimpleNamespace(plano=None, passos_roteiro=1)
    assert falta_sequencia_musical_s(_entrada(programa, total_falas), decisao, _portas(anteriores)) == esperado


def test_sequencia_musical_so_no_formato_com_minimo_e_sem_relogio(db_session, programa):
    from app.live.contexto import falta_sequencia_musical_s

    portas = _portas([250])
    assert falta_sequencia_musical_s(_entrada(programa, 2), SimpleNamespace(plano=None, passos_roteiro=1), portas) is None
    programa.perfil_programacao = "musical_companhia"
    db_session.commit()
    com_relogio = SimpleNamespace(plano=object(), passos_roteiro=1)
    assert falta_sequencia_musical_s(_entrada(programa, 2), com_relogio, portas) is None


def test_busca_sem_relogio_prefere_a_que_completa_a_sequencia(db_session, programa, monkeypatch):
    from app.live.router import _buscar_musica_para_bloco

    escolhas = _spotify(monkeypatch)
    musica = _buscar_musica_para_bloco(db_session, programa, duracao_min_s=300)
    assert musica.titulo == "Fecha" and escolhas == [["Fecha"]]
