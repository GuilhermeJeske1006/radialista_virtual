"""Inspeciona payloads reais do código, sem sintetizar áudio ou permitir rede.

Da raiz do projeto:
backend/.venv-test/bin/python docs/analises/2026-11-21-prosodia-gaucha/reproduzir.py

Requer as dependências de desenvolvimento. Usa o isolamento de tests/conftest.py.
O resultado descreve o comportamento atual; não é um teste perceptivo nem de API.
"""

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch


def main():
    destino = Path(__file__).resolve().parent
    raiz = destino.parents[2]
    corpus = json.loads((destino / "corpus.json").read_text(encoding="utf-8"))
    anterior = Path.cwd()
    os.chdir(raiz / "backend")
    sys.path.insert(0, str(raiz / "backend"))
    try:
        with patch("socket.socket.connect", side_effect=RuntimeError("Rede desativada nesta auditoria")):
            runpy.run_path("tests/conftest.py")
            from app.numeros import normalizar_texto_fala
            from app.tts import client as tts
            from app.live.router import _tom_sintese_do_bloco

            modelos = ["eleven_v3", "eleven_v4", "eleven_v4_turbo", "eleven_flash_v2_5"]
            resultados = []
            with patch.object(tts.random, "uniform", return_value=0.0):
                for modelo in modelos:
                    for perfil in ("atual", "natural"):
                        for caso in corpus["casos"]:
                            _, payload = tts._preparar_sintese(
                                caso["texto"], caso["tipo"], caso["tom"], False,
                                "A música anterior acabou.", modelo, perfil,
                                voice_id="voz-catalogo-nao-consultada",
                            )
                            resultados.append(dict(caso=caso["id"], perfil=perfil, payload=payload))

                def preparar(modelo, tom, texto="Bah, tchê, que baita som!"):
                    return tts._preparar_sintese(
                        texto, "comentario", tom, False, None, modelo,
                        voice_id="voz-catalogo-nao-consultada",
                    )[1]

                flash_calmo = preparar("eleven_flash_v2_5", "calmo")
                flash_energico = preparar("eleven_flash_v2_5", "energico")
                v4 = preparar("eleven_v4", "energico")
                v3_energico = preparar("eleven_v3", "energico")
                probes = {
                    "flash_payload_calmo_igual_energico": flash_calmo == flash_energico,
                    "v4_envia_speed_e_style": {"speed", "style"} <= v4["voice_settings"].keys(),
                    "v4_remove_similarity_boost": "similarity_boost" not in v4["voice_settings"],
                    "energico_sem_tag_automatica": not v3_energico["text"].startswith("[excited]"),
                    "tag_curiosidade_removida": "[curious]" not in preparar(
                        "eleven_v4", "neutro", "[curious] Mas capaz! Tu também tava lá?"
                    )["text"],
                    "pausa_curta_descritiva_removida": "[short pause]" not in preparar(
                        "eleven_v4", "neutro", "Bah. [short pause] Que baita som!"
                    )["text"],
                    "giria_preservada_sem_alias": preparar("eleven_v3", "neutro")["text"] == "Bah, tchê, que baita som!",
                    "comentario_direcionado_calmo": _tom_sintese_do_bloco("comentario") == "calmo",
                }
                assert all(probes.values()), "Comportamento mudou; revisar o diagnóstico."
                caracteres_base = sum(len(normalizar_texto_fala(c["texto"])) for c in corpus["casos"])
                dados = {
                    "data": "2026-11-21",
                    "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                    "rede_bloqueada": True,
                    "sinteses_executadas": 0,
                    "jitter_zerado_para_comparacao": True,
                    "voz_real_nao_consultada": True,
                    "sondagens_confirmadas": probes,
                    "piloto_proposto": {
                        "casos": len(corpus["casos"]), "vozes": 1, "condicoes": 2,
                        "repeticoes": 2, "sinteses": len(corpus["casos"]) * 4,
                        "caracteres_base_por_passagem": caracteres_base,
                        "estimativa_caracteres_enviados": 4 * caracteres_base + 64 * len(corpus["casos"]),
                        "hipotese_estimativa": "Mesmo texto nas duas condições; até 32 caracteres extras de tags por caso apenas na candidata; sem STT ou tentativas extras. Não equivale a caracteres faturados.",
                    },
                    "payloads": resultados,
                }
                (destino / "diagnostico.json").write_text(
                    json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps({k: v for k, v in dados.items() if k != "payloads"}, ensure_ascii=False, indent=2))
                print(f"Payloads inspecionados: {len(resultados)}")
    finally:
        os.chdir(anterior)


if __name__ == "__main__":
    main()
