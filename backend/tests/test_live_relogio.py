"""Relógio da hora, espelho e hard time (F1): modelo, presets e serviço puro (app.live.relogio).

Desenho e numeração dos casos (U1-U21) em docs/melhoria-radio/f1/auditoria.md §6. Tudo com
instante explícito: nenhum teste aqui depende de now() nem do banco.
"""

import datetime
import json
import logging
import pathlib
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.live import relogio as r
from app.live.orcamento import estimar_duracao_s

SP = ZoneInfo("America/Sao_Paulo")
DIR_FIXTURES_RELOGIOS = pathlib.Path(__file__).resolve().parent / "fixtures" / "programas" / "relogios"
COM_PATROCINIO = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0), r.Peca(6, 20.0)), vinheta_encerramento_s=3.0)


def _programa(inicio=(14, 0), fim=(15, 0), **extra):
    campos = dict(id=1, horario_inicio=datetime.time(*inicio), horario_fim=datetime.time(*fim), dias_semana=[],
                  data_especifica=None, feriados_municipais=[], relogio_hora=None)
    campos.update(extra)
    return SimpleNamespace(**campos)


def _em(dia, hora, minuto, segundo=0, fuso=SP):
    return datetime.datetime(2026, 11, dia, hora, minuto, segundo, tzinfo=fuso)


def _planejar(programa, instante, relogio="A", *, executadas=(), pecas=COM_PATROCINIO, musical=False,
              ultima="musica", fuso="America/Sao_Paulo", cfg=r.CONFIG_PADRAO, ja_encerrou=False):
    relogio = r.PRESETS[relogio] if isinstance(relogio, str) else relogio
    return r.planejar(programa, relogio, fuso, instante, formato_musical=musical, ultima_categoria=ultima,
                      ja_encerrou=ja_encerrou, executadas=set(executadas), pecas=pecas, cfg=cfg)


def _ocorrencia(programa, instante, fuso="America/Sao_Paulo"):
    ocorrencia = r.ocorrencia_em(programa, fuso, instante)
    assert ocorrencia is not None
    return ocorrencia


ABERTURA_FEITA = ("0:0:fala:abertura",)


def _relogio(*eventos):
    inicio, saida = 0, []
    for tipo, duracao, natureza, hard in eventos:
        saida.append({"inicio_s": inicio, "duracao_s": duracao, "tipo": tipo, "natureza": natureza,
                      "hard_time": hard, "rotulo": tipo})
        inicio += duracao
    return r.RelogioHora.model_validate({"eventos": saida})


# --- U1-U3: presets, paridade e validação -----------------------------------------------------

def test_u1_presets_somam_uma_hora_com_hard_times_e_naturezas():
    hard_times = {"A": [0, 1440, 3180, 3570], "B": [0, 900, 1080, 2460, 3480], "C": [0, 960, 2460, 3480]}
    for chave, esperados in hard_times.items():
        relogio = r.PRESETS[chave]
        assert relogio.preset == chave
        inicio = 0
        for evento in relogio.eventos:
            assert evento.inicio_s == inicio
            inicio += evento.duracao_s
            if evento.tipo in ("abertura", "manchetes", "intervalo", "passagem", "fechamento"):
                assert evento.natureza == "obrigatorio", (chave, evento.rotulo)
            elif evento.tipo != "entrevista":
                assert evento.natureza == "ajustavel", (chave, evento.rotulo)
        assert inicio == 3600
        assert [e.inicio_s for e in relogio.eventos if e.hard_time] == esperados
    assert r.totais(r.PRESETS["A"]).model_dump() == {"musica_s": 3015, "fala_s": 225, "intervalo_s": 360}
    assert [p.nome for p in r.PRESETS_INFO.values()] == ["Musical com companhia", "Jornal/revista informativa",
                                                          "Morning/variedades"]


def test_u2_paridade_com_fixtures_da_f0():
    campos = ("inicio_s", "duracao_s", "tipo", "natureza", "hard_time")
    arquivos = sorted(DIR_FIXTURES_RELOGIOS.glob("*.json"))
    assert len(arquivos) == 3
    for arquivo in arquivos:
        fixture = json.loads(arquivo.read_text(encoding="utf-8"))
        preset = r.PRESETS[fixture["id"]]
        assert [{c: e[c] for c in campos} for e in fixture["eventos"]] == \
            [{c: getattr(e, c) for c in campos} for e in preset.eventos], arquivo.name
        # A fixture (com campos extras de medição) também é um relógio válido.
        assert r.RelogioHora.model_validate({"eventos": fixture["eventos"]}).eventos == preset.eventos


def _eventos_a():
    return [e.model_dump() for e in r.PRESETS["A"].eventos]


@pytest.mark.parametrize("mexer, trecho", [
    (lambda ev: ev[-1].update(duracao_s=29), "somam 59:59"),
    (lambda ev: ev[-1].update(duracao_s=31), "somam 60:01"),
    (lambda ev: ev[1].update(duracao_s=670), "buraco"),
    (lambda ev: ev[1].update(duracao_s=690), "sobreposição"),
    (lambda ev: ev[2].update(duracao_s=0), "maior que zero"),
    (lambda ev: ev[3].update(inicio_s=3600), "0 a 3599"),
    (lambda ev: ev.extend([dict(ev[0])] * 30), "de 1 a 40 eventos"),
    (lambda ev: ev[0].update(tipo="karaoke"), "Tipo de evento desconhecido"),
])
def test_u3_validacao_com_mensagens_em_portugues(mexer, trecho):
    eventos = _eventos_a()
    mexer(eventos)
    with pytest.raises(ValidationError) as erro:
        r.RelogioHora.model_validate({"eventos": eventos})
    mensagens = " | ".join(r.mensagens_de_erro(erro.value))
    assert trecho in mensagens
    assert "Input should" not in mensagens and "Value error" not in mensagens


def test_u3_json_invalido_no_programa_cai_no_caminho_atual(caplog):
    eventos = _eventos_a()
    eventos[-1]["duracao_s"] = 29
    with caplog.at_level(logging.WARNING, logger="radialista.live.relogio"):
        assert r.relogio_do_programa(_programa(relogio_hora={"eventos": eventos})) is None
    assert "relogio_invalido_no_banco" in caplog.text
    assert r.relogio_do_programa(_programa(relogio_hora=None)) is None
    assert r.relogio_do_programa(_programa(relogio_hora=r.PRESETS["C"].model_dump())) == r.PRESETS["C"]


# --- U4-U9: posição no relógio, virada de hora, meia-noite, fuso, feriado ------------------------

def test_u4_etapa_e_segundos_ate_hard_time():
    programa = _programa()
    ocorrencia = _ocorrencia(programa, _em(10, 14, 0))
    kwargs = {"pecas": COM_PATROCINIO}
    assert r.etapa_em(r.PRESETS["A"], ocorrencia, _em(10, 14, 0, 10), **kwargs).evento.tipo == "abertura"
    assert r.etapa_em(r.PRESETS["A"], ocorrencia, _em(10, 14, 12, 10), **kwargs).evento.tipo == "link"
    assert r.segundos_ate_hard_time(r.PRESETS["A"], ocorrencia, _em(10, 14, 20), **kwargs) == 240


def test_u5_virada_de_hora():
    programa = _programa(fim=(16, 0))
    ocorrencia = _ocorrencia(programa, _em(10, 14, 0))
    passagem = r.etapa_em(r.PRESETS["A"], ocorrencia, _em(10, 14, 59, 50), pecas=COM_PATROCINIO)
    assert passagem.tipo_efetivo == "identificacao"
    compromisso = r.proximo_compromisso(r.PRESETS["A"], ocorrencia, _em(10, 14, 59, 50), pecas=COM_PATROCINIO)
    assert (compromisso.hora, compromisso.evento.tipo, compromisso.tipo_efetivo) == (1, "abertura", "retomada")
    assert (compromisso.inicio - _em(10, 14, 59, 50)).total_seconds() == 10
    plano = _planejar(programa, _em(10, 14, 59, 50), executadas={"0:3570"})
    assert plano.tipo_bloco != "encerramento"
    plano = _planejar(programa, _em(10, 15, 0, 1))
    assert (plano.tipo_bloco, plano.etapa.hora, plano.primeira) == ("retomada", 1, False)
    assert _planejar(programa, _em(10, 15, 59, 40)).acao == "encerramento"


def test_u6_fim_no_meio_do_relogio_e_programa_curto():
    programa = _programa(fim=(15, 30))
    espelho = r.montar_espelho(r.PRESETS["A"], _ocorrencia(programa, _em(10, 14, 0)), pecas=COM_PATROCINIO)
    assert espelho[-1].tipo_efetivo == "encerramento" and espelho[-1].hard_time
    assert espelho[-1].inicio == _em(10, 15, 29, 15) and espelho[-1].fim == _em(10, 15, 30)
    assert all(e.fim <= espelho[-1].inicio for e in espelho[:-1])
    assert [e.evento.tipo for e in espelho if e.hora == 1][:3] == ["abertura", "musica", "link"]

    curto = _programa(fim=(14, 45))
    espelho = r.montar_espelho(r.PRESETS["A"], _ocorrencia(curto, _em(10, 14, 0)), pecas=COM_PATROCINIO)
    assert espelho[-2].evento.rotulo == "Sequência musical D"
    assert espelho[-2].fim == _em(10, 14, 44, 15)
    assert "intervalo" not in [e.evento.tipo for e in espelho if e.inicio >= _em(10, 14, 44, 15)]
    assert sum(e.duracao_s for e in espelho) == 45 * 60


def test_u7_programa_que_cruza_a_meia_noite():
    programa = _programa(inicio=(23, 0), fim=(1, 0))
    instante = _em(11, 0, 0, 5)  # quarta, 00:00:05
    ocorrencia = _ocorrencia(programa, instante)
    assert ocorrencia.data == datetime.date(2026, 11, 10)
    etapa = r.etapa_em(r.PRESETS["A"], ocorrencia, instante, pecas=COM_PATROCINIO)
    assert (etapa.hora, etapa.tipo_efetivo) == (1, "retomada")
    assert _planejar(programa, _em(11, 0, 59, 45)).acao == "encerramento"
    assert r.ocorrencia_em(programa, "America/Sao_Paulo", _em(10, 22, 59)) is None
    assert _planejar(programa, _em(10, 22, 59)) is None


def test_u8_fuso_da_radio_e_horario_de_verao():
    programa = _programa(inicio=(13, 0))
    instante = datetime.datetime(2026, 11, 10, 17, 12, 10, tzinfo=datetime.timezone.utc)
    em_sp = r.etapa_em(r.PRESETS["A"], _ocorrencia(programa, instante), instante)
    ocorrencia_manaus = _ocorrencia(programa, instante, "America/Manaus")
    em_manaus = r.etapa_em(r.PRESETS["A"], ocorrencia_manaus, instante)
    assert (em_sp.hora, em_sp.evento.tipo) == (1, "link")
    assert (em_manaus.hora, em_manaus.evento.tipo) == (0, "link")

    nova_york = ZoneInfo("America/New_York")
    madrugada = _programa(inicio=(0, 30), fim=(2, 30))
    instante = datetime.datetime(2026, 11, 1, 1, 40, tzinfo=nova_york)
    ocorrencia = _ocorrencia(madrugada, instante, "America/New_York")
    assert (ocorrencia.fim - ocorrencia.inicio).total_seconds() == 3 * 3600
    espelho = r.montar_espelho(r.PRESETS["A"], ocorrencia)
    assert max(e.hora for e in espelho) == 2
    assert _planejar(madrugada, instante, fuso="America/New_York") is not None


def test_u9_feriados():
    programa = _programa()
    feriado, comum = _em(15, 14, 24), _em(16, 14, 24)
    assert _planejar(programa, feriado).tipo_bloco == _planejar(programa, comum).tipo_bloco == "patrocinador:5"

    sem_intervalos = r.PRESETS["A"].model_copy(update={"em_feriado": "sem_intervalos"})
    assert _planejar(programa, feriado, sem_intervalos, executadas=ABERTURA_FEITA + ("0:720",)).acao == "musica"
    assert _planejar(programa, comum, sem_intervalos).tipo_bloco == "patrocinador:5"

    sem_relogio = r.PRESETS["A"].model_copy(update={"em_feriado": "sem_relogio"})
    assert _planejar(programa, feriado, sem_relogio) is None
    assert r.relogio_do_programa(_programa(relogio_hora=sem_relogio.model_dump()), datetime.date(2026, 11, 15)) is None

    # A data que vale é a da ocorrência: 23:00 do dia 14 até 01:00 do 15 não é feriado.
    noturno = _programa(inicio=(23, 0), fim=(1, 0))
    assert _planejar(noturno, _em(15, 0, 30), sem_relogio) is not None

    municipal = _programa(feriados_municipais=[{"data": "11-10", "nome": "Aniversário da cidade"}])
    assert _planejar(municipal, _em(10, 14, 24), sem_relogio) is None


# --- U10-U16: backtiming, orçamento, debate, música, intervalo, deslocamento, encerramento -------

def test_u10_backtiming_desconta_obrigatorios_sem_hard_time():
    relogio = _relogio(("abertura", 60, "obrigatorio", True), ("musica", 1740, "ajustavel", False),
                       ("link", 60, "obrigatorio", False), ("musica", 1680, "ajustavel", False),
                       ("passagem", 60, "obrigatorio", True))
    programa = _programa()
    ocorrencia = _ocorrencia(programa, _em(10, 14, 0))
    assert r.espaco_livre(relogio, ocorrencia, _em(10, 14, 10), set()) == 3540 - 600 - 60
    assert r.espaco_livre(relogio, ocorrencia, _em(10, 14, 10), {"0:1800"}) == 3540 - 600
    plano = _planejar(programa, _em(10, 14, 10), relogio, executadas=ABERTURA_FEITA)
    assert (plano.acao, plano.espaco_s, plano.duracao_max_musica_s) == ("musica", 2880, 1260)


def _relogio_link_antes_do_intervalo():
    return _relogio(("abertura", 40, "obrigatorio", True), ("musica", 680, "ajustavel", False),
                    ("link", 35, "ajustavel", False), ("intervalo", 180, "obrigatorio", True),
                    ("musica", 2635, "ajustavel", False), ("passagem", 30, "obrigatorio", True))


def test_u11_orcamento_do_link():
    programa = _programa()
    relogio = _relogio_link_antes_do_intervalo()
    no_horario = _planejar(programa, _em(10, 14, 12, 0), relogio, executadas=ABERTURA_FEITA)
    assert (no_horario.tipo_bloco, no_horario.acao, no_horario.orcamento_s) == ("comentario", "fala", (10, 35))
    apertado = _planejar(programa, _em(10, 14, 12, 17), relogio, executadas=ABERTURA_FEITA)
    assert (apertado.acao, apertado.orcamento_s, apertado.palavras_max) == ("fala_reduzida", (10, 18), 43)
    sem_espaco = _planejar(programa, _em(10, 14, 12, 28), relogio, executadas=ABERTURA_FEITA)
    assert sem_espaco.tipo_bloco != "comentario" or sem_espaco.acao == "reserva"
    assert "0:720" in sem_espaco.puladas
    musical = _planejar(programa, _em(10, 14, 12, 0), relogio, executadas=ABERTURA_FEITA, musical=True)
    assert (musical.tipo_bloco, musical.orcamento_s, musical.palavras_max) == ("retomada", (6, 12), 25)


@pytest.mark.parametrize("chave", ["A", "B", "C"])
@pytest.mark.parametrize("musical", [False, True])
def test_u11_nenhum_plano_com_orcamento_abaixo_do_minimo(chave, musical):
    programa = _programa()
    pecas = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0),), tem_fonte_noticia=True)
    for segundo in range(0, 3620, 7):
        plano = _planejar(programa, _em(10, 14, 0) + datetime.timedelta(seconds=segundo), chave, pecas=pecas,
                          musical=musical)
        for candidato in (plano, plano.alternativa):
            if candidato is not None and candidato.orcamento_s is not None:
                minimo, maximo = candidato.orcamento_s
                assert maximo >= minimo, (segundo, candidato.acao, candidato.tipo_bloco)
                if musical:
                    assert candidato.palavras_max <= maximo * 145 // 60
                else:
                    assert candidato.palavras_max == maximo * 145 // 60


def test_u12_debate_estourou_gera_fechamento_curto():
    programa = _programa()
    instante = _em(10, 14, 15, 50)  # 10 s antes do intervalo de 16:00 do relógio C
    plano = _planejar(programa, instante, "C", executadas=("0:0:fala:abertura",), ultima="comentario")
    assert (plano.acao, plano.orcamento_s, plano.instrucao) == ("fechamento_curto", (6, 10), "fechamento_curto")
    assert plano.chave_estado == "0:600:fechamento_curto"
    sem_conversa = _planejar(programa, instante, "C", executadas=("0:0:fala:abertura",), ultima="musica")
    assert sem_conversa.acao != "fechamento_curto" and sem_conversa.tipo_bloco != "comentario"
    repetido = _planejar(programa, instante, "C", executadas=("0:0:fala:abertura", "0:600:fechamento_curto"),
                         ultima="comentario")
    assert repetido.acao != "fechamento_curto"


def test_u13_musica_teto_e_alternativas(caplog):
    programa = _programa()
    instante = _em(10, 14, 20, 0)  # 240 s antes do intervalo de 14:24
    feito = ABERTURA_FEITA + ("0:720",)
    plano = _planejar(programa, instante, executadas=feito)
    # Teto = espaço + folga (3 s: a pausa entre blocos ainda cabe nos 5 s de tolerância do hard time).
    assert (plano.acao, plano.duracao_max_musica_s) == ("musica", 243)
    # Sobra que nem faixa (mín. 200 s) nem preenchimento (60 s) + adiantamento (90 s) cobrem.
    assert plano.sobra_proibida_s == (150, 200)
    assert (plano.alternativa.acao, plano.alternativa.tipo_bloco) == ("reserva", "identificacao")
    plano = _planejar(programa, instante, executadas=feito + ("0:755:reserva",))
    assert (plano.alternativa.acao, plano.alternativa.tipo_bloco) == ("reserva", "comentario")
    plano = _planejar(programa, instante, executadas=feito + ("0:755:reserva",), musical=True)
    assert (plano.alternativa.acao, plano.alternativa.tipo_bloco) == ("adiantamento", "patrocinador:5")
    assert plano.alternativa.forcado is True  # 240 s > adiantamento_max_s: documentado e registrado
    assert "relogio_adiantamento_acima_do_maximo" in caplog.text

    perto = _planejar(programa, _em(10, 14, 22, 40), executadas=feito + ("0:755:reserva", "0:755:preenchimento"))
    assert (perto.acao, perto.tipo_bloco, perto.forcado) == ("adiantamento", "patrocinador:5", False)
    assert r.musica_cabe(240, plano) and not r.musica_cabe(244, plano)
    assert not r.musica_cabe(60, plano) and r.musica_cabe(60, plano, estrito=False)
    assert r.duracao_preferida_musica_s(plano) == 243  # espaço para uma faixa só
    longe = _planejar(programa, _em(10, 14, 13), executadas=feito)
    assert r.duracao_preferida_musica_s(longe) == 660 - 200  # deixa lugar para outra música
    # Antes de uma etapa ajustável, a faixa pode avançar no máximo 60 s sobre ela.
    assert _planejar(programa, _em(10, 14, 10), executadas=ABERTURA_FEITA).duracao_max_musica_s == 120 + 60


def test_u14_intervalo_por_patrocinador():
    programa = _programa()
    instante = _em(10, 14, 24, 0)
    primeiro = _planejar(programa, instante)
    assert (primeiro.acao, primeiro.tipo_bloco, primeiro.chave_estado) == \
        ("intervalo", "patrocinador:5", "0:1440:patrocinador:5")
    segundo = _planejar(programa, instante + datetime.timedelta(seconds=30), executadas={"0:1440:patrocinador:5"})
    assert segundo.tipo_bloco == "patrocinador:6"
    depois = _planejar(programa, instante + datetime.timedelta(seconds=50),
                       executadas={"0:1440:patrocinador:5", "0:1440:patrocinador:6", *ABERTURA_FEITA, "0:720"})
    assert (depois.etapa.evento.tipo, depois.tipo_bloco) == ("retorno", "chamada_ouvinte")
    sem_patrocinio = _planejar(programa, instante, pecas=r.PecasDisponiveis(), executadas=ABERTURA_FEITA + ("0:720",))
    assert sem_patrocinio.acao == "musica" and sem_patrocinio.etapa.tipo_efetivo == "musica"


def test_u15_etapa_deslocada_acontece_antes_do_hard_time():
    programa = _programa()
    atrasado = _planejar(programa, _em(10, 14, 13, 30), executadas=ABERTURA_FEITA)
    assert (atrasado.etapa.chave, atrasado.tipo_bloco, atrasado.chave_estado) == ("0:720", "comentario", "0:720")
    assert _planejar(programa, _em(10, 14, 13, 30), executadas=ABERTURA_FEITA + ("0:720",)).acao == "musica"


def test_u16_encerramento():
    programa = _programa()
    plano = _planejar(programa, _em(10, 14, 59, 30))
    # 30 s − 3 s da vinheta; usa a parte de cima do espaço (janela de 10 s).
    assert (plano.acao, plano.orcamento_s) == ("encerramento", (17, 27))
    assert _planejar(programa, _em(10, 14, 59, 50)).orcamento_s == (15, 15)
    assert _planejar(programa, _em(10, 15, 5)).acao == "encerramento"  # depois do fim, na graça
    assert _planejar(programa, _em(10, 14, 59, 30), musical=True).orcamento_s == (10, 18)
    assert _planejar(programa, _em(10, 14, 59, 30), ja_encerrou=True) is None


def test_u17_instante_fora_da_ocorrencia():
    programa = _programa()
    assert _planejar(programa, _em(10, 13, 59)) is None
    assert _planejar(programa, _em(10, 15, 21)) is None
    assert _planejar(_programa(dias_semana=[0]), _em(10, 14, 10)) is None  # 10/11/2026 é terça


def test_u18_instante_previsto():
    agora = datetime.datetime(2026, 11, 10, 17, 0, tzinfo=datetime.timezone.utc)
    assert r.instante_previsto(None, agora) == (agora, False)
    assert r.instante_previsto(agora - datetime.timedelta(seconds=5), agora) == (agora, True)
    previsto, aceito = r.instante_previsto(datetime.datetime(2026, 11, 10, 17, 10), agora)
    assert (previsto, aceito) == (agora + datetime.timedelta(minutes=10), True)
    assert r.instante_previsto(agora + datetime.timedelta(minutes=31), agora) == (agora, False)


def test_u19_duracao_prevista_bloco():
    assert estimar_duracao_s("[animado] Uma duas três quatro cinco", 150) == 2.0
    fala = SimpleNamespace(tipo="musica", fala="[calmo] " + "palavra " * 29, falas=None, video_id="v1", musicas=[
        SimpleNamespace(inicio_segundos=10, fim_segundos=200, duracao_segundos=240),
        SimpleNamespace(inicio_segundos=0, fim_segundos=None, duracao_segundos=None),
    ], vinheta_encerramento_id=None)
    assert r.duracao_prevista_bloco(fala) == round(29 / 145 * 60 + 190 + 210, 2)
    vinheta = SimpleNamespace(tipo="vinheta", fala="Rádio Teste")
    assert r.duracao_prevista_bloco(vinheta, duracao_peca_s=8) == 8
    assert r.duracao_prevista_bloco(vinheta) == round(2 / 145 * 60, 2)
    encerramento = SimpleNamespace(tipo="encerramento", fala="Até amanhã", falas=None, video_id=None, musicas=[],
                                   vinheta_encerramento_id=3, vinheta_encerramento_texto="Rádio Teste")
    assert r.duracao_prevista_bloco(encerramento, duracao_vinheta_fim_s=9) == round(2 / 145 * 60 + 9, 2)
    assert r.duracao_prevista_fala_s("um dois", 145) == estimar_duracao_s("um dois", 145)


def test_u20_numeros_vem_da_configuracao():
    programa = _programa()
    instante = _em(10, 14, 12, 0)
    unidades = dict(r.UNIDADES_PADRAO, link=(10, 20))
    curto = r.ConfigRelogio(unidades=unidades, wpm=120)
    plano = _planejar(programa, instante, executadas=ABERTURA_FEITA, cfg=curto)
    assert (plano.orcamento_s, plano.palavras_max) == ((10, 20), 40)
    instante = _em(10, 14, 20, 0)
    feito = ABERTURA_FEITA + ("0:720",)
    tolerante = r.ConfigRelogio(folga_teto_s=20)
    assert _planejar(programa, instante, executadas=feito, cfg=tolerante).duracao_max_musica_s == 260
    sem_folga = r.ConfigRelogio(musica_duracao_min_s=170, adiantamento_max_s=60)
    assert _planejar(programa, instante, executadas=feito, cfg=sem_folga).sobra_proibida_s == (120, 170)


def test_u21_estado_no_redis_falha_aberto(monkeypatch, caplog):
    from app.config.redis_client import redis_client

    ocorrencia = _ocorrencia(_programa(), _em(10, 14, 0))
    r.marcar_executada(1, ocorrencia, "0:720", None)
    assert r.etapas_executadas(1, ocorrencia) == {"0:720"}

    def quebrado(*a, **k):
        raise ConnectionError("redis fora")

    monkeypatch.setattr(redis_client, "smembers", quebrado)
    monkeypatch.setattr(redis_client, "sadd", quebrado)
    assert r.etapas_executadas(1, ocorrencia) == set()
    r.marcar_executada(1, ocorrencia, "0:755")
    assert "relogio_estado_indisponivel" in caplog.text and "relogio_estado_nao_gravado" in caplog.text
    assert _planejar(_programa(), _em(10, 14, 12, 0), executadas=r.etapas_executadas(1, ocorrencia)) is not None
