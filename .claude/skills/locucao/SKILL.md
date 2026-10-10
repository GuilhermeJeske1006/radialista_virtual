---
name: locucao
description: Gera os áudios de fala de um Reel da Locufy com a ElevenLabs (narradora e locutores da demonstração).
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read Edit
---

1. Rode, em `backend`:

   ```bash
   PYTHONPATH=. .venv/bin/python scripts/locucao_reel.py $ARGUMENTS
   ```

2. O script gera `marketing/reels/$ARGUMENTS/audio/cena-NN.mp3` para cada cena com `fala` e
   grava a duração em `audio_s` no roteiro.json. Consome créditos da ElevenLabs e pula falas
   que não mudaram.
3. Se aparecer `AVISO` de fala mais longa que a cena, encurte o texto da `fala` no roteiro.json
   e rode de novo.
