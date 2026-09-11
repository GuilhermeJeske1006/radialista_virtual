import datetime

import pytest

from app.models.noticia import Noticia
from app.models.noticia_historico import NoticiaHistorico
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.news.pauta import (
    ANGULO_CORRECAO,
    LIMIAR_SCORE_PLANTAO,
    correcao_pendente,
    montar_escalada,
    montar_lauda,
    proxima_noticia,
    proxima_para_plantao,
    proximas_noticias,
)


def _agora() -> datetime.datetime:
    # proxima_noticia usa datetime.now(UTC) real internamente -- calcular a janela de validade
    # relativa a esse "agora" (em vez de uma data fixa no passado) evita o teste ficar obsoleto
    # conforme o tempo passa.
    return datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Jornal da Manha",
        horario_inicio=datetime.time(6, 0),
        horario_fim=datetime.time(8, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def _criar_noticia(db_session, account, **kwargs):
    base = dict(
        account_id=account.id,
        fonte_nome="Prefeitura de Blumenau",
        fonte_tipo="oficial",
        titulo="Rua São Paulo interditada apos obra",
        resumo="Trecho de 300 metros fechado desde a manha.",
        url="https://exemplo.com/materia",
        url_hash="hash-fixo",
        publicado_em=_agora() - datetime.timedelta(hours=1),
        categoria="transito",
        cidade="Blumenau",
        score=80.0,
        ativa=True,
        detalhes={"servico": "Desvio pela Antonio da Veiga"},
    )
    base.update(kwargs)
    noticia = Noticia(**base)
    db_session.add(noticia)
    db_session.commit()
    db_session.refresh(noticia)
    return noticia


def test_sem_noticia_no_banco_devolve_none(db_session, account, programa):
    assert proxima_noticia(db_session, programa, account) is None


def test_encontra_noticia_com_angulo_fato(db_session, account, programa):
    noticia = _criar_noticia(db_session, account)
    pauta = proxima_noticia(db_session, programa, account)
    assert pauta is not None
    assert pauta.noticia_id == noticia.id
    assert pauta.angulo == "fato"
    assert pauta.aberturas_usadas == []


def test_noticia_fora_da_janela_de_validade_e_ignorada(db_session, account, programa):
    _criar_noticia(db_session, account, categoria="transito", publicado_em=_agora() - datetime.timedelta(hours=48))
    assert proxima_noticia(db_session, programa, account) is None


def test_topico_proibido_do_programa_descarta_a_noticia(db_session, account, programa):
    programa.topicos_proibidos = ["obra"]
    db_session.commit()
    _criar_noticia(db_session, account)
    assert proxima_noticia(db_session, programa, account) is None


def test_tipos_noticias_configurado_filtra_por_categoria(db_session, account, programa):
    programa.tipos_noticias = ["esporte"]
    db_session.commit()
    _criar_noticia(db_session, account, categoria="transito")
    assert proxima_noticia(db_session, programa, account) is None


def test_noticia_ja_ao_ar_nao_volta_a_ser_pauta(db_session, account, programa):
    noticia = _criar_noticia(db_session, account)
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo="fato", fala="Fala original."))
    db_session.commit()
    assert proxima_noticia(db_session, programa, account) is None


def test_montar_lauda_nao_cita_fonte_inclui_angulo_e_servico():
    from app.news.pauta import NoticiaPauta

    pauta = NoticiaPauta(
        noticia_id=1, titulo="Rua interditada", resumo="Trecho fechado", fonte_nome="Prefeitura",
        fonte_tipo="oficial", url="https://x", categoria="transito", publicado_em=_agora(),
        angulo="servico", aberturas_usadas=[], detalhes={"servico": "Desvio pela Antonio da Veiga"},
    )
    texto = montar_lauda(pauta)
    assert "Prefeitura" not in texto
    assert "ÂNGULO DESTE BLOCO: SERVICO" in texto
    assert "Desvio pela Antonio da Veiga" in texto


def test_proximas_noticias_devolve_ate_o_limite_pedido(db_session, account, programa):
    for i in range(4):
        _criar_noticia(db_session, account, titulo=f"Manchete {i}", url=f"https://x/{i}", url_hash=f"hash-{i}", score=50 + i)
    pautas = proximas_noticias(db_session, programa, account, limite=3)
    assert len(pautas) == 3
    # mais relevante (maior score) primeiro
    assert pautas[0].titulo == "Manchete 3"


def test_proxima_para_plantao_exige_score_minimo(db_session, account, programa):
    _criar_noticia(db_session, account, score=LIMIAR_SCORE_PLANTAO - 1)
    assert proxima_para_plantao(db_session, programa, account) is None


def test_proxima_para_plantao_aceita_score_acima_do_limiar(db_session, account, programa):
    noticia = _criar_noticia(db_session, account, score=LIMIAR_SCORE_PLANTAO + 1)
    pauta = proxima_para_plantao(db_session, programa, account)
    assert pauta is not None
    assert pauta.noticia_id == noticia.id


def test_correcao_pendente_none_quando_noticia_nao_retificada(db_session, account, programa):
    noticia = _criar_noticia(db_session, account)
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo="fato", fala="Fala original."))
    db_session.commit()
    assert correcao_pendente(db_session, programa) is None


def test_correcao_pendente_encontra_noticia_retificada_ja_ao_ar(db_session, account, programa):
    noticia = _criar_noticia(db_session, account)
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo="fato", fala="Fala original."))
    db_session.commit()
    noticia.retificada = True
    noticia.texto_retificacao = "Na verdade foram 5 casas, não 20."
    db_session.commit()

    pauta = correcao_pendente(db_session, programa)

    assert pauta is not None
    assert pauta.angulo == ANGULO_CORRECAO
    assert pauta.resumo == "Na verdade foram 5 casas, não 20."


def test_correcao_pendente_nao_repete_apos_ja_corrigida(db_session, account, programa):
    noticia = _criar_noticia(db_session, account)
    noticia.retificada = True
    noticia.texto_retificacao = "Correção já dada."
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo="fato", fala="Fala original."))
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo=ANGULO_CORRECAO, fala="Corrigindo o que dissemos antes."))
    db_session.commit()

    assert correcao_pendente(db_session, programa) is None


def test_correcao_nao_conta_como_noticia_ja_ao_ar(db_session, account, programa):
    noticia = _criar_noticia(db_session, account)
    db_session.add(NoticiaHistorico(programa_id=programa.id, noticia_id=noticia.id, angulo=ANGULO_CORRECAO, fala="Correção no ar."))
    db_session.commit()

    pauta = proxima_noticia(db_session, programa, account)

    assert pauta is not None
    assert pauta.angulo == "fato"


def test_dose_pitada_prioriza_categoria_leve_sobre_hard_news_de_score_parecido(db_session, account, programa):
    programa.dose_noticia = "pitada"
    db_session.commit()
    _criar_noticia(db_session, account, titulo="Hard news", url="https://x/1", url_hash="hash-1", categoria="seguranca", score=70)
    _criar_noticia(db_session, account, titulo="Agenda cultural", url="https://x/2", url_hash="hash-2", categoria="agenda_cultura", score=65)

    pauta = proxima_noticia(db_session, programa, account)

    assert pauta.titulo == "Agenda cultural"


def test_montar_escalada_lista_manchetes_numeradas():
    from app.news.pauta import NoticiaPauta

    pautas = [
        NoticiaPauta(noticia_id=1, titulo="Fato A", resumo="", fonte_nome="Fonte A", fonte_tipo="oficial", url="x", categoria="geral", publicado_em=_agora(), angulo="fato", aberturas_usadas=[]),
        NoticiaPauta(noticia_id=2, titulo="Fato B", resumo="", fonte_nome="Fonte B", fonte_tipo="imprensa", url="x", categoria="geral", publicado_em=_agora(), angulo="fato", aberturas_usadas=[]),
    ]
    texto = montar_escalada(pautas)
    assert "1. Fato A" in texto
    assert "2. Fato B" in texto
    assert "fonte" not in texto.lower()


def test_montar_lauda_correcao_prioriza_frase_de_correcao():
    from app.news.pauta import NoticiaPauta

    pauta = NoticiaPauta(
        noticia_id=1, titulo="Fato original", resumo="Na verdade foram 5 casas.", fonte_nome="Defesa Civil",
        fonte_tipo="oficial", url="x", categoria="seguranca", publicado_em=_agora(), angulo=ANGULO_CORRECAO,
        aberturas_usadas=[],
    )
    texto = montar_lauda(pauta)
    assert "CORREÇÃO PENDENTE" in texto
    assert "Na verdade foram 5 casas." in texto
