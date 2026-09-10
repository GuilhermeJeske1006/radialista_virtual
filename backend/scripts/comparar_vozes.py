"""Gera seis amostras reais para comparar naturalidade; consome creditos ElevenLabs.

Execute em backend: PYTHONPATH=. .venv/bin/python scripts/comparar_vozes.py --output /tmp/locufy-vozes
Usa a voz do ambiente ou --voice-id. Nao publica audio nem altera configuracoes persistidas.
"""

import argparse
import base64
import html
import json
import time
from pathlib import Path


CASOS = {
    "musica": {
        "tom": "energico",
        "texto": "Boa tarde pra você que está ligado na nossa programação! O Marcos mandou mensagem pedindo Twist and Shout, dos Beatles, e o pedido está na sequência. Tem música que dá vontade de aumentar o volume e acompanhar do começo ao fim. Você também pode participar pelo WhatsApp da rádio e contar qual canção quer ouvir. Agora, deixa o som acompanhar a sua tarde. Vamos de Beatles!",
    },
    "comentario": {
        "tom": "calmo",
        "texto": "Tem música que faz a gente lembrar de uma pessoa, de uma viagem, ou daquele fim de tarde sem pressa. Às vezes, bastam os primeiros acordes pra memória voltar inteira. Se aconteceu com você, conta pra gente pelo WhatsApp da rádio. É bom dividir essas histórias, enquanto a próxima canção chega por aqui.",
    },
}
VARIANTES = [
    ("flash_anterior", "Flash anterior", "eleven_flash_v2_5"),
    ("flash_ajustado", "Flash ajustado", "eleven_flash_v2_5"),
    ("v3", "Eleven v3", "eleven_v3"),
]


def salvar_comparacao(pasta, registros):
    (pasta / "resultados.json").write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")
    secoes = []
    for caso, entrada in CASOS.items():
        cards = []
        for item in registros:
            if item["caso"] != caso:
                continue
            players = []
            for chave, label in [("sem_efeitos", "Sem efeitos · volume normalizado"), ("radio_fm", "Com tratamento Rádio FM")]:
                if chave not in item:
                    continue
                audio = base64.b64encode((pasta / item[chave]).read_bytes()).decode("ascii")
                players.append(f'<label>{label}<audio controls preload="none" src="data:audio/mpeg;base64,{audio}"></audio></label>')
            tempo = f'Síntese: {item["sintese_segundos"]:.2f} s' if "sintese_segundos" in item else "Síntese não concluída"
            erro = f'<p>Falha: {html.escape(item["erro"])}</p>' if "erro" in item else ""
            cards.append(f'<article><h3>{html.escape(item["label"])}</h3><p>{tempo}</p>{"".join(players)}{erro}</article>')
        secoes.append(f'<section><h2>{html.escape(caso.capitalize())}</h2><p>{html.escape(entrada["texto"])}</p><div class="grid">{"".join(cards)}</div></section>')
    pagina = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Comparação de vozes · Locufy</title>
<style>body{font:17px/1.6 system-ui,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;color:#202833;background:#f4f6f9}
h1,h2,h3{line-height:1.2}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}
article{background:white;border:1px solid #ccd3de;border-radius:12px;padding:18px}label{display:block;margin-top:16px}
audio{display:block;width:100%;margin-top:8px}section{margin:36px 0}p{max-width:90ch}</style>
<h1>Qual voz soa mais real?</h1><p>Ouça primeiro as versões sem efeitos. Compare entonação, timbre e finais de frase.
Depois ouça o tratamento Rádio FM para perceber se ele acentua o som metálico.</p>
<p>Mesma voz e mesmo texto por cenário. As versões sem efeitos receberam apenas normalização de volume;
ambas usam alvo de −16 LUFS e teto de −2 dBTP. Uma síntese por variante: a entrega pode variar em novas gerações.
O tempo exibido mede a síntese completa, incluindo rede, antes do tratamento.</p>'''
    pagina += "".join(secoes)
    pagina += '''<script>document.addEventListener('play',event=>{
if(event.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==event.target)a.pause()});
},true);</script></html>'''
    (pasta / "comparacao.html").write_text(pagina, encoding="utf-8")


def comparar(pasta, voice_id=None):
    import httpx
    from app.config.settings import settings
    from app.postprod.audio_io import mp3_bytes_para_array
    from app.postprod.client import processar_audio
    from app.postprod.mastering import finalizar_audio
    from app.tts import client as tts

    voice_id = voice_id or settings.elevenlabs_voice_id
    if not tts.tts_habilitado(voice_id):
        raise SystemExit("Configure ELEVENLABS_API_KEY e ELEVENLABS_VOICE_ID ou use --voice-id.")
    pasta.mkdir(parents=True, exist_ok=True)
    # Evita sobrescrever resultados de uma escuta anterior.
    if (pasta / "resultados.json").exists():
        raise SystemExit("A pasta ja contem resultados. Escolha outra pasta para esta comparacao.")
    metadados = tts.obter_metadados_voz(voice_id) or {}
    eh_clonada = metadados.get("categoria") == "cloned"
    registros = []
    modelo_original = settings.elevenlabs_model
    try:
        with httpx.Client(timeout=35) as cliente:
            for indice, (caso, entrada) in enumerate(CASOS.items()):
                variantes = VARIANTES[indice:] + VARIANTES[:indice]
                for variante, label, modelo in variantes:
                    settings.elevenlabs_model = modelo
                    headers, payload = tts._preparar_sintese(entrada["texto"], caso, entrada["tom"], eh_clonada, None)
                    if variante == "flash_anterior":
                        # Antes do ajuste, Flash e Multilingual v2 recebiam exatamente
                        # os mesmos presets. Reproduz o payload anterior so neste processo.
                        payload["voice_settings"] = tts._construir_voice_settings(caso, entrada["tom"], "eleven_multilingual_v2", eh_clonada)
                    item = dict(caso=caso, variante=variante, label=label, modelo=modelo,
                                eh_clonada=eh_clonada, texto=payload["text"], voice_settings=payload["voice_settings"])
                    inicio = time.perf_counter()
                    try:
                        resposta = cliente.post(tts._ELEVENLABS_URL.format(voice_id=voice_id), headers=headers, json=payload)
                        resposta.raise_for_status()
                        item["sintese_segundos"] = round(time.perf_counter() - inicio, 3)
                        original = resposta.content
                        nome = f"{caso}-{variante}"
                        item["original"] = f"{nome}-original.mp3"
                        (pasta / item["original"]).write_bytes(original)
                        amostras, taxa, _ = mp3_bytes_para_array(original)
                        inicio_fm = time.perf_counter()
                        tratado = processar_audio(original, "radio_fm")
                        item["radio_fm_segundos"] = round(time.perf_counter() - inicio_fm, 3)
                        item["radio_fm"] = f"{nome}-radio-fm.mp3"
                        (pasta / item["radio_fm"]).write_bytes(tratado)
                        normalizado = finalizar_audio(amostras, taxa, {"loudness_target_lufs": -16, "true_peak_db": -2})
                        item["sem_efeitos"] = f"{nome}-sem-efeitos.mp3"
                        (pasta / item["sem_efeitos"]).write_bytes(normalizado)
                        item["ok"] = True
                    except Exception as exc:
                        item.update(ok=False, erro=type(exc).__name__)
                        if isinstance(exc, httpx.HTTPStatusError):
                            item["status"] = exc.response.status_code
                    registros.append(item)
                    salvar_comparacao(pasta, registros)
                    print({k: item[k] for k in ("caso", "variante", "ok", "sintese_segundos", "erro", "status") if k in item}, flush=True)
    finally:
        settings.elevenlabs_model = modelo_original
    if not all(item["ok"] for item in registros):
        raise SystemExit("Comparacao incompleta; consulte resultados.json.")
    print(f"Abra {pasta / 'comparacao.html'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice-id", help="ID da voz a comparar; usa a voz do ambiente quando omitido.")
    args = parser.parse_args()
    comparar(args.output, args.voice_id)
