"""Gera métricas e página de escuta offline a partir do benchmark_falas.py."""
import argparse
import html
import json
from pathlib import Path
import re
import unicodedata


def palavras(texto):
    return re.findall(r"\w+", "".join(c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)))


def distancia(a, b):
    anterior = list(range(len(b) + 1))
    for i, palavra in enumerate(a, 1):
        linha = [i]
        for j, outra in enumerate(b, 1):
            linha.append(min(linha[-1] + 1, anterior[j] + 1, anterior[j - 1] + (palavra != outra)))
        anterior = linha
    return anterior[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta", type=Path)
    args = parser.parse_args()
    pasta = args.pasta
    textos = json.loads((pasta / "texto.json").read_text())
    vozes = json.loads((pasta / "voz.json").read_text())
    qualidade = json.loads((pasta / "qualidade_audio.json").read_text())
    entradas = json.loads((pasta / "entradas_voz.json").read_text())
    precos = {"claude-opus-5": (5, 25), "claude-sonnet-5": (2, 10), "claude-haiku-4-5": (1, 5)}
    resumo = {"texto": {}, "voz": [], "aprovacao_troca_modelos": False}
    for modelo, (entrada, saida) in precos.items():
        itens = [r for r in textos if r["modelo"] == modelo and r["ok"]]
        resumo["texto"][modelo] = {
            "amostras": len(itens),
            "custo_usd_estimado": sum((r["input_tokens"] * entrada + r["output_tokens"] * saida) / 1_000_000 for r in itens),
            "latencia_media_segundos": sum(r["segundos"] for r in itens) / len(itens) if itens else None,
        }
    cards = []
    for caso, texto in entradas.items():
        cards.append(f"<section><h2>{html.escape(caso.title())}</h2><p>{html.escape(texto)}</p>")
        for i, modelo in enumerate(("eleven_v3", "eleven_flash_v2_5")):
            audio = next((v for v in vozes if v["caso"] == caso and v["modelo"] == modelo), None)
            if not audio or not audio["ok"]:
                cards.append(f"<p>Amostra {chr(65+i)} indisponível: geração não concluída.</p>")
                continue
            metrica = next(q.copy() for q in qualidade if q["arquivo"] == audio["arquivo"])
            if metrica.get("transcricao"):
                referencia, transcrito = palavras(texto), palavras(metrica["transcricao"])
                metrica["wer_indicativo"] = distancia(referencia, transcrito) / max(1, len(referencia))
            resumo["voz"].append(metrica)
            arquivo = html.escape(Path(audio["arquivo"]).name, quote=True)
            cards.append(f'<article><h3>Amostra {chr(65+i)}</h3><audio controls preload="none" src="{arquivo}"></audio>'
                         f'<details><summary>Modelo e medições</summary><pre>{html.escape(json.dumps(metrica,ensure_ascii=False,indent=2))}</pre></details></article>')
        cards.append("</section>")
    (pasta / "metricas.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2))
    (pasta / "escuta.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Locufy — comparação de voz</title><style>body{font:17px/1.6 system-ui;max-width:900px;margin:40px auto;padding:0 20px}'
        'section{border-top:1px solid #bbb;padding:20px 0}audio{width:100%}pre{white-space:pre-wrap;font-size:14px}summary{cursor:pointer}</style>'
        '<h1>Comparação de voz</h1><p>Ouça antes de abrir o nome dos modelos. Compare pronúncia, naturalidade, pausas e identidade da voz. '
        'Todas as amostras são sintéticas e receberam o mesmo perfil de pós-produção.</p><p>Transcrição e ausência de saturação '
        'não comprovam equivalência de expressividade. A troca automática de modelo não foi aprovada.</p>'
        + ''.join(cards) + '</html>'
    )
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
