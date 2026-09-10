"""Compara ajustes do v3 na voz configurada, sem alterar o aplicativo.

Em backend: PYTHONPATH=. .venv/bin/python scripts/comparar_clone_v3.py --output /tmp/clone-v3
Sem --executar-api, apenas descreve o experimento. Com a flag, consome créditos
em 12 sínteses (2 textos x 3 perfis x 2 repetições), sem criar novas vozes.
"""

import argparse
import base64
import copy
import html
import json
import random
import subprocess
import time
from pathlib import Path

CASOS = {
    "musica": ("energico", "Boa tarde pra você que está acompanhando a nossa programação! O Marcos pediu uma música que combina com esse fim de tarde. Daqui a pouco tem mais participação dos ouvintes, mas agora é hora de aumentar um pouquinho o volume e aproveitar o som."),
    "comentario": ("calmo", "Tem música que faz a gente lembrar de uma pessoa, de uma viagem, ou daquele fim de tarde sem pressa. Às vezes, bastam os primeiros acordes pra memória voltar inteira. Se aconteceu com você, conta pra gente. É bom dividir essas histórias enquanto a próxima canção chega por aqui."),
}
VARIANTES = ("atual", "estabilidade_fixa", "perfil_neutro")


def medir(caminho):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(caminho), "-af",
         "loudnorm=I=-16:TP=-2:LRA=7:print_format=json", "-f", "null", "-"],
        capture_output=True, check=True, timeout=30,
    )
    log = result.stderr.decode()
    data = json.loads(log[log.rfind("{"):log.rfind("}") + 1])
    return {"lufs": float(data["input_i"]), "true_peak_dbtp": float(data["input_tp"])}


def salvar(pasta, resultados):
    (pasta / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2))
    cards = []
    itens = list(resultados["sinteses"])
    random.Random(23).shuffle(itens)
    for n, item in enumerate(itens, 1):
        players = []
        for tipo in ("normalizado", "radio_fm"):
            if tipo in item:
                encoded = base64.b64encode((pasta / item[tipo]).read_bytes()).decode()
                players.append(f'<p>{tipo}</p><audio controls preload="none" src="data:audio/mpeg;base64,{encoded}"></audio>')
        detalhe = html.escape(json.dumps({k: v for k, v in item.items() if k not in ("payload",)}, ensure_ascii=False, indent=2))
        cards.append(f'<article><h2>Amostra {n} · {html.escape(item["caso"])}</h2>{"".join(players)}<details><summary>Revelar perfil e medidas</summary><pre>{detalhe}</pre></details></article>')
    pagina = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Teste de voz clonada · Locufy</title><style>body{font:17px/1.6 system-ui;max-width:1100px;margin:32px auto;padding:0 20px;background:#f5f5f5;color:#222}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:20px}article{background:white;padding:20px;border:1px solid #ccc;border-radius:12px}audio{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}</style>
<h1>Comparação de ajustes do v3</h1><p>Áudio sintético, voz já configurada no projeto. Dois textos, três perfis, duas repetições. A ordem está embaralhada; revele o perfil depois de ouvir. Normalizado: somente ajuste de volume. Rádio FM: tratamento atual, derivado da mesma síntese. Alvo de ambos: −16 LUFS, teto −2 dBTP.</p>
<p>Avalie de 1 a 5: naturalidade, pronúncia, ritmo e finais de frase. Fidelidade ao locutor exige uma gravação humana de referência, ausente neste teste. As medidas não escolhem o vencedor.</p><div class="grid">'''
    pagina += "".join(cards) + '</div><script>document.addEventListener("play",e=>{if(e.target.tagName==="AUDIO")document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>'
    (pasta / "comparacao.html").write_text(pagina)


def executar(pasta):
    import httpx
    from app.config.settings import settings
    from app.postprod.audio_io import mp3_bytes_para_array
    from app.postprod.client import processar_audio
    from app.postprod.mastering import finalizar_audio
    from app.tts import client as tts

    if not tts.tts_habilitado() or settings.elevenlabs_model != "eleven_v3":
        raise SystemExit("Requer voz/chave configuradas e ELEVENLABS_MODEL=eleven_v3.")
    if pasta.exists():
        raise SystemExit("Escolha uma pasta nova para preservar resultados anteriores.")
    pasta.mkdir(parents=True)
    resultados = {"modelo": "eleven_v3", "repeticoes": 2, "referencia_humana": False, "sinteses": []}
    with httpx.Client(timeout=45) as client:
        voz = client.get(tts._ELEVENLABS_VOICE_URL.format(voice_id=settings.elevenlabs_voice_id), headers={"xi-api-key": settings.elevenlabs_api_key})
        voz.raise_for_status()
        resultados["categoria_provedor"] = voz.json().get("category")
        resultados["eh_clonada_no_app"] = resultados["categoria_provedor"] == "cloned"
        salvar(pasta, resultados)
        for repeticao in range(2):
            for caso, (tom, texto) in CASOS.items():
                random.seed(20260910 + repeticao)
                headers, base = tts._preparar_sintese(texto, caso, tom, resultados["eh_clonada_no_app"], None)
                # Uma seed por repetição, igual entre perfis. A API só promete
                # determinismo best-effort; a seed não garante a mesma atuação.
                base["seed"] = 20260910 + repeticao
                ordem = list(VARIANTES)
                random.Random(31 + repeticao + len(caso)).shuffle(ordem)
                for variante in ordem:
                    payload = copy.deepcopy(base)
                    if variante == "estabilidade_fixa":
                        # Ablação: muda somente estabilidade; conserva speed,
                        # style e tags da chamada original para isolar o fator.
                        payload["voice_settings"]["stability"] = 0.5
                    elif variante == "perfil_neutro":
                        payload["voice_settings"] = {"stability": 0.5, "style": 0.0, "speed": 1.0}
                        payload["text"] = texto
                    item = {"caso": caso, "variante": variante, "repeticao": repeticao + 1, "payload": payload}
                    nome = f"{caso}-{variante}-{repeticao + 1}"
                    inicio = time.perf_counter()
                    try:
                        response = client.post(tts._ELEVENLABS_URL.format(voice_id=settings.elevenlabs_voice_id), headers=headers, json=payload)
                        item["status"] = response.status_code
                        item["sintese_segundos"] = round(time.perf_counter() - inicio, 3)
                        response.raise_for_status()
                        original = response.content
                        (pasta / f"{nome}-original.mp3").write_bytes(original)
                        audio, sr, _ = mp3_bytes_para_array(original)
                        item["duracao_segundos"] = round(audio.shape[1] / sr, 3)
                        item["sample_rate"] = sr
                        item["palavras_por_minuto"] = round(len(texto.split()) / item["duracao_segundos"] * 60, 1)
                        item["medidas"] = {}
                        for tipo, blob in (
                            ("normalizado", finalizar_audio(audio, sr, {"loudness_target_lufs": -16, "true_peak_db": -2})),
                            ("radio_fm", processar_audio(original, "radio_fm")),
                        ):
                            item[tipo] = f"{nome}-{tipo}.mp3"
                            (pasta / item[tipo]).write_bytes(blob)
                            item["medidas"][tipo] = medir(pasta / item[tipo])
                        item["ok"] = True
                    except Exception as exc:
                        item.update(ok=False, erro=type(exc).__name__)
                    resultados["sinteses"].append(item)
                    salvar(pasta, resultados)
                    print({k: item[k] for k in ("caso", "variante", "repeticao", "ok", "status", "sintese_segundos") if k in item}, flush=True)
                    if item.get("status") in (401, 402, 403, 429):
                        raise SystemExit("API indisponível para continuar; resultados parciais preservados.")
    if not all(i["ok"] for i in resultados["sinteses"]):
        raise SystemExit("Comparação incompleta; consulte resultados.json.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executar-api", action="store_true")
    args = parser.parse_args()
    if args.executar_api:
        executar(args.output)
    else:
        print(json.dumps({"sinteses": 12, "variantes": VARIANTES, "caracteres_texto_sem_tags": sum(len(t) for _, t in CASOS.values()) * 6, "requer": "--executar-api (consome créditos)"}, ensure_ascii=False))
