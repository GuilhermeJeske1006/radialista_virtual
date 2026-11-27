"""Custo real por hora e margem a partir dos logs de produção (llm_consumo e tts_consumo).

    ssh ubuntu@VPS "cd /opt/locufy && docker compose logs -t --no-log-prefix --since 2026-11-30T14:55:00Z \
        --until 2026-11-30T17:05:00Z backend" | python scripts/custo_log.py --horas 2 [--dias-mes 22 --horas-dia 2]

Lê stdin. `--horas` é a duração do programa no período (padrão: do primeiro ao último log de consumo). Mostra tokens
e USD por modelo, caracteres e USD de voz, custo por hora e a margem do plano Flex (docs/simulacao-plano-consumo.md):
cliente paga R$ 69,90 + 2 × custo direto; sobra = receita × 0,90 − 1,15 × custo − R$ 52 (base operacional).
Os USD vêm das tarifas do código (settings); a voz usa o preço por mil caracteres de settings, a confirmar na fatura.
"""
import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime

LLM = re.compile(r"llm_consumo modelo=(?P<m>\S+) entrada=(?P<i>\d+) saida=(?P<o>\d+) cache_write=(?P<cw>\d+) "
                 r"cache_read=(?P<cr>\d+) usd=(?P<usd>[\d.]+)")
TTS = re.compile(r"tts_consumo modelo=(?P<m>\S+) caracteres=(?P<c>\d+) usd=(?P<usd>[\d.]+)")
HORA = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")

MENSALIDADE_BRL = 69.90
ACRESCIMO = 2.0  # cobrado = 2 × custo direto
TAXAS = 0.10
RESERVA = 0.15
BASE_OPERACIONAL_BRL = 52.0


def ler(linhas):
    llm = defaultdict(lambda: dict(chamadas=0, entrada=0, saida=0, cache_write=0, cache_read=0, usd=0.0))
    tts = defaultdict(lambda: dict(chamadas=0, caracteres=0, usd=0.0))
    horas = []
    for linha in linhas:
        if m := LLM.search(linha):
            d = llm[m["m"]]
            d["chamadas"] += 1
            d["entrada"] += int(m["i"])
            d["saida"] += int(m["o"])
            d["cache_write"] += int(m["cw"])
            d["cache_read"] += int(m["cr"])
            d["usd"] += float(m["usd"])
        elif m := TTS.search(linha):
            d = tts[m["m"]]
            d["chamadas"] += 1
            d["caracteres"] += int(m["c"])
            d["usd"] += float(m["usd"])
        else:
            continue
        if t := HORA.match(linha):
            horas.append(datetime.fromisoformat(t[1]))
    return llm, tts, horas


def margem(custo_hora_brl: float, horas_mes: float) -> dict:
    custo = custo_hora_brl * horas_mes
    receita = MENSALIDADE_BRL + ACRESCIMO * custo
    sobra = receita * (1 - TAXAS) - (1 + RESERVA) * custo - BASE_OPERACIONAL_BRL
    return {"custo_mes": custo, "receita": receita, "sobra": sobra, "margem": sobra / receita if receita else 0.0,
            "cobrado_hora": ACRESCIMO * custo_hora_brl}


def main(argv=None, entrada=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--horas", type=float, default=None, help="duração do programa no período, em horas")
    ap.add_argument("--cambio", type=float, default=5.5)
    ap.add_argument("--dias-mes", type=int, default=22)
    ap.add_argument("--horas-dia", type=float, default=2.0)
    a = ap.parse_args(argv)
    llm, tts, instantes = ler(entrada if entrada is not None else sys.stdin)
    if not llm and not tts:
        print("Nenhum llm_consumo/tts_consumo no período.")
        return 1
    horas = a.horas or max((max(instantes) - min(instantes)).total_seconds() / 3600, 1 / 60)
    print(f"Período: {horas:.2f} h de programa\n")
    total_llm = sum(d["usd"] for d in llm.values())
    total_tts = sum(d["usd"] for d in tts.values())
    print("LLM")
    for modelo, d in sorted(llm.items(), key=lambda kv: -kv[1]["usd"]):
        med = d["entrada"] / d["chamadas"]
        print(f"  {modelo:22s} {d['chamadas']:4d} chamadas  entrada média {med:7.0f}  saída {d['saida']:6d}  "
              f"cache escrita {d['cache_write']:7d}  leitura {d['cache_read']:7d}  US$ {d['usd']:.3f}  "
              f"(US$ {d['usd'] / horas:.2f}/h)")
    print("Voz")
    for modelo, d in tts.items():
        print(f"  {modelo:22s} {d['chamadas']:4d} falas  {d['caracteres']:7d} caracteres  US$ {d['usd']:.3f}  "
              f"({d['caracteres'] / horas:.0f} caracteres/h)")
    total = total_llm + total_tts
    por_hora = total / horas
    print(f"\nCusto por hora de programa: US$ {por_hora:.2f}  (LLM {total_llm / horas:.2f} + voz {total_tts / horas:.2f})")
    lidas = sum(d["cache_read"] for d in llm.values())
    ent = sum(d["entrada"] for d in llm.values())
    if lidas or sum(d["cache_write"] for d in llm.values()):
        print(f"Cache de prompt: {100 * lidas / max(lidas + ent, 1):.0f}% dos tokens de entrada lidos do cache")
    brl_h = por_hora * a.cambio
    m = margem(brl_h, a.dias_mes * a.horas_dia)
    print(f"Em reais: R$ {brl_h:.2f}/h de custo, R$ {m['cobrado_hora']:.2f}/h cobrado (2×; o site promete ≈ R$ 8,35/h)")
    print(f"Mensal ({a.dias_mes} dias × {a.horas_dia:g} h): custo R$ {m['custo_mes']:.0f}, cliente paga R$ {m['receita']:.0f} "
          f"(mensalidade R$ 69,90 + uso), sobra R$ {m['sobra']:.0f}, margem {100 * m['margem']:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
