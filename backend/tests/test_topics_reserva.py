import datetime
import json

import pytest

from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics import reserva


@pytest.fixture()
def programa(db_session, account):
    account.cidade = "Blumenau"
    db_session.commit()
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Sertanejo da Manha",
        horario_inicio=datetime.time(5, 0), horario_fim=datetime.time(8, 0),
        generos_musicais=["sertanejo"], tom="animado e proximo",
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def test_briefing_deriva_publico_quando_publico_alvo_vazio(db_session, account, programa):
    assert programa.publico_alvo == ""

    briefing = reserva.montar_briefing_publico(db_session, programa, account)

    assert "trabalhador" in briefing or "cedo" in briefing
    assert "sertanejo" in briefing
    assert "Blumenau" in briefing


def test_briefing_usa_publico_alvo_quando_preenchido(db_session, account, programa):
    programa.publico_alvo = "donas de casa entre 30 e 50 anos"
    db_session.commit()

    briefing = reserva.montar_briefing_publico(db_session, programa, account)

    assert briefing == "donas de casa entre 30 e 50 anos"


def test_gerar_reserva_semanal_grava_assuntos_e_casamento(db_session, account, programa, monkeypatch):
    resposta = (
        '[{"titulo": "Expressao regional", "gancho": "de onde vem esse jeito de falar", '
        '"tags": ["curiosidade"], "pergunta_ouvinte": ""}, '
        '{"titulo": "Pergunta do dia", "gancho": "qual musica marcou sua infancia", '
        '"tags": ["memoria"], "pergunta_ouvinte": "qual foi a primeira musica que voce aprendeu?"}]'
    )
    monkeypatch.setattr("app.topics.reserva.gerar_classificacao", lambda system, msg, **_: resposta)

    gravados = reserva.gerar_reserva_semanal(db_session, programa, account)

    assert gravados == 2
    assuntos = db_session.query(Assunto).filter_by(origem="reserva").all()
    assert len(assuntos) == 2
    assert all(a.validade_ate is None for a in assuntos)
    casamentos = db_session.query(AssuntoPrograma).filter_by(programa_id=programa.id).all()
    assert len(casamentos) == 2
    assert all("observacao" in ap.eixos_sugeridos and "fato" not in ap.eixos_sugeridos for ap in casamentos)
    assert "pergunta" not in casamentos[0].eixos_sugeridos
    assert "pergunta" in casamentos[1].eixos_sugeridos


def test_gerar_reserva_semanal_nao_regenera_dentro_da_janela(db_session, account, programa, monkeypatch):
    chamadas = []

    def _fake(system, msg, **_):
        chamadas.append(1)
        return '[{"titulo": "X", "gancho": "Y", "tags": [], "pergunta_ouvinte": ""}]'
    monkeypatch.setattr("app.topics.reserva.gerar_classificacao", _fake)

    reserva.gerar_reserva_semanal(db_session, programa, account)
    segunda = reserva.gerar_reserva_semanal(db_session, programa, account)

    assert segunda == 0
    assert len(chamadas) == 1


def test_gerar_reserva_semanal_com_forcar_ignora_marcador(db_session, account, programa, monkeypatch):
    chamadas = []

    def gerar(*args, **kwargs):
        chamadas.append(1)
        return json.dumps([{"titulo": f"Título {len(chamadas)}", "gancho": f"Recorte {len(chamadas)}"}])

    monkeypatch.setattr(
        "app.topics.reserva.gerar_classificacao",
        gerar,
    )

    reserva.gerar_reserva_semanal(db_session, programa, account)
    segunda = reserva.gerar_reserva_semanal(db_session, programa, account, forcar=True)

    assert segunda == 1
    assert len(chamadas) == 2


def test_repertorio_estruturado_preserva_recorte_sem_promover_notas_a_fatos(db_session, account, programa, monkeypatch):
    item = {"titulo": "Reconhecer pelo começo", "gancho": "Reconhecer uma canção antes da voz entrar",
            "familia": "musica", "recorte": "Os primeiros acordes de uma música conhecida",
            "abordagens": ["Reconhecer pela introdução", "Esperar o refrão para lembrar"],
            "contextos": ["Depois de uma faixa conhecida"], "tags": ["musica"],
            "fatos": ["Um fato inventado que não deve ser aceito"]}
    mensagens = []
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda system, msg, **kw: mensagens.append(json.loads(msg)) or json.dumps([item]))
    programa.publico_alvo = "Público adulto"
    programa.descricao = "Histórias e música"
    programa.assuntos_ao_vivo = ["memória musical"]

    assert reserva.gerar_reserva_semanal(db_session, programa, account) == 1
    assunto = db_session.query(Assunto).one()
    assert assunto.repertorio["familia"] == "musica"
    assert assunto.repertorio["abordagens"] == item["abordagens"]
    assert assunto.fatos == []
    assert mensagens[0]["descricao"] == "Histórias e música"
    assert mensagens[0]["assuntos_ao_vivo"] == ["memória musical"]
    assert mensagens[0]["horario"] == "05:00 a 08:00"


def test_nao_duplica_recorte_entre_lotes_nem_no_mesmo_lote(db_session, account, programa, monkeypatch):
    itens = [{"titulo": "Canção sem nome", "gancho": "Tentar descobrir uma música cantarolando o refrão"},
             {"titulo": "CANÇÃO SEM NOME!", "gancho": "Outro texto"},
             {"titulo": "Título diferente", "gancho": "Tentar descobrir uma musica cantarolando o refrao!"}]
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda *args, **kw: json.dumps(itens))

    assert reserva.gerar_reserva_semanal(db_session, programa, account) == 1
    assert reserva.gerar_reserva_semanal(db_session, programa, account, forcar=True) == 0
    assert db_session.query(Assunto).count() == 1


def test_reposicao_diaria_quando_estoque_baixo_sem_esperar_semana(db_session, account, programa, monkeypatch):
    from freezegun import freeze_time

    mensagens = []
    def gerar(system, msg, **kw):
        mensagens.append(json.loads(msg))
        return json.dumps([{"titulo": f"Pauta {len(mensagens)}", "gancho": f"Gancho {len(mensagens)}"}])
    monkeypatch.setattr(reserva, "gerar_classificacao", gerar)
    with freeze_time("2026-11-25 12:00:00"):
        assert reserva.gerar_reserva_semanal(db_session, programa, account) == 1
        assert reserva.gerar_reserva_semanal(db_session, programa, account) == 0
    with freeze_time("2026-11-26 12:01:00"):
        assert reserva.gerar_reserva_semanal(db_session, programa, account) == 1
    assert mensagens[1]["estoque"][0]["titulo"] == "Pauta 1"


def test_limita_estoque_e_resposta_maior_que_o_lote(db_session, account, programa, monkeypatch):
    for numero in range(74):
        a = Assunto(account_id=account.id, origem="reserva", titulo=f"Antiga {numero}", gancho=f"Antigo {numero}")
        db_session.add(a)
        db_session.flush()
        db_session.add(AssuntoPrograma(assunto_id=a.id, programa_id=programa.id, score=2))
    db_session.commit()
    mensagens = []
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda system, msg, **kw: mensagens.append(json.loads(msg)) or json.dumps(
        [{"titulo": f"Nova {n}", "gancho": f"Novo recorte {n}"} for n in range(30)]))

    assert reserva.gerar_reserva_semanal(db_session, programa, account) == 1
    assert mensagens[0]["quantidade"] == 1
    assert reserva.gerar_reserva_semanal(db_session, programa, account, forcar=True) == 0
    assert len(mensagens) == 1


def test_filtra_resposta_malformada_e_topico_proibido_nas_notas(db_session, account, programa, monkeypatch):
    programa.topicos_proibidos = ["apostas"]
    itens = [None, 1, {}, {"titulo": ["lista"], "gancho": "Inválido"},
             {"titulo": "Rotina", "gancho": "Recorte leve", "abordagens": ["Conversar sobre apostas"]},
             {"titulo": "Música", "gancho": "Reconhecer pelo começo", "tags": "musica", "familia": []}]
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda *args, **kw: json.dumps(itens))

    assert reserva.gerar_reserva_semanal(db_session, programa, account) == 1
    assert db_session.query(Assunto).one().tags == []


def test_falha_de_geracao_tem_backoff_sem_bloquear_semana(db_session, account, programa, monkeypatch):
    from freezegun import freeze_time

    chamadas = []
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda *args, **kw: chamadas.append(1) or "não é json")
    with freeze_time("2026-11-25 12:00:00"):
        assert reserva.gerar_reserva_semanal(db_session, programa, account) == 0
        assert reserva.gerar_reserva_semanal(db_session, programa, account) == 0
    with freeze_time("2026-11-25 13:01:00"):
        assert reserva.gerar_reserva_semanal(db_session, programa, account) == 0
    assert len(chamadas) == 2


@pytest.mark.parametrize("resposta_valida", [True, False])
def test_renova_so_reserva_confirmada_preservando_fixados_e_falha(db_session, account, programa, monkeypatch, resposta_valida):
    from app.models.canal_whatsapp import BlocoReproduzido, DecisaoPauta

    antigos = []
    for numero in range(2):
        a = Assunto(account_id=account.id, origem="reserva", titulo=f"Antiga {numero}", gancho=f"Antigo recorte {numero}")
        db_session.add(a)
        db_session.flush()
        db_session.add(AssuntoPrograma(assunto_id=a.id, programa_id=programa.id, score=2))
        db_session.add(BlocoReproduzido(account_id=account.id, programa_id=programa.id, assunto_id=a.id,
            ocorrencia="ontem", token=f"token{numero}", tipo="comentario", estado="concluido", fala="Uma fala"))
        antigos.append(a)
    db_session.add(DecisaoPauta(programa_id=programa.id, assunto_id=antigos[1].id, estado="fixado"))
    db_session.commit()
    resposta = json.dumps([{"titulo": "Outro assunto", "gancho": "Um recorte diferente"}]) if resposta_valida else "[]"
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda *args, **kw: resposta)

    assert reserva.gerar_reserva_semanal(db_session, programa, account) == int(resposta_valida)
    db_session.refresh(antigos[0])
    assert (antigos[0].validade_ate is not None) is resposta_valida
    assert antigos[1].validade_ate is None
    assert db_session.query(BlocoReproduzido).count() == 2


def test_pauta_descartada_nao_e_recriada_apos_remocao_do_casamento(db_session, account, programa, monkeypatch):
    from app.models.canal_whatsapp import DecisaoPauta

    a = Assunto(account_id=account.id, origem="reserva", titulo="Escolha descartada", gancho="Uma ideia descartada")
    db_session.add(a)
    db_session.flush()
    db_session.add(DecisaoPauta(programa_id=programa.id, assunto_id=a.id, estado="descartado"))
    db_session.commit()
    monkeypatch.setattr(reserva, "gerar_classificacao", lambda *args, **kw: json.dumps([
        {"titulo": "Escolha descartada", "gancho": "Outra redação"}]))

    assert reserva.gerar_reserva_semanal(db_session, programa, account) == 0
    assert db_session.query(AssuntoPrograma).count() == 0
