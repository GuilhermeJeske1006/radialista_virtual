"""Compara eleven_v4 / v4 Turbo com o v3 e o Flash pelo mesmo caminho de síntese do ao vivo.

Consome créditos reais (TTS + Scribe). Execute a partir de backend:
  PYTHONPATH=. .venv/bin/python scripts/comparar_v4.py --output ../docs/benchmarks/2026-10-08-eleven-v4
Mede latência (primeiro byte e total, via streaming), duração, palavras/minuto, caracteres
cobrados (header character-cost) e fidelidade pela transcrição: palavras faltando/sobrando e
tag de direção vocal lida em voz alta. Não mede expressividade -- isso exige audição.
"""

import argparse
import json
import re
import subprocess
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import httpx

MODELOS = ["eleven_v3", "eleven_v4", "eleven_v4_turbo", "eleven_flash_v2_5"]
VOZES = {"padrao": None, "paulo": "Qrdut83w0Cr152Yb4Xn3", "yasmin": "lWq4KDY8znfkV0DrK8Vb"}

# Falas no formato que o LLM entrega pro ao vivo: tags da whitelist, "......" de troca de
# assunto e números/valores que passam por app.numeros antes da síntese.
CASOS = {
    "abertura": ("abertura", "energico",
        "Boa tarde, Curitiba! [excited] São 15h30, 22 graus lá fora, e a Rádio Teste segue com você até o fim da "
        "tarde. Tem pedido de ouvinte, tem previsão do tempo e tem muita música boa. Fica com a gente!"),
    "noticia": ("noticia", "calmo",
        "A prefeitura anunciou hoje a reforma de 12 escolas municipais. O investimento é de R$ 4,5 milhões e as "
        "obras começam na próxima segunda-feira, dia 14. Segundo a secretaria, as aulas não serão interrompidas."),
    "comentario": ("comentario", "neutro",
        "Olha, eu confesso que essa semana foi corrida demais. [laughs] Mas sabe quando chega sexta e tudo melhora? "
        "Pois é...... hoje é sexta! E a gente vai comemorar do jeito certo, com o melhor da música brasileira."),
    "patrocinador": ("patrocinador", "neutro",
        "Padaria Pão Quente: pão francês a R$ 12,90 o quilo e café passado na hora. Rua das Flores, 230, aberta "
        "todos os dias das 6h às 20h. Padaria Pão Quente, o sabor do seu bairro."),
    "chamada_ouvinte": ("chamada_ouvinte", "energico",
        "E olha quem mandou mensagem: a dona Cida, lá do Boqueirão! [sighs] Ela diz que tá com saudade do filho que "
        "mora longe e pediu uma música pra ele. Cida, esse abraço vai pra vocês dois!"),
}

TAGS = {"excited", "calm", "laughs", "sighs", "whispers", "sarcastic", "pause"}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", texto)


def duracao(caminho):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(caminho)]).strip())


def transcrever(chave, audio):
    resposta = httpx.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": chave},
                          files={"file": ("a.mp3", audio, "audio/mpeg")},
                          data={"model_id": "scribe_v2", "language_code": "por", "tag_audio_events": "true"},
                          timeout=60)
    resposta.raise_for_status()
    return resposta.json().get("text", "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--modelos", default=",".join(MODELOS))
    parser.add_argument("--vozes", default=",".join(VOZES))
    args = parser.parse_args()
    pasta = Path(args.output)
    pasta.mkdir(parents=True, exist_ok=True)

    from app.config.settings import settings
    settings.ia_orcamento_bloquear = False
    settings.ia_medicao_habilitada = False
    settings.ia_cache_habilitado = False
    from app.tts import client as tts

    # Captura o header character-cost da resposta sem mudar o caminho de síntese.
    custos = []
    original = tts.unidades_sintese
    tts.unidades_sintese = lambda r, p: custos.append(r.headers.get("character-cost")) or original(r, p)

    # Retoma execução interrompida: mantém as sínteses ok e refaz só o que falta ou falhou.
    saida = pasta / "resultados.json"
    registros = [r for r in json.loads(saida.read_text()) if r.get("ok")] if saida.exists() else []
    feitos = {(r["voz"], r["modelo"], r["caso"]) for r in registros}
    modelos = args.modelos.split(",")
    for nome_voz in args.vozes.split(","):
        voice_id = VOZES[nome_voz] or settings.elevenlabs_voice_id
        meta = tts.obter_metadados_voz(voice_id) or {}
        eh_clonada = meta.get("categoria") == "cloned"
        for i, (caso, (tipo, tom, texto)) in enumerate(CASOS.items()):
            # Gira a ordem dos modelos por caso pra diluir variação de carga do provedor.
            for modelo in modelos[i % len(modelos):] + modelos[:i % len(modelos)]:
                if (nome_voz, modelo, caso) in feitos:
                    continue
                _, payload = tts._preparar_sintese(texto, tipo, tom, eh_clonada, None, modelo, voice_id=voice_id)
                registro = dict(voz=nome_voz, categoria_voz=meta.get("categoria"), modelo=modelo, caso=caso,
                                texto_enviado=payload["text"], caracteres=len(payload["text"]))
                inicio = time.perf_counter()
                primeiro = None
                partes = []
                try:
                    for parte in tts.sintetizar_audio_stream(texto, voice_id, tipo, tom, eh_clonada, modelo=modelo,
                                                             reutilizar_audio=False):
                        primeiro = primeiro or time.perf_counter() - inicio
                        partes.append(parte)
                except Exception as exc:
                    registro.update(ok=False, erro=f"{type(exc).__name__}: {exc}"[:300])
                    registros.append(registro)
                    print(registro, flush=True)
                    continue
                audio = b"".join(partes)
                arquivo = pasta / f"{nome_voz}-{caso}-{modelo}.mp3"
                arquivo.write_bytes(audio)
                esperado = normalizar(re.sub(r"\[[^\]]*\]", " ", payload["text"]))
                transcricao = transcrever(settings.elevenlabs_api_key, audio)
                # Scribe marca evento sonoro entre parênteses; tag falada aparece como palavra solta.
                ouvido = normalizar(re.sub(r"\([^)]*\)", " ", transcricao))
                blocos = SequenceMatcher(None, esperado, ouvido, autojunk=False)
                iguais = sum(b.size for b in blocos.get_matching_blocks())
                seg = duracao(arquivo)
                registro.update(
                    ok=True, arquivo=arquivo.name, primeiro_byte_s=round(primeiro, 2),
                    total_s=round(time.perf_counter() - inicio, 2), duracao_s=round(seg, 2),
                    ppm=round(len(esperado) / seg * 60), character_cost=custos[-1] if custos else None,
                    faltando=len(esperado) - iguais, sobrando=len(ouvido) - iguais,
                    tags_faladas=sorted(TAGS & set(ouvido)), transcricao=transcricao)
                registros.append(registro)
                saida.write_text(json.dumps(registros, ensure_ascii=False, indent=1))
                print({k: v for k, v in registro.items() if k not in ("texto_enviado", "transcricao")}, flush=True)


if __name__ == "__main__":
    main()
