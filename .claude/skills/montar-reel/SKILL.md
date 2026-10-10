---
name: montar-reel
description: Renderiza o MP4 final e a capa de um Reel da Locufy com Remotion, nas cores e fontes da marca.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read
---

1. Se `marketing/reels/$ARGUMENTS/montagem.json` não existir, rode `/legendas $ARGUMENTS` antes.
2. Rode em `marketing/reels-remotion` (na primeira vez, `npm install` antes):

   ```bash
   node render.mjs $ARGUMENTS
   ```

3. Mostre o caminho de `marketing/reels/$ARGUMENTS/out/$ARGUMENTS.mp4` e da `capa.jpg`.

Para ajustar o visual, o projeto está em `marketing/reels-remotion/src/Reel.tsx`
(`npm run studio` abre o editor do Remotion com prévia ao vivo).
