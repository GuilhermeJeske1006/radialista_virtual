---
name: gravar-tela
description: Grava em vídeo as telas do painel Locufy (ou do site) para um Reel, seguindo o roteiro.json.
argument-hint: [id-do-video] [rota-ou-url]
arguments: [video, rota]
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob
---

Grave as cenas de tela do vídeo $video.

1. Leia `marketing/reels/$video/roteiro.json` e use as cenas do tipo `tela`
   (só as da rota $rota, se ela foi informada).
2. Se faltar, instale o Playwright em `marketing/tools`
   (`npm i -D playwright` e `npx playwright install chromium`).
3. Escreva ou reaproveite `marketing/tools/gravar.mjs`:
   - Chromium com viewport 1080x1920 e `recordVideo` em `marketing/reels/$video/tela/`;
   - login no painel com o usuário de demonstração do /seed-demo;
   - para cada cena, as `acoes` do roteiro, localizando botões pelo texto visível;
   - pausas humanas: 300 a 800 ms entre cliques, digitação com 40 ms por tecla.
4. Rotas que começam com `/` rodam em http://localhost:3000. Se $rota começar com `http`,
   grave essa URL sem login.
5. Salve um arquivo por cena (`cena-01.webm`, `cena-02.webm`...) e liste a duração de cada um.
