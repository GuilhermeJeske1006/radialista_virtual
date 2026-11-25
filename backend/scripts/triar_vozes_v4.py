"""Tria vozes pt-BR da biblioteca da ElevenLabs para o catálogo do locutor no eleven_v4.

Consome créditos reais (TTS + Scribe). Execute a partir de backend:
  PYTHONPATH=. .venv-test/bin/python scripts/triar_vozes_v4.py --output ../docs/benchmarks/2026-11-25-vozes-v4

Três etapas, todas retomáveis (o que já foi gerado não é gerado de novo):
1. Elegibilidade (sem custo): relê cada candidata em /v1/shared-voices e confere se segue verificada
   em pt-BR no eleven_v4, sem preço extra (rate 1, sem fiat_rate), com aviso de remoção de pelo menos
   365 dias e sem moderação ao vivo (que pode bloquear fala no meio do programa).
2. Triagem: a fala "triagem" do corpus em cada candidata elegível, com o payload do ao vivo
   (app.tts.client._preparar_sintese, eleven_v4). Scribe mede fidelidade, idioma e ritmo.
   Reprovada: mais de 3 palavras faltando/sobrando, idioma detectado fora do português ou ritmo fora
   de 120 a 230 palavras por minuto.
3. Escuta: aprovadas na triagem + vozes atuais do catálogo (âncoras) falam as falas do próprio perfil.
   Gera escuta.html às cegas (nota de 1 a 5 e "combina com o perfil") e decisao.html (com nomes, o
   catálogo proposto em app/tts/voices.py primeiro, Aprovar/Reprovar por voz). A decisão é pelo ouvido
   (docs/benchmarks/2026-11-23-entrega-voz: métrica automática não bate com a escuta).
"""

import argparse
import concurrent.futures as cf
import html
import json
import random
import time
from pathlib import Path

import httpx

from scripts.avaliar_entrega_voz import analisar, transcrever

CORPUS = Path(__file__).parent / "simulacao" / "corpus_vozes_v4.json"
SHARED = "https://api.elevenlabs.io/v1/shared-voices"
MODELO = "eleven_v4"

PERFIS = {
    "comunicador": "Comunicador popular (manhã, variedades, recado de ouvinte)",
    "jovem": "Jovem / pop / hits / dance",
    "jornalismo": "Jornalismo e notícia",
    "noite": "Noite, romântico, flashback, MPB",
    "gospel": "Gospel e reflexão",
    "interior": "Sertanejo, interior e rural",
    "regional": "Sotaque regional",
    "esporte": "Esporte",
    "maduro": "Voz madura (60+)",
}

# Escolhidas em 25/11/2026 entre 499 vozes pt-BR da biblioteca que passaram no filtro de elegibilidade
# (de 2.463 retornadas por buscas por uso, clonagem, tendência, caso de uso e termos de rádio): as mais
# usadas de cada perfil, mais as descritas como locutor de rádio, sotaque regional, esporte ou idade madura.
CANDIDATAS = [
    ("HR2TRGmi4QbMsO5omv7l", "Rômulo Franklin", "masculina", ["comunicador"]),
    ("TJ1zld0fSLwyF02SLwgy", "Eddy Miller", "masculina", ["comunicador", "jovem"]),
    ("uMk2ijhneJaRm2sKMgdi", "Daniel Mercer", "masculina", ["comunicador", "noite"]),
    ("a2RTfXZv18BLdBvhWhl2", "Fabio Manarin", "masculina", ["comunicador"]),
    ("4za2kOXGgUd57HRSQ1fn", "Lendário", "masculina", ["comunicador", "esporte"]),
    ("YU8EsJtXFMyKMxYtheDk", "Mário", "masculina", ["comunicador", "jovem"]),
    ("ulzsiMeCbfKyTPCNhCD5", "Nassif (talk show)", "masculina", ["comunicador"]),
    ("YklVF5l1Q8os8glyd5SM", "Camilla", "feminina", ["comunicador", "noite"]),
    ("B2J9b1PGBDt65GMZeYtU", "Clarice Rodrigues", "feminina", ["comunicador", "jornalismo"]),
    ("TOXnXBKJSHqTwwqoWW0D", "Christine", "feminina", ["comunicador", "jornalismo"]),
    ("36rVQA1AOIPwpA3Hg1tC", "Matheus", "masculina", ["jovem"]),
    ("33B4UnXyTNbgLmdEDh5P", "Keren", "feminina", ["jovem"]),
    ("r2fkFV8WAqXq2AqBpgJT", "Amandoca", "feminina", ["jovem"]),
    ("7lu3ze7orhWaNeSPowWx", "Lucas", "masculina", ["jovem"]),
    ("LuQ9eaWO9yCQrR73VQFa", "Victor Pinho", "masculina", ["jovem"]),
    ("RqO9a86p7KIlAA8RMw0I", "Betina", "feminina", ["jovem", "comunicador"]),
    ("osNEKWSDSIVQD3Same62", "Taiguara Torro", "masculina", ["jovem"]),
    ("RGymW84CSmfVugnA5tvA", "Roberta", "feminina", ["jovem", "comunicador"]),
    ("ORgG8rwdAiMYRug8RJwR", "Ana Alice", "feminina", ["jovem"]),
    ("MZxV5lN3cv7hi1376O0m", "Ana Dias", "feminina", ["jornalismo"]),
    ("7iqXtOF3wl3pomwXFY7G", "Fernanda", "feminina", ["jornalismo"]),
    ("eUAnqvLQWNX29twcYLUM", "Dyego", "masculina", ["jornalismo"]),
    ("YWH2duBH9dDQ9GowwyB5", "Alex", "masculina", ["jornalismo"]),
    ("JGY4KPk38Uc6uhd4jzeF", "Nassif (notícia)", "masculina", ["jornalismo"]),
    ("mPDAoQyGzxBSkE0OAOKw", "Carla", "feminina", ["jornalismo"]),
    ("TY3h8ANhQUsJaa0Bga5F", "Cassio Cruz", "masculina", ["jornalismo"]),
    ("9pDzHy2OpOgeXM8SeL0t", "Borges", "masculina", ["jornalismo"]),
    ("ZqE9vIHPcrC35dZv0Svu", "Adam Borges", "masculina", ["noite"]),
    ("EbiSUflQjzm4g7S895SC", "Leo Antonio", "masculina", ["noite", "gospel"]),
    ("4r3G9XKliGgVZLKMgjik", "Lair", "masculina", ["noite"]),
    ("GM2UA3fbsIaLHcswCDX9", "Nina", "feminina", ["noite"]),
    ("UZ8QqWVrz7tMdxiglcLh", "Livia", "feminina", ["noite", "gospel"]),
    ("hwnuNyWkl9DjdTFykrN6", "Adriano", "masculina", ["noite"]),
    ("YNOujSUmHtgN6anjqXPf", "Victor Power", "masculina", ["gospel"]),
    ("hgTbkcw2ddnzYh66cwCI", "Aninha", "feminina", ["gospel"]),
    ("pycQyzKletH76EvhFjXL", "Miranda", "feminina", ["gospel"]),
    ("6pQlwCgfwffNdI3jjzM6", "Fernando Borges", "masculina", ["gospel", "jornalismo"]),
    ("XBqltNZ5pAkMg6TB8lGM", "Sulamita", "feminina", ["gospel", "maduro"]),
    ("mP51FBaz7jxNEIeFJwxX", "Silas Lemos", "masculina", ["interior"]),
    ("lUaTJLTsNnLQQ5G5LJen", "Tomaz", "masculina", ["interior", "regional"]),
    ("GOkMqfyKMLVUcYfO2WbB", "Jenifer", "feminina", ["interior"]),
    ("362PVGN0qz9gh4Hb4qdA", "Jairo Moraes", "masculina", ["interior", "maduro"]),
    ("CS2gH5fPqUCmkVNpHsy4", "Raquel (interior)", "feminina", ["interior", "maduro"]),
    ("4J31DrhygVjvFsoj7BsM", "Eduardo S.", "masculina", ["regional", "comunicador"]),
    ("EsbcEfYoTFrRNrRCVEHp", "Gaúcha", "feminina", ["regional"]),
    ("bOfmGBubwU6YlrKXeRkh", "Cícero", "masculina", ["regional"]),
    ("Fy0y2P2qP6NrsDcvbxmJ", "Thayane", "feminina", ["regional"]),
    ("PznTnBc8X6pvixs9UkQm", "Dani", "feminina", ["regional"]),
    ("5p4THmLc2S6kXKO1pOM5", "Nayara Técia", "feminina", ["regional"]),
    ("Fjiik8aKXNDjmxd1Q2jF", "Nassif (esporte)", "masculina", ["esporte"]),
    ("ZgmYvdcrNoefQ4HErYZN", "Felipe Leão", "masculina", ["esporte"]),
    ("rnJZLKxtlBZt77uIED10", "Sergio", "masculina", ["maduro", "jornalismo"]),
    ("zoe2cQFqDDW4DteHDEWI", "Manoel Lopes", "masculina", ["maduro"]),
    ("woJb39z6DzSDNXoKKEnJ", "Sara", "feminina", ["maduro"]),
    ("tafm7ExcoJRarAhYvRDv", "Ester", "feminina", ["maduro"]),
]

# Vozes do catálogo atual: entram na escuta como referência (Paulo/Yasmin v4 tiveram nota 4,17 em 23/11).
ANCORAS = [
    ("Qrdut83w0Cr152Yb4Xn3", "Paulo", "masculina", ["jornalismo", "comunicador"]),
    ("lWq4KDY8znfkV0DrK8Vb", "Yasmin Alves", "feminina", ["noite", "jovem"]),
    ("rpNe0HOx7heUulPiOEaG", "Diego", "masculina", ["comunicador", "esporte"]),
    ("GDzHdQOi6jjf8zaXhCYD", "Raquel", "feminina", ["jovem", "comunicador"]),
]


def elegibilidade(chave, voice_id):
    r = httpx.get(SHARED, headers={"xi-api-key": chave}, params={"search": voice_id, "page_size": 5}, timeout=30)
    r.raise_for_status()
    v = next((x for x in r.json().get("voices", []) if x["voice_id"] == voice_id), None)
    if v is None:
        return {"elegivel": False, "motivo": "fora da biblioteca"}
    v4 = any(idioma.get("model_id") == MODELO and idioma.get("locale") == "pt-BR"
             for idioma in v.get("verified_languages") or [])
    motivos = []
    if not v4:
        motivos.append("sem pt-BR verificado no eleven_v4")
    if v.get("rate") != 1.0 or v.get("fiat_rate"):
        motivos.append(f"preço extra (rate {v.get('rate')}, fiat {v.get('fiat_rate')})")
    if (v.get("notice_period") or 0) < 365:
        motivos.append(f"aviso de remoção de {v.get('notice_period')} dias")
    if v.get("live_moderation_enabled"):
        motivos.append("moderação ao vivo")
    return {"elegivel": not motivos, "motivo": "; ".join(motivos), "public_owner_id": v["public_owner_id"],
            "nome_biblioteca": v["name"], "idade": v.get("age"), "descritivo": v.get("descriptive"),
            "uso": v.get("use_case"), "descricao": v.get("description"), "preview_url": v.get("preview_url"),
            "uso_1a_caracteres": v.get("usage_character_count_1y"), "clonada_por": v.get("cloned_by_count"),
            "aviso_dias": v.get("notice_period")}


def sintetizar(chave, voice_id, fala):
    from app.tts import client as tts
    _, payload = tts._preparar_sintese(fala["texto"], fala["tipo"], fala["tom"], False, None, MODELO, voice_id=voice_id)
    for tentativa in range(4):
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers={"xi-api-key": chave},
                       json=payload, timeout=120)
        if r.status_code == 429 and tentativa < 3:
            time.sleep(3 * (tentativa + 1))
            continue
        r.raise_for_status()
        return payload, r.content
    raise RuntimeError("429 persistente")


def gerar(chave, pasta, voice_id, fala):
    """Sintetiza + transcreve + analisa um take; devolve registro (reaproveita o que já está em disco)."""
    base = pasta / f"{fala['id']}-{voice_id}"
    mp3, scribe = base.with_suffix(".mp3"), base.with_suffix(".scribe.json")
    payload = None
    if not mp3.exists():
        payload, audio = sintetizar(chave, voice_id, fala)
        mp3.write_bytes(audio)
    if not scribe.exists():
        scribe.write_text(json.dumps(transcrever(chave, mp3.read_bytes()), ensure_ascii=False))
    transcricao = json.loads(scribe.read_text())
    if payload is None:
        from app.tts import client as tts
        _, payload = tts._preparar_sintese(fala["texto"], fala["tipo"], fala["tom"], False, None, MODELO,
                                           voice_id=voice_id)
    m = analisar(mp3, transcricao, payload["text"])
    m.update(idioma=transcricao.get("language_code"), idioma_prob=round(transcricao.get("language_probability") or 0, 3),
             transcricao=transcricao.get("text"), enviado=payload["text"])
    return m


def reprovacao(m):
    motivos = []
    if m["faltando"] > 3 or m["sobrando"] > 3:
        motivos.append(f"fidelidade ({m['faltando']} faltando, {m['sobrando']} sobrando)")
    if m["idioma"] not in ("por", "pt") or m["idioma_prob"] < 0.8:
        motivos.append(f"idioma {m['idioma']} ({m['idioma_prob']})")
    if not 120 <= m["ppm"] <= 230:
        motivos.append(f"ritmo {m['ppm']} ppm")
    return "; ".join(motivos)


def escrever_escuta(pasta, vozes, falas, registros):
    """Página às cegas: por perfil, cada voz (código embaralhado) com as falas do perfil."""
    rnd = random.Random(20261125)
    codigos = {vid: f"V{i:02d}" for i, vid in enumerate(rnd.sample(sorted(vozes), len(vozes)), 1)}
    gabarito = {codigos[vid]: {"voice_id": vid, "nome": vozes[vid]["nome"], "genero": vozes[vid]["genero"],
                               "ancora": vozes[vid]["ancora"]} for vid in vozes}
    (pasta / "gabarito.json").write_text(json.dumps(gabarito, ensure_ascii=False, indent=1))
    partes = [
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Escuta: vozes v4</title><style>'
        ":root{--bg:#fafaf9;--fg:#1c1917;--mut:#57534e;--card:#fff;--bd:#e7e5e4}"
        "@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--card:#292524;--bd:#44403c}}"
        "body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui;margin:0 auto;padding:16px;max-width:1100px}"
        "section{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 16px;margin:14px 0}"
        ".voz{border-top:1px solid var(--bd);padding:10px 0;display:grid;gap:6px}"
        ".falas{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px}"
        ".fala{font-size:13px;color:var(--mut)} audio{width:100%} .nota{display:flex;gap:12px;flex-wrap:wrap}"
        "button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--fg)}"
        "textarea{width:100%;height:140px;font:12px monospace}"
        "</style></head><body><h1>Escuta às cegas: vozes para o locutor (eleven v4)</h1>"
        "<p>Cada voz tem um código. Ouça as falas e dê a nota: 1 = muito estranho, 3 = dá pra ouvir mas incomoda, "
        "5 = soa como locutor de verdade. Marque “combina” se a voz serve para aquele tipo de programa. "
        "As notas ficam salvas neste navegador; no fim, clique em Copiar notas.</p>"
    ]
    textos = {f["id"]: f for f in falas}
    for perfil, rotulo in PERFIS.items():
        do_perfil = sorted((vid for vid in vozes if perfil in vozes[vid]["perfis"]), key=codigos.get)
        if not do_perfil:
            continue
        partes.append(f"<section><h2>{html.escape(rotulo)}</h2>")
        for vid in do_perfil:
            cod = codigos[vid]
            k = f"{perfil}:{cod}"
            partes.append(f'<div class="voz"><b>{cod}</b><div class="falas">')
            for fid in ["triagem"] + [f["id"] for f in falas if perfil in f["perfis"]]:
                if (vid, fid) in registros:
                    partes.append(f'<div><audio controls preload="none" src="{fid}-{vid}.mp3"></audio>'
                                  f'<div class="fala" title="{html.escape(textos[fid]["texto"])}">{fid}</div></div>')
            partes.append('</div><span class="nota">')
            partes += [f'<label><input type="radio" name="{k}" value="{n}" data-k="{k}"> {n}</label>' for n in range(1, 6)]
            partes.append(f'<label><input type="checkbox" data-c="{k}"> combina com o perfil</label></span></div>')
        partes.append("</section>")
    partes.append(
        '<p><button id="copiar">Copiar notas</button></p><textarea id="saida" readonly></textarea><script>'
        "const K='escuta-vozes-v4';const s=JSON.parse(localStorage.getItem(K)||'{}');"
        "document.querySelectorAll('input[data-k]').forEach(i=>{if(s[i.dataset.k]==i.value)i.checked=true;"
        "i.onchange=()=>{s[i.dataset.k]=+i.value;localStorage.setItem(K,JSON.stringify(s))}});"
        "document.querySelectorAll('input[data-c]').forEach(i=>{const k='combina:'+i.dataset.c;i.checked=!!s[k];"
        "i.onchange=()=>{s[k]=i.checked;localStorage.setItem(K,JSON.stringify(s))}});"
        "document.getElementById('copiar').onclick=()=>{const t=JSON.stringify(s,null,1);"
        "document.getElementById('saida').value=t;navigator.clipboard&&navigator.clipboard.writeText(t)};"
        "</script></body></html>")
    (pasta / "escuta.html").write_text("".join(partes))


def escrever_decisao(pasta, res, falas):
    """Página para decidir o catálogo (com nomes): por perfil, as vozes do catálogo proposto
    (app/tts/voices.py) primeiro e as alternativas depois, cada uma com seus áudios e Aprovar/Reprovar."""
    from app.tts.voices import VOZES_DISPONIVEIS

    no_catalogo = {v["voz_id"]: v for v in VOZES_DISPONIVEIS}
    textos = {f["id"]: f["texto"] for f in falas}
    partes = [
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Decisão: vozes v4</title><style>'
        ":root{--bg:#fafaf9;--fg:#1c1917;--mut:#57534e;--card:#fff;--bd:#e7e5e4;--ok:#15803d;--no:#b91c1c}"
        "@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--card:#292524;--bd:#44403c;"
        "--ok:#4ade80;--no:#f87171}}"
        "body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui;margin:0 auto;padding:16px;max-width:1100px}"
        "section{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 16px;margin:14px 0}"
        ".voz{border-top:1px solid var(--bd);padding:10px 0;display:grid;gap:6px}"
        ".meta{color:var(--mut);font-size:13px} .tag{font-size:12px;border:1px solid var(--bd);border-radius:99px;padding:0 8px}"
        ".falas{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px}"
        ".fala{font-size:12px;color:var(--mut)} audio{width:100%} .acoes{display:flex;gap:8px;align-items:center}"
        "button{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--fg)}"
        "button[aria-pressed=true].sim{border-color:var(--ok);color:var(--ok);font-weight:600}"
        "button[aria-pressed=true].nao{border-color:var(--no);color:var(--no);font-weight:600}"
        "textarea{width:100%;height:140px;font:12px monospace} h3{margin:8px 0 0;font-size:14px;color:var(--mut)}"
        "</style></head><body><h1>Vozes para o locutor (eleven v4): o que entra no catálogo</h1>"
        "<p>Ouça e marque Aprovar ou Reprovar. “No catálogo proposto” são as vozes que já estão na branch; "
        "reprovar tira do catálogo, aprovar uma alternativa coloca. A mesma voz aparece em mais de um perfil: a "
        "decisão vale para todos. Fica salvo neste navegador; no fim, clique em Copiar decisões.</p>"
    ]
    for perfil, rotulo in PERFIS.items():
        vozes = [vid for vid, r in res.items() if perfil in r["perfis"] and r.get("falas")]
        vozes += [vid for vid in no_catalogo if perfil in no_catalogo[vid]["perfis"] and vid not in vozes and vid in res]
        if not vozes:
            continue
        partes.append(f"<section><h2>{html.escape(rotulo)}</h2>")
        for titulo, grupo in (("No catálogo proposto", [v for v in vozes if v in no_catalogo]),
                              ("Alternativas", [v for v in vozes if v not in no_catalogo])):
            if not grupo:
                continue
            partes.append(f"<h3>{titulo}</h3>")
            for vid in grupo:
                r = res[vid]
                nome = no_catalogo[vid]["nome"] if vid in no_catalogo else r["nome"]
                t = r.get("triagem") or r.get("falas", {}).get("triagem") or {}
                uso = r.get("uso_1a_caracteres")
                meta = [r["genero"], f"{t['ppm']} palavras/min" if t.get("ppm") else None,
                        f"{uso / 1e6:.0f} mi caracteres/ano na biblioteca" if uso else None,
                        "já no catálogo antes" if r.get("ancora") else None]
                partes.append(f'<div class="voz"><div><b>{html.escape(nome)}</b> '
                              f'<span class="meta">{html.escape(" · ".join(m for m in meta if m))}</span></div>')
                if r.get("descricao"):
                    partes.append(f'<div class="meta">{html.escape(r["descricao"][:220])}</div>')
                partes.append('<div class="falas">')
                for fid in ["triagem"] + [f["id"] for f in falas if f["id"] != "triagem"]:
                    if fid in r.get("falas", {}) and "erro" not in r["falas"][fid]:
                        partes.append(f'<div><audio controls preload="none" src="{fid}-{vid}.mp3"></audio>'
                                      f'<div class="fala" title="{html.escape(textos[fid])}">{fid}</div></div>')
                partes.append(f'</div><div class="acoes"><button class="sim" data-v="{vid}" data-d="aprovar">Aprovar</button>'
                              f'<button class="nao" data-v="{vid}" data-d="reprovar">Reprovar</button></div></div>')
        partes.append("</section>")
    partes.append(
        '<p><button id="copiar">Copiar decisões</button></p><textarea id="saida" readonly></textarea><script>'
        "const K='decisao-vozes-v4';const s=JSON.parse(localStorage.getItem(K)||'{}');"
        "function pintar(){document.querySelectorAll('button[data-v]').forEach(b=>b.setAttribute('aria-pressed',"
        "s[b.dataset.v]===b.dataset.d))}"
        "document.querySelectorAll('button[data-v]').forEach(b=>b.onclick=()=>{s[b.dataset.v]=s[b.dataset.v]===b.dataset.d?"
        "undefined:b.dataset.d;localStorage.setItem(K,JSON.stringify(s));pintar()});pintar();"
        "document.getElementById('copiar').onclick=()=>{const t=JSON.stringify(s,null,1);"
        "document.getElementById('saida').value=t;navigator.clipboard&&navigator.clipboard.writeText(t)};"
        "</script></body></html>")
    (pasta / "decisao.html").write_text("".join(partes))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    pasta = Path(args.output)
    pasta.mkdir(parents=True, exist_ok=True)

    from app.config.settings import settings
    settings.ia_orcamento_bloquear = False
    settings.ia_medicao_habilitada = False
    settings.ia_cache_habilitado = False
    chave = settings.elevenlabs_api_key
    falas = json.loads(CORPUS.read_text())["falas"]
    triagem = next(f for f in falas if f["id"] == "triagem")

    saida = pasta / "resultados.json"
    res = json.loads(saida.read_text()) if saida.exists() else {}

    def salvar():
        saida.write_text(json.dumps(res, ensure_ascii=False, indent=1))

    # 1. Elegibilidade
    for vid, nome, genero, perfis in CANDIDATAS:
        if vid not in res:
            res[vid] = {"nome": nome, "genero": genero, "perfis": perfis, "ancora": False, **elegibilidade(chave, vid)}
    for vid, nome, genero, perfis in ANCORAS:
        res.setdefault(vid, {"nome": nome, "genero": genero, "perfis": perfis, "ancora": True, "elegivel": True,
                             "motivo": ""})
    salvar()

    # 2. Triagem
    elegiveis = [vid for vid, r in res.items() if r["elegivel"] and not r["ancora"]]
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futuros = {ex.submit(gerar, chave, pasta, vid, triagem): vid for vid in elegiveis
                   if "triagem" not in res[vid]}
        for fut in cf.as_completed(futuros):
            vid = futuros[fut]
            try:
                res[vid]["triagem"] = fut.result()
            except Exception as exc:  # noqa: BLE001 -- registra a falha da voz e segue com as outras
                res[vid]["triagem"] = {"erro": f"{type(exc).__name__}: {exc}"[:300]}
            salvar()
    for vid in elegiveis:
        t = res[vid]["triagem"]
        res[vid]["reprovada"] = t.get("erro") or reprovacao(t)
    salvar()

    # 3. Escuta: aprovadas + âncoras, falas do perfil
    escuta = [vid for vid, r in res.items() if r["ancora"] or (r["elegivel"] and not r.get("reprovada"))]
    tarefas = []
    for vid in escuta:
        for f in falas:
            if (f["id"] == "triagem" or set(f["perfis"]) & set(res[vid]["perfis"])) and f["id"] not in res[vid].get("falas", {}):
                tarefas.append((vid, f))
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futuros = {ex.submit(gerar, chave, pasta, vid, f): (vid, f["id"]) for vid, f in tarefas}
        for fut in cf.as_completed(futuros):
            vid, fid = futuros[fut]
            try:
                res[vid].setdefault("falas", {})[fid] = fut.result()
            except Exception as exc:  # noqa: BLE001
                res[vid].setdefault("falas", {})[fid] = {"erro": f"{type(exc).__name__}: {exc}"[:300]}
            salvar()

    registros = {(vid, fid) for vid in escuta for fid, m in res[vid].get("falas", {}).items() if "erro" not in m}
    escrever_escuta(pasta, {vid: res[vid] for vid in escuta}, falas, registros)
    escrever_decisao(pasta, {vid: res[vid] for vid in escuta}, falas)

    n_eleg = len(elegiveis)
    n_aprov = sum(1 for vid in elegiveis if not res[vid]["reprovada"])
    print(f"{len(CANDIDATAS)} candidatas, {n_eleg} elegíveis, {n_aprov} aprovadas na triagem, "
          f"{len(registros)} áudios na escuta")
    for vid in elegiveis:
        if res[vid]["reprovada"]:
            print("  reprovada:", res[vid]["nome"], "-", res[vid]["reprovada"])
    for vid, r in res.items():
        if not r["elegivel"]:
            print("  inelegível:", r["nome"], "-", r["motivo"])


if __name__ == "__main__":
    main()
