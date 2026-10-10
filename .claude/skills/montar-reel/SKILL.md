---
name: montar-reel
description: Monta e renderiza o MP4 final de um Reel da Locufy com Remotion, nas cores e fontes da marca.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob
---

1. Se `marketing/reels-remotion` não existir, crie um projeto Remotion em TypeScript com a
   composição `Reel` em 1080x1920 e 30 fps, que recebe o id do vídeo por props.
2. Componentes:
   - `Cartela`: gradiente #3E3A98 > #3D69BC > #138FAE, títulos em Nunito 900, texto em Figtree;
   - `Tela`: vídeos de `marketing/reels/<id>/tela/`;
   - `ChatWhatsApp`: anima `conversa.json` como um celular, mensagem a mensagem;
   - `Legenda`: lê `legendas.srt`, texto branco com contorno escuro, fora dos 250 px de cima e de baixo;
   - `LogoFinal`: `marketing/brand/locufy-logo-white.png` sobre o gradiente.
3. Monte as cenas do roteiro.json na ordem, com os áudios de `audio/` e, se existir
   `marketing/brand/trilha.mp3`, a trilha a -20 dB.
4. Renderize em `marketing/reels/$ARGUMENTS/out/$ARGUMENTS.mp4` (H.264) e gere `capa.jpg`
   com o título do vídeo.
5. Mostre o caminho do arquivo e a duração final.
