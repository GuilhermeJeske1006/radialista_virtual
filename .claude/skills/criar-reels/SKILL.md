---
name: criar-reels
description: Produz os Reels da Locufy de ponta a ponta (rádio de demonstração, conversa no WhatsApp, gravação de tela, locução, legendas, montagem e revisão de marca). Sem argumento, faz os 9 vídeos; com ids, só os informados.
argument-hint: [V1 V5 ... | vazio = todos] [--refazer]
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob Grep Agent
---

Produza os Reels da Locufy: $ARGUMENTS (vazio = todos de `marketing/reels/pipeline.json`).

1. Confira se o backend (http://localhost:8000) e o painel (http://localhost:3000) estão no ar.
   Se não estiverem, peça para o usuário rodar `./start-dev.sh` e pare.

2. Rode a produção, que é toda automática:

   ```bash
   cd marketing/tools && node criar-reels.mjs $ARGUMENTS
   ```

   O script instala as dependências na primeira vez, roda o seed da rádio de demonstração e,
   para cada vídeo, as etapas de `pipeline.json` (conversa de teste, gravação, locução,
   legendas e render). Ele retoma de onde parou; `--refazer` refaz tudo. Pode levar vários
   minutos por vídeo: use um timeout longo ou rode em segundo plano e acompanhe a saída.

3. Se algum vídeo parar com erro (veja `marketing/reels/resumo.json`):
   - ação de tela que falhou: abra `marketing/reels/<id>/tela/cena-NN-erro.png` e o `page.tsx`
     da rota em `frontend-painel/app`, corrija a ação em `marketing/reels/<id>/roteiro.json`
     (o texto visível do botão ou o rótulo do campo) e rode de novo só esse vídeo;
   - outro erro: leia a mensagem, corrija a causa e rode de novo só esse vídeo.
   Tente no máximo duas correções por vídeo; depois, registre o problema e siga.

4. Revisão: para cada `marketing/reels/<id>/out/<id>.mp4` gerado, delegue ao subagente
   `revisor-marca`, todos ao mesmo tempo, e salve cada parecer em `marketing/reels/<id>/revisao.md`.

5. Termine com uma tabela: vídeo · arquivo · duração · revisão (APROVADO, REPROVADO ou erro e
   etapa onde parou), e as correções sugeridas para os reprovados.

Nunca publique nada no Instagram e nunca use o banco de produção.
