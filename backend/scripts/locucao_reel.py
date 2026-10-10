"""Gera os audios de fala (narracao e locutores) de um Reel da Locufy com a ElevenLabs.

Execute em backend: PYTHONPATH=. .venv/bin/python scripts/locucao_reel.py V5
Le marketing/reels/<id>/roteiro.json, gera marketing/reels/<id>/audio/cena-NN.mp3 para cada
cena com "fala" e grava a duracao real em "audio_s" no proprio roteiro.json. Consome creditos
da ElevenLabs (mesma chave do backend/.env). Pula falas que ja tem audio com o mesmo texto.

"voz" da cena: "narrador" (voz Scheila do catalogo) ou o nome de um radialista da demonstracao
(voz_id lido de marketing/reels/.demo.json).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
# Material de marketing nao e' consumo de cliente: sem isso, com a medicao ligada no .env, a
# sintese fora de um request (sem conta atribuida) seria recusada com 503.
os.environ["IA_MEDICAO_HABILITADA"] = "false"
os.environ["IA_ORCAMENTO_BLOQUEAR"] = "false"
VOZ_NARRADOR = "cyD08lEy76q03ER1jZ7y"  # Scheila, app/tts/voices.py


def _duracao_segundos(caminho: Path) -> float:
    if shutil.which("ffprobe"):
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(caminho)],
            capture_output=True, text=True, check=True,
        )
        return round(float(saida.stdout.strip()), 2)
    # Sem ffprobe: MP3 a 128 kbps constante (formato padrao de sintetizar_audio).
    return round(caminho.stat().st_size * 8 / 128_000, 2)


def main(video: str) -> None:
    from app.tts.client import sintetizar_audio

    pasta = RAIZ / "marketing" / "reels" / video
    roteiro_path = pasta / "roteiro.json"
    roteiro = json.loads(roteiro_path.read_text())
    demo_path = RAIZ / "marketing" / "reels" / ".demo.json"
    radialistas = json.loads(demo_path.read_text())["radialistas"] if demo_path.exists() else {}
    (pasta / "audio").mkdir(parents=True, exist_ok=True)

    avisos = []
    for cena in roteiro["cenas"]:
        texto = cena.get("fala")
        if not texto:
            continue
        nome_voz = cena.get("voz") or "narrador"
        voz_id = VOZ_NARRADOR if nome_voz == "narrador" else (radialistas.get(nome_voz) or {}).get("voz_id")
        if not voz_id:
            sys.exit(f"Voz '{nome_voz}' da cena {cena['n']} nao encontrada. Rode scripts/seed_demo.py.")

        destino = pasta / "audio" / f"cena-{cena['n']:02d}.mp3"
        assinatura = hashlib.sha256(f"{voz_id}|{texto}".encode()).hexdigest()[:16]
        if destino.exists() and cena.get("audio_assinatura") == assinatura:
            print(f"cena {cena['n']}: audio ja existe, pulando")
        else:
            audio = sintetizar_audio(texto, voice_id=voz_id, tipo_bloco="comentario", tom="energico",
                                     reutilizar_audio=False)
            destino.write_bytes(audio)
            cena["audio_assinatura"] = assinatura
        cena["audio_s"] = _duracao_segundos(destino)
        limite = cena["fim_s"] - cena["inicio_s"]
        print(f"cena {cena['n']}: {cena['audio_s']}s de fala (cena tem {limite}s)")
        if cena["audio_s"] > limite:
            avisos.append(f"cena {cena['n']}: fala de {cena['audio_s']}s passa da cena ({limite}s); encurte o texto.")

    roteiro_path.write_text(json.dumps(roteiro, ensure_ascii=False, indent=2) + "\n")
    for aviso in avisos:
        print(f"AVISO {aviso}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: scripts/locucao_reel.py <id-do-video>")
    main(sys.argv[1])
