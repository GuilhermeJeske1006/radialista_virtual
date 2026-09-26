"""Teste real pequeno: 1 classificação + 1 síntese e suas repetições em cache.

PYTHONPATH=. .venv/bin/python scripts/validar_cache_ia.py --executar-api --output /tmp/cache-ia
Usa texto fictício, Redis em memória e não acessa o banco da aplicação.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executar-api", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.executar_api:
        print("Prévia: uma classificação Haiku e uma síntese v3 de 118 caracteres; repetições sem nova chamada.")
        return 0

    import fakeredis
    from app.config.settings import settings
    from app.llm import client as llm
    from app.llm import economia
    from app.tts import cache, client as tts

    settings.ia_orcamento_bloquear = False
    settings.ia_medicao_habilitada = False
    settings.ia_cache_habilitado = True
    cache.redis_client = economia.redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    args.output.mkdir(parents=True, exist_ok=True)
    resultado = {"classificacoes_api": 0, "sinteses_api": 0}
    criar_original = llm._client.messages.create
    preparar_original = tts._preparar_sintese

    def criar(**kwargs):
        resultado["classificacoes_api"] += 1
        resposta = criar_original(**kwargs)
        resultado["usage_llm"] = resposta.usage.model_dump()
        return resposta

    def preparar(*args, **kwargs):
        resultado["sinteses_api"] += 1
        return preparar_original(*args, **kwargs)

    llm._client.messages.create = criar
    tts._preparar_sintese = preparar
    try:
        primeira = llm.classificar_tom_fala("Vamos curtir os Beatles!", "musica")
        segunda = llm.classificar_tom_fala("Vamos curtir os Beatles!", "musica")
        resultado.update(classificacao=primeira, classificacao_identica=primeira == segunda)
        meta = tts.obter_metadados_voz(settings.elevenlabs_voice_id)
        if not meta:
            raise RuntimeError("Não foi possível confirmar a categoria da voz configurada")
        resultado["categoria_voz"] = meta["categoria"]
        texto = "Boa tarde! O Marcos pediu e a gente atende: vem aí Twist and Shout, com os Beatles. Aumenta o som e segue com a gente!"
        parametros = {"modelo": "eleven_v3", "tipo_bloco": "musica", "tom": "energico", "eh_clonada": meta["categoria"] == "cloned"}
        audio = tts.sintetizar_audio(texto, **parametros, timeout_segundos=25, max_tentativas=1)
        repetido = tts.sintetizar_audio(texto, **parametros)
        streaming = b"".join(tts.sintetizar_audio_stream(texto, **parametros))
        (args.output / "original.mp3").write_bytes(audio)
        resultado.update(bytes_identicos=audio == repetido == streaming,
                         sha256=hashlib.sha256(audio).hexdigest(), bytes=len(audio))
        resultado["ok"] = bool(primeira == segunda and audio == repetido == streaming
                               and resultado["sinteses_api"] == 1 and resultado["classificacoes_api"] == 1)
    except Exception as exc:
        resultado.update(ok=False, erro=type(exc).__name__)
    finally:
        llm._client.messages.create = criar_original
        tts._preparar_sintese = preparar_original
        (args.output / "cache-real.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False))
        print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
