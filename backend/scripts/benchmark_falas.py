"""Comparação real e limitada de APIs; usa dados fictícios e consome créditos.

Execute a partir de backend: PYTHONPATH=. .venv/bin/python scripts/benchmark_falas.py
  {texto,voz} --output /tmp/locufy-benchmark --repeticoes 2
Não altera configurações persistidas nem chama endpoints de transmissão.
"""

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace


def salvar(destino, registros):
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=2))


def medir_texto(pasta, repeticoes):
    import fakeredis
    from anthropic import Anthropic
    from app.config.settings import settings
    from app.llm import prompt_builder

    prompt_builder.redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    prompt_builder.obter_clima_atual = lambda cidade: None
    conta = SimpleNamespace(nome_radio="Rádio Teste", frequencia="98.5 FM", cidade="Curitiba",
                            slogan="", telefone="", endereco="", conhecimento_local={}, biblia_radio={})
    locutor = SimpleNamespace(id=1, nome_locutor="Paulo", personalidade="Natural e acolhedor",
                             timezone="America/Sao_Paulo", biografia="", tracos_marcantes=[], fatos_do_dia=[])
    programa = SimpleNamespace(id=1, nome="Tarde Musical", tom="animado", descricao="",
        topicos_permitidos=["música", "conversa com ouvintes", "cultura local"], generos_musicais=[],
        musicas_permitidas=[], assuntos_ao_vivo=[], tipos_noticias=[], fontes_noticias=[],
        criterios_busca_musicas="", topicos_proibidos=[], musicas_bloqueadas=[], estrutura_blocos=[],
        pode_pesquisar=False, feriados_municipais=[])
    base = prompt_builder.montar_system_prompt(conta, locutor, programa)
    casos = {
        "musica": ("Anuncie Twist and Shout, dos Beatles, pedida por Marcos. Escreva de 60 a 90 palavras, sem inventar curiosidades.", ""),
        "evento_sem_autorizacao": ("Faça uma chamada animada convidando os ouvintes para o Festival da Praça hoje. Use até 90 palavras.",
            "\nConhecimento local: Festival da Praça, edição deste ano, hoje das oito às vinte e três horas. A rádio não autorizou divulgação desse evento."),
        "evento_data_incerta": ("Ouvinte: quando vai acontecer a Festa do Bairro? Responda em até 60 palavras.",
            "\nConhecimento local: Festa do Bairro, evento anual. Não há data confirmada para a edição atual."),
        "evento_encerrado": ("Convide o público para a feira hoje. Use até 60 palavras.",
            "\nA rádio autorizou divulgar a Feira Cultural, realizada em 10/08/2025, das oito às dezoito horas. Essa edição já terminou."),
        "dialogo": ("Anunciem Twist and Shout, dos Beatles, pedida por Marcos, em 2 a 4 falas e até 120 palavras no total.",
            '\nNeste bloco, Paulo e Maria apresentam juntos. Responda apenas JSON: {"linhas":[{"locutor":"Paulo ou Maria","texto":"fala"}]}.')
    }
    modelos = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"]
    salvar(pasta / "entradas_texto.json", {"system_prompt": base, "casos": casos})
    cliente = Anthropic(api_key=settings.anthropic_api_key, timeout=35, max_retries=0)
    registros = []
    for rodada in range(repeticoes):
        for caso, (mensagem, extra) in casos.items():
            # Alterna a ordem para reduzir viés de aquecimento/horário.
            for modelo in modelos[rodada % 3:] + modelos[:rodada % 3]:
                registro = dict(modelo=modelo, caso=caso, rodada=rodada + 1)
                inicio = time.perf_counter()
                try:
                    parametros = {} if "haiku" in modelo else {
                        "thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}
                    resposta = cliente.messages.create(model=modelo, max_tokens=512,
                        system=base + extra, messages=[{"role": "user", "content": mensagem}], **parametros)
                    registro.update(ok=True, texto="".join(b.text for b in resposta.content if b.type == "text"),
                        modelo_retornado=resposta.model, stop_reason=resposta.stop_reason, input_tokens=resposta.usage.input_tokens,
                        output_tokens=resposta.usage.output_tokens)
                except Exception as exc:
                    registro.update(ok=False, erro=type(exc).__name__, status=getattr(exc, "status_code", None))
                registro["segundos"] = round(time.perf_counter() - inicio, 3)
                registros.append(registro)
                salvar(pasta / "texto.json", registros)
                print({k: v for k, v in registro.items() if k != "texto"}, flush=True)


def medir_voz(pasta, repeticoes):
    from app.config.settings import settings
    from app.tts.client import sintetizar_audio
    from app.tts.voices import voz_valida
    from app.postprod.client import processar_audio

    casos = {
        "curta": "Boa tarde! O Marcos pediu e a gente atende: vem aí Twist and Shout, com os Beatles. Aumenta o som e segue com a gente!",
        "media": "Boa tarde pra você que está ligado na nossa programação! O Marcos mandou mensagem pedindo Twist and Shout, dos Beatles, e o pedido está na sequência. Tem música que dá vontade de aumentar o volume e acompanhar do começo ao fim. Você também pode participar pelo WhatsApp da rádio e contar qual canção quer ouvir. Agora, deixa o som acompanhar a sua tarde. Vamos de Beatles!",
        "longa": "Boa tarde pra você que está ligado na nossa programação! O Marcos mandou mensagem pedindo Twist and Shout, dos Beatles, e o pedido está na sequência. Tem música que dá vontade de aumentar o volume e acompanhar do começo ao fim. Você também pode participar pelo WhatsApp da rádio e contar qual canção quer ouvir. Mande o nome da música e do artista, que a gente confere o pedido por aqui. Às vezes, uma canção lembra uma viagem, uma amizade ou um momento em família. Se essa música faz parte da sua história, conta pra gente. Enquanto isso, seguimos juntos com mais música e companhia para a sua tarde. Um abraço para quem está trabalhando e para quem já conseguiu uma pausa. Vamos de Beatles!"
    }
    registros = []
    modelos = ["eleven_v3", "eleven_flash_v2_5"]
    salvar(pasta / "entradas_voz.json", casos)
    for rodada in range(repeticoes):
        for caso, texto in casos.items():
            for modelo in modelos[rodada % 2:] + modelos[:rodada % 2]:
                settings.elevenlabs_model = modelo
                registro = dict(modelo=modelo, caso=caso, rodada=rodada + 1, caracteres=len(texto))
                inicio = time.perf_counter()
                try:
                    audio = sintetizar_audio(texto, settings.elevenlabs_voice_id, tipo_bloco="musica",
                        tom="energico", eh_clonada=not voz_valida(settings.elevenlabs_voice_id),
                        timeout_segundos=35, max_tentativas=1)
                    registro["sintese_segundos"] = round(time.perf_counter() - inicio, 3)
                    inicio_pos = time.perf_counter()
                    audio = processar_audio(audio, "radio_fm")
                    registro["posproducao_segundos"] = round(time.perf_counter() - inicio_pos, 3)
                    nome = f"{modelo}-{caso}-{rodada + 1}.mp3"
                    (pasta / nome).write_bytes(audio)
                    registro.update(ok=True, arquivo=nome, bytes=len(audio))
                except Exception as exc:
                    registro.update(ok=False, erro=type(exc).__name__)
                registro["segundos"] = round(time.perf_counter() - inicio, 3)
                registros.append(registro)
                salvar(pasta / "voz.json", registros)
                print(registro, flush=True)


def verificar_audio(pasta, repeticoes):
    import base64
    import numpy as np
    from app.postprod.audio_io import mp3_bytes_para_array
    from app.stt.client import transcrever_audio

    registros = []
    for item in json.loads((pasta / "voz.json").read_text()):
        if not item["ok"]:
            continue
        conteudo = (pasta / item["arquivo"]).read_bytes()
        amostras, taxa, _ = mp3_bytes_para_array(conteudo)
        registro = {k: item[k] for k in ["modelo", "caso", "rodada", "arquivo"]}
        registro.update(duracao_segundos=round(amostras.shape[1] / taxa, 3),
                        amostras_finitas=bool(np.isfinite(amostras).all()),
                        pico=float(np.max(np.abs(amostras))),
                        fracao_amostras_saturadas=float(np.mean(np.abs(amostras) >= 0.999)))
        # Quatro transcrições para conferir omissões/pronúncia; não mede expressividade.
        if item["rodada"] == 1 and item["caso"] in ("media", "longa"):
            try:
                registro["transcricao"] = transcrever_audio(base64.b64encode(conteudo).decode(), "audio/mpeg")
            except Exception as exc:
                registro["erro_transcricao"] = type(exc).__name__
        registros.append(registro)
        salvar(pasta / "qualidade_audio.json", registros)
        print({k: v for k, v in registro.items() if k != "transcricao"}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("etapa", choices=["texto", "voz", "verificar_audio"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeticoes", type=int, choices=range(1, 6), default=2)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    {"texto": medir_texto, "voz": medir_voz, "verificar_audio": verificar_audio}[args.etapa](args.output, args.repeticoes)
