"""Fase G do plano-assuntos.md: ligacao viva entre blocos -- musica que acabou de tocar puxa o
assunto do comentario seguinte, e a noticia que acabou de ir ao ar tem prioridade pro comentario
seguinte (por outro eixo). Ambos sao callbacks de curtissimo prazo (Redis, TTL curto, consumo
unico) -- ver app.topics.pauta_conversa.
"""

import datetime

import pytest

from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics.pauta_conversa import (
    proximo_assunto,
    registrar_callback_musica,
    registrar_callback_noticia,
)


@pytest.fixture()
def programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Programa",
        horario_inicio=datetime.time(6, 0), horario_fim=datetime.time(9, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def test_callback_de_musica_vira_o_proximo_assunto_sem_precisar_de_pipeline(db_session, account, programa):
    """Nao precisa de nenhum Assunto/AssuntoPrograma no banco -- o callback e' ad-hoc, reaproveita
    o contexto que ja' foi computado (sem LLM extra) pra anunciar a musica."""
    registrar_callback_musica(programa.id, "Cancao Boa - Artista X", "Fala sobre saudade do interior.")

    escolhido = proximo_assunto(db_session, programa)

    assert escolhido is not None
    assert escolhido.origem == "musica"
    assert escolhido.eixo == "memoria"
    assert "Fala sobre saudade do interior." in escolhido.gancho


def test_callback_de_musica_e_consumido_uma_unica_vez(db_session, account, programa):
    registrar_callback_musica(programa.id, "X", "contexto")

    primeiro = proximo_assunto(db_session, programa)
    segundo = proximo_assunto(db_session, programa)

    assert primeiro is not None
    assert segundo is None  # sem callback e sem nenhum AssuntoPrograma no banco


def test_callback_de_noticia_prioriza_assunto_derivado_da_mesma_noticia(db_session, account, programa):
    noticia_id = 777
    assunto_da_noticia = Assunto(
        account_id=account.id, origem="noticia", origem_ref_id=noticia_id,
        titulo="Chuva forte", gancho="quem trabalha na rua leva capa",
        fatos=["chuva forte a tarde"], tags=["servico"], peso_base=5.0,
    )
    outro_assunto = Assunto(
        account_id=account.id, origem="reserva", titulo="Curiosidade qualquer",
        gancho="gancho generico", fatos=[], tags=["curiosidade"], peso_base=1.5,
    )
    db_session.add_all([assunto_da_noticia, outro_assunto])
    db_session.flush()
    # O assunto generico tem score BASE maior -- sem o callback, ele venceria.
    db_session.add(AssuntoPrograma(assunto_id=assunto_da_noticia.id, programa_id=programa.id, score=3.0, ponte="", eixos_sugeridos=["fato"]))
    db_session.add(AssuntoPrograma(assunto_id=outro_assunto.id, programa_id=programa.id, score=9.0, ponte="", eixos_sugeridos=["fato"]))
    db_session.commit()

    registrar_callback_noticia(programa.id, noticia_id)

    escolhido = proximo_assunto(db_session, programa)

    assert escolhido is not None
    assert escolhido.assunto_id == assunto_da_noticia.id


def test_sem_callback_de_noticia_vence_o_maior_score_normal(db_session, account, programa):
    noticia_id = 777
    assunto_da_noticia = Assunto(
        account_id=account.id, origem="noticia", origem_ref_id=noticia_id,
        titulo="Chuva forte", gancho="quem trabalha na rua leva capa",
        fatos=[], tags=["servico"], peso_base=5.0,
    )
    outro_assunto = Assunto(
        account_id=account.id, origem="reserva", titulo="Curiosidade qualquer",
        gancho="gancho generico", fatos=[], tags=["curiosidade"], peso_base=1.5,
    )
    db_session.add_all([assunto_da_noticia, outro_assunto])
    db_session.flush()
    db_session.add(AssuntoPrograma(assunto_id=assunto_da_noticia.id, programa_id=programa.id, score=3.0, ponte="", eixos_sugeridos=["fato"]))
    db_session.add(AssuntoPrograma(assunto_id=outro_assunto.id, programa_id=programa.id, score=9.0, ponte="", eixos_sugeridos=["fato"]))
    db_session.commit()

    # Sem registrar_callback_noticia nenhum.
    escolhido = proximo_assunto(db_session, programa)

    assert escolhido is not None
    assert escolhido.assunto_id == outro_assunto.id


def test_musica_concorre_com_pauta_sem_prioridade_absoluta(db_session, account, programa):
    assunto = Assunto(account_id=account.id, origem="noticia", titulo="Assunto relevante",
                      gancho="Fato apurado", fatos=["Fato apurado"], tags=["servico"])
    db_session.add(assunto)
    db_session.flush()
    db_session.add(AssuntoPrograma(assunto_id=assunto.id, programa_id=programa.id, score=9, eixos_sugeridos=["fato"]))
    db_session.commit()
    registrar_callback_musica(programa.id, "Faixa", "Contexto da música")

    assert proximo_assunto(db_session, programa).assunto_id == assunto.id
    # O gancho não fica pendente para surgir sem contexto em outro momento.
    assert proximo_assunto(db_session, programa).assunto_id == assunto.id


def test_pauta_fixada_pelo_operador_vence_callback_musical(db_session, account, programa):
    assunto = Assunto(account_id=account.id, origem="reserva", titulo="Escolha editorial", gancho="Uma observação")
    db_session.add(assunto)
    db_session.flush()
    db_session.add(AssuntoPrograma(assunto_id=assunto.id, programa_id=programa.id, score=102))
    db_session.commit()
    registrar_callback_musica(programa.id, "Faixa", "Contexto")
    assert proximo_assunto(db_session, programa).assunto_id == assunto.id


def test_callback_vazio_nao_cria_pauta(db_session, account, programa):
    registrar_callback_musica(programa.id, "Faixa", "  ")
    assert proximo_assunto(db_session, programa) is None
