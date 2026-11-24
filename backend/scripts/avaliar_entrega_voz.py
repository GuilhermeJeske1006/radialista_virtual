"""Mede a entrega da voz (como o locutor fala, não o que fala) em falas reais do ao vivo.

Consome créditos reais (TTS + Scribe). Execute a partir de backend:
  PYTHONPATH=. .venv-test/bin/python scripts/avaliar_entrega_voz.py --output ../docs/benchmarks/2026-11-23-entrega-voz

Cada fala do corpus é sintetizada em variantes e repetições (o eleven_v3 muda de take pra take
mesmo com seed fixa; "às vezes fala estranho" só aparece com repetição). Por áudio, mede:
- eventos sonoros que o Scribe marca entre parênteses (risada, suspiro, respiração alta);
- fidelidade: palavras faltando/sobrando contra o texto enviado;
- pausas longas no meio da frase (silêncio entre palavras sem pontuação no texto);
- ritmo por frase (sílabas por segundo) e quanto ele oscila entre frases;
- palavras esticadas (duração por sílaba muito acima da mediana do áudio);
- pitch: faixa em semitons, quadros muito acima da mediana (grito/falsete) e saltos bruscos;
- volume por frase (frase muito abaixo da mediana = sussurro).
Não substitui audição: gera escuta.html às cegas para comparar as variantes.

Variantes "atual" e "novo" chamam o mesmo app.tts.client._preparar_sintese: "atual" foi gerada no
commit anterior à mudança da direção vocal, "novo" depois. Resultados em
docs/benchmarks/2026-11-23-entrega-voz/README.md.
"""

import argparse
import concurrent.futures as cf
import html
import json
import random
import re
import statistics
import subprocess
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import httpx
import numpy as np

CORPUS = Path(__file__).parent / "simulacao" / "corpus_entrega_voz.json"
VOZES = {"paulo": "Qrdut83w0Cr152Yb4Xn3", "yasmin": "lWq4KDY8znfkV0DrK8Vb"}
# Variante "outra_voz": vozes pt-BR da biblioteca, entre as mais usadas em 2026 (shared-voices,
# accent=brazilian): Diego "Confident Announcer" e Raquel "Expressive and Energetic".
VOZES_ALTERNATIVAS = {"paulo": "rpNe0HOx7heUulPiOEaG", "yasmin": "GDzHdQOi6jjf8zaXhCYD"}


def normalizar_palavras(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", texto)


def silabas(palavra):
    return max(1, len(re.findall(r"[aeiouáéíóúâêôãõà]+", palavra.lower())))


# ---------------------------------------------------------------- variantes

def preparar_candidata(variante, fala, voice_id):
    """Implementação local das candidatas, independente da app, para medir antes de mexer no código."""
    from app.numeros import normalizar_texto_fala
    from app.tts import client as tts
    texto, tipo, tom = fala["texto"], fala["tipo"], fala["tom"]
    if variante in ("atual", "novo"):
        # "atual" = código de antes da mudança; "novo" = código depois (mesma chamada, rodar no commit certo).
        _, payload = tts._preparar_sintese(texto, tipo, tom, False, None, "eleven_v3", voice_id=voice_id)
        return payload
    if variante == "novo_v4":
        _, payload = tts._preparar_sintese(texto, tipo, tom, False, None, "eleven_v4", voice_id=voice_id)
        return payload
    # Rodada 2 (escuta: entonação, pronúncia e ritmo da fala inteira): modelo, ajuste e voz.
    if variante in ("v3_robusto", "v3_sem_idioma", "outra_voz"):
        _, payload = tts._preparar_sintese(texto, tipo, tom, False, None, "eleven_v3", voice_id=voice_id)
        if variante == "v3_robusto":
            payload["voice_settings"]["stability"] = 1.0
        if variante == "v3_sem_idioma":
            payload.pop("language_code", None)
        return payload
    if variante == "v2":
        _, payload = tts._preparar_sintese(texto, tipo, tom, False, None, "eleven_multilingual_v2", voice_id=voice_id)
        return payload
    t = normalizar_texto_fala(texto)
    # "......" no meio da frase vira vírgula; no fim, ponto final.
    t = re.sub(r"\.{4,}\s*(?=[a-zà-ú])", ", ", t)
    t = re.sub(r",?\s*\.{4,}", ".", t)
    inicial = re.match(r"\s*\[(excited|calm)\]", t) if variante == "tag_inicial" else None
    t = re.sub(r"\[[^\]]*\]", "", t)
    if inicial:
        t = f"[{inicial.group(1)}] " + t.lstrip()
    t = re.sub(r"[ \t]+([,.!?])", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t).strip()
    vs = tts._construir_voice_settings(tipo, tom, "eleven_v3", False, voice_id)
    if variante in ("sem_tags_natural",):
        vs["stability"] = 0.5
    return {"text": t, "model_id": "eleven_v3", "voice_settings": vs, "language_code": "pt"}


# ---------------------------------------------------------------- síntese e transcrição

def sintetizar(chave, voice_id, payload):
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers={"xi-api-key": chave},
                   json=payload, timeout=120)
    r.raise_for_status()
    return r.content


def transcrever(chave, audio):
    r = httpx.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": chave},
                   files={"file": ("a.mp3", audio, "audio/mpeg")},
                   data={"model_id": "scribe_v2", "language_code": "por", "tag_audio_events": "true",
                         "timestamps_granularity": "word"}, timeout=120)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- análise

def carregar_pcm(caminho, sr=16000):
    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(caminho), "-ac", "1", "-ar", str(sr),
                                   "-f", "f32le", "pipe:1"])
    return np.frombuffer(pcm, dtype="<f4"), sr


def analisar(caminho, transcricao, texto_enviado):
    import librosa
    from app.numeros import normalizar_texto_fala

    y, sr = carregar_pcm(caminho)
    duracao = len(y) / sr
    palavras = [w for w in transcricao.get("words", []) if w.get("type") == "word"]
    eventos = [w["text"] for w in transcricao.get("words", []) if w.get("type") == "audio_event"]

    # Fidelidade (Scribe escreve número em algarismo; normaliza igual ao texto enviado).
    esperado = normalizar_palavras(re.sub(r"\[[^\]]*\]", " ", texto_enviado))
    ouvido = normalizar_palavras(normalizar_texto_fala(re.sub(r"\([^)]*\)", " ", transcricao.get("text", ""))))
    sm = SequenceMatcher(None, esperado, ouvido, autojunk=False)
    iguais = sum(b.size for b in sm.get_matching_blocks())
    faltando, sobrando = len(esperado) - iguais, len(ouvido) - iguais

    # Pausas entre palavras: no meio da frase = palavra anterior sem pontuação.
    pausas_meio, pausas_longas = [], []
    for a, b in zip(palavras, palavras[1:]):
        gap = b["start"] - a["end"]
        if gap >= 1.0:
            pausas_longas.append(round(gap, 2))
        if gap >= 0.6 and not re.search(r"[,.!?;:…]$", a["text"]):
            pausas_meio.append({"apos": a["text"], "s": round(gap, 2), "t": round(a["end"], 2)})

    # Frases pela pontuação da transcrição; ritmo e volume por frase.
    frases, atual = [], []
    for w in palavras:
        atual.append(w)
        if re.search(r"[.!?]$", w["text"]):
            frases.append(atual)
            atual = []
    if atual:
        frases.append(atual)
    ritmos, volumes = [], []
    for f in frases:
        dur = f[-1]["end"] - f[0]["start"]
        if dur >= 1.0:
            ritmos.append(sum(silabas(w["text"]) for w in f) / dur)
            seg = y[int(f[0]["start"] * sr):int(f[-1]["end"] * sr)]
            if len(seg):
                volumes.append(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9))
    ritmo_cv = statistics.pstdev(ritmos) / statistics.mean(ritmos) if len(ritmos) >= 2 else 0.0
    vol_med = statistics.median(volumes) if volumes else 0.0
    frases_baixas = sum(1 for v in volumes if v < vol_med - 8)

    # Palavras esticadas: segundos por sílaba muito acima da mediana do áudio.
    # Token com dígito ("14:57") junta várias palavras faladas: fora da conta.
    por_silaba = [(w, (w["end"] - w["start"]) / silabas(w["text"])) for w in palavras
                  if w["end"] > w["start"] and not re.search(r"\d", w["text"])]
    mediana_sil = statistics.median([v for _, v in por_silaba]) if por_silaba else 0.2
    esticadas = [{"palavra": w["text"], "s": round(w["end"] - w["start"], 2), "t": round(w["start"], 2)}
                 for w, v in por_silaba if v > 2.6 * mediana_sil and (w["end"] - w["start"]) > 0.55]

    # Pitch (pyin): semitons relativos à mediana do próprio áudio.
    f0, voiced, _ = librosa.pyin(y, fmin=65, fmax=500, sr=sr, frame_length=1024, hop_length=160)
    f0v = f0[voiced & ~np.isnan(f0)]
    if len(f0v) > 20:
        st = 12 * np.log2(f0v / np.median(f0v))
        faixa = float(np.percentile(st, 95) - np.percentile(st, 5))
        acima = float(np.mean(st > 7.0) * 100)
        # salto brusco entre quadros vozeados consecutivos (10 ms)
        serie = 12 * np.log2(np.where(voiced, f0, np.nan) / np.median(f0v))
        dif = np.abs(np.diff(serie))
        saltos = int(np.nansum(dif > 5.0))
    else:
        faixa = acima = 0.0
        saltos = 0

    palavras_min = len(esperado) / duracao * 60 if duracao else 0
    return {
        "duracao_s": round(duracao, 2), "ppm": round(palavras_min),
        "eventos": eventos, "faltando": faltando, "sobrando": sobrando,
        "pausas_longas": pausas_longas, "pausas_meio_frase": pausas_meio,
        "ritmo_sil_s": [round(r, 2) for r in ritmos], "ritmo_cv": round(ritmo_cv, 3),
        "frases_baixas": frases_baixas, "esticadas": esticadas,
        "pitch_faixa_st": round(faixa, 2), "pitch_acima_7st_pct": round(acima, 2), "pitch_saltos": saltos,
    }


def sinais(m):
    """Contagem de sinais de entrega estranha num áudio (cada um é algo que um ouvinte nota)."""
    s = {
        "evento_sonoro": len(m["eventos"]),
        "pausa_meio_frase": len(m["pausas_meio_frase"]),
        "palavra_esticada": len(m["esticadas"]),
        "frase_sussurrada": m["frases_baixas"],
        "pitch_grito": int(m["pitch_acima_7st_pct"] > 3.0),
        "ritmo_irregular": int(m["ritmo_cv"] > 0.22),
        "erro_texto": int(m["faltando"] + m["sobrando"] > 3),
    }
    s["total"] = sum(s.values())
    return s


# ---------------------------------------------------------------- escuta

def escrever_escuta(pasta, registros, falas, variantes, reps, nome="escuta", nota=False):
    rng = random.Random(7)
    linhas = []
    gabarito = {}
    for fala in falas:
        regs = [r for r in registros if r["fala"] == fala["id"] and r.get("ok")
                and r["variante"] in variantes and r["rep"] <= reps]
        rng.shuffle(regs)
        celulas = []
        for i, r in enumerate(regs):
            rotulo = chr(65 + i)
            k = f"{fala['id']}:{rotulo}"
            gabarito[k] = f"{r['variante']} #{r['rep']}"
            if nota:
                controle = '<span class="nota">' + "".join(
                    f'<label><input type="radio" name="{k}" value="{n}" data-k="{k}"> {n}</label>' for n in range(1, 6)) + "</span>"
            else:
                controle = f'<label><input type="checkbox" data-k="{k}"> estranho</label>'
            celulas.append(f'<div class="take"><b>{rotulo}</b><audio controls preload="none" src="{r["arquivo"]}"></audio>'
                           f'{controle}</div>')
        linhas.append(f'<section><h2>{html.escape(fala["id"])}</h2><p class="txt">{html.escape(fala["texto"])}</p>'
                      f'<div class="takes">{"".join(celulas)}</div></section>')
    (pasta / f"gabarito{nome.removeprefix('escuta')}.json").write_text(json.dumps(gabarito, ensure_ascii=False, indent=1))
    instrucao = ("Nota de 1 a 5 para cada take: entonação, pronúncia e ritmo da fala inteira. 1 = muito estranho, "
                 "3 = dá pra ouvir mas incomoda, 5 = soa como locutor de verdade. No fim, copie as notas."
                 if nota else "Cada fala tem vários takes embaralhados. Marque os que soam estranhos. No fim, copie as marcações.")
    coletar = ("Object.fromEntries([...document.querySelectorAll('input:checked')].map(e=>[e.dataset.k,+e.value]))"
               if nota else "[...document.querySelectorAll('input:checked')].map(e=>e.dataset.k)")
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Escuta às cegas</title><style>
:root{{--bg:#fafaf9;--fg:#1c1917;--mut:#57534e;--card:#fff;--bd:#e7e5e4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--card:#292524;--bd:#44403c}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui;margin:0;padding:16px;max-width:1100px;margin:auto}}
section{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 16px;margin:14px 0}}
.txt{{color:var(--mut);font-size:13px}} .takes{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}}
.take{{display:flex;flex-direction:column;gap:4px}} audio{{width:100%}} .nota{{display:flex;gap:14px}}
button{{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--fg)}}
</style></head><body><h1>Escuta às cegas: entrega da voz</h1>
<p>{instrucao}</p>
{"".join(linhas)}
<button id="copiar">Copiar resultado</button> <pre id="saida"></pre>
<script>document.getElementById('copiar').onclick=()=>{{const m={coletar};
const t=JSON.stringify(m);document.getElementById('saida').textContent=t;navigator.clipboard&&navigator.clipboard.writeText(t).catch(()=>{{}});}}</script>
</body></html>"""
    (pasta / f"{nome}.html").write_text(pagina)


# ---------------------------------------------------------------- principal

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--variantes", default="atual,sem_tags,sem_tags_natural")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--falas", default="")
    parser.add_argument("--so-analisar", action="store_true")
    parser.add_argument("--escuta-variantes", default="atual,novo")
    parser.add_argument("--escuta-reps", type=int, default=3)
    parser.add_argument("--escuta-nome", default="escuta")
    parser.add_argument("--escuta-nota", action="store_true", help="nota de 1 a 5 em vez de marcar estranho")
    args = parser.parse_args()
    pasta = Path(args.output)
    pasta.mkdir(parents=True, exist_ok=True)

    from app.config.settings import settings
    settings.ia_orcamento_bloquear = False
    settings.ia_medicao_habilitada = False
    settings.ia_cache_habilitado = False
    chave = settings.elevenlabs_api_key

    falas = json.loads(CORPUS.read_text())
    if args.falas:
        falas = [f for f in falas if f["id"] in args.falas.split(",")]
    variantes = args.variantes.split(",")
    saida = pasta / "resultados.json"
    registros = {(r["fala"], r["variante"], r["rep"]): r for r in json.loads(saida.read_text())} if saida.exists() else {}

    tarefas = []
    for fala in falas:
        for variante in variantes:
            voice_id = (VOZES_ALTERNATIVAS if variante == "outra_voz" else VOZES)[fala["voz"]]
            for rep in range(1, args.reps + 1):
                chave_reg = (fala["id"], variante, rep)
                if chave_reg in registros and registros[chave_reg].get("ok"):
                    continue
                tarefas.append((fala, variante, rep, voice_id))

    def executar(t):
        fala, variante, rep, voice_id = t
        payload = preparar_candidata(variante, fala, voice_id)
        nome = f"{fala['id']}-{variante}-{rep}.mp3"
        reg = {"fala": fala["id"], "variante": variante, "rep": rep, "voz": fala["voz"],
               "texto_enviado": payload["text"], "voice_settings": payload["voice_settings"], "arquivo": nome}
        try:
            audio = sintetizar(chave, voice_id, payload)
            (pasta / nome).write_bytes(audio)
            tr = transcrever(chave, audio)
            (pasta / (nome[:-4] + ".scribe.json")).write_text(json.dumps(tr, ensure_ascii=False))
            reg.update(ok=True, transcricao=tr.get("text", ""))
        except Exception as exc:  # noqa: BLE001 -- registra e segue
            reg.update(ok=False, erro=f"{type(exc).__name__}: {exc}"[:300])
        return reg

    if not args.so_analisar and tarefas:
        print(f"{len(tarefas)} sínteses; ~{sum(len(preparar_candidata(v, f, vid)['text']) for f, v, _, vid in tarefas)} caracteres", flush=True)
        with cf.ThreadPoolExecutor(3) as ex:
            for reg in ex.map(executar, tarefas):
                registros[(reg["fala"], reg["variante"], reg["rep"])] = reg
                print(reg["fala"], reg["variante"], reg["rep"], "ok" if reg.get("ok") else reg.get("erro"), flush=True)
                saida.write_text(json.dumps(list(registros.values()), ensure_ascii=False, indent=1))

    # Análise (pyin é lento: processos em paralelo).
    pendentes = [r for r in registros.values() if r.get("ok")]
    with cf.ProcessPoolExecutor(6) as ex:
        for r, m in zip(pendentes, ex.map(_analisar_wrapper, [(str(pasta), r) for r in pendentes])):
            r["metricas"] = m
            r["sinais"] = sinais(m)
    saida.write_text(json.dumps(list(registros.values()), ensure_ascii=False, indent=1))

    # Resumo por variante.
    linhas = ["| Variante | Áudios | Sinais/áudio | Áudios com sinal | Evento sonoro | Pausa meio frase | Palavra esticada | "
              "Frase sussurrada | Pitch grito | Ritmo irregular | Erro texto | Faixa pitch (st) | ppm |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for v in variantes:
        rs = [r for r in pendentes if r["variante"] == v and "sinais" in r]
        if not rs:
            continue
        def soma(k, rs=rs):
            return sum(r["sinais"][k] for r in rs)
        linhas.append(
            f"| {v} | {len(rs)} | {soma('total') / len(rs):.2f} | {sum(1 for r in rs if r['sinais']['total'])} | "
            f"{soma('evento_sonoro')} | {soma('pausa_meio_frase')} | {soma('palavra_esticada')} | {soma('frase_sussurrada')} | "
            f"{soma('pitch_grito')} | {soma('ritmo_irregular')} | {soma('erro_texto')} | "
            f"{statistics.median(r['metricas']['pitch_faixa_st'] for r in rs):.1f} | "
            f"{statistics.median(r['metricas']['ppm'] for r in rs)} |")
    (pasta / "resumo.md").write_text("\n".join(linhas) + "\n")
    print("\n".join(linhas))
    escrever_escuta(pasta, list(registros.values()), falas, args.escuta_variantes.split(","), args.escuta_reps,
                    args.escuta_nome, args.escuta_nota)


def _analisar_wrapper(arg):
    pasta, r = arg
    pasta = Path(pasta)
    tr = json.loads((pasta / (r["arquivo"][:-4] + ".scribe.json")).read_text())
    return analisar(pasta / r["arquivo"], tr, r["texto_enviado"])


if __name__ == "__main__":
    main()
