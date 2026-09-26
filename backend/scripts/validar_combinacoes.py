"""Validação real de cada combinação texto + voz. Consome créditos (Anthropic e ElevenLabs).

Execute a partir de backend:
  PYTHONPATH=. .venv-test/bin/python scripts/validar_combinacoes.py --output ../docs/benchmarks/<data>-combinacoes
  --combinacoes <ids> --acrescentar   valida só essas e mantém as demais já medidas na pasta
  --exportar-exemplos                 grava o exemplo de cada combinação (caso "musica") para o
                                      catálogo: app/billing/exemplos_combinacoes.json e o áudio em
                                      frontend-painel/public/exemplos/combinacoes/

Para cada combinação de app/billing/combinacoes.py:
1. Texto: gera as falas dos casos com o modelo de texto e o mesmo prompt do ao vivo (inclusive a
   instrução de direção vocal quando a voz é v3). Checagens determinísticas (tamanho, tags, JSON)
   e juiz LLM pontual com critérios por caso (padrão da skill llm-evaluation).
2. Voz: sintetiza cada fala pelo pipeline real (normalização de números, tags, perfil da voz),
   transcreve com Scribe v2 (skill speech-to-text) e mede divergência de palavras (WER), tag lida
   em voz alta, duração e saturação.
Dados fictícios. Não usa banco, não altera configurações persistidas nem chama endpoints.
"""

import argparse
import html
import json
import re
import shutil
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

TAGS_V3 = {"excited", "calm", "laughs", "sighs", "whispers", "sarcastic", "pause"}
# Palavras de tag que não aparecem naturalmente em português falado: se o transcritor as
# ouviu, a tag vazou para a locução.
TAGS_FALADAS = re.compile(r"\b(excited|calm|laughs|sighs|whispers|sarcastic|pause)\b", re.I)

CASOS = {
    "musica": {
        "pedido": "Anuncie Twist and Shout, dos Beatles, pedida por Marcos. Escreva de 60 a 90 palavras, sem inventar curiosidades.",
        "contexto": "", "max_palavras": 90, "tipo_bloco": "musica", "tom": "energico",
        "criterio": "Anuncia Twist and Shout, dos Beatles, e cita o ouvinte Marcos. Não inventa curiosidades, datas ou fatos sobre a música ou a banda.",
    },
    "evento_sem_autorizacao": {
        "pedido": "Faça uma chamada animada convidando os ouvintes para o Festival da Praça hoje. Use até 90 palavras.",
        "contexto": "\nConhecimento local: Festival da Praça, edição deste ano, hoje das oito às vinte e três horas. A rádio não autorizou divulgação desse evento.",
        "max_palavras": 90, "tipo_bloco": "comentario", "tom": "neutro",
        "criterio": "NÃO divulga nem convida para o Festival da Praça (a rádio não autorizou). Pode mudar de assunto com naturalidade, sem explicar regras internas ao ouvinte.",
    },
    "evento_data_incerta": {
        "pedido": "Ouvinte: quando vai acontecer a Festa do Bairro? Responda em até 60 palavras.",
        "contexto": "\nConhecimento local: Festa do Bairro, evento anual. Não há data confirmada para a edição atual.",
        "max_palavras": 60, "tipo_bloco": "comentario", "tom": "neutro",
        "criterio": "Não informa data nem acrescenta fatos (local, tradição, atrações) além de ser um evento anual sem data confirmada.",
    },
    "evento_encerrado": {
        "pedido": "Convide o público para a feira hoje. Use até 60 palavras.",
        "contexto": "\nA rádio autorizou divulgar a Feira Cultural, realizada em 10/08/2025, das oito às dezoito horas. Essa edição já terminou.",
        "max_palavras": 60, "tipo_bloco": "comentario", "tom": "neutro",
        "criterio": "Não convida para a Feira Cultural como se fosse hoje: a edição já terminou. Não inventa nova data.",
    },
    "numeros": {
        "pedido": "Informe que faz 23 graus agora, o telefone da rádio, 41 3333-4444, e que o ingresso da Feira do Livro custa R$ 19,90. Use até 50 palavras.",
        "contexto": "\nA rádio autorizou divulgar a Feira do Livro, amanhã, com ingresso a R$ 19,90.",
        "max_palavras": 50, "tipo_bloco": "comentario", "tom": "calmo",
        "criterio": "Mantém exatamente 23 graus, o telefone 41 3333-4444 e o preço R$ 19,90.",
    },
    "dialogo": {
        "pedido": "Anunciem Twist and Shout, dos Beatles, pedida por Marcos, em 2 a 4 falas e até 120 palavras no total.",
        "contexto": '\nNeste bloco, Paulo e Maria apresentam juntos. Responda apenas JSON: {"linhas":[{"locutor":"Paulo ou Maria","texto":"fala"}]}.',
        "max_palavras": 120, "tipo_bloco": "musica", "tom": "energico", "dialogo": True,
        "criterio": "Diálogo natural entre Paulo e Maria, 2 a 4 falas, anuncia Twist and Shout dos Beatles pedida por Marcos, sem inventar curiosidades.",
    },
}

JUIZ = """Você avalia falas geradas para uma rádio brasileira ao vivo. Seja rigoroso e objetivo.
O locutor conhece o prompt do sistema enviado junto (nome da rádio, frequência, programa, cidade,
data e hora atuais): usar essas informações NÃO é inventar. Inventar é afirmar fato ausente do
prompt, do contexto e do pedido.
Critérios (1 a 5):
- fidelidade: nenhum fato além do pedido e do contexto (5 = nada inventado).
- instrucoes: cumpre o critério do caso e o limite de palavras.
- naturalidade: soa como fala de locutor de rádio em português do Brasil.
Responda só JSON: {"fidelidade":n,"instrucoes":n,"naturalidade":n,"aprovado":true|false,"motivo":"uma frase"}
Aprovado exige fidelidade e instrucoes >= 4."""


DIGITOS = "zero um dois tres quatro cinco seis sete oito nove".split()


def normalizar(texto):
    """Mesma forma para o texto enviado e o transcrito: números por extenso como o sintetizador
    recebe, sem acento e pontuação. O transcritor escreve "98.5", "98,5" ou "4133334-444" para a
    mesma fala; sem isso a divergência mediria formato, não pronúncia."""
    from app.numeros import normalizar_texto_fala
    texto = normalizar_texto_fala(texto)
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\d", lambda m: f" {DIGITOS[int(m.group())]} ", texto)  # sequências que o normalizador não converte
    texto = re.sub(r"\bvirgula\b", "ponto", texto)
    texto = re.sub(r"\befe eme\b", "fm", texto)
    return re.findall(r"[a-z]+", texto)


def wer(referencia, hipotese):
    r, h = referencia, hipotese
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        anterior, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            atual = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, anterior + (r[i - 1] != h[j - 1]))
            anterior = atual
    return d[len(h)] / max(1, len(r))


def gerar_textos(combinacao, base, cliente):
    from app.live.router import INSTRUCAO_TAGS_V3
    registros = []
    for caso, dados in CASOS.items():
        system = base + dados["contexto"]
        if combinacao.voz == "eleven_v3" and dados["tipo_bloco"] != "noticia":
            system += "\n" + INSTRUCAO_TAGS_V3
        parametros = {} if "haiku" in combinacao.texto else {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}
        inicio = time.perf_counter()
        r = cliente.messages.create(model=combinacao.texto, max_tokens=512, system=system,
                                    messages=[{"role": "user", "content": dados["pedido"]}], **parametros)
        texto = "".join(b.text for b in r.content if b.type == "text").strip()
        registros.append({"combinacao": combinacao.id, "caso": caso, "texto": texto, "stop_reason": r.stop_reason, "system": system,
                          "entrada": r.usage.input_tokens, "saida": r.usage.output_tokens,
                          "segundos_texto": round(time.perf_counter() - inicio, 2)})
    return registros


def falas(registro):
    """Trechos que vão para a voz. Diálogo: uma fala por linha do JSON."""
    if not CASOS[registro["caso"]].get("dialogo"):
        return [registro["texto"]]
    from app.llm.json_utils import extrair_json
    try:
        return [linha["texto"] for linha in extrair_json(registro["texto"])["linhas"]]
    except Exception:
        return []


def checar_texto(registro, combinacao):
    dados = CASOS[registro["caso"]]
    trechos = falas(registro)
    corpo = " ".join(trechos)
    tags = re.findall(r"\[([^\[\]]+)\]", corpo)
    palavras = len(re.findall(r"\w+", re.sub(r"\[[^\]]*\]", "", corpo)))
    problemas = []
    if dados.get("dialogo") and not 2 <= len(trechos) <= 4:
        problemas.append(f"diálogo com {len(trechos)} falas ou JSON inválido")
    if palavras > dados["max_palavras"] * 1.1:
        problemas.append(f"{palavras} palavras (limite {dados['max_palavras']})")
    if combinacao.voz != "eleven_v3" and tags:
        problemas.append(f"tags sem voz v3: {tags}")
    fora = [t for t in tags if t.strip().lower() not in TAGS_V3]
    if fora:
        problemas.append(f"tags fora da lista: {fora}")
    if len(tags) > (2 * max(1, len(trechos))):
        problemas.append(f"{len(tags)} tags (máximo 2 por fala)")
    if registro["stop_reason"] != "end_turn":
        problemas.append(f"parada: {registro['stop_reason']}")
    return {"palavras": palavras, "tags": tags, "problemas_texto": problemas}


def julgar(registro, cliente, modelo_juiz):
    from app.llm.json_utils import extrair_json
    dados = CASOS[registro["caso"]]
    pedido = (f"Prompt do sistema do locutor:\n<prompt>\n{registro['system']}\n</prompt>\n\nPedido: {dados['pedido']}\n"
              f"Critério do caso: {dados['criterio']}\n\nFala gerada:\n{registro['texto']}")
    r = cliente.messages.create(model=modelo_juiz, max_tokens=300, system=JUIZ,
                                messages=[{"role": "user", "content": pedido}],
                                thinking={"type": "disabled"}, output_config={"effort": "low"})
    try:
        return extrair_json("".join(b.text for b in r.content if b.type == "text"))
    except Exception:
        return {"aprovado": False, "motivo": "juiz sem JSON válido"}


def transcrever(audio, chaves):
    import httpx
    from app.config.settings import settings
    for modelo in ("scribe_v2", "scribe_v1"):
        with httpx.Client(timeout=90) as c:
            r = c.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": settings.elevenlabs_api_key},
                       files={"file": ("fala.mp3", audio, "audio/mpeg")},
                       data={"model_id": modelo, "language_code": "por", "keyterms": chaves} if modelo == "scribe_v2"
                       else {"model_id": modelo, "language_code": "por"})
        if r.status_code == 422 and modelo == "scribe_v2":
            continue
        r.raise_for_status()
        corpo = r.json()
        palavras = [w["text"] for w in corpo.get("words", []) if w.get("type") == "word"]
        eventos = [w["text"] for w in corpo.get("words", []) if w.get("type") == "audio_event"]
        return {"modelo_stt": modelo, "transcricao": " ".join(palavras) or corpo.get("text", ""), "eventos_audio": eventos}
    raise RuntimeError("Scribe indisponível")


def sintetizar(combinacao, registro, pasta):
    import numpy as np
    from app.config.settings import settings
    from app.postprod.audio_io import mp3_bytes_para_array
    from app.tts.client import _TAG_INLINE_RE, _preparar_sintese, sintetizar_audio
    from app.tts.voices import voz_valida
    dados = CASOS[registro["caso"]]
    voz = settings.elevenlabs_voice_id
    clonada = not voz_valida(voz)
    resultados = []
    for i, trecho in enumerate(falas(registro)):
        _, payload = _preparar_sintese(trecho, dados["tipo_bloco"], dados["tom"], clonada, None, combinacao.voz, "atual", None, voz)
        falado = _TAG_INLINE_RE.sub(" ", payload["text"])
        item = {"trecho": i, "texto_enviado": payload["text"], "caracteres": len(payload["text"])}
        inicio = time.perf_counter()
        try:
            audio = sintetizar_audio(trecho, voz, tipo_bloco=dados["tipo_bloco"], tom=dados["tom"], eh_clonada=clonada,
                                     modelo=combinacao.voz, timeout_segundos=90, max_tentativas=3, reutilizar_audio=False)
        except Exception as exc:
            item.update(ok=False, erro=f"{type(exc).__name__}: {str(exc)[:120]}")
            resultados.append(item)
            continue
        item["segundos_voz"] = round(time.perf_counter() - inicio, 2)
        arquivo = f"{combinacao.id}-{registro['caso']}-{i + 1}.mp3"
        (pasta / arquivo).write_bytes(audio)
        amostras, taxa, _ = mp3_bytes_para_array(audio)
        stt = transcrever(audio, ["Twist and Shout", "Beatles", "Marcos", "Paulo", "Maria"])
        item.update(ok=True, arquivo=arquivo, duracao_segundos=round(amostras.shape[1] / taxa, 2),
                    pico=round(float(np.max(np.abs(amostras))), 4),
                    fracao_saturada=float(np.mean(np.abs(amostras) >= 0.999)),
                    wer=round(wer(normalizar(falado), normalizar(stt["transcricao"])), 4),
                    tag_falada=bool(TAGS_FALADAS.search(stt["transcricao"])), **stt)
        resultados.append(item)
    return resultados


def validar(combinacao, base, pasta, modelo_juiz):
    from anthropic import Anthropic
    from app.config.settings import settings
    cliente = Anthropic(api_key=settings.anthropic_api_key, timeout=60, max_retries=1)
    registros = gerar_textos(combinacao, base, cliente)
    for registro in registros:
        registro.update(checar_texto(registro, combinacao))
        registro["juiz"] = julgar(registro, cliente, modelo_juiz)
        registro["voz"] = sintetizar(combinacao, registro, pasta)
        print(json.dumps({k: registro[k] for k in ("combinacao", "caso", "problemas_texto")} | {
            "aprovado": registro["juiz"].get("aprovado"),
            "wer": [v.get("wer") for v in registro["voz"]]}, ensure_ascii=False), flush=True)
    return registros


def resumo(registros, combinacoes, tarifas):
    linhas = []
    for c in combinacoes:
        rs = [r for r in registros if r["combinacao"] == c.id]
        vozes = [v for r in rs for v in r["voz"]]
        ok = [v for v in vozes if v.get("ok")]
        entrada, saida = sum(r["entrada"] for r in rs), sum(r["saida"] for r in rs)
        custo_texto = (entrada * tarifas[c.texto][0] + saida * tarifas[c.texto][1]) / 1e6
        custo_voz = sum(v["caracteres"] for v in vozes) / 1000 * tarifas[c.voz]
        linhas.append({
            "combinacao": c.id, "texto": c.texto, "voz": c.voz,
            "casos_aprovados_juiz": sum(1 for r in rs if r["juiz"].get("aprovado")), "casos": len(rs),
            "casos_sem_problema_texto": sum(1 for r in rs if not r["problemas_texto"]),
            "fidelidade_media": round(sum(r["juiz"].get("fidelidade", 0) for r in rs) / len(rs), 2),
            "instrucoes_media": round(sum(r["juiz"].get("instrucoes", 0) for r in rs) / len(rs), 2),
            "naturalidade_media": round(sum(r["juiz"].get("naturalidade", 0) for r in rs) / len(rs), 2),
            "audios_ok": len(ok), "audios": len(vozes),
            "wer_medio": round(sum(v["wer"] for v in ok) / len(ok), 4) if ok else None,
            "wer_maximo": max((v["wer"] for v in ok), default=None),
            "tags_faladas": sum(1 for v in ok if v["tag_falada"]),
            "saturacao_max": max((v["fracao_saturada"] for v in ok), default=None),
            "segundos_voz_medio": round(sum(v["segundos_voz"] for v in ok) / len(ok), 2) if ok else None,
            "custo_usd_amostra": round(custo_texto + custo_voz, 4),
        })
    return linhas


NOMES_MODELOS = {"claude-opus-5": "Opus 5", "claude-sonnet-5": "Sonnet 5", "claude-haiku-4-5": "Haiku 4.5",
                 "eleven_v3": "ElevenLabs v3", "eleven_flash_v2_5": "ElevenLabs Flash 2.5"}
CASO_EXEMPLO = "musica"


def escrever_escuta(pasta, registros, combinacoes):
    """Página estática para escuta humana lado a lado (o plano exige validação de áudio por ouvido)."""
    nomes = {c.id: f"{c.nome} · {NOMES_MODELOS[c.texto]} + {NOMES_MODELOS[c.voz]}" for c in combinacoes}
    blocos = []
    for caso in CASOS:
        itens = []
        for r in [r for r in registros if r["caso"] == caso]:
            j = r["juiz"]
            audios = "".join(
                f'<figure><audio controls preload="none" src="{v["arquivo"]}"></audio><figcaption>WER {v["wer"]:.1%} · '
                f'{v["duracao_segundos"]} s · ouvido: “{html.escape(v["transcricao"])}”</figcaption></figure>'
                for v in r["voz"] if v.get("ok"))
            alerta = f"<p class='alerta'>{html.escape('; '.join(r['problemas_texto']))}</p>" if r["problemas_texto"] else ""
            itens.append(
                f'<article><h3>{nomes[r["combinacao"]]}</h3><p class="nota">Juiz: {"aprovado" if j.get("aprovado") else "reprovado"}'
                f' · fidelidade {j.get("fidelidade")} · instruções {j.get("instrucoes")} · naturalidade {j.get("naturalidade")}</p>'
                f'<p class="nota">{html.escape(j.get("motivo", ""))}</p>{alerta}<details><summary>Texto gerado</summary>'
                f'<pre>{html.escape(r["texto"])}</pre></details>{audios}</article>')
        blocos.append(f'<section><h2>{caso.replace("_", " ")}</h2><div class="grade">{"".join(itens)}</div></section>')
    estilo = """:root{color-scheme:light dark;--fundo:#f6f7fb;--cartao:#fff;--texto:#1b1f2a;--suave:#5b6275;--borda:#d9dce5;--alerta:#b54708}
@media (prefers-color-scheme:dark){:root{--fundo:#0f1320;--cartao:#171c2c;--texto:#e7e9f0;--suave:#9aa1b5;--borda:#2a3145;--alerta:#f5a524}}
body{margin:0;padding:24px 16px;background:var(--fundo);color:var(--texto);font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto} h1{font-size:1.4rem} h2{text-transform:capitalize;font-size:1.1rem;margin-top:2rem}
.grade{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr))}
article{background:var(--cartao);border:1px solid var(--borda);border-radius:14px;padding:14px} h3{margin:0 0 4px;font-size:1rem}
.nota,figcaption{color:var(--suave);font-size:.85rem;margin:2px 0} .alerta{color:var(--alerta);font-size:.85rem}
audio{width:100%;margin-top:8px} pre{white-space:pre-wrap;word-break:break-word;font-size:.85rem} figure{margin:0}"""
    (pasta / "escuta.html").write_text(
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Escuta das combinações</title><style>{estilo}</style></head><body><main><h1>Escuta das combinações texto + voz</h1>'
        f'<p>Dados fictícios, uma geração por caso. Ouça antes de consultar as notas: WER e juiz não medem expressividade nem '
        f'identidade vocal.</p>{"".join(blocos)}</main></body></html>')


def exportar_exemplos(pasta, registros, raiz_repo):
    """Exemplo do catálogo: o anúncio de música de cada combinação, com o texto sem as tags de
    direção vocal (o cliente ouve o efeito) e as unidades medidas para recalcular o preço."""
    publico = raiz_repo / "frontend-painel" / "public" / "exemplos" / "combinacoes"
    publico.mkdir(parents=True, exist_ok=True)
    saida = {}
    for r in registros:
        if r["caso"] != CASO_EXEMPLO or not r["voz"] or not r["voz"][0].get("ok"):
            continue
        voz = r["voz"][0]
        shutil.copyfile(pasta / voz["arquivo"], publico / f"{r['combinacao']}.mp3")
        saida[r["combinacao"]] = {
            "pedido": CASOS[CASO_EXEMPLO]["pedido"],
            "texto": re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", " ", r["texto"])).strip(),
            "audio_url": f"/exemplos/combinacoes/{r['combinacao']}.mp3",
            "duracao_segundos": voz["duracao_segundos"],
            "caracteres_voz": voz["caracteres"],
            "unidades_texto": {"entrada": r["entrada"], "saida": r["saida"]},
        }
    destino = raiz_repo / "backend" / "app" / "billing" / "exemplos_combinacoes.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n")
    print(f"exemplos exportados: {sorted(saida)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--combinacoes", nargs="*", help="ids (padrão: todas)")
    parser.add_argument("--juiz", default="claude-opus-5")
    parser.add_argument("--acrescentar", action="store_true", help="mantém na pasta os resultados das demais combinações")
    parser.add_argument("--exportar-exemplos", action="store_true", help="atualiza os exemplos do catálogo")
    parser.add_argument("--so-exportar", action="store_true", help="não chama APIs; só regenera escuta/resumo/exemplos")
    args = parser.parse_args()

    import fakeredis
    from app.billing.combinacoes import COMBINACOES
    from app.config.settings import settings
    from app.llm import prompt_builder
    # Validação isolada: sem conta, sem banco, sem cache de áudio entre combinações.
    settings.ia_orcamento_bloquear = False
    settings.ia_medicao_habilitada = False
    settings.ia_cache_habilitado = False
    prompt_builder.redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    prompt_builder.obter_clima_atual = lambda cidade: None
    conta = SimpleNamespace(nome_radio="Rádio Teste", frequencia="98.5 FM", cidade="Curitiba", slogan="", telefone="",
                            endereco="", conhecimento_local={}, biblia_radio={})
    locutor = SimpleNamespace(id=1, nome_locutor="Paulo", personalidade="Natural e acolhedor", timezone="America/Sao_Paulo",
                              biografia="", tracos_marcantes=[], fatos_do_dia=[])
    programa = SimpleNamespace(id=1, nome="Tarde Musical", tom="animado", descricao="",
                               topicos_permitidos=["música", "conversa com ouvintes", "cultura local"], generos_musicais=[],
                               musicas_permitidas=[], assuntos_ao_vivo=[], tipos_noticias=[], fontes_noticias=[],
                               criterios_busca_musicas="", topicos_proibidos=[], musicas_bloqueadas=[], estrutura_blocos=[],
                               pode_pesquisar=False, feriados_municipais=[])
    base = prompt_builder.montar_system_prompt(conta, locutor, programa)

    combinacoes = [c for c in COMBINACOES if not args.combinacoes or c.id in args.combinacoes]
    args.output.mkdir(parents=True, exist_ok=True)
    arquivo = args.output / "resultados.json"
    anteriores = json.loads(arquivo.read_text()) if (args.acrescentar or args.so_exportar) and arquivo.exists() else []
    registros = []
    if not args.so_exportar:
        (args.output / "casos.json").write_text(json.dumps({"system_prompt": base, "casos": CASOS}, ensure_ascii=False, indent=2))
        # Uma combinação por thread; dentro dela, sequencial (respeita limite de concorrência da voz).
        with ThreadPoolExecutor(max_workers=len(combinacoes)) as pool:
            registros = [r for lote in pool.map(lambda c: validar(c, base, args.output, args.juiz), combinacoes) for r in lote]
    novas = {r["combinacao"] for r in registros}
    # Prompt base já está em casos.json; repetir em cada registro só incharia o arquivo.
    registros = [r for r in anteriores if r["combinacao"] not in novas] + [{k: v for k, v in r.items() if k != "system"} for r in registros]
    ordem = [c.id for c in COMBINACOES]
    registros.sort(key=lambda r: (ordem.index(r["combinacao"]), list(CASOS).index(r["caso"])))
    arquivo.write_text(json.dumps(registros, ensure_ascii=False, indent=2))
    presentes = [c for c in COMBINACOES if any(r["combinacao"] == c.id for r in registros)]
    escrever_escuta(args.output, registros, presentes)
    if args.exportar_exemplos:
        exportar_exemplos(args.output, registros, Path(__file__).resolve().parents[2])
    tarifas = {**{k: v for k, v in settings.ia_tarifas_llm.items()}, **settings.ia_tarifas_tts}
    linhas = resumo(registros, presentes, tarifas)
    (args.output / "resumo.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=2))
    for linha in linhas:
        print(json.dumps(linha, ensure_ascii=False))


if __name__ == "__main__":
    main()
