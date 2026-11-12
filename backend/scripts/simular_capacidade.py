"""Picos de rádios contra o controle real, com Redis e provedores simulados.

Executar no backend com dependências de desenvolvimento. Não chama APIs nem usa
credenciais reais. Mede o controle de carga, não a capacidade do servidor em produção.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radios", type=int, nargs="+", default=[1, 5, 10, 25, 50])
    parser.add_argument("--concorrencia", type=int, default=3)
    parser.add_argument("--geracao-s", type=float, default=.03)
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()
    if not (1 <= min(args.radios) <= max(args.radios) <= 200 and 1 <= args.concorrencia <= 50 and .001 <= args.geracao_s <= 1):
        parser.error("Use 1–200 rádios, concorrência 1–50 e geração de .001–1 segundo.")
    # Substituir credenciais de IA antes de importar a configuração.
    os.environ.update(ANTHROPIC_API_KEY="simulado", ELEVENLABS_API_KEY="simulado",
                      WUZAPI_USER_TOKEN="simulado", JWT_SECRET="simulado", STRIPE_WEBHOOK_SECRET="simulado")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import fakeredis
    from app.guardrails import provedores as p
    p.redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    p.settings.ia_limites_provedores = {**p.settings.ia_limites_provedores, "tts": {"concorrencia": args.concorrencia}}
    p.settings.ia_limites_por_pool = {}
    p.settings.ia_fila_max = 250
    p.settings.ia_fila_espera_s = 30
    resultados = []
    for radios in args.radios:
        p.redis_client.flushall()
        trava = threading.Lock()
        ativos = pico = 0
        def gerar(_):
            nonlocal ativos, pico
            with trava:
                ativos += 1
                pico = max(pico, ativos)
            time.sleep(args.geracao_s)
            with trava:
                ativos -= 1
            return SimpleNamespace(status_code=200)
        def radio(_):
            for _ in range(2):
                p.executar("tts", "simulado", gerar, timeout_s=40)
        inicio = time.monotonic()
        with ThreadPoolExecutor(max_workers=radios) as executor:
            list(executor.map(radio, range(radios)))
        assert ativos == 0 and pico <= args.concorrencia
        estado = next(x for x in p.estado_provedores()["provedores"] if x["pool"] == "tts")
        resultados.append({"radios": radios, "geracoes": radios * 2, "pico_simultaneo": pico,
                           "duracao_s": round(time.monotonic() - inicio, 3),
                           "ativos_apos": estado["ativos"], "fila_apos": estado["fila"],
                           "rejeicoes": estado["ultimos_15_minutos"]["rejeicoes"]})
    resultado = {"tipo": "simulacao_local_sem_apis", "limite": args.concorrencia,
                 "duracao_geracao_simulada_s": args.geracao_s, "resultados": resultados}
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(texto + "\n")
    print(texto)


if __name__ == "__main__":
    main()
