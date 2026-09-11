import datetime

import pytest

from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics.eixos import EIXOS_ASSUNTO, MAX_RETORNOS_POR_ASSUNTO
from app.topics.pauta_conversa import (
    montar_pauta_assunto,
    pipeline_tem_estoque,
    proximo_assunto,
    registrar_assunto_usado,
)


@pytest.fixture()
def programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Manha na Cidade",
        horario_inicio=datetime.time(6, 0), horario_fim=datetime.time(9, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def _criar_assunto_casado(db_session, account, programa, *, score=5.0, eixos_sugeridos=None, tags=None, validade_ate=None, ponte="briefing neutro", origem="noticia"):
    assunto = Assunto(
        account_id=account.id, origem=origem, titulo="Chuva forte a tarde",
        gancho="quem trabalha na rua leva capa", fatos=["Defesa Civil confirmou chuva forte"],
        tags=tags or ["servico", "trabalho"], validade_ate=validade_ate, peso_base=5.0,
    )
    db_session.add(assunto)
    db_session.flush()
    assunto_programa = AssuntoPrograma(
        assunto_id=assunto.id, programa_id=programa.id, score=score,
        ponte=ponte, eixos_sugeridos=eixos_sugeridos if eixos_sugeridos is not None else list(EIXOS_ASSUNTO),
    )
    db_session.add(assunto_programa)
    db_session.commit()
    return assunto, assunto_programa


def test_sem_nenhum_casamento_devolve_none(db_session, account, programa):
    assert proximo_assunto(db_session, programa) is None
    assert pipeline_tem_estoque(db_session, programa.id) is False


def test_comentario_recebe_assunto_casado_com_o_programa(db_session, account, programa):
    assunto, _ap = _criar_assunto_casado(db_session, account, programa)

    escolhido = proximo_assunto(db_session, programa)

    assert escolhido is not None
    assert escolhido.assunto_id == assunto.id
    assert escolhido.ponte == "briefing neutro"
    assert escolhido.eixo in EIXOS_ASSUNTO
    assert pipeline_tem_estoque(db_session, programa.id) is True


def test_assunto_expirado_nao_entra_no_ar(db_session, account, programa):
    ontem = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    _criar_assunto_casado(db_session, account, programa, validade_ate=ontem)

    assert proximo_assunto(db_session, programa) is None


def test_assunto_volta_com_eixo_diferente_ate_o_limite(db_session, account, programa):
    """Fase E: o mesmo assunto pode voltar ate' MAX_RETORNOS_POR_ASSUNTO vezes, cada vez com um
    eixo novo -- esgotado o cardapio (ou o limite), some da escolha (ver ADR item 6)."""
    assunto, _ap = _criar_assunto_casado(db_session, account, programa)

    eixos_vistos = set()
    for _ in range(MAX_RETORNOS_POR_ASSUNTO):
        escolhido = proximo_assunto(db_session, programa)
        assert escolhido is not None
        assert escolhido.assunto_id == assunto.id
        assert escolhido.eixo not in eixos_vistos
        eixos_vistos.add(escolhido.eixo)
        registrar_assunto_usado(
            programa.id, programa.radio_config_id, escolhido.assunto_id,
            eixo=escolhido.eixo, origem=escolhido.origem, tag_principal=escolhido.tag_principal,
        )

    assert len(eixos_vistos) == MAX_RETORNOS_POR_ASSUNTO
    assert proximo_assunto(db_session, programa) is None


def test_assunto_com_cardapio_de_eixo_menor_que_o_limite_esgota_antes(db_session, account, programa):
    _criar_assunto_casado(db_session, account, programa, eixos_sugeridos=["fato", "impacto"])

    primeiro = proximo_assunto(db_session, programa)
    registrar_assunto_usado(programa.id, programa.radio_config_id, primeiro.assunto_id, eixo=primeiro.eixo, origem=primeiro.origem, tag_principal=primeiro.tag_principal)
    segundo = proximo_assunto(db_session, programa)
    registrar_assunto_usado(programa.id, programa.radio_config_id, segundo.assunto_id, eixo=segundo.eixo, origem=segundo.origem, tag_principal=segundo.tag_principal)

    assert {primeiro.eixo, segundo.eixo} == {"fato", "impacto"}
    assert proximo_assunto(db_session, programa) is None


def test_mesmo_gancho_em_dois_programas_da_radio_penaliza_sem_bloquear(db_session, account, programa):
    """ADR item 3: cruzamento entre programas da mesma radio e' penalidade de score, nao
    bloqueio duro -- se depois da penalidade o gancho ainda for a melhor opcao, ele vai ao ar."""
    outro_programa = Programa(
        radio_config_id=programa.radio_config_id, nome="Outro Programa",
        horario_inicio=datetime.time(9, 0), horario_fim=datetime.time(12, 0),
    )
    db_session.add(outro_programa)
    db_session.commit()

    assunto, _ap = _criar_assunto_casado(db_session, account, programa)
    # O MESMO assunto (gancho) tambem foi usado no outro programa da mesma radio ha pouco.
    registrar_assunto_usado(outro_programa.id, programa.radio_config_id, assunto.id, eixo="fato", origem="noticia", tag_principal="servico")

    escolhido = proximo_assunto(db_session, programa)

    # Penalizado, mas como e' o unico candidato disponivel, ainda assim e' escolhido.
    assert escolhido is not None
    assert escolhido.assunto_id == assunto.id


def test_ponte_persistida_e_neutra_de_eixo_gera_falas_diferentes(db_session, account, programa):
    """ADR item 1: a mesma ponte (briefing) serve pra qualquer eixo -- quem muda a instrucao de
    prompt e' o eixo, nao o texto do briefing."""
    assunto, _ap = _criar_assunto_casado(db_session, account, programa, eixos_sugeridos=["fato", "pergunta"])
    assunto.pergunta_ouvinte = "como esta o tempo ai no seu bairro?"
    db_session.commit()

    escolhido = proximo_assunto(db_session, programa)
    escolhido.eixo = "fato"
    texto_fato = montar_pauta_assunto(escolhido)
    escolhido.eixo = "pergunta"
    texto_pergunta = montar_pauta_assunto(escolhido)

    assert texto_fato != texto_pergunta
    assert "briefing neutro" in texto_fato and "briefing neutro" in texto_pergunta
    assert "FATO" in texto_fato
    assert "PERGUNTA" in texto_pergunta
    assert "como esta o tempo ai no seu bairro?" in texto_pergunta
    assert "como esta o tempo ai no seu bairro?" not in texto_fato
