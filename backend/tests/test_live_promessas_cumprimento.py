"""Cumprimento, contingência e vencimento das promessas (F4, I3-I6, I16 e U12 da auditoria §8).

A contingência é garantida pelo código (D5): o dublê do LLM ignora a instrução, e mesmo assim a frase vai ao ar.
Falas e textos de contingência originais.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live import promessas as p
from app.live import promessas_repo as repo
from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.promessa_no_ar import PromessaNoAr
from app.models.radio_config import RadioConfig

FAIXA = MusicaEncontrada(video_id="f1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200)
CONTINGENCIA_RECADO = "Ainda não chegou recado para ler agora; o WhatsApp da Rádio Teste segue aberto."


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


def _gerador(prompts: list, *respostas: str):
    def gerar(system, mensagem):
        prompts.append(system)
        return respostas[min(len(prompts), len(respostas)) - 1]
    return gerar


def _post(client, account, auth_headers, radialista, programa, **corpo):
    corpo.setdefault("incluir_audio", False)
    resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima", json=corpo,
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _relogio(db_session, account, radialista, prog, preset, *executadas):
    from app.live import relogio as r

    patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                   tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                      for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
    db_session.add_all(patrocinadores)
    db_session.flush()
    prog.horario_inicio, prog.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
    prog.estrutura_blocos = ["comentario", *[f"patrocinador:{x.id}" for x in patrocinadores]]
    prog.relogio_hora = r.PRESETS[preset].model_dump()
    db_session.commit()
    return _marcar(prog, radialista, "0:0:fala:abertura", *executadas,
                   *(c.format(*[x.id for x in patrocinadores]) for c in INTERVALOS))


# Chaves dos patrocinadores dos intervalos 24:00 (A) e 16:00 (C), formatadas com os ids do banco.
INTERVALOS = ("0:1440:patrocinador:{0}", "0:1440:patrocinador:{1}", "0:960:patrocinador:{0}",
              "0:960:patrocinador:{1}")


def _marcar(prog, radialista, *chaves):
    from app.live import relogio as r

    instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    ocorrencia = r.ocorrencia_em(prog, radialista.timezone, instante)
    r.marcar_executada(prog.id, ocorrencia, *chaves)
    return ocorrencia.chave


def _promessa(db_session, prog, ocorrencia, chave="etapa:0:1620", texto="Mais tarde a gente lê os recados.",
              tipo="participacao", rotulo="Retorno e participação", posicao=None, request_id="anterior"):
    promessa = p.detectar(texto)[0]
    evento = p.EventoAgendado(chave=chave, tipo=tipo, rotulo=rotulo, posicao=posicao)
    return repo.registrar(db_session, programa=prog, ocorrencia=ocorrencia, request_id=request_id,
                          itens=[(promessa, evento)])[0]


RETORNO_A = dict(total_falas=6, historico=["patrocinador: Loja Dois, perto de você."],
                 inicio_previsto="2026-11-10T12:27:00-03:00")
EXECUTADAS_ATE_O_RETORNO = ("0:40", "0:720")


# --- I3 e I4: o retorno cumpre ou dá a contingência ----------------------------------------------------

def test_i3_retorno_com_pedido_cumpre_a_promessa(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    with freeze_time("2026-11-10 15:26:50"):
        ocorrencia = _relogio(db_session, account, radialista, prog, "A", *EXECUTADAS_ATE_O_RETORNO)
        promessa = _promessa(db_session, prog, ocorrencia)
        db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="1", nome="Seu Valdir", tipo="abraco",
                                  natureza="recado_comum", mensagem_usuario="abraço pra turma da oficina"))
        db_session.commit()
        prompts: list[str] = []
        monkeypatch.setattr("app.live.router.gerar_resposta",
                            _gerador(prompts, "Seu Valdir, um abraço para a turma da oficina!"))
        dados = _post(client, account, auth_headers, radialista, prog, **RETORNO_A)
    assert dados["tipo"] == "chamada_ouvinte"
    assert "Você prometeu 'Mais tarde a gente lê os recados.'. Cumpra agora: o recado de Seu Valdir." in prompts[0]
    db_session.refresh(promessa)
    assert (promessa.estado, promessa.motivo) == ("cumprida", "cumprida no bloco")
    assert dados["promessas"]["resolvidas"] == [{"id": promessa.id, "estado": "cumprida", "contingencia": None}]
    assert dados["relogio"]["obrigacoes"] == ["0:1620"]


def test_i4_retorno_sem_pedido_garante_a_contingencia(client, account, auth_headers, programa, db_session,
                                                      monkeypatch):
    radialista, prog = programa
    with freeze_time("2026-11-10 15:26:50"):
        ocorrencia = _relogio(db_session, account, radialista, prog, "A", *EXECUTADAS_ATE_O_RETORNO)
        promessa = _promessa(db_session, prog, ocorrencia)
        prompts: list[str] = []
        convite = "O WhatsApp da Rádio Teste está aberto para o seu recado."
        monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, convite))
        dados = _post(client, account, auth_headers, radialista, prog, **RETORNO_A)
    assert f"Comece a fala com esta frase, exatamente: '{CONTINGENCIA_RECADO}'" in prompts[0]
    assert len(prompts) == 1
    # O dublê ignorou a instrução: o código põe a frase no começo.
    assert dados["fala"] == f"{CONTINGENCIA_RECADO} {convite}"
    db_session.refresh(promessa)
    assert (promessa.estado, promessa.motivo, promessa.contingencia) == (
        "cancelada", "contingencia:conteudo_caiu", CONTINGENCIA_RECADO)
    assert dados["promessas"]["resolvidas"] == [
        {"id": promessa.id, "estado": "cancelada", "contingencia": CONTINGENCIA_RECADO}]


def test_i4_contingencia_dita_pelo_llm_nao_duplica(client, account, auth_headers, programa, db_session,
                                                   monkeypatch):
    radialista, prog = programa
    with freeze_time("2026-11-10 15:26:50"):
        ocorrencia = _relogio(db_session, account, radialista, prog, "A", *EXECUTADAS_ATE_O_RETORNO)
        _promessa(db_session, prog, ocorrencia)
        fala = f"{CONTINGENCIA_RECADO} Manda o seu."
        monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: fala)
        dados = _post(client, account, auth_headers, radialista, prog, **RETORNO_A)
    assert dados["fala"] == fala


# --- I5: obrigação no backtiming ------------------------------------------------------------------------

def test_i5_promessa_aberta_reserva_tempo_antes_da_participacao(client, account, auth_headers, programa,
                                                                db_session, monkeypatch):
    radialista, prog = programa
    corpo = dict(total_falas=6, historico=["comentario: oi"], inicio_previsto="2026-11-10T12:25:30-03:00")
    from app.config.redis_client import redis_client

    with freeze_time("2026-11-10 15:25:20"):
        ocorrencia = _relogio(db_session, account, radialista, prog, "C", "0:120", "0:600")
        executadas = redis_client.smembers(f"relogio_etapas:{prog.id}:{ocorrencia}")
        livre = _post(client, account, auth_headers, radialista, prog, **corpo)
        redis_client.flushall()
        _marcar(prog, radialista, *executadas)
        _promessa(db_session, prog, ocorrencia, chave="etapa:0:2040", rotulo="Participação ou jogo")
        obrigado = _post(client, account, auth_headers, radialista, prog, **corpo)
    assert livre["relogio"]["acao"] == obrigado["relogio"]["acao"] == "musica"
    assert livre["relogio"].get("obrigacoes") is None and obrigado["relogio"]["obrigacoes"] == ["0:2040"]
    assert obrigado["relogio"]["espaco_s"] == livre["relogio"]["espaco_s"] - 90


# --- I6: vencida antes do alvo e encerramento ---------------------------------------------------------

ROTEIRO = ["abertura", "musica", "chamada_ouvinte", "comentario", "musica", "comentario"]


@freeze_time("2026-08-10 15:00:00")
def test_i6_sem_relogio_posicao_passou_vira_contingencia_na_proxima_fala(client, account, auth_headers, programa,
                                                                          db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ROTEIRO
    db_session.commit()
    from app.live.contexto import chave_ocorrencia

    ocorrencia = chave_ocorrencia(prog, radialista.timezone, datetime.datetime.now(datetime.timezone.utc))
    promessa = _promessa(db_session, prog, ocorrencia, chave="roteiro:2", posicao=2)
    comentario = ("Repara como cada família tem um jeito próprio de arrumar a mesa, e cada um tem a sua versão "
                  "dessa história, do almoço de domingo ao café da tarde com a vizinhança.")
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: comentario)
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=3, historico=["comentario: oi"])
    assert dados["tipo"] == "comentario"
    assert dados["fala"] == f"{CONTINGENCIA_RECADO} {comentario}"
    db_session.refresh(promessa)
    assert (promessa.estado, promessa.motivo) == ("cancelada", "contingencia:prazo_vencido")


@freeze_time("2026-08-10 16:58:00")
def test_i6_encerramento_resolve_todas_e_nada_fica_aberto(client, account, auth_headers, programa, db_session,
                                                           monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ROTEIRO
    db_session.commit()
    from app.live.contexto import chave_ocorrencia

    ocorrencia = chave_ocorrencia(prog, radialista.timezone, datetime.datetime.now(datetime.timezone.utc))
    recado = _promessa(db_session, prog, ocorrencia, chave="roteiro:40", posicao=40)
    quadro = _promessa(db_session, prog, ocorrencia, chave="roteiro:41", posicao=41, tipo="quadro",
                       rotulo="Cantinho da Casa", texto="Mais tarde tem o Cantinho da Casa.", request_id="outra")
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        _gerador(prompts, "Obrigado pela companhia, foi uma tarde boa."))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=30, historico=["musica: oi"])
    assert dados["tipo"] == "encerramento"
    assert dados["fala"].startswith(f"{CONTINGENCIA_RECADO} O Cantinho da Casa não entra hoje.")
    db_session.refresh(recado)
    db_session.refresh(quadro)
    assert {recado.motivo, quadro.motivo} == {"contingencia:fim_do_programa"}
    assert db_session.query(PromessaNoAr).filter_by(estado="aberta").count() == 0


@freeze_time("2026-08-10 15:00:00")
def test_promessa_de_outra_ocorrencia_vence_ao_abrir_a_nova(client, account, auth_headers, programa, db_session,
                                                            monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    db_session.commit()
    velha = _promessa(db_session, prog, "20260809T130000Z")
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Seguimos juntos nesta tarde.")
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    db_session.refresh(velha)
    assert (velha.estado, velha.motivo) == ("vencida", "transmissao_encerrada")
    assert dados["fala"] == "Seguimos juntos nesta tarde."


# --- I16: prewarm -----------------------------------------------------------------------------------------

def test_i16_transmissao_recomecada_nao_apaga_promessas(client, account, auth_headers, programa, db_session,
                                                        monkeypatch):
    radialista, prog = programa
    with freeze_time("2026-11-10 15:12:20"):
        _relogio(db_session, account, radialista, prog, "A", "0:40")
        monkeypatch.setattr("app.live.router.gerar_resposta",
                            lambda system, msg: "Seguimos com você. Mais tarde a gente lê os recados.")
        _post(client, account, auth_headers, radialista, prog, total_falas=3, historico=["musica: oi"],
              inicio_previsto="2026-11-10T12:12:30-03:00")
        # Painel recarregado: total_falas 0 e histórico vazio zeram a cadeia, não as promessas.
        monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Boa tarde, seguimos.")
        _post(client, account, auth_headers, radialista, prog, total_falas=0, historico=[],
              inicio_previsto="2026-11-10T12:12:40-03:00")
    assert db_session.query(PromessaNoAr).filter_by(estado="aberta").count() == 1
    assert db_session.query(PromessaNoAr).one().request_id


# --- U12: contingência garantida --------------------------------------------------------------------------

def test_u12_garantir_contingencia_insere_e_nao_duplica():
    from app.live.geracao import FalaItem

    cont = p.Contingencia(promessa_id=1, texto=CONTINGENCIA_RECADO, motivo="conteudo_caiu")
    fala, linhas, ditas = p.garantir_contingencia("Manda o seu recado.", [], [cont])
    assert fala == f"{CONTINGENCIA_RECADO} Manda o seu recado." and ditas == [cont] and linhas == []
    assert p.garantir_contingencia(fala, [], [cont])[0] == fala
    assert p.garantir_contingencia("", [], [cont]) == ("", [], [])
    dialogo = [FalaItem(radio_config_id=1, nome_locutor="A", voz_id=None, texto="Oi, Maria."),
               FalaItem(radio_config_id=2, nome_locutor="Maria", voz_id=None, texto="Oi!")]
    fala, linhas, _ = p.garantir_contingencia("Oi, Maria. Oi!", dialogo, [cont])
    assert linhas[0].texto == f"{CONTINGENCIA_RECADO} Oi, Maria." and fala == " ".join(x.texto for x in linhas)


def test_u12_contingencia_preservada_pelo_encurtamento():
    from app.live.orcamento import OrcamentoFala, encurtar_por_frases

    texto = f"{CONTINGENCIA_RECADO} Uma frase a mais. Outra frase que pode sair. E mais uma ainda aqui."
    curto = encurtar_por_frases(texto, 16, preservar=[CONTINGENCIA_RECADO])
    assert curto is not None and curto.startswith(CONTINGENCIA_RECADO)
    assert OrcamentoFala  # tipo usado pelo momento C (encurtar_pela_medida usa a mesma regra)


PECA_PEDIDO = "Os recados de hoje já foram lidos; o WhatsApp da Rádio Teste continua esperando o seu."


def test_f11_contingencia_usa_a_peca_de_reserva_aprovada_e_registra_o_uso(client, account, auth_headers, programa,
                                                                         db_session, monkeypatch):
    """F11 (item 3): a contingência de pedido usa a peça aprovada do tipo "pedido" em vez da frase padrão."""
    from app.live.router import _pecas_reserva_usadas

    radialista, prog = programa
    prog.pecas_reserva = [{"id": 1, "tipo": "pedido", "texto": "Peça não aprovada.", "aprovada": False},
                          {"id": 2, "tipo": "pedido", "texto": PECA_PEDIDO, "aprovada": True}]
    db_session.commit()
    with freeze_time("2026-11-10 15:26:50"):
        ocorrencia = _relogio(db_session, account, radialista, prog, "A", *EXECUTADAS_ATE_O_RETORNO)
        promessa = _promessa(db_session, prog, ocorrencia)
        convite = "O WhatsApp da Rádio Teste está aberto para o seu recado."
        monkeypatch.setattr("app.live.router.gerar_resposta", _gerador([], convite))
        dados = _post(client, account, auth_headers, radialista, prog, **RETORNO_A)
        usadas = _pecas_reserva_usadas(prog.id, ocorrencia)
    assert dados["fala"] == f"{PECA_PEDIDO} {convite}"
    db_session.refresh(promessa)
    assert promessa.contingencia == PECA_PEDIDO
    assert usadas == frozenset({2})


def test_f11_peca_ja_usada_na_ocorrencia_volta_para_a_frase_padrao(client, account, auth_headers, programa,
                                                                  db_session, monkeypatch):
    from app.live.router import _registrar_peca_usada

    radialista, prog = programa
    prog.pecas_reserva = [{"id": 2, "tipo": "pedido", "texto": PECA_PEDIDO, "aprovada": True}]
    db_session.commit()
    with freeze_time("2026-11-10 15:26:50"):
        ocorrencia = _relogio(db_session, account, radialista, prog, "A", *EXECUTADAS_ATE_O_RETORNO)
        _promessa(db_session, prog, ocorrencia)
        _registrar_peca_usada(prog.id, ocorrencia, 2)
        convite = "O WhatsApp da Rádio Teste está aberto para o seu recado."
        monkeypatch.setattr("app.live.router.gerar_resposta", _gerador([], convite))
        dados = _post(client, account, auth_headers, radialista, prog, **RETORNO_A)
    assert dados["fala"] == f"{CONTINGENCIA_RECADO} {convite}"


@pytest.mark.parametrize("tipo_promessa,rotulo,tipo_peca", [
    ("participacao", "", "pedido"),
    ("informacao", "previsão do tempo", "fonte"),
    ("quadro", "entrevista com o prefeito", "convidado"),
    ("quadro", "curiosidade das 10", None),
])
def test_f11_tipo_da_peca_pela_promessa(tipo_promessa, rotulo, tipo_peca):
    assert p.tipo_peca_reserva(tipo_promessa, rotulo) == tipo_peca
