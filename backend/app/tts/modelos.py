"""Capacidades dos modelos de voz da ElevenLabs que mudam o payload montado pelo app.

Fica fora de app.tts.client porque app.tts.cache (importado pelo client) tambem precisa.
"""

# Modelos que leem audio tag inline ([pause], [calm], ...) como direcao vocal -- os demais
# falariam a tag como texto. v4/v4 Turbo aceitam o mesmo roteiro do v3 (medido na API em
# 2026-10-08: [pause] rende ~1.2s de silencio no v4, como no uso que app.tts.client faz no v3).
MODELOS_COM_TAGS = {"eleven_v3", "eleven_v4", "eleven_v4_turbo"}

# previous_text da 400 (unsupported_model) so' no eleven_v3 -- v4/v4 Turbo aceitam (medido
# na API em 2026-10-08), entao a prosodia contigua entre falas volta a valer nesses modelos.
MODELOS_SEM_CONTEXTO = {"eleven_v3"}
