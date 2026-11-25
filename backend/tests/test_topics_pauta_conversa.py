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
    assert "FATO" in texto_fato
    assert "PERGUNTA" in texto_pergunta
    # F5: o briefing e a pergunta vão como dado no bloco da mensagem (iguais nos dois eixos); o system aponta.
    from app.dados.fontes import de_assunto

    dado = de_assunto(escolhido)
    assert dado.detalhes["contexto"] == "briefing neutro"
    assert dado.detalhes["pergunta"] == "como esta o tempo ai no seu bairro?"
    assert "briefing neutro" not in texto_fato and "briefing neutro" not in texto_pergunta
    assert "campo 'pergunta'" in texto_pergunta and "campo 'pergunta'" not in texto_fato


def test_montar_pauta_assunto_marca_bloco_como_dado_nao_instrucao(db_session, account, programa):
    """Item 3 da auditoria: mesmo enquadramento "dado de referencia, nunca instrucao" ja'
    usado em app.llm.noticias e app.live.router pro conteudo de pesquisa/ouvinte -- o gancho
    (derivado de fonte externa via app.topics.derivador) entrava no system prompt so' com
    instrucao funcional, sem esse aviso."""
    _criar_assunto_casado(db_session, account, programa)
    escolhido = proximo_assunto(db_session, programa)
    escolhido.eixo = "fato"
    texto = montar_pauta_assunto(escolhido)
    assert "nunca instru" in texto.lower()


def test_reserva_sem_fatos_nao_recebe_abordagem_factual(db_session, account, programa):
    assunto, ap = _criar_assunto_casado(db_session, account, programa, origem="reserva", eixos_sugeridos=["fato", "servico", "curiosidade"])
    assunto.fatos = []
    db_session.commit()

    escolhido = proximo_assunto(db_session, programa)

    assert escolhido.eixo == "observacao"
    assert "não contém fatos verificados" in montar_pauta_assunto(escolhido)


def test_prioriza_recorte_novo_em_vez_de_retomada_imediata(db_session, account, programa):
    repetido, _ = _criar_assunto_casado(db_session, account, programa, score=8)
    novo, _ = _criar_assunto_casado(db_session, account, programa, score=6)
    registrar_assunto_usado(programa.id, programa.radio_config_id, repetido.id, eixo="fato", origem="noticia", tag_principal="servico")

    assert proximo_assunto(db_session, programa).assunto_id == novo.id


def test_alterna_eixo_entre_assuntos_diferentes(db_session, account, programa):
    _criar_assunto_casado(db_session, account, programa)
    registrar_assunto_usado(programa.id, programa.radio_config_id, 999, eixo="fato", origem="noticia", tag_principal="outro")

    assert proximo_assunto(db_session, programa).eixo == "impacto"


def test_equilibra_familia_mesmo_com_tags_diferentes(db_session, account, programa):
    saturado, _ = _criar_assunto_casado(db_session, account, programa, score=6, tags=["tag_diferente"])
    outro, _ = _criar_assunto_casado(db_session, account, programa, score=5)
    saturado.repertorio = {"familia": "musica"}
    outro.repertorio = {"familia": "cotidiano"}
    db_session.commit()
    for numero in range(3):
        registrar_assunto_usado(programa.id, programa.radio_config_id, 900 + numero, eixo="memoria", origem="musica", tag_principal="musica")

    escolhido = proximo_assunto(db_session, programa)
    assert escolhido.assunto_id == outro.id
    assert escolhido.tag_principal == "cotidiano"


@pytest.mark.parametrize("estado", ["preparado", "reproduzindo", "interrompido", "falhou", "concluido"])
def test_continuidade_so_usa_bloco_concluido(db_session, account, programa, estado):
    from app.models.canal_whatsapp import BlocoReproduzido
    from app.topics.continuidade import ocorrencia_atual
    from app.dados.fontes import de_assunto

    assunto, _ = _criar_assunto_casado(db_session, account, programa)
    bloco = BlocoReproduzido(account_id=account.id, programa_id=programa.id,
        ocorrencia=ocorrencia_atual(db_session, programa), token="token", tipo="comentario",
        assunto_id=assunto.id, estado=estado, fala="O começo da música já traz uma lembrança.",
        assunto={"pergunta": "Que música você reconhece pela introdução?"})
    db_session.add(bloco)
    db_session.commit()

    escolhido = proximo_assunto(db_session, programa)
    if estado == "concluido":
        assert escolhido.continuidade[0]["fala"] == bloco.fala
        assert "O começo da música" in de_assunto(escolhido).detalhes["continuidade"]
        assert bloco.fala not in montar_pauta_assunto(escolhido)
    else:
        assert escolhido.continuidade == []
        assert "continuidade" not in de_assunto(escolhido).detalhes


def test_memoria_confirmada_isola_ocorrencia_programa_e_conta(db_session, account, programa, account_factory):
    from app.models.canal_whatsapp import BlocoReproduzido
    from app.topics.continuidade import ocorrencia_atual

    outro = account_factory(email="outra@repertorio.test")
    assunto, _ = _criar_assunto_casado(db_session, account, programa)
    for account_id, programa_id, ocorrencia in [
        (account.id, programa.id, "ocorrencia-anterior"),
        (outro.id, programa.id, ocorrencia_atual(db_session, programa)),
        (account.id, None, ocorrencia_atual(db_session, programa)),
    ]:
        db_session.add(BlocoReproduzido(account_id=account_id, programa_id=programa_id, ocorrencia=ocorrencia,
            token="token", tipo="comentario", assunto_id=assunto.id, estado="concluido", fala="Texto de outro contexto"))
    db_session.commit()

    assert proximo_assunto(db_session, programa).continuidade == []


def test_assunto_de_outra_conta_nao_entra_mesmo_com_associacao_incorreta(db_session, account, programa, account_factory):
    outro = account_factory(email="outra@pauta.test")
    assunto, _ = _criar_assunto_casado(db_session, account, programa)
    assunto.account_id = outro.id
    db_session.commit()
    assert proximo_assunto(db_session, programa) is None


def test_assunto_descartado_nao_entra_na_selecao(db_session, account, programa):
    from app.models.canal_whatsapp import DecisaoPauta

    assunto, _ = _criar_assunto_casado(db_session, account, programa)
    db_session.add(DecisaoPauta(programa_id=programa.id, assunto_id=assunto.id, estado="descartado"))
    db_session.commit()
    assert proximo_assunto(db_session, programa) is None


def test_contribuicao_sem_aprovacao_rastreavel_nao_vira_pauta(db_session, account, programa):
    assunto, _ = _criar_assunto_casado(db_session, account, programa, origem="ouvinte")
    assunto.origem_ref_id = 999
    db_session.commit()
    assert proximo_assunto(db_session, programa) is None


def test_notas_editoriais_sao_dados_e_passam_pela_limpeza(db_session, account, programa):
    from app.dados.fontes import de_assunto

    assunto, _ = _criar_assunto_casado(db_session, account, programa, origem="reserva")
    assunto.repertorio = {"familia": "musica", "recorte": "A introdução de uma canção",
                         "abordagens": ["Reconhecer pelos primeiros acordes"],
                         "contextos": ["Depois de uma faixa conhecida"]}
    db_session.commit()
    escolhido = proximo_assunto(db_session, programa)
    dado = de_assunto(escolhido)
    assert dado.detalhes["recorte"] == "A introdução de uma canção"
    assert dado.detalhes["abordagens"] == "Reconhecer pelos primeiros acordes"
    assert "Reconhecer pelos primeiros acordes" not in montar_pauta_assunto(escolhido)


def test_simulacao_de_pautas_mantem_variedade_de_recorte_familia_e_abordagem(db_session, account, programa):
    from app.topics.repertorio import FAMILIAS

    for familia in FAMILIAS:
        for numero in range(3):
            a = Assunto(account_id=account.id, origem="reserva", titulo=f"{familia} {numero}",
                gancho=f"Um recorte de {familia}: {numero}", fatos=[], tags=["generica"],
                repertorio={"familia": familia, "recorte": f"{familia} {numero}"})
            db_session.add(a)
            db_session.flush()
            db_session.add(AssuntoPrograma(assunto_id=a.id, programa_id=programa.id, score=2,
                eixos_sugeridos=["observacao", "comparacao", "memoria"]))
    db_session.commit()
    escolhidos = []
    for _ in range(21):
        escolhido = proximo_assunto(db_session, programa)
        assert escolhido is not None
        escolhidos.append(escolhido)
        registrar_assunto_usado(programa.id, programa.radio_config_id, escolhido.assunto_id,
            eixo=escolhido.eixo, origem=escolhido.origem, tag_principal=escolhido.tag_principal)

    assert len({e.assunto_id for e in escolhidos}) == 21
    assert {e.tag_principal for e in escolhidos} == set(FAMILIAS)
    assert len({e.tag_principal for e in escolhidos[:7]}) == 7
    assert {e.eixo for e in escolhidos} == {"observacao", "comparacao", "memoria"}
    assert not any(escolhidos[i].tag_principal == escolhidos[i + 1].tag_principal == escolhidos[i + 2].tag_principal
                   for i in range(len(escolhidos) - 2))


def test_pauta_editorial_prevalece_sobre_formato_aleatorio_e_convite_generico(db_session, account, programa):
    import dataclasses
    from app.dados.fontes import de_assunto
    from app.live.prompt_emissao import montar_prompt
    from tests.test_live_formatos_prompt import contexto

    assunto, _ = _criar_assunto_casado(db_session, account, programa, origem="reserva")
    escolhido = proximo_assunto(db_session, programa)
    ctx = contexto("padrao", "comentario")
    ctx = dataclasses.replace(ctx, dados=(de_assunto(escolhido),), variacoes=dataclasses.replace(
        ctx.variacoes, assunto=escolhido, formato_comentario="Faça uma lista de três coisas.",
        convite_ouvinte="Convide o ouvinte para responder pelo WhatsApp agora."))

    prompt = montar_prompt(ctx)
    assert "EIXO DESTE BLOCO" in prompt.system
    assert "Faça uma lista de três coisas" not in prompt.system
    assert "Convide o ouvinte para responder pelo WhatsApp agora" not in prompt.system
