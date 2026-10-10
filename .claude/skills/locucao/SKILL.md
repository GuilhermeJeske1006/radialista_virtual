---
name: locucao
description: Gera os áudios de fala de um Reel da Locufy com as vozes ElevenLabs dos radialistas da demonstração.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob Grep
---

1. Leia as cenas com `fala` em `marketing/reels/$ARGUMENTS/roteiro.json`.
2. Reaproveite o cliente de `backend/app/tts/client.py`, com a chave do `backend/.env` e o
   `voz_id` do radialista indicado em `voz` (busque no banco local da demonstração).
   Para o narrador, use a voz padrão de `backend/app/tts/voices.py`.
   A skill `text-to-speech` deste repositório tem a referência da API da ElevenLabs.
3. Gere um MP3 por fala em `marketing/reels/$ARGUMENTS/audio/cena-XX.mp3` e grave a duração
   real de cada um no roteiro.json, no campo `audio_s` da cena.
4. Se uma fala passar do tempo da cena, avise e sugira um texto mais curto; não corte o áudio.
