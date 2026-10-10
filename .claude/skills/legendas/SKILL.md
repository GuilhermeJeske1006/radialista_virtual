---
name: legendas
description: Gera o arquivo de legendas SRT de um Reel da Locufy a partir do roteiro e dos áudios.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read Write
---

Gere `marketing/reels/$ARGUMENTS/legendas.srt`:

- uma legenda por `fala` e por `legenda` de cartela do roteiro.json;
- falas sincronizadas por `inicio_s` + `audio_s`; cartelas, por `inicio_s` e `fim_s`;
- mensagens de `conversa.json` não entram (já aparecem no celular animado);
- no máximo 2 linhas de 32 caracteres; frases longas viram blocos seguidos.
