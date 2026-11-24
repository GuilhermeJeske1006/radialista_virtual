"""Capacidades dos modelos de voz da ElevenLabs que mudam o payload montado pelo app.

Fica fora de app.tts.client porque app.tts.cache (importado pelo client) tambem precisa.
"""

import re

# Modelos que leem audio tag inline ([pause], [calm], ...) como direcao vocal -- os demais
# falariam a tag como texto. v4/v4 Turbo aceitam o mesmo roteiro do v3 (medido na API em
# 2026-10-08: [pause] rende ~1.2s de silencio no v4, como no uso que app.tts.client faz no v3).
MODELOS_COM_TAGS = {"eleven_v3", "eleven_v4", "eleven_v4_turbo"}

# previous_text da 400 (unsupported_model) so' no eleven_v3 -- v4/v4 Turbo aceitam (medido
# na API em 2026-10-08), entao a prosodia contigua entre falas volta a valer nesses modelos.
MODELOS_SEM_CONTEXTO = {"eleven_v3"}

# Tags de direção entre a reticência e a palavra seguinte: quem decide é a palavra, não o colchete.
TAGS_SEGUIDAS = r"(?:\[[^\]]*\]\s*)*"
# Pontuação que fecha: reticência logo antes dela não abre frase nova.
PONTUACAO_FECHAMENTO = "!?.,;:)”»—–"

# Reticência dupla ("......") que vira a pausa longa [pause] nos modelos com tags: só quando a
# fala segue com frase nova (maiúscula, número, aspas de abertura). Emendando a mesma frase em
# minúscula, antes de pontuação de fechamento ou no fim do texto ela vira vírgula/some/ponto em
# app.tts.client -- com [pause] ali o v3 fecha a frase com cadência final antes da continuação
# (docs/benchmarks/2026-11-23-entrega-voz). Aplicada ao texto do roteiro, antes da normalização
# de números e pronúncias. Fica aqui porque app.live.orcamento conta essas mesmas pausas na
# duração estimada e no ritmo medido.
PAUSA_LONGA_RE = re.compile(
    r"\.{4,}(?!\.)(?=\s*" + TAGS_SEGUIDAS + r"[^\s\[a-zà-ÿ" + re.escape(PONTUACAO_FECHAMENTO) + r"])")

# v4 usa Stability e Similarity; Style e Speed não são controles desse modelo.
# https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4
MODELOS_V4 = frozenset({"eleven_v4", "eleven_v4_turbo"})


def filtrar_voice_settings(modelo: str, valores: dict) -> dict:
    if modelo in MODELOS_V4:
        return {k: v for k, v in valores.items() if k in {"stability", "similarity_boost"}}
    if modelo == "eleven_v3":
        return {k: v for k, v in valores.items() if k not in {"similarity_boost", "use_speaker_boost"}}
    return valores
