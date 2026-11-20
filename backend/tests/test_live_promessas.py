"""Promessas no ar (F4): detector, agenda e casamento puros (app.live.promessas).

Numeração dos casos (U1-U6) em docs/melhoria-radio/f4/auditoria.md §8. Falas de exemplo originais; nenhuma
transcreve ou imita locutor real.
"""

import datetime
import json
import pathlib
import random
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.live import promessas as p
from app.live import relogio as r
from app.live.roteiro import tipo_na_posicao

SP = ZoneInfo("America/Sao_Paulo")
RAIZ = pathlib.Path(__file__).resolve().parents[2]
CASOS = RAIZ / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "programas"
COM_PATROCINIO = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),), vinheta_encerramento_s=3.0,
                                    quadros=("Quadro da Receita",))


def _programa(**extra):
    campos = dict(id=1, horario_inicio=datetime.time(12, 0), horario_fim=datetime.time(13, 0), dias_semana=[],
                  data_especifica=None, feriados_municipais=[], relogio_hora=None, ativo=True, estrutura_blocos=[],
                  perfil_programacao="padrao", ia_pode_adicionar_blocos=False, quadros_fixos={})
    campos.update(extra)
    return SimpleNamespace(**campos)


def _em(hora, minuto, segundo=0):
    return datetime.datetime(2026, 11, 10, hora, minuto, segundo, tzinfo=SP)


def _uma(texto):
    achadas = p.detectar(texto)
    assert len(achadas) == 1, achadas
    return achadas[0]


# --- U1: detector ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("texto, classe", [
    ("Já já tem recado de ouvinte.", "imediato"),
    ("Em instantes, recado de ouvinte.", "imediato"),
    ("A seguir, um recado da equipe.", "imediato"),
    ("Daqui a pouco tem recado.", "curto"),
    ("Daqui a pouquinho a gente lê os recados.", "curto"),
    ("Depois do intervalo, tem recado.", "intervalo"),
    ("Na volta do intervalo, recado de ouvinte.", "intervalo"),
    ("Mais tarde a gente lê os recados.", "fim"),
    ("Ainda hoje sai o resultado.", "fim"),
    ("Amanhã tem mais recado.", "fora"),
])
def test_u1_classes_de_prazo(texto, classe):
    assert _uma(texto).classe == classe


@pytest.mark.parametrize("texto, tipo", [
    ("Daqui a pouco tem recado de ouvinte.", "participacao"),
    ("Daqui a pouco tem a previsão do tempo.", "informacao"),
    ("Daqui a pouco tem entrevista com uma artesã.", "entrevista"),
    ("Daqui a pouco tem o quadro da semana.", "quadro"),
    ("Daqui a pouco tem mais música boa.", "musica"),
    ("Depois do intervalo, a Tarde Serena continua.", "continuidade"),
    ("Daqui a pouco tem receita de bolo.", "conteudo"),
])
def test_u1_tipo_pelas_palavras(texto, tipo):
    assert _uma(texto).tipo == tipo


def test_u1_acento_caixa_e_uma_por_frase():
    assert _uma("DAQUI A POUCO tem RECADO.").classe == "curto"
    assert _uma("Ja ja vem recado.").marcador == "ja ja"
    # Dois marcadores na mesma frase: uma promessa só, a de intervalo (procurada primeiro).
    assert _uma("Daqui a pouco, depois do intervalo, tem recado.").classe == "intervalo"
    duas = p.detectar("Daqui a pouco tem recado. Mais tarde tem a previsão.")
    assert [d.classe for d in duas] == ["curto", "fim"]


@pytest.mark.parametrize("texto", [
    "Toca agora Estrada Aberta, com Banda Horizonte.",
    "Agora vem Estrada Aberta.",
    "Agora, Rua das Acácias.",
    "Antes de seguir, um café.",
    "Vai chover forte no fim da tarde.",
    "Logo depois de usar, guarde a panela.",
])
def test_u1_anuncio_e_falsos_marcadores_nao_contam(texto):
    assert p.detectar(texto) == []


def test_u1_continuidade_e_ate_amanha():
    despedida = _uma("Obrigado pela companhia, até amanhã.")
    assert despedida.classe == "fora" and despedida.despedida
    assert not p.a_registrar(despedida)
    assert not p.a_registrar(_uma("Seguimos com o papo, já já tem mais rádio."))
    assert p.a_registrar(_uma("Daqui a pouco tem recado de ouvinte."))


# --- U2: agenda do relógio ----------------------------------------------------------------------------

def _seguintes(relogio, instante, pecas=COM_PATROCINIO, programa=None):
    programa = programa or _programa()
    ocorrencia = r.ocorrencia_em(programa, "America/Sao_Paulo", instante)
    espelho = r.montar_espelho(r.PRESETS[relogio], ocorrencia, pecas=pecas)
    return [e for e in espelho if e.inicio > instante]


def test_u2_relogio_a_traz_o_retorno_e_tira_musica_e_intervalo_sem_patrocinio():
    agenda = p.agenda_do_plano(_seguintes("A", _em(12, 13)))
    chaves = {e.chave: e for e in agenda}
    retorno = chaves["etapa:0:1620"]
    assert retorno.tipo == "participacao" and retorno.inicio == _em(12, 27).astimezone(datetime.timezone.utc)
    assert chaves["etapa:0:1440"].tipo == "retorno"  # intervalo com patrocinador
    assert agenda[-1].chave == "encerramento"
    assert all(e.tipo != "musica" for e in agenda)
    sem_patrocinio = p.agenda_do_plano(_seguintes("A", _em(12, 13), pecas=r.PecasDisponiveis()))
    assert "etapa:0:1440" not in {e.chave for e in sem_patrocinio}  # virou música


def test_u2_entrevista_fora_e_noticioso_so_com_fonte():
    sem_fonte = p.agenda_do_plano(_seguintes("B", _em(12, 1)))
    assert {e.tipo for e in sem_fonte} <= {"retorno", "participacao", "encerramento"}
    assert all("1080" not in e.chave for e in sem_fonte)  # entrevista
    com_fonte = p.agenda_do_plano(_seguintes("B", _em(12, 1), pecas=r.PecasDisponiveis(
        patrocinadores=(r.Peca(5, 30.0),), tem_fonte_noticia=True)))
    assert "etapa:0:660" in {e.chave for e in com_fonte if e.tipo == "informacao"}
    assert all("1080" not in e.chave for e in com_fonte)


def test_u2_quadro_com_rotulo_e_etapas_passadas_fora():
    agenda = p.agenda_do_plano(_seguintes("C", _em(12, 30)), quadros=("Quadro da Receita",))
    quadro = next(e for e in agenda if e.tipo == "quadro")
    assert quadro.rotulo == "Quadro da Receita" and quadro.conteudo == "Quadro recorrente"
    assert all(e.inicio is None or e.inicio > _em(12, 30) for e in agenda if e.chave != "encerramento")


# --- U3: agenda do roteiro ----------------------------------------------------------------------------

def _categoria(tipo):
    from app.live.relogio import _categoria_simples
    return _categoria_simples(tipo)


POPULAR = ["abertura", "musica", "musica", "chamada_ouvinte", "musica", "comentario", "musica", "patrocinador:7"]


def test_u3_estrutura_do_popular():
    programa = _programa(estrutura_blocos=POPULAR)
    agenda = p.agenda_do_roteiro(lambda pos: tipo_na_posicao(programa, pos, _categoria), _categoria,
                                 posicao=4, posicoes=8)
    assert [(e.chave, e.tipo) for e in agenda] == [
        ("roteiro:7", "retorno"), ("roteiro:11", "participacao"), ("encerramento", "encerramento")]


def test_u3_musical_sem_agenda_prometivel():
    programa = _programa(perfil_programacao="musical_companhia",
                         estrutura_blocos=["vinheta:3", "musica", "musica", "identificacao", "musica", "retomada"])
    agenda = p.agenda_do_roteiro(lambda pos: tipo_na_posicao(programa, pos, _categoria), _categoria,
                                 posicao=1, posicoes=6)
    assert [e.tipo for e in agenda] == ["encerramento"]
    assert p.descrever_agenda(p.SituacaoAgenda(agenda=agenda)) == ""


def test_u3_sem_sorteio_e_ia_pode_adicionar_blocos_nao_muda(monkeypatch):
    def proibido(*_a, **_k):
        raise AssertionError("a agenda sem relógio não pode sortear")

    for nome in ("random", "choice", "randint", "shuffle", "choices"):
        monkeypatch.setattr(random, nome, proibido)
    fixo = _programa(estrutura_blocos=POPULAR)
    livre = _programa(estrutura_blocos=POPULAR, ia_pode_adicionar_blocos=True)
    agendas = [p.agenda_do_roteiro(lambda pos, prog=prog: tipo_na_posicao(prog, pos, _categoria), _categoria,
                                   posicao=2, posicoes=8) for prog in (fixo, livre)]
    assert agendas[0] == agendas[1]


def test_u3_tipo_na_posicao_igual_ao_roteiro_do_router():
    from app.live.router import _tipo_proximo_bloco

    for estrutura, perfil in ((POPULAR, "padrao"), ([], "padrao"), ([], "musical_companhia"),
                              (["vinheta:3", "musica", "identificacao", "abertura"], "musical_companhia")):
        programa = _programa(estrutura_blocos=estrutura, perfil_programacao=perfil)
        for posicao in range(1, 20):
            esperado = _tipo_proximo_bloco(programa, posicao, "musica")
            assert tipo_na_posicao(programa, posicao, _categoria) == esperado, (estrutura, posicao)


# --- U4: casamento ------------------------------------------------------------------------------------

INSTANTE = _em(12, 13).astimezone(datetime.timezone.utc)


def _evento(chave, tipo, minutos=None, posicao=None, **extra):
    inicio = INSTANTE + datetime.timedelta(minutes=minutos) if minutos is not None else None
    return p.EventoAgendado(chave=chave, tipo=tipo, inicio=inicio, posicao=posicao, **extra)


def _casar(texto, *eventos, musica=None, **situacao):
    padrao = dict(agenda=tuple(eventos), instante=INSTANTE, nomes_programa=("Tarde Serena", "Rádio Serra Clara"))
    padrao.update(situacao)
    return p.casar(_uma(texto), p.SituacaoAgenda(**padrao), musica=musica)


def test_u4_prazo_em_segundos():
    retorno = _evento("etapa:0:1620", "participacao", minutos=14)
    assert _casar("Daqui a pouco tem recado de ouvinte.", retorno).evento == retorno
    assert _casar("Já já tem recado de ouvinte.", retorno).situacao == "violacao"  # 14 min > 5 min
    assert _casar("Mais tarde tem recado de ouvinte.", retorno).situacao == "evento"
    longe = _evento("etapa:0:3000", "participacao", minutos=40)
    assert _casar("Daqui a pouco tem recado de ouvinte.", longe).situacao == "violacao"


def test_u4_prazo_em_posicoes():
    perto = _evento("roteiro:6", "participacao", posicao=6)
    longe = _evento("roteiro:12", "participacao", posicao=12)
    sem_relogio = dict(instante=None, posicao=4)
    assert _casar("Daqui a pouco tem recado.", perto, **sem_relogio).evento == perto
    assert _casar("Já já tem recado.", perto, **sem_relogio).situacao == "violacao"  # 2 posições: 4 e 5
    assert _casar("Daqui a pouco tem recado.", longe, **sem_relogio).situacao == "violacao"
    assert _casar("Mais tarde tem recado.", longe, **sem_relogio).evento == longe


def test_u4_rotulo_conteudo_tipo_e_cancelado():
    quadro = _evento("etapa:0:2640", "quadro", minutos=10, rotulo="Cantinho da Casa", conteudo="geladeira organizada")
    assert _casar("Daqui a pouco tem Cantinho da Casa.", quadro).evento == quadro
    assert _casar("Daqui a pouco tem dica para a geladeira.", quadro).evento == quadro
    assert _casar("Daqui a pouco tem o quadro de hoje.", quadro).evento == quadro
    assert _casar("Daqui a pouco tem receita de bolo de fubá.", quadro).situacao == "violacao"
    cancelado = _evento("etapa:0:2640", "quadro", minutos=10, rotulo="Cantinho da Casa", cancelado=True)
    assert _casar("Daqui a pouco tem Cantinho da Casa.", cancelado).situacao == "violacao"


def test_u4_depois_do_intervalo_exige_intervalo():
    intervalo = _evento("etapa:0:1440", "retorno", minutos=11)
    retorno = _evento("etapa:0:1620", "participacao", minutos=14, rotulo="Retorno e participação")
    assert _casar("Depois do intervalo, a Tarde Serena continua.", intervalo, retorno).situacao == "livre"
    assert _casar("Depois do intervalo, a Tarde Serena continua.", retorno).situacao == "violacao"
    assert _casar("Depois do intervalo, tem recado de ouvinte.", intervalo, retorno).evento == retorno
    assert _casar("Depois do intervalo, tem recado de ouvinte.", retorno).situacao == "violacao"
    assert _casar("Depois do intervalo, tem entrevista.", intervalo, retorno).situacao == "violacao"


def test_u4_musica_so_confirmada_e_mais_musica():
    assert _casar("A seguir, Areia Fina.", musica=True).situacao == "livre"
    assert _casar("Já já vem Moinho Antigo.", musica=False).situacao == "violacao"
    assert _casar("Daqui a pouco tem mais música.").situacao == "livre"
    assert _casar("Daqui a pouco tem mais música.", tem_musica=False).situacao == "violacao"
    assert _casar("Seguimos com o papo, já já tem mais rádio.").situacao == "livre"


def test_u4_fora_volta_pela_grade_e_conteudo_de_amanha():
    terca = datetime.date(2026, 11, 10)
    so_terca = _programa(dias_semana=[1])            # terça
    todo_dia = _programa(dias_semana=[])
    for programa, esperado in ((todo_dia, "livre"), (so_terca, "violacao")):
        situacao = dict(data=terca, volta_em=lambda d, prog=programa: p.programa_volta_em(prog, d))
        assert _casar("Obrigado pela companhia, até amanhã.", **situacao).situacao == esperado
        assert _casar("Amanhã, no mesmo horário, a Rádio Serra Clara está aqui de novo.", **situacao).situacao \
            == esperado
    assert _casar("Amanhã tem mais recado de ouvinte.").situacao == "violacao"
    assert _casar("Amanhã tem receita de bolo.").situacao == "violacao"
    especifica = _programa(data_especifica=terca)
    assert not p.programa_volta_em(especifica, terca + datetime.timedelta(days=1))


@pytest.mark.parametrize("fala", [
    "Segundo a federação, o próximo jogo será amanhã, às dezesseis horas.",
    "Conforme a prefeitura, a obra começa amanhã.",
    "De acordo com a organização, o festival ocorre semana que vem.",
])
def test_data_futura_em_relato_atribuido_nao_e_promessa_da_emissora(fala):
    assert p.detectar(fala) == []


@pytest.mark.parametrize("fala", [
    "Segundo a agenda, amanhã teremos uma surpresa aqui no programa.",
    "Segundo a produção, amanhã vamos mostrar uma surpresa.",
    "Conforme a programação, amanhã tem mais recado de ouvinte.",
])
def test_atribuicao_nao_libera_promessa_de_conteudo_da_emissora(fala):
    assert _casar(fala).situacao == "violacao"


def test_u4_teto_de_promessas_abertas():
    retorno = _evento("etapa:0:1620", "participacao", minutos=14)
    assert _casar("Daqui a pouco tem recado.", retorno, abertas=2).situacao == "evento"
    teto = _casar("Daqui a pouco tem recado.", retorno, abertas=p.CONFIG_PROMESSAS.max_promessas_abertas)
    assert teto.situacao == "violacao" and teto.motivo == "teto_de_promessas"


def test_u4_avaliar_conta_o_teto_dentro_da_fala():
    retorno = _evento("etapa:0:1620", "participacao", minutos=14)
    situacao = p.SituacaoAgenda(agenda=(retorno,), instante=INSTANTE, abertas=2)
    resultado = p.avaliar("Daqui a pouco tem recado. Mais tarde tem mais recado.", situacao)
    assert [c.situacao for _, c in resultado] == ["evento", "violacao"]


def test_u4_textos_de_contingencia_sem_nova_promessa():
    for tipo, rotulo in (("participacao", ""), ("quadro", "Cantinho da Casa"), ("informacao", "o trânsito"),
                         ("generico", "a receita")):
        texto = p.texto_contingencia(tipo, rotulo, "Rádio Vila Ventura")
        assert p.detectar(texto) == [], texto
        assert "{" not in texto
    assert p.texto_contingencia("participacao", "", "") == \
        "Ainda não chegou recado para ler agora; o WhatsApp da rádio segue aberto."
    assert p.texto_contingencia("generico", "a receita", "R") == "A receita não vai entrar hoje."


def test_u4_numeros_em_configuracao():
    cfg = p.ConfigPromessas(prazo_curto_s=60)
    retorno = _evento("etapa:0:1620", "participacao", minutos=14)
    situacao = p.SituacaoAgenda(agenda=(retorno,), instante=INSTANTE)
    assert p.casar(_uma("Daqui a pouco tem recado."), situacao, config=cfg).situacao == "violacao"


# --- U6: benchmark --------------------------------------------------------------------------------------

_TIPO_BENCHMARK = {"intervalo": "retorno", "retorno": "participacao", "participacao": "participacao",
                   "quadro": "quadro", "servico": "informacao", "noticia": "informacao"}


def _situacao_do_caso(caso):
    fixture = json.loads((FIXTURES / f"{caso['formato']}.json").read_text(encoding="utf-8"))
    nomes = (fixture["conta"]["nome_radio"], fixture["programa"]["nome"], fixture["radialista"]["nome_locutor"])
    agenda = []
    for i, evento in enumerate(caso["contexto"]["eventos_agendados"] or []):
        tipo = _TIPO_BENCHMARK.get(evento["tipo"])
        if tipo is not None:
            agenda.append(p.EventoAgendado(chave=f"caso:{i}", tipo=tipo, rotulo=evento.get("rotulo", ""),
                                           conteudo=evento.get("conteudo", ""),
                                           cancelado=evento.get("status") == "cancelado"))
    return p.SituacaoAgenda(agenda=tuple(agenda), nomes_programa=nomes), nomes


def _musica_do_caso(caso, nomes):
    from app.live.contexto import MusicaRef
    from app.live.validacao_fala import confirmada, mencoes_musica

    ctx = caso["contexto"]
    rotulos = [x for x in [ctx.get("proxima_confirmada"), *(ctx.get("tocou") or [])] if x]
    permitidas = [x.rpartition(" - ")[0] or x for x in rotulos]
    citaveis = [MusicaRef(x.rpartition(" - ")[0], x.rpartition(" - ")[2], origem="conhecida")
                for x in rotulos + [pd.get("musica") for pd in ctx.get("pedidos") or [] if pd.get("musica")]]

    def julgar(frase):
        mencoes = mencoes_musica(frase, citaveis, list(nomes) + [pd["nome"] for pd in ctx.get("pedidos") or []])
        if not mencoes:
            return None
        return all(confirmada(m, permitidas) for m in mencoes)
    return julgar


def test_u6_benchmark_promessas():
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    acertos, falsos, perdidos, total = 0, [], [], 0
    for caso in casos:
        situacao, nomes = _situacao_do_caso(caso)
        julgar = _musica_do_caso(caso, nomes)
        for fala in caso["falas_rotuladas"]:
            total += 1
            achou = any(c.situacao == "violacao" for _, c in p.avaliar(fala["texto"], situacao, julgar))
            esperado = bool(fala["esperado"]["promessa_sem_evento"])
            if achou and esperado:
                acertos += 1
            elif achou:
                falsos.append((caso["id"], fala["texto"]))
            elif esperado:
                perdidos.append((caso["id"], fala["texto"]))
    assert total == 96  # 35 casos da F0 à F5 e 13 da F6, duas falas cada
    assert (acertos, perdidos, falsos) == (7, [], [])
