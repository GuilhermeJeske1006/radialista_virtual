"""Simula uma hora de programa pelo POST /live/{rid}/programas/{pid}/proxima real (F0).

Uso (a partir de backend/):

    PYTHONPATH=. .venv/bin/python scripts/simular_hora.py --programa musical_adulto --saida /tmp/sim/musical_adulto \
        [--modo fake|llm|completo] [--semente 7] [--wpm 162] [--relogio A|B|C|<caminho>] [--antecedencia 2] \
        [--preparo-antecipado-s 90] [--corte agendado|manual] [--relogio-backend fixture|nenhum]
        [--sem-inicio-previsto] [--confirmo-custo]

- fake (padrão): sem rede. LLM, TTS, música, notícia e clima são dublês; a fala dura palavras/wpm.
  --wpm é o ritmo com que o dublê do LLM escreve e estima; sem ele, o mesmo do backend sem calibração
  (app.live.ritmo_voz.wpm_para: padrão do modelo de voz, senão settings.fala_wpm_padrao).
- llm: texto real da Anthropic (consome créditos); TTS continua estimado.
- completo: Anthropic + ElevenLabs (consome créditos); mede a duração real do áudio.

--relogio-backend fixture (padrão do CLI desde a F1) grava no programa o relógio da fixture
(app.live.relogio.PRESETS, fonte de verdade) e o backend decide pelo relógio; nenhum reproduz a linha de
base da F0 (a função simular() mantém nenhum como padrão). --sem-inicio-previsto imita o painel antigo.

llm e completo sem --confirmo-custo rodam só o modo fake, imprimem a estimativa e saem com código 3.
Só passe --confirmo-custo com aprovação explícita do usuário. Códigos de saída: 0 simulação concluída
(as métricas não mudam o código), 2 erro ou tentativa de rede no modo fake, 3 falta confirmação.

Saída: <saida>/as_run.json e <saida>/resumo.json, mais uma linha-resumo no stdout. Desenho completo em
docs/melhoria-radio/f0/auditoria.md (§5). Este arquivo não importa app.* no topo: o ambiente (variáveis,
fakeredis) é preparado antes, em main().
"""

import argparse
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
CORTES = ("agendado", "manual")
RELOGIOS_BACKEND = ("fixture", "nenhum")
VERSAO_FORMATO = 1
# Revisões por orçamento/repetição fazem o LLM real ser chamado mais vezes que o número de falas.
FATOR_REVISOES_ESTIMADO = 1.2
OBSERVACOES = [
    "O GET /preparo (preparo prévio no servidor) fica de fora: a primeira fala sai do /proxima normal.",
    "Modo fake: o comprimento das falas é sintético (o dublê fala dentro da meta por construção); "
    "só a mecânica é medida (relógio, fila, corte, pedidos, continuidade e detectores).",
    "Detectores de promessa, música anunciada e abertura repetida são provisórios da F0.",
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
            relogio_backend: str = "nenhum", inicio_previsto: bool = True) -> Resultado:
    """Roda uma hora de programa. `programa` aceita o id da fixture, o caminho ou um FixturePrograma.

    Pressupõe o ambiente pronto (main() ou tests/conftest.py). Guarda e restaura random global e
    app.dependency_overrides; limpa o fakeredis no início.
    """
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo}")
    if corte not in CORTES:
        raise ValueError(f"corte inválido: {corte}")
    if relogio_backend not in RELOGIOS_BACKEND:
        raise ValueError(f"relogio_backend inválido: {relogio_backend}")
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
    relogio_fixture = carregar_relogio(relogio or fixture.relogio)
    catalogo = carregar_catalogo(fixture.catalogo)
    base = fixture.inicio.astimezone(ZoneInfo(fixture.timezone))

    inicio_parede = time.perf_counter()
    estado_random = random.getstate()
    random.seed(semente)
    redis_client.flushall()
    engine, sessao = ambiente.criar_banco()
    wpm = wpm if wpm is not None else ambiente.wpm_do_backend(sessao)
    bloqueio = BloqueioRede() if modo == "fake" else None
    try:
        with freeze_time(base - datetime.timedelta(seconds=preparo_antecipado_s)) as relogio_virtual, \
                ambiente.rng_isolado(semente), \
                ambiente.cliente_http(sessao) as client, \
                aplicar_dubles(fixture, catalogo, modo=modo, sessao=sessao, wpm=wpm, semente=semente) as dubles, \
                (bloqueio or nullcontext()):
            cenario = ambiente.semear(sessao, fixture)
            relogio_aplicado = ambiente.aplicar_relogio(sessao, cenario, relogio_fixture, fixture.duracao_programa_s()) \
                if relogio_backend == "fixture" else None
            headers = {"Authorization": f"Bearer {criar_token(cenario.usuario_id)}"}
            emissao = Emissao(
                client=client, headers=headers, sessao=sessao, fixture=fixture, cenario=cenario, dubles=dubles,
                relogio=relogio_virtual, base=base, modo=modo, wpm=wpm, antecedencia=antecedencia,
                preparo_antecipado_s=preparo_antecipado_s, corte=corte, enviar_inicio_previsto=inicio_previsto,
            )
            emissao.executar()
            pedidos = emissao.pedidos_finais()
            chamadas_dubles = dubles.chamadas_por_funcao()
            contadores_llm = dict(dubles.llm.contadores)
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
            "modo": modo, "semente": semente, "wpm": wpm, "antecedencia": antecedencia,
            "preparo_antecipado_s": preparo_antecipado_s, "corte": corte, "fixture": fixture.id,
            "relogio": relogio_fixture.id, "relogio_backend": relogio_backend, "inicio_previsto": inicio_previsto,
            "commit": _commit_atual(), "versao_formato": VERSAO_FORMATO,
        },
        "chamadas_proxima": contagem["chamadas_proxima"],
        "chamadas_llm": {
            "total": total_llm,
            "falas": contadores_llm.get("falas", 0),
            "revisoes": revisoes,
        },
        "chamadas_tts": contagem["chamadas_tts"],
        "caracteres_tts": contagem["caracteres_tts"],
        "caracteres_tts_estimados": sum(len(f["texto"]) for f in falas),
        "tentativas_rede": bloqueio.tentativas if bloqueio else 0,
        "destinos_rede": bloqueio.destinos[:10] if bloqueio else [],
        "erros_http": contagem["erros_http"],
        "confirmacoes_pedido": contagem["confirmacoes_pedido"],
        "blocos_gerados": len(emissao.blocos),
        "blocos_nao_tocados": contagem["blocos_nao_tocados"],
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
    resumo["tempo_execucao_s"] = round(time.perf_counter() - inicio_parede, 2)

    if saida is not None:
        pasta = pathlib.Path(saida)
        pasta.mkdir(parents=True, exist_ok=True)
        _gravar(pasta / "as_run.json", as_run)
        _gravar(pasta / "resumo.json", resumo)
    return Resultado(as_run=as_run, resumo=resumo)


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
        f"promessa_vencida={resumo['promessa_vencida']} pedido_indevido={resumo['pedido_indevido']} "
        f"hard_times_perdidos={resumo['hard_times_perdidos']} encerramento_no_ar={resumo['encerramento_no_ar']} "
        f"estouro_fim_s={resumo['estouro_fim_programa_s']} relogio_backend={resumo['config']['relogio_backend']} "
        f"atraso_hard_time_s={resumo['atraso_hard_time_s']} fim_antecipado_s={resumo['fim_antecipado_s']} "
        f"falas_abaixo_minimo={resumo['falas_abaixo_minimo']}"
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
    parser.add_argument("--sem-inicio-previsto", action="store_true",
                        help="não envia inicio_previsto em /proxima (painel antigo)")
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
