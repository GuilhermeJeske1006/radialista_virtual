"""Relógio da hora com promessas (F4, U9 da auditoria §8): `Plano.seguintes` e obrigações no backtiming.

Sem obrigação, o plano é o mesmo de antes da F4: o retrato da grade dos presets A, B e C
(`fixtures/relogio_planos_sem_obrigacao.json`) foi gravado no código anterior à mudança.
"""

import dataclasses
import datetime
import json
import logging
import os
import pathlib
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.live import relogio as r

SP = ZoneInfo("America/Sao_Paulo")
GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "relogio_planos_sem_obrigacao.json"
COM_PATROCINIO = r.PecasDisponiveis(patrocinadores=(r.Peca(5, 30.0), r.Peca(6, 20.0)), vinheta_encerramento_s=3.0,
                                    vinhetas_passagem=(r.Peca(9, 6.0),), tem_fonte_noticia=True,
                                    quadros=("Quadro da Receita",))
ABERTURA_FEITA = ("0:0:fala:abertura",)


def _programa():
    return SimpleNamespace(id=1, horario_inicio=datetime.time(14, 0), horario_fim=datetime.time(15, 0),
                           dias_semana=[], data_especifica=None, feriados_municipais=[], relogio_hora=None)


def _em(hora, minuto, segundo=0):
    return datetime.datetime(2026, 11, 10, hora, minuto, segundo, tzinfo=SP)


def _planejar(instante, relogio="A", executadas=ABERTURA_FEITA, pecas=COM_PATROCINIO, **extra):
    relogio = r.PRESETS[relogio] if isinstance(relogio, str) else relogio
    return r.planejar(_programa(), relogio, "America/Sao_Paulo", instante, formato_musical=extra.pop("musical", False),
                      ultima_categoria=extra.pop("ultima", "musica"), ja_encerrou=False, executadas=set(executadas),
                      pecas=pecas, **extra)


def _retrato(plano):
    if plano is None:
        return None
    campos = {}
    for campo in dataclasses.fields(plano):
        if campo.name in ("seguintes", "obrigacoes", "instante", "ocorrencia"):
            continue
        valor = getattr(plano, campo.name)
        if campo.name in ("etapa", "proximo_compromisso"):
            valor = valor.chave if valor is not None else None
        elif campo.name == "alternativa":
            valor = _retrato(valor)
        elif isinstance(valor, tuple):
            valor = list(valor)
        campos[campo.name] = valor
    return campos


def _grade():
    retratos = {}
    for preset in ("A", "B", "C"):
        for musical in (False, True):
            for segundo in range(30, 3600, 45):
                instante = _em(14, 0) + datetime.timedelta(seconds=segundo)
                plano = _planejar(instante, preset, musical=musical)
                retratos[f"{preset}:{int(musical)}:{segundo}"] = _retrato(plano)
    return retratos


def test_u9_sem_obrigacao_o_plano_fica_igual_na_grade_dos_presets():
    retratos = json.loads(json.dumps(_grade()))
    if os.environ.get("ATUALIZAR_GOLDEN") == "1" or not GOLDEN.exists():
        if os.environ.get("ATUALIZAR_GOLDEN") != "1":
            pytest.fail(f"golden ausente: {GOLDEN.name} (rode com ATUALIZAR_GOLDEN=1)")
        GOLDEN.write_text(json.dumps(retratos, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return
    assert retratos == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_u9_seguintes_excluem_as_concluidas():
    plano = _planejar(_em(14, 13), "A", executadas=ABERTURA_FEITA + ("0:720",))
    chaves = [e.chave for e in plano.seguintes]
    assert "0:720" not in chaves and "0:0" not in chaves
    assert chaves[0] == "0:1440" and "0:1620" in chaves and chaves[-1] == "0:3570"
    assert all(e.inicio >= plano.etapa.inicio for e in plano.seguintes)
    assert plano.etapa.chave not in chaves


def _relogio_participacao_antes_do_intervalo():
    eventos, inicio = [], 0
    for tipo, duracao, natureza, hard in (("abertura", 60, "obrigatorio", True), ("musica", 500, "ajustavel", False),
                                          ("participacao", 40, "ajustavel", False),
                                          ("intervalo", 120, "obrigatorio", True), ("musica", 2850, "ajustavel", False),
                                          ("passagem", 30, "obrigatorio", True)):
        eventos.append({"inicio_s": inicio, "duracao_s": duracao, "tipo": tipo, "natureza": natureza,
                        "hard_time": hard, "rotulo": tipo})
        inicio += duracao
    return r.RelogioHora.model_validate({"eventos": eventos})


def test_u9_obrigacao_reserva_a_unidade_e_encolhe_a_musica():
    relogio = _relogio_participacao_antes_do_intervalo()
    instante = _em(14, 6, 40)  # 400 s: música; a participação (560 s) vem antes do intervalo (600 s)
    livre = _planejar(instante, relogio)
    obrigado = _planejar(instante, relogio, obrigacoes=frozenset({"0:560"}))
    assert (livre.acao, obrigado.acao) == ("musica", "musica")
    # Reserva o máximo da unidade de participação, limitado à duração da etapa (40 s).
    assert obrigado.espaco_s == livre.espaco_s - 40
    assert obrigado.duracao_max_musica_s < livre.duracao_max_musica_s
    assert obrigado.obrigacoes == frozenset({"0:560"})
    assert r.relogio_ao_vivo(obrigado, "A", True).obrigacoes == ["0:560"]
    assert r.relogio_ao_vivo(livre, "A", True).obrigacoes is None


def test_u9_etapa_prometida_sem_espaco_gera_log(caplog):
    relogio = _relogio_participacao_antes_do_intervalo()
    caplog.set_level(logging.INFO, logger="radialista.live.relogio")
    # 595 s: 5 s até o intervalo, a participação não cabe (mínimo 20 s) e é pulada.
    plano = _planejar(_em(14, 9, 55), relogio, obrigacoes=frozenset({"0:560"}))
    assert "0:560" in plano.puladas
    assert "relogio_promessa_pulada" in caplog.text and "0:560" in caplog.text
