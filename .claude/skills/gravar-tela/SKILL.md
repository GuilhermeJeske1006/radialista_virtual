---
name: gravar-tela
description: Grava em vídeo as telas do painel Locufy (ou do site) de um Reel, seguindo o roteiro.json.
argument-hint: [id-do-video] [rota]
disable-model-invocation: true
allowed-tools: Bash Read Edit Glob Grep
---

1. Rode em `marketing/tools` (na primeira vez, `npm install` antes):

   ```bash
   node gravar.mjs $ARGUMENTS
   ```

2. O script entra com o login de demonstração, executa as `acoes` de cada cena de tela do
   `marketing/reels/<id>/roteiro.json` e salva em `marketing/reels/<id>/tela/`:
   `cena-NN.webm` (1080x1920), `cena-NN.json` (marcações) e os áudios reais do ao vivo.
3. Se uma ação falhar, abra `tela/cena-NN-erro.png` e o `page.tsx` da rota em
   `frontend-painel/app`, ajuste o texto do botão ou o rótulo do campo no roteiro.json e rode de novo.

Ações aceitas: `{"ir": "/rota"}`, `{"clicar": "texto do botão"}`,
`{"digitar": {"campo": "rótulo", "texto": "..."}}`, `{"selecionar": {"campo": "rótulo", "opcao": "..."}}`,
`{"rolar": 600}`, `{"destacar": "texto"}`, `{"esperar": 2000}`, `{"esperar_ao_vivo": 2}`.
