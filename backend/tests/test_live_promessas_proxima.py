"""Promessas e participação pela rota POST /proxima (F4, integração I1-I18 da auditoria §8).

Mesmo padrão de tests/test_live_validacao_proxima.py: freeze_time, fakeredis do conftest e dublês por nome em
app.live.router. Falas de exemplo originais.
"""

import datetime
import json

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.promessa_no_ar import PromessaNoAr
from app.models.radio_config import RadioConfig

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 em São Paulo, dentro de um programa 10:00-14:00
FAIXA = MusicaEncontrada(video_id="f1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200)


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


def _relogio_a(db_session, account, radialista, prog, *executadas):
    """Programa 12:00-13:00 com o relógio A e dois patrocinadores (o intervalo de 24:00 fica no espelho)."""
    from app.live import relogio as r

    patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                   tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                      for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
    db_session.add_all(patrocinadores)
    db_session.flush()
    prog.horario_inicio, prog.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
    prog.estrutura_blocos = ["comentario", *[f"patrocinador:{p.id}" for p in patrocinadores]]
    prog.relogio_hora = r.PRESETS["A"].model_dump()
    db_session.commit()
    instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    r.marcar_executada(prog.id, r.ocorrencia_em(prog, radialista.timezone, instante), "0:0:fala:abertura",
                       *executadas)


LINK_A = dict(total_falas=3, historico=["musica: oi [Música(s) tocada(s) nesse bloco: Rio - Dupla]"],
              inicio_previsto="2026-11-10T12:12:30-03:00")


# --- I1 e I2: registro e promessa sem evento -----------------------------------------------------------

def test_i1_promessa_com_evento_no_relogio_fica_aberta(client, account, auth_headers, programa, db_session,
                                                        monkeypatch):
    radialista, prog = programa
    with freeze_time("2026-11-10 15:12:20"):
        _relogio_a(db_session, account, radialista, prog, "0:40")
        prompts: list[str] = []
        monkeypatch.setattr("app.live.router.gerar_resposta",
                            _gerador(prompts, "Seguimos com você nesta tarde. Mais tarde a gente lê os recados."))
        dados = _post(client, account, auth_headers, radialista, prog, **LINK_A)
    assert len(prompts) == 1
    assert dados["fala"].endswith("Mais tarde a gente lê os recados.")
    linha = db_session.query(PromessaNoAr).one()
    assert (linha.estado, linha.evento_alvo, linha.tipo, linha.classe) == ("aberta", "etapa:0:1620", "participacao",
                                                                           "fim")
    assert linha.ocorrencia == "20261110T150000Z"
    registrada = dados["promessas"]["registradas"][0]
    assert registrada["id"] == linha.id and registrada["evento_alvo"] == "etapa:0:1620"
    assert dados["promessas"]["resolvidas"] == []


def test_i2_promessa_sem_evento_reescreve_com_a_agenda_e_sai(client, account, auth_headers, programa, db_session,
                                                              monkeypatch):
    radialista, prog = programa
    with freeze_time("2026-11-10 15:12:20"):
        _relogio_a(db_session, account, radialista, prog, "0:40")
        prompts: list[str] = []
        base = ("Seguimos com você nesta tarde de sol, com calma e boa companhia, e com a música que combina com o "
                "ritmo de quem trabalha, de quem cozinha e de quem descansa um pouco agora.")
        promessa = f"{base} Daqui a pouco tem receita de bolo."
        monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, promessa, promessa))
        dados = _post(client, account, auth_headers, radialista, prog, **LINK_A)
    assert len(prompts) == 2
    assert "Você prometeu 'Daqui a pouco tem receita de bolo.' sem programação confirmada." in prompts[1]
    assert "Retorno e participação em cerca de 14 minutos" in prompts[1]
    assert dados["fala"] == base
    assert [v["regra"] for v in dados["validacao_fala"]["violacoes"]] == ["promessa_sem_evento",
                                                                          "promessa_sem_evento"]
    assert dados["validacao_fala"]["acao"] == "mencao_removida"
    assert db_session.query(PromessaNoAr).count() == 0
    assert dados.get("promessas") is None


@freeze_time(AGORA_UTC)
def test_i2_continuidade_e_ate_amanha_nao_sao_registradas(client, account, auth_headers, programa, db_session,
                                                          monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    db_session.commit()
    fala = "Seguimos com o papo, já já tem mais rádio. A Tarde Viva continua."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: fala)
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert dados["fala"] == fala and dados.get("validacao_fala") is None and dados.get("promessas") is None
    assert db_session.query(PromessaNoAr).count() == 0


@freeze_time(AGORA_UTC)
def test_modo_avisar_da_promessa_so_registra(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    db_session.commit()
    monkeypatch.setattr("app.live.router.settings.validacao_promessa_modo", "avisar")
    prompts: list[str] = []
    fala = "Bom papo por aqui. Daqui a pouco tem receita de bolo."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, fala))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert len(prompts) == 1 and dados["fala"] == fala
    assert dados["validacao_fala"]["acao"] == "nenhuma"
    assert dados["validacao_fala"]["violacoes"][0]["regra"] == "promessa_sem_evento"


# --- I7: sem relógio, agenda pelo roteiro ----------------------------------------------------------------

POPULAR = ["abertura", "musica", "musica", "chamada_ouvinte", "musica", "comentario", "musica", "comentario"]


@freeze_time(AGORA_UTC)
def test_i7_sem_relogio_promessa_longe_sai_e_mais_tarde_registra_pela_posicao(
        client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = POPULAR
    db_session.commit()
    # Bloco na posição 4 (chamada_ouvinte, sem pedido): o próximo chamada_ouvinte está na posição 11.
    prompts: list[str] = []
    convite = "O WhatsApp da Rádio Teste está aberto para o seu recado."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(
        prompts, f"{convite} Daqui a pouco tem mais recado de ouvinte por aqui."))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=3, historico=["musica: oi"])
    assert dados["tipo"] == "chamada_ouvinte"
    assert dados["fala"] == convite
    assert db_session.query(PromessaNoAr).count() == 0
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(
        [], f"{convite} Mais tarde a gente lê mais recados por aqui."))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=3, historico=["musica: oi"])
    linha = db_session.query(PromessaNoAr).one()
    assert (linha.evento_alvo, linha.prazo_posicao, linha.prazo) == ("roteiro:11", 11, None)
    assert dados["promessas"]["registradas"][0]["prazo_posicao"] == 11


# --- I8, I9, I10: participação --------------------------------------------------------------------------

def _novo_pedido(db_session, account, radialista, prog, nome, tipo="musica", **extra):
    from app.whatsapp.atendimento import ocorrencia

    account.atendimento_ouvinte_ativo = True
    pedido = FilaAoVivo(radio_config_id=radialista.id, programa_id=prog.id,
                        transmissao=ocorrencia(prog, radialista.timezone), estado="em_fila", telefone=extra.pop(
                            "telefone", "5511"), nome=nome, tipo=tipo, mensagem_usuario="oi",
                        texto_autorizado=extra.pop("texto_autorizado", "Pediu uma música."), **extra)
    db_session.add(pedido)
    db_session.commit()
    return pedido


@freeze_time(AGORA_UTC)
def test_i8_toca_agora_com_pedido_selecionado_passa_e_nome_em_fila_sai(client, account, auth_headers, programa,
                                                                      db_session, monkeypatch):
    radialista, prog = programa
    selecionado = _novo_pedido(db_session, account, radialista, prog, "Joana Lis", musica_query="Estrada Aberta")
    _novo_pedido(db_session, account, radialista, prog, "Rosa Bezerra", musica_query="Lenço no Portão",
                 telefone="5512")
    prompts: list[str] = []
    fala = ("Joana Lis pediu, e toca agora Estrada Aberta, com Banda Horizonte. "
            "Rosa Bezerra pediu Lenço no Portão, que toca já já.")
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, fala, fala))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["comentario: oi"])
    assert len(prompts) <= 2
    assert dados["fala"] == "Joana Lis pediu, e toca agora Estrada Aberta, com Banda Horizonte."
    assert dados["pedido_id"] == selecionado.id
    regras = {v["regra"] for v in dados["validacao_fala"]["violacoes"]}
    assert "pedido_nao_selecionado" in regras


def _abraco_legado(db_session, radialista, nome="Cida Morais", mensagem="Um beijo para a minha irmã!"):
    pedido = FilaAoVivo(radio_config_id=radialista.id, telefone="5513", nome=nome, tipo="abraco",
                        natureza="recado_comum", mensagem_usuario=mensagem)
    db_session.add(pedido)
    db_session.commit()
    return pedido


@freeze_time(AGORA_UTC)
def test_i9_ouvinte_inexistente_junto_do_selecionado_sai_so_a_oracao(client, account, auth_headers, programa,
                                                                      db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["chamada_ouvinte"]
    db_session.commit()
    _abraco_legado(db_session, radialista)
    fala = "Um abraço para Cida Morais e também para a Dona Firmina, que escreveu agora."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador([], fala, fala))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert dados["fala"] == "Um abraço para Cida Morais."
    assert [v["regra"] for v in dados["validacao_fala"]["violacoes"]][-1] == "ouvinte_nao_autorizado"
    assert dados["validacao_fala"]["violacoes"][-1]["ref_id"] == "Dona Firmina"


@freeze_time(AGORA_UTC)
def test_i10_participacao_simulada_sem_pedido_sai(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["chamada_ouvinte"]
    db_session.commit()
    simulada = "Chegou agora uma mensagem linda de uma ouvinte que pediu um beijo para a mãe."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador([], simulada, simulada))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert dados["fala"] == "Você está no Tarde Viva, na Rádio Teste."
    assert dados["validacao_fala"]["acao"] == "fala_neutra"
    assert "participacao_simulada" in {v["regra"] for v in dados["validacao_fala"]["violacoes"]}


@freeze_time(AGORA_UTC)
def test_d10_pedido_selecionado_que_some_da_fala_volta_para_a_fila(client, account, auth_headers, programa,
                                                                    db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["chamada_ouvinte"]
    db_session.commit()
    pedido = _abraco_legado(db_session, radialista)
    prompts: list[str] = []
    sem_nome = "Um abraço para a família toda, que a tarde segue boa."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, sem_nome, sem_nome))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert len(prompts) == 2 and "Cumprimente Cida Morais pelo nome." in prompts[1]
    assert dados["pedido_id"] is None
    assert "pedido_sem_mencao" in {v["regra"] for v in dados["validacao_fala"]["violacoes"]}
    db_session.refresh(pedido)
    assert (pedido.estado, pedido.atendido) == ("em_fila", False)
    assert pedido.eventos[-1]["acao"] == "devolver_sem_mencao"


@freeze_time(AGORA_UTC)
def test_d10_fluxo_novo_devolve_sem_token(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["chamada_ouvinte"]
    db_session.commit()
    pedido = _novo_pedido(db_session, account, radialista, prog, "Seu Valdir", tipo="abraco",
                          texto_autorizado="Mandou abraço para a oficina.")
    sem_nome = "Um abraço para a oficina toda!"
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador([], sem_nome, "Valdir, um abraço para a oficina!"))
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert dados["pedido_id"] == pedido.id  # a reescrita trouxe o nome
    db_session.refresh(pedido)
    assert pedido.estado == "selecionado"


# --- I15, I17, I18 --------------------------------------------------------------------------------------

@freeze_time(AGORA_UTC)
def test_i15_contrato_sem_promessa_campos_nulos(client, account, auth_headers, programa, monkeypatch):
    radialista, prog = programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Seguimos juntos nesta tarde.")
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["comentario: oi"])
    assert dados["promessas"] is None and dados["validacao_fala"] is None
    assert dados["fala"] == "Seguimos juntos nesta tarde."


def test_i17_redis_fora_promessas_vem_do_banco(client, account, auth_headers, programa, db_session, monkeypatch):
    import redis

    from app.config import redis_client as modulo

    radialista, prog = programa
    with freeze_time("2026-11-10 15:12:20"):
        _relogio_a(db_session, account, radialista, prog, "0:40")

        def quebrado(*args, **kwargs):
            raise redis.ConnectionError("redis fora")

        for nome in modulo.PADROES_SESSAO:
            monkeypatch.setattr(modulo.redis_client, nome, quebrado)
        monkeypatch.setattr("app.live.router.gerar_resposta",
                            lambda system, msg: "Seguimos com você. Mais tarde a gente lê os recados.")
        try:
            dados = _post(client, account, auth_headers, radialista, prog, **LINK_A)
        finally:
            modulo.disjuntor.fechar()
    assert dados["promessas"]["registradas"][0]["evento_alvo"] == "etapa:0:1620"
    assert db_session.query(PromessaNoAr).count() == 1


@freeze_time(AGORA_UTC)
def test_i18_multivoz_remove_por_linha(client, account, auth_headers, programa, db_session, monkeypatch):
    radialista, prog = programa
    prog.estrutura_blocos = ["comentario"]
    convidada = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone=radialista.timezone)
    db_session.add(convidada)
    db_session.flush()
    db_session.add(ProgramaRadialista(programa_id=prog.id, radio_config_id=convidada.id, papel="Co-apresentadora"))
    db_session.commit()
    dialogo = json.dumps({"linhas": [
        {"locutor": "Zé do Rádio", "texto": "Maria, a feira de domingo estava cheia."},
        {"locutor": "Maria", "texto": "Estava sim. Daqui a pouco tem receita de bolo."}]}, ensure_ascii=False)
    monkeypatch.setattr("app.live.router.gerar_dialogo_multivoz", lambda system, msg: dialogo)
    dados = _post(client, account, auth_headers, radialista, prog, total_falas=1, historico=["musica: oi"])
    assert [linha["texto"] for linha in dados["falas"]] == ["Maria, a feira de domingo estava cheia.", "Estava sim."]
