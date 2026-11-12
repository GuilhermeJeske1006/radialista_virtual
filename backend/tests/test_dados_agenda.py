"""D12 da F5 (docs/melhoria-radio/f5/auditoria.md §6.10, U9): a validade da agenda vem da data do evento.

A curadoria devolve `data_evento` (ISO, ou vazio), o worker a guarda nos detalhes da notícia e a agenda com data vale
até o fim do evento (`ConfigDados.duracao_evento_padrao_s` depois da hora de início, ou o fim do dia quando só há a
data). Sem data, a janela de hoje (7 dias da publicação). Evento que já acabou não vira pauta nem dado válido.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.dados import fontes as f
from app.dados.verificavel import CONFIG_DADOS, valido_ate_da_noticia
from app.models.noticia import Noticia
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.news.curadoria import curar_item
from app.news.feeds import ItemFeed
from app.news.pauta import NoticiaPauta, proxima_noticia

TZ = "America/Sao_Paulo"
LOCAL = ZoneInfo(TZ)
UTC = datetime.timezone.utc
PUBLICADO = datetime.datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


# --- regra única ---------------------------------------------------------------------------------------

def test_agenda_com_data_vale_ate_o_fim_do_dia_do_evento():
    ate = valido_ate_da_noticia("agenda_cultura", PUBLICADO, {"data_evento": "2026-11-14"}, TZ)
    assert ate == datetime.datetime(2026, 11, 15, 0, 0, tzinfo=LOCAL)


def test_agenda_com_hora_vale_a_duracao_padrao_depois_do_inicio():
    ate = valido_ate_da_noticia("agenda_cultura", PUBLICADO, {"data_evento": "2026-11-14T19:30"}, TZ)
    assert ate == datetime.datetime(2026, 11, 14, 19, 30, tzinfo=LOCAL) + datetime.timedelta(
        seconds=CONFIG_DADOS.duracao_evento_padrao_s)


@pytest.mark.parametrize("detalhes", [{}, {"data_evento": ""}, {"data_evento": "sábado que vem"}])
def test_agenda_sem_data_valida_usa_a_janela(detalhes):
    assert valido_ate_da_noticia("agenda_cultura", PUBLICADO, detalhes, TZ) == PUBLICADO + datetime.timedelta(days=7)


def test_outra_categoria_ignora_data_evento():
    ate = valido_ate_da_noticia("transito", PUBLICADO, {"data_evento": "2026-12-01"}, TZ)
    assert ate == PUBLICADO + datetime.timedelta(hours=24)


def test_de_pauta_da_agenda_usa_a_data_do_evento_e_leva_a_data_no_dado():
    pauta = NoticiaPauta(noticia_id=3, titulo="Feira abre no sábado", resumo="", fonte_nome="Prefeitura",
                         fonte_tipo="oficial", url="x", categoria="agenda_cultura", publicado_em=PUBLICADO,
                         angulo="fato", aberturas_usadas=[], detalhes={"data_evento": "2026-11-14"})
    dado = f.de_pauta(pauta, tz=TZ)
    assert dado.valido_ate == datetime.datetime(2026, 11, 15, 0, 0, tzinfo=LOCAL)
    assert dado.detalhes["data_evento"] == "2026-11-14"


# --- curadoria e worker -----------------------------------------------------------------------------------

def _item() -> ItemFeed:
    return ItemFeed(titulo="Feira de artesanato no sábado", resumo="Das nove às dezoito horas, dia 14.",
                    url="https://x.invalid/feira", publicado_em=PUBLICADO)


@pytest.mark.parametrize("bruto,esperado", [("2026-11-14", "2026-11-14"), ("2026-11-14T09:00", "2026-11-14T09:00"),
                                            ("sábado", ""), ("", ""), (None, "")])
def test_curadoria_devolve_data_evento_iso_ou_vazio(monkeypatch, bruto, esperado):
    resposta = '{"bloqueada": false, "categoria": "agenda_cultura", "score": 70, "data_evento": %s}' % (
        "null" if bruto is None else f'"{bruto}"')
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", lambda system, msg, **_: resposta)
    resultado = curar_item(_item(), fonte_nome="Prefeitura", fonte_tipo="oficial", cidade="X")
    assert resultado.data_evento == esperado


def test_prompt_da_curadoria_pede_a_data_do_evento():
    from app.news.curadoria import _SYSTEM_PROMPT

    assert '"data_evento"' in _SYSTEM_PROMPT


def test_worker_guarda_data_evento_nos_detalhes(db_session, account, monkeypatch):
    from app.models.fonte_noticia import FonteNoticia
    from app.news.curadoria import ResultadoCuradoria
    from app.news.worker import coletar_fonte

    fonte = FonteNoticia(account_id=account.id, nome="Prefeitura", tipo="oficial", url_feed="https://x.invalid/rss",
                         ativa=True)
    db_session.add(fonte)
    db_session.commit()
    monkeypatch.setattr("app.news.worker.ler_feed", lambda f: [_item()])
    monkeypatch.setattr("app.news.worker.curar_item", lambda *a, **k: ResultadoCuradoria(
        categoria="agenda_cultura", score=70, data_evento="2026-11-14"))
    coletar_fonte(db_session, account, fonte)
    assert db_session.query(Noticia).one().detalhes["data_evento"] == "2026-11-14"


# --- pauta -----------------------------------------------------------------------------------------------

@pytest.fixture()
def programa(db_session, account):
    radialista = RadioConfig(account_id=account.id, timezone=TZ)
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0))
    db_session.add(programa)
    db_session.commit()
    return programa


def _agenda(db_session, account, data_evento: str | None, url: str) -> Noticia:
    noticia = Noticia(account_id=account.id, fonte_nome="Prefeitura", fonte_tipo="oficial", titulo=f"Evento {url}",
                      resumo="", url=url, url_hash=url, publicado_em=PUBLICADO, categoria="agenda_cultura",
                      cidade="X", score=70.0, ativa=True,
                      detalhes={"data_evento": data_evento} if data_evento is not None else {})
    db_session.add(noticia)
    db_session.commit()
    return noticia


@freeze_time("2026-11-12 15:00:00")
def test_evento_que_ja_acabou_nao_vira_pauta(db_session, account, programa):
    _agenda(db_session, account, "2026-11-11", "passado")
    assert proxima_noticia(db_session, programa, account) is None


@freeze_time("2026-11-12 15:00:00")
def test_evento_futuro_e_agenda_sem_data_viram_pauta(db_session, account, programa):
    futuro = _agenda(db_session, account, "2026-11-14", "futuro")
    assert proxima_noticia(db_session, programa, account).noticia_id == futuro.id
    db_session.delete(futuro)
    sem_data = _agenda(db_session, account, None, "sem-data")
    assert proxima_noticia(db_session, programa, account).noticia_id == sem_data.id
