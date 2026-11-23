"""Recalcula as métricas de humanização da fala (H0) sobre um as_run.json gravado.

Uso (a partir de backend/):

    PYTHONPATH=. .venv/bin/python scripts/recalcular_humanizacao.py --as-run <arquivo> [--slogan <texto>]... \
        [--saida <json>]

A linha de base da H0 guarda os textos (os as-runs), não os números: o detector de sinais de IA ainda não existe e o
léxico vai ser calibrado (docs/humanizacao/h0/auditoria.md, fato 1). A H1, a H4 e a H5 rodam este comando nas duas
pontas (linha de base e depois) com o detector da vez, o mesmo do backend (scripts/simulacao/metricas.py,
metricas_humanizacao). Sem rede e sem LLM.

Bordões: os --slogan; sem eles, o slogan da fixture do as-run (tests/fixtures/programas/ ou cenarios/), se houver.
Saída: JSON com o caminho do as-run, os bordões e as métricas, no stdout e em --saida. Códigos: 0 ok, 2 erro.
"""

import argparse
import json
import pathlib
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.simulacao.fixtures import DIR_FIXTURES, carregar_fixture  # noqa: E402

PASTAS_FIXTURE = (DIR_FIXTURES, DIR_FIXTURES / "cenarios")


def _slogan_da_fixture(programa: str | None) -> list[str]:
    for pasta in PASTAS_FIXTURE:
        caminho = pasta / f"{programa}.json"
        if programa and caminho.exists():
            slogan = carregar_fixture(caminho).conta.slogan
            return [slogan] if slogan else []
    return []


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recalcula as métricas de humanização sobre um as_run.json.")
    parser.add_argument("--as-run", required=True, help="as_run.json gravado por scripts/simular_hora.py")
    parser.add_argument("--slogan", action="append", default=None,
                        help="bordão a contar (repita para mais de um); padrão: o slogan da fixture do as-run")
    parser.add_argument("--saida", default=None, help="arquivo JSON onde gravar o resultado")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    from scripts.simulacao.ambiente import preparar_processo

    preparar_processo("fake")
    from scripts.simulacao.metricas import metricas_humanizacao

    caminho = pathlib.Path(args.as_run)
    try:
        as_run = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        print(f"erro ao ler o as-run: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 2
    bordoes = args.slogan if args.slogan is not None else _slogan_da_fixture(as_run.get("programa"))
    resultado = {"as_run": str(caminho), "bordoes": bordoes, **metricas_humanizacao(as_run, bordoes=bordoes)}
    texto = json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.saida:
        pathlib.Path(args.saida).write_text(texto, encoding="utf-8")
    print(texto, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
