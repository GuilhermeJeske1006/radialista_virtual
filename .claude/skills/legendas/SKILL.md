---
name: legendas
description: Gera as legendas (SRT) e a montagem (montagem.json) de um Reel da Locufy a partir do roteiro, das gravações e dos áudios.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read
---

Rode em `marketing/tools`:

```bash
node preparar.mjs $ARGUMENTS
```

O script gera `marketing/reels/$ARGUMENTS/legendas.srt` (para subir junto no Instagram) e
`montagem.json` (lido pelo Remotion). Ele legenda as falas da narradora e as falas reais do
ao vivo, com o nome do locutor. Mostre os `AVISO`s, se houver: indicam etapa que faltou rodar.
