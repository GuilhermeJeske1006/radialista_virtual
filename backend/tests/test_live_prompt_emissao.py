"""ContextoEmissao e montagem pura do prompt (F3, U1 e U2 da auditoria §6)."""

import ast
import datetime
import pathlib
import random

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

APP_LIVE = pathlib.Path(__file__).resolve().parents[1] / "app" / "live"


@pytest.mark.parametrize("modulo", ["contexto", "prompt_emissao", "roteiro", "geracao", "portas", "prompts"])
def test_modulos_extraidos_nao_importam_o_router(modulo):
    arvore = ast.parse((APP_LIVE / f"{modulo}.py").read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
            importados.update(f"{no.module}.{a.name}" for a in no.names)
        elif isinstance(no, ast.Import):
            importados.update(a.name for a in no.names)
    assert not any(nome.startswith("app.live.router") for nome in importados), importados
    # O que os testes trocam por nome no router não pode ser importado direto (passa pelas portas).
    proibidos = {"app.llm.client.gerar_resposta", "app.llm.client.gerar_dialogo_multivoz",
                 "app.live.music.buscar_musica", "app.llm.noticias.pesquisar_noticias"}
    assert not (importados & proibidos)


def _capturar_contexto(client, account, auth_headers, db_session, monkeypatch, corpo, preparar=None):
    capturados = []
    from app.live import router

    original = router.montar_prompt

    def espiao(ctx):
        capturados.append(ctx)
        return original(ctx)

    monkeypatch.setattr("app.live.router.montar_prompt", espiao)
    sistemas = []
    monkeypatch.setattr("app.live.router.gerar_resposta",
                        lambda system, mensagem: sistemas.append((system, mensagem)) or "Seguimos juntos.")
    monkeypatch.setattr("app.live.router.buscar_musica", lambda q, **k: MusicaEncontrada(
        video_id="v1", titulo="Estrada Aberta", canal="Banda Horizonte", duracao_segundos=200))
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *a: "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=[])
    db_session.add(programa)
    db_session.commit()
    if preparar:
        preparar(programa)
        db_session.commit()
    resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima",
                           json={"incluir_audio": False, **corpo}, headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return capturados[0], sistemas[0]


@freeze_time("2026-08-10 15:00:00")
@pytest.mark.parametrize("corpo", [
    {"total_falas": 1, "historico": ["comentario: falávamos do trânsito"]},
    {"total_falas": 3, "historico": ["musica: boa [Música(s) tocada(s) nesse bloco: Rio de Prata - Dupla Serra]"]},
    {"total_falas": 0, "historico": []},
])
def test_montar_prompt_e_pura_e_repete_o_texto_da_rota(client, account, auth_headers, db_session, monkeypatch,
                                                         corpo):
    from app.config.redis_client import redis_client
    from app.live.prompt_emissao import montar_prompt

    ctx, (system, mensagem) = _capturar_contexto(client, account, auth_headers, db_session, monkeypatch, corpo)

    def proibido(*a, **k):
        raise AssertionError("montar_prompt não pode tocar Redis nem sortear")

    for nome in ("get", "set", "incr", "lrange", "smembers", "hget", "hset", "expire", "lpush"):
        monkeypatch.setattr(redis_client, nome, proibido)
    for nome in ("random", "choice", "choices", "randint", "shuffle"):
        monkeypatch.setattr(random, nome, proibido)
    primeiro, segundo = montar_prompt(ctx), montar_prompt(ctx)
    assert primeiro == segundo
    assert (primeiro.system, primeiro.mensagem) == (system, mensagem)
    assert f"Tipo do próximo bloco: {ctx.tipo}." in primeiro.mensagem
    assert ctx.prompt_base in primeiro.system
    assert f"'{ctx.variacoes.verbo_identificacao}'" in primeiro.system


@freeze_time("2026-08-10 15:00:00")
def test_contexto_traz_a_faixa_confirmada_e_o_orcamento(client, account, auth_headers, db_session, monkeypatch):
    ctx, (system, _) = _capturar_contexto(client, account, auth_headers, db_session, monkeypatch,
                                          {"total_falas": 1, "historico": ["comentario: oi"]})
    assert ctx.tipo == ctx.categoria == "musica"
    assert (ctx.musica.confirmada.titulo, ctx.musica.confirmada.artista) == ("Estrada Aberta", "Banda Horizonte")
    assert ctx.musica.resolve_citadas is True
    assert "anuncie exatamente a música 'Estrada Aberta' de 'Banda Horizonte'" in system
    assert ctx.orcamento.fonte == "observacao" and ctx.limite_palavras is None
    assert ctx.participacao.pedido_musica is None
    assert ctx.dados == () and dict(ctx.extensoes) == {}


@freeze_time("2026-08-10 15:00:00")
def test_formato_musical_nao_resolve_citadas_no_bloco_de_musica(client, account, auth_headers, db_session,
                                                                 monkeypatch):
    from app.models.fila_ao_vivo import FilaAoVivo

    def preparar(programa):
        programa.perfil_programacao = "musical_companhia"
        db_session.add(FilaAoVivo(radio_config_id=programa.radio_config_id, telefone="1", nome="Joana", tipo="musica",
                                  mensagem_usuario="toca Estrada Aberta", musica_query="Estrada Aberta"))

    ctx, _ = _capturar_contexto(client, account, auth_headers, db_session, monkeypatch,
                                {"total_falas": 1, "historico": ["retomada: oi"]}, preparar)
    assert ctx.categoria == "musica" and ctx.formato_musical
    assert ctx.musica.resolve_citadas is False
    assert ctx.participacao.pedido_musica.nome == "Joana"
    assert ctx.orcamento.aplicar and ctx.limite_palavras is not None


def test_prompt_revisao_mantem_a_frase_que_o_duble_le():
    from app.live.prompt_emissao import MotivosRevisao, PromptEmissao, prompt_revisao
    from app.live.orcamento import OrcamentoFala

    class Ctx:
        orcamento = OrcamentoFala(6, 9, 12, 25, "formato", True)
        wpm_fala = 150.0

    texto = prompt_revisao(Ctx(), PromptEmissao("SYS", "MSG"), "uma fala longa demais",
                           MotivosRevisao(revisar_orcamento=True, excedeu_duracao=True, estimada_s=20.0,
                                          instrucoes_extras=("Você citou 'X', que não vai tocar.",)))
    assert texto.startswith("SYS\nA versão anterior ultrapassou o tempo de locução (cerca de 20 segundos para no "
                            "máximo 12)")
    assert "Reescreva com no máximo 25 palavras" in texto
    assert texto.endswith("\nVocê citou 'X', que não vai tocar.")


def test_tocadas_saem_das_linhas_do_painel():
    from app.live.contexto import tocadas_no_historico

    linhas = ["musica: boa [Música(s) tocada(s) nesse bloco: Rio de Prata - Dupla Serra, Varanda Azul - Trio Maré]",
              "comentario: sem música", "musica: só título [Música(s) tocada(s) nesse bloco: Sem Canal]"]
    assert [(m.titulo, m.artista, m.origem) for m in tocadas_no_historico(linhas)] == [
        ("Rio de Prata", "Dupla Serra", "historico"), ("Varanda Azul", "Trio Maré", "historico"),
        ("Sem Canal", "", "historico")]


@freeze_time("2026-08-10 15:00:00")
def test_contexto_traz_tocadas_da_sessao_e_ouvintes_da_fila_sem_aprovar(client, account, auth_headers, db_session,
                                                                        monkeypatch):
    from app.models.fila_ao_vivo import FilaAoVivo

    def preparar(programa):
        programa.musicas_permitidas = ["Banda Horizonte - Estrada Aberta"]
        db_session.add(FilaAoVivo(radio_config_id=programa.radio_config_id, telefone="1", nome="Rosa", tipo="musica",
                                  mensagem_usuario="toca Lenço no Portão", musica_query="Lenço no Portão"))

    ctx, _ = _capturar_contexto(client, account, auth_headers, db_session, monkeypatch,
                                {"total_falas": 3, "historico": [
                                    "musica: boa [Música(s) tocada(s) nesse bloco: Rio de Prata - Dupla Serra]"]},
                                preparar)
    assert ctx.categoria == "comentario"
    assert [m.titulo for m in ctx.musica.tocou if m.origem == "historico"] == ["Rio de Prata"]
    assert {m.titulo for m in ctx.musica.citaveis} == {"Estrada Aberta", "Lenço no Portão"}
    assert ctx.participacao.nomes_autorizados == ("Rosa",)
    # Pedido em fila não vira pedido aprovado nem faixa confirmada.
    assert ctx.participacao.pedido_musica is None and ctx.musica.confirmada is None
