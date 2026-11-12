"""Caracterização C2 da F5 (docs/melhoria-radio/f5/auditoria.md §8): a janela de validade da pauta RSS por categoria,
na borda (dentro e fora), gravada antes de a janela sair de app.news.pauta para app.dados.verificavel.ConfigDados.
A mudança de lugar não pode mudar a seleção nem a validade do assunto derivado da notícia."""

import datetime

import pytest
from freezegun import freeze_time

from app.models.noticia import Noticia
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.news.pauta import proxima_noticia

AGORA = datetime.datetime(2026, 11, 10, 17, 0, tzinfo=datetime.timezone.utc)

# Os valores de antes da F5 (app.news.pauta._JANELA_VALIDADE_HORAS e o padrão 48), copiados aqui de propósito.
JANELAS_DE_ANTES = {
    "seguranca": 24, "transito": 24, "clima_defesa_civil": 24, "saude": 24, "economia": 48,
    "servico_publico": 48, "geral": 48, "agenda_cultura": 24 * 7, "categoria_desconhecida": 48,
}


@pytest.fixture()
def programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Jornal", horario_inicio=datetime.time(6, 0),
                        horario_fim=datetime.time(8, 0))
    db_session.add(programa)
    db_session.commit()
    return programa


def _noticia(db_session, account, categoria: str, idade: datetime.timedelta) -> Noticia:
    noticia = Noticia(account_id=account.id, fonte_nome="Prefeitura", fonte_tipo="oficial", titulo="Fato do dia",
                      resumo="Resumo.", url=f"https://exemplo.com/{categoria}", url_hash=f"h-{categoria}-{idade}",
                      publicado_em=AGORA - idade, categoria=categoria, cidade="X", score=50.0, ativa=True,
                      detalhes={})
    db_session.add(noticia)
    db_session.commit()
    return noticia


@pytest.mark.parametrize("categoria", list(JANELAS_DE_ANTES))
def test_c2_dentro_da_janela_entra(db_session, account, programa, categoria):
    horas = JANELAS_DE_ANTES[categoria]
    noticia = _noticia(db_session, account, categoria, datetime.timedelta(hours=horas, minutes=-1))
    with freeze_time(AGORA):
        pauta = proxima_noticia(db_session, programa, account)
    assert pauta is not None and pauta.noticia_id == noticia.id


@pytest.mark.parametrize("categoria", list(JANELAS_DE_ANTES))
def test_c2_na_borda_exata_ainda_entra(db_session, account, programa, categoria):
    horas = JANELAS_DE_ANTES[categoria]
    _noticia(db_session, account, categoria, datetime.timedelta(hours=horas))
    with freeze_time(AGORA):
        assert proxima_noticia(db_session, programa, account) is not None


@pytest.mark.parametrize("categoria", list(JANELAS_DE_ANTES))
def test_c2_fora_da_janela_nao_entra(db_session, account, programa, categoria):
    horas = JANELAS_DE_ANTES[categoria]
    _noticia(db_session, account, categoria, datetime.timedelta(hours=horas, minutes=1))
    with freeze_time(AGORA):
        assert proxima_noticia(db_session, programa, account) is None


@pytest.mark.parametrize("categoria", ["transito", "agenda_cultura", "categoria_desconhecida"])
def test_c2_assunto_derivado_vale_pela_mesma_janela(db_session, account, categoria, monkeypatch):
    from app.topics.derivador import GanchoDerivado
    from app.topics.fontes import de_noticia

    noticia = _noticia(db_session, account, categoria, datetime.timedelta(hours=1))
    monkeypatch.setattr(de_noticia, "derivar_ganchos", lambda *a, **k: [GanchoDerivado(
        titulo="T", gancho="G", fatos=["F"], tags=["t"], pergunta_ouvinte="P")])
    assuntos = de_noticia.derivar_de_noticia(db_session, noticia, account)
    esperado = noticia.publicado_em.replace(tzinfo=datetime.timezone.utc) \
        + datetime.timedelta(hours=JANELAS_DE_ANTES[categoria])
    validade = assuntos[0].validade_ate
    assert (validade if validade.tzinfo else validade.replace(tzinfo=datetime.timezone.utc)) == esperado
