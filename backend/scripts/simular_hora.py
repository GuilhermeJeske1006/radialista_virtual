"""Simula uma hora de programa pelo POST /live/{rid}/programas/{pid}/proxima real (F0).

Uso (a partir de backend/):

    PYTHONPATH=. .venv/bin/python scripts/simular_hora.py --programa musical_adulto --saida /tmp/sim/musical_adulto \
        [--modo fake|llm|completo] [--semente 7] [--wpm 162] [--relogio A|B|C|<caminho>] [--antecedencia 2] \
        [--preparo-antecipado-s 90] [--corte agendado|manual] [--relogio-backend fixture|nenhum]
        [--tts duble|nenhum] [--wpm-real 145] [--sem-inicio-previsto] [--formato programa|fixture|<id>]
        [--confirmo-custo]

- fake (padrão): sem rede. LLM, TTS, música, notícia e clima são dublês; a fala dura palavras/wpm.
  --wpm é o ritmo com que o dublê do LLM escreve e estima; sem ele, o mesmo do backend sem calibração
  (app.live.ritmo_voz.wpm_para: padrão do modelo de voz, senão settings.fala_wpm_padrao).
  --tts duble (padrão do CLI desde a F2) liga o dublê de TTS: mp3 silencioso com a duração de uma voz a
  --wpm-real palavras/min; o simulador chama o /tts como o painel, a fala dura o que o áudio mede e o
  backend calibra o ritmo da voz. --tts nenhum reproduz as linhas de base da F0/F1 (simular() mantém
  nenhum como padrão).
- llm: texto real da Anthropic (consome créditos); TTS continua estimado.
- completo: Anthropic + ElevenLabs (consome créditos); mede a duração real do áudio.

--relogio-backend fixture (padrão do CLI desde a F1) grava no programa o relógio da fixture
(app.live.relogio.PRESETS, fonte de verdade) e o backend decide pelo relógio; nenhum reproduz a linha de
base da F0 (a função simular() mantém nenhum como padrão). --sem-inicio-previsto imita o painel antigo.

--formato (F6, D19): programa (padrão) usa o perfil_programacao gravado na fixture, como as linhas de base da F0 à F5;
fixture aplica o campo `formato` da fixture (musical_adulto, popular_sertanejo, variedades_leves), como as rodadas da
F6 em diante; um id do catálogo (ou alias) aplica esse formato. resumo.json ganha o bloco `formato` (auditoria F6 §9).

llm e completo sem --confirmo-custo rodam só o modo fake, imprimem a estimativa e saem com código 3.
Só passe --confirmo-custo com aprovação explícita do usuário. Códigos de saída: 0 simulação concluída
(as métricas não mudam o código), 2 erro ou tentativa de rede no modo fake, 3 falta confirmação.

Saída: <saida>/as_run.json e <saida>/resumo.json, mais uma linha-resumo no stdout. Desenho completo em
docs/melhoria-radio/f0/auditoria.md (§5). Este arquivo não importa app.* no topo: o ambiente (variáveis,
fakeredis) é preparado antes, em main().
"""

import argparse
import collections
import dataclasses
import datetime
import json
import pathlib
import random
import subprocess
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.simulacao.fixtures import FixturePrograma, carregar_catalogo, carregar_fixture, carregar_relogio  # noqa: E402

MODOS = ("fake", "llm", "completo")
FORMATOS_SIMULACAO = ("programa", "fixture")  # ou um id do catálogo (app.live.formatos.ids_aceitos)
CORTES = ("agendado", "manual")
RELOGIOS_BACKEND = ("fixture", "nenhum")
TTS = ("duble", "nenhum")
# Voz do dublê de TTS no CLI: 145 palavras/min, o ritmo com que a F0/F1 mediam a fala e ~10% abaixo do
# padrão do modelo v3 (162): a estimativa do backend começa otimista e a calibração tem o que corrigir.
WPM_REAL_PADRAO = 145
VERSAO_FORMATO = 1
# Revisões por orçamento/repetição fazem o LLM real ser chamado mais vezes que o número de falas.
FATOR_REVISOES_ESTIMADO = 1.2
OBSERVACOES = [
    "O GET /preparo (preparo prévio no servidor) fica de fora: a primeira fala sai do /proxima normal.",
    "Modo fake: o comprimento das falas é sintético (o dublê fala dentro da meta por construção); "
    "só a mecânica é medida (relógio, fila, corte, pedidos, continuidade e detectores).",
    "Música anunciada sem confirmação: o mesmo detector do backend (app/live/validacao_fala.py, F3). Promessa e "
    "participação também (app/live/promessas.py e app/live/participacao.py, F4): promessa vencida e com "
    "contingência vêm da tabela promessas_no_ar e das falas que foram ao ar. Abertura repetida continua o "
    "detector provisório da F0.",
    "Com --tts duble (F2), a fala dura o que o /tts mede num mp3 silencioso à velocidade wpm_real; a calibração "
    "do ritmo por voz começa vazia em cada simulação (pior caso: a primeira hora de uma voz nova).",
    "SQLite em memória e execução sequencial: with_for_update(skip_locked) não é exercitado.",
]


@dataclasses.dataclass
class Resultado:
    as_run: dict
    resumo: dict


def _commit_atual() -> str | None:
    try:
        saida = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5,
                               cwd=pathlib.Path(__file__).resolve().parent)
        return saida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _gravar(caminho: pathlib.Path, dados: dict) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def simular(programa, modo: str = "fake", semente: int = 7, wpm: float | None = None, saida=None, relogio=None,
            antecedencia: int = 2, preparo_antecipado_s: float = 90, corte: str = "agendado",
            relogio_backend: str = "nenhum", inicio_previsto: bool = True, tts: str = "nenhum",
            wpm_real: float | None = None, injecoes_extra=(), pedidos_extra=(), formato: str | None = None) -> Resultado:
    """Roda uma hora de programa. `programa` aceita o id da fixture, o caminho ou um FixturePrograma.

    Pressupõe o ambiente pronto (main() ou tests/conftest.py). Guarda e restaura random global e
    app.dependency_overrides; limpa o fakeredis no início. `injecoes_extra` e `pedidos_extra` (só para testes,
    F4) somam injeções e pedidos aos da fixture sem mudar as três fixtures de linha de base. `formato` (F6): None ou
    "programa" mantém o perfil_programacao da fixture; "fixture" aplica o campo `formato` dela; senão, um id aceito pelo
    catálogo (a referência de orçamento do as-run passa a ser a do catálogo nos dois últimos casos).
    """
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo}")
    if corte not in CORTES:
        raise ValueError(f"corte inválido: {corte}")
    if relogio_backend not in RELOGIOS_BACKEND:
        raise ValueError(f"relogio_backend inválido: {relogio_backend}")
    if tts not in TTS:
        raise ValueError(f"tts inválido: {tts}")
    from contextlib import nullcontext
    from zoneinfo import ZoneInfo

    from freezegun import freeze_time

    import app.main  # noqa: F401 -- carrega o app (e o Sentry) antes do freeze_time: módulo importado durante o
    # congelamento é varrido pelo freezegun na saída, o que dispara imports preguiçosos (numpy.testing) com o
    # relógio já desfeito e deixa o datetime falso preso no Sentry.
    from app.auth.security import criar_token
    from app.config.redis_client import redis_client
    from scripts.simulacao import ambiente, metricas
    from scripts.simulacao.dubles import BloqueioRede, aplicar_dubles
    from scripts.simulacao.emissao import Emissao

    fixture = programa if isinstance(programa, FixturePrograma) else carregar_fixture(programa)
    fixture = _aplicar_formato(fixture, formato)
    if injecoes_extra or pedidos_extra:
        fixture = fixture.model_copy(update={"injecoes": [*fixture.injecoes, *injecoes_extra],
                                             "pedidos": [*fixture.pedidos, *pedidos_extra]})
    relogio_fixture = carregar_relogio(relogio or fixture.relogio)
    catalogo = carregar_catalogo(fixture.catalogo)
    base = fixture.inicio.astimezone(ZoneInfo(fixture.timezone))

    inicio_parede = time.perf_counter()
    estado_random = random.getstate()
    random.seed(semente)
    redis_client.flushall()
    engine, sessao = ambiente.criar_banco()
    wpm = wpm if wpm is not None else ambiente.wpm_do_backend(sessao)
    wpm_real = (wpm_real if wpm_real is not None else wpm) if tts == "duble" else None
    bloqueio = BloqueioRede() if modo == "fake" else None
    try:
        with freeze_time(base - datetime.timedelta(seconds=preparo_antecipado_s)) as relogio_virtual, \
                ambiente.rng_isolado(semente), \
                ambiente.cliente_http(sessao) as client, \
                aplicar_dubles(fixture, catalogo, modo=modo, sessao=sessao, wpm=wpm, semente=semente,
                               tts_wpm_real=wpm_real) as dubles, \
                (bloqueio or nullcontext()):
            cenario = ambiente.semear(sessao, fixture)
            relogio_aplicado = ambiente.aplicar_relogio(sessao, cenario, relogio_fixture, fixture.duracao_programa_s()) \
                if relogio_backend == "fixture" else None
            headers = {"Authorization": f"Bearer {criar_token(cenario.usuario_id)}"}
            emissao = Emissao(
                client=client, headers=headers, sessao=sessao, fixture=fixture, cenario=cenario, dubles=dubles,
                relogio=relogio_virtual, base=base, modo=modo, wpm=wpm, antecedencia=antecedencia,
                preparo_antecipado_s=preparo_antecipado_s, corte=corte, enviar_inicio_previsto=inicio_previsto,
                medir_tts=dubles.tts is not None,
            )
            emissao.executar()
            pedidos = emissao.pedidos_finais()
            promessas = emissao.promessas_finais()
            chamadas_dubles = dubles.chamadas_por_funcao()
            contadores_llm = dict(dubles.llm.contadores)
            instrucao_formato = dubles.llm.instrucao()
    finally:
        random.setstate(estado_random)
        sessao.close()
        engine.dispose()
        redis_client.flushall()

    as_run = {
        "versao": VERSAO_FORMATO,
        "programa": fixture.id,
        "formato": fixture.formato,
        "modo": modo,
        "semente": semente,
        "wpm": wpm,
        "tts": tts,
        "wpm_real": wpm_real,
        "inicio": base.isoformat(),
        "fim_programa": (base + datetime.timedelta(seconds=fixture.duracao_programa_s())).isoformat(),
        "duracao_programa_s": fixture.duracao_programa_s(),
        "relogio": relogio_fixture.model_dump(),
        "relogio_backend": relogio_aplicado,
        "ouvintes": {
            "fixture": [p.nome for p in fixture.pedidos],
            "inexistentes": [i.nome for i in fixture.injecoes if i.tipo == "cita_ouvinte" and i.nome],
        },
        "pedidos": pedidos,
        # F4: promessas_no_ar ao fim, com o bloco de registro e de resolução (e se foram ao ar).
        "promessas": promessas,
        # Nomes próprios que não são música (detector de música anunciada, F3).
        "nomes_nao_musica": _nomes_nao_musica(fixture),
        "blocos_nao_tocados": emissao.nao_tocados,
        "eventos": emissao.eventos,
        "observacoes": OBSERVACOES,
    }
    metricas.anotar_eventos(as_run, dubles.musicas.citaveis())
    calculadas = metricas.calcular_metricas(as_run)

    falas = [e for e in emissao.eventos if e["tipo"] == "fala"]
    contagem = emissao.contagem
    revisoes = contadores_llm.get("revisoes", 0)
    total_llm = contadores_llm.get("gerar_resposta", 0) + contadores_llm.get("gerar_dialogo_multivoz", 0)
    blocos_musica_llm = contadores_llm.get("blocos_musica_llm", 0)
    resumo = {
        "config": {
            "modo": modo, "semente": semente, "wpm": wpm, "tts": tts, "wpm_real": wpm_real,
            "antecedencia": antecedencia,
            "preparo_antecipado_s": preparo_antecipado_s, "corte": corte, "fixture": fixture.id,
            "relogio": relogio_fixture.id, "relogio_backend": relogio_backend, "inicio_previsto": inicio_previsto,
            "commit": _commit_atual(), "versao_formato": VERSAO_FORMATO, "formato": formato or "programa",
            "perfil_programacao": fixture.programa.get("perfil_programacao"),
        },
        "chamadas_proxima": contagem["chamadas_proxima"],
        "chamadas_llm": {
            "total": total_llm,
            "falas": contadores_llm.get("falas", 0),
            "revisoes": revisoes,
        },
        "orcamento_fala": _custo_orcamento(emissao.blocos, contadores_llm),
        "chamadas_tts": contagem["chamadas_tts"],
        "caracteres_tts": contagem["caracteres_tts"],
        "caracteres_tts_estimados": sum(len(f["texto"]) for f in falas),
        "tentativas_rede": bloqueio.tentativas if bloqueio else 0,
        "destinos_rede": bloqueio.destinos[:10] if bloqueio else [],
        "erros_http": contagem["erros_http"],
        "confirmacoes_pedido": contagem["confirmacoes_pedido"],
        "blocos_gerados": len(emissao.blocos),
        "blocos_nao_tocados": contagem["blocos_nao_tocados"],
        "blocos_fala_nao_tocados": sum(1 for b in emissao.nao_tocados if b["texto"]),
        "segundos_cortados": round(sum(e["cortado_s"] for e in emissao.eventos) + contagem["segundos_nao_tocados"], 2),
        "dubles": {
            "faixa_reconhecida_pct": round(100 * contadores_llm.get("faixa_reconhecida", 0) / blocos_musica_llm, 1)
            if blocos_musica_llm else None,
            "tipo_reconhecido_pct": round(100 * contadores_llm.get("tipo_reconhecido", 0) / total_llm, 1)
            if total_llm and modo == "fake" else None,
            "blocos_musica_com_llm": blocos_musica_llm,
            "contadores": chamadas_dubles,
        },
        **{k: v for k, v in calculadas.items() if k != "pedidos"},
        "pedidos": calculadas["pedidos"],
        "wpm_observado": _wpm_observado(falas) if modo == "completo" else None,
        "observacoes": OBSERVACOES,
    }
    resumo["injecao"] = _injecao(resumo, chamadas_dubles, fixture, emissao.eventos)
    # F6: coerência com o formato que o backend resolveu para o programa (app.live.formatos.coerencia).
    resumo["formato"] = metricas.metricas_formato(
        as_run, formato=fixture.formato_backend.id, quadros=fixture.quadros(),
        nomes=(str(fixture.programa.get("nome", "")), fixture.conta.nome_radio), instrucao=instrucao_formato)
    resumo["tempo_execucao_s"] = round(time.perf_counter() - inicio_parede, 2)

    if saida is not None:
        pasta = pathlib.Path(saida)
        pasta.mkdir(parents=True, exist_ok=True)
        _gravar(pasta / "as_run.json", as_run)
        _gravar(pasta / "resumo.json", resumo)
    return Resultado(as_run=as_run, resumo=resumo)


def _aplicar_formato(fixture: FixturePrograma, formato: str | None) -> FixturePrograma:
    """F6 (D19): "programa" (ou None) não muda nada; "fixture" grava o campo `formato` da fixture em
    programa.perfil_programacao, como injecoes_extra faz, sem tocar no arquivo; um id aceito pelo catálogo grava esse
    id. Fora disso, ValueError."""
    if formato in (None, "programa"):
        return fixture
    from app.live.formatos import ids_aceitos

    valor = fixture.formato if formato == "fixture" else formato
    if valor not in ids_aceitos():
        raise ValueError(f"formato inválido para a simulação: {valor} (aceitos: programa, fixture, "
                         f"{', '.join(sorted(ids_aceitos()))})")
    return fixture.model_copy(update={"programa": {**fixture.programa, "perfil_programacao": valor},
                                      "orcamento_do_catalogo": True})


def _injecao(resumo: dict, contadores: dict, fixture, eventos: list[dict]) -> dict:
    """F5: texto externo da fixture no system ou fora do bloco de dados (o dublê confere em cada chamada), frases
    com ordem embutida tiradas pela limpeza e a afirmação pedida pela injeção que foi ao ar."""
    pedidas = [i.frase for i in fixture.injecoes if i.tipo == "obedece_injecao" and i.frase]
    falas = [e["texto"] for e in eventos if e["tipo"] == "fala"]
    return {
        **resumo.get("injecao", {}),
        "no_system": contadores.get("injecao_no_system", 0),
        "fora_do_bloco": contadores.get("injecao_fora_do_bloco", 0),
        "obedecida_no_ar": sum(1 for texto in falas if any(frase in texto for frase in pedidas)),
    }


def _nomes_nao_musica(fixture) -> list[str]:
    nomes = [fixture.conta.nome_radio, str(fixture.programa.get("nome", "")), fixture.radialista.nome_locutor,
             getattr(fixture.conta, "cidade", "") or "", *fixture.rotulos_quadros.keys(),
             *fixture.rotulos_quadros.values(), *(p.nome for p in fixture.pedidos),
             *(i.nome for i in fixture.injecoes if i.tipo == "cita_ouvinte" and i.nome)]
    return [n for n in dict.fromkeys(nomes) if n]


def _custo_orcamento(blocos, contadores_llm: dict) -> dict:
    """Contadores da F2 por fala gerada (todos os blocos, tocados ou não): reescritas e ajustes que o backend
    devolveu em fala_ajuste, revisões motivadas pela duração (vistas no prompt pelo dublê), chamadas de LLM
    e sínteses (dublê de TTS: /proxima + /tts do painel) por fala."""
    ajustes = collections.Counter((b.segmento or {}).get("fala_ajuste") for b in blocos)
    sinteses = [b.sinteses_tts for b in blocos if b.sinteses_tts is not None]
    return {
        "revisoes_por_duracao": contadores_llm.get("revisoes_duracao", 0),
        "reescritas": ajustes["reescrita"],
        "encurtadas": ajustes["encurtada"],
        "cortadas": ajustes["cortada"],
        "acima_do_teto": ajustes["acima_do_teto"],
        "max_chamadas_llm_por_fala": max((b.chamadas_llm for b in blocos), default=0),
        "max_sinteses_por_fala": max(sinteses, default=0),
        "ressinteses_tts": sum(max(0, n - 1) for n in sinteses),
    }


def _wpm_observado(falas: list[dict]) -> dict | None:
    medidas = [f for f in falas if f.get("duracao_medida_s")]
    if not medidas:
        return None
    palavras = sum(f["palavras"] for f in medidas)
    segundos = sum(f["duracao_medida_s"] for f in medidas)
    return {"voz_do_programa": round(palavras / segundos * 60, 1), "falas_medidas": len(medidas)}


def _linha_resumo(resumo: dict) -> str:
    return (
        f"{resumo['config']['fixture']} modo={resumo['config']['modo']} relogio={resumo['config']['relogio']} "
        f"tempo={resumo['tempo_execucao_s']}s proxima={resumo['chamadas_proxima']} "
        f"llm={resumo['chamadas_llm']['total']} tentativas_rede={resumo['tentativas_rede']} "
        f"fora_orcamento_pct={resumo['fora_orcamento_pct']} anuncio_sem_confirmacao={resumo['anuncio_sem_confirmacao']} "
        f"promessa_vencida={resumo['promessa_vencida']} promessa_sem_registro={resumo['promessa_sem_registro']} "
        f"pedido_indevido={resumo['pedido_indevido']} ouvinte_inexistente={resumo['ouvinte_inexistente']} "
        f"hard_times_perdidos={resumo['hard_times_perdidos']} encerramento_no_ar={resumo['encerramento_no_ar']} "
        f"estouro_fim_s={resumo['estouro_fim_programa_s']} relogio_backend={resumo['config']['relogio_backend']} "
        f"atraso_hard_time_s={resumo['atraso_hard_time_s']} fim_antecipado_s={resumo['fim_antecipado_s']} "
        f"falas_abaixo_minimo={resumo['falas_abaixo_minimo']} tts={resumo['config']['tts']} "
        f"estouro_max_pct={resumo['estouro_max_pct']} acima_teto={resumo['acima_teto_orcamento']} "
        f"max_llm_por_fala={resumo['orcamento_fala']['max_chamadas_llm_por_fala']} "
        f"max_sinteses_por_fala={resumo['orcamento_fala']['max_sinteses_por_fala']} "
        f"formato={resumo['formato']['id']} coerencia_automatica={resumo['formato']['coerencia_automatica']}"
    )


def _linha_estimativa(modo: str, resumo: dict) -> str:
    falas = resumo["chamadas_llm"]["falas"]
    estimadas = round(falas * FATOR_REVISOES_ESTIMADO)
    tts = f" caracteres_tts_estimados={resumo['caracteres_tts_estimados']}" if modo == "completo" else ""
    return (
        f"estimativa modo={modo} programa={resumo['config']['fixture']} falas_llm={falas} "
        f"chamadas_llm_estimadas={estimadas}{tts} tentativas_rede={resumo['tentativas_rede']}. "
        "Nada foi enviado a provedores pagos (rodou só o modo fake). Para rodar de verdade, repita com "
        "--confirmo-custo depois da aprovação explícita do usuário; o preço sai da tabela vigente do provedor."
    )


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simula uma hora de programa da Locufy.")
    parser.add_argument("--programa", required=True, help="id da fixture (ex.: musical_adulto) ou caminho do JSON")
    parser.add_argument("--saida", required=True, help="pasta onde gravar as_run.json e resumo.json")
    parser.add_argument("--modo", choices=MODOS, default="fake")
    parser.add_argument("--semente", type=int, default=7)
    parser.add_argument("--wpm", type=float, default=None,
                        help="ritmo do dublê do LLM (padrão: o do backend sem calibração, wpm_para)")
    parser.add_argument("--relogio", default=None, help="A, B, C ou caminho de um relógio (padrão: o da fixture)")
    parser.add_argument("--antecedencia", type=int, default=2)
    parser.add_argument("--preparo-antecipado-s", type=float, default=90)
    parser.add_argument("--corte", choices=CORTES, default="agendado")
    parser.add_argument("--relogio-backend", choices=RELOGIOS_BACKEND, default="fixture",
                        help="fixture: o backend decide pelo relógio da fixture (F1); nenhum: linha de base da F0")
    parser.add_argument("--tts", choices=TTS, default="duble",
                        help="duble: mp3 silencioso medido pelo /tts (F2); nenhum: linha de base da F0/F1")
    parser.add_argument("--wpm-real", type=float, default=WPM_REAL_PADRAO,
                        help="ritmo real da voz do dublê de TTS, em palavras/min")
    parser.add_argument("--sem-inicio-previsto", action="store_true",
                        help="não envia inicio_previsto em /proxima (painel antigo)")
    parser.add_argument("--formato", default="programa",
                        help="programa (perfil gravado na fixture, linhas de base), fixture (campo formato da fixture, "
                             "rodadas da F6) ou um id do catálogo de formatos")
    parser.add_argument("--confirmo-custo", action="store_true",
                        help="autoriza os modos pagos (só com aprovação explícita do usuário)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    pago_sem_confirmacao = args.modo != "fake" and not args.confirmo_custo
    modo_efetivo = "fake" if pago_sem_confirmacao else args.modo

    from scripts.simulacao.ambiente import preparar_processo

    preparar_processo(modo_efetivo)
    import logging

    import app.main  # noqa: F401 -- configura o logging do backend antes de silenciá-lo
    logging.getLogger().setLevel(logging.WARNING)

    try:
        resultado = simular(
            args.programa, modo=modo_efetivo, semente=args.semente, wpm=args.wpm,
            saida=None if pago_sem_confirmacao else args.saida, relogio=args.relogio,
            antecedencia=args.antecedencia, preparo_antecipado_s=args.preparo_antecipado_s, corte=args.corte,
            relogio_backend=args.relogio_backend, inicio_previsto=not args.sem_inicio_previsto,
            tts=args.tts, wpm_real=args.wpm_real, formato=args.formato,
        )
    except Exception as erro:  # noqa: BLE001 -- o CLI devolve código 2 com a causa
        print(f"erro na simulação: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 2

    if pago_sem_confirmacao:
        print(_linha_estimativa(args.modo, resultado.resumo))
        return 3
    print(_linha_resumo(resultado.resumo))
    if modo_efetivo == "fake" and resultado.resumo["tentativas_rede"] > 0:
        print(f"tentativa de rede no modo fake: {resultado.resumo['destinos_rede']}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
