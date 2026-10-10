---
name: criar-reels
description: Produz os Reels da Locufy de ponta a ponta (roteiro, gravação, locução, legendas, montagem e revisão). Sem argumento, faz os 9 vídeos; com ids, só os informados.
argument-hint: [V1 V5 ... | vazio = todos]
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob Grep Agent
---

Produza os Reels da Locufy: $ARGUMENTS (vazio = todos de `marketing/reels/pipeline.json`).

As etapas de cada vídeo estão em `marketing/reels/pipeline.json`. Cada etapa é uma skill deste
repositório: para executá-la, leia `.claude/skills/<etapa>/SKILL.md` e siga as instruções,
trocando `$ARGUMENTS` e `$video` pelo id do vídeo e `$rota` pela rota da etapa.

1. Preparação (uma vez)
   - Confira se backend (8000) e painel (3000) estão no ar; se não, peça `./start-dev.sh` e pare.
   - Rode a etapa `seed-demo`.
   - Confira se `marketing/brand/locufy-logo-white.png` existe.

2. Roteiros (em paralelo)
   - Para cada vídeo sem `roteiro.json`, delegue ao subagente `roteirista-reels`, um por vídeo,
     todos ao mesmo tempo. Se `roteiro.json` já existe, pule.

3. Produção (um vídeo por vez, na ordem dos ids)
   - Execute as etapas do vídeo na ordem do pipeline.json.
   - Antes de cada etapa, veja se o resultado dela já existe (tela/cena-*.webm, conversa.json,
     audio/*.mp3, legendas.srt, out/<id>.mp4). Se existir, pule: assim dá para retomar.
   - Se uma etapa falhar, registre o erro, pare esse vídeo e siga para o próximo.

4. Revisão (em paralelo)
   - Para cada vídeo com `out/<id>.mp4`, delegue ao subagente `revisor-marca`, todos ao mesmo tempo.
   - Salve cada parecer em `marketing/reels/<id>/revisao.md`.

5. Resumo final, em uma tabela: vídeo · arquivo · duração · revisão (APROVADO, REPROVADO ou
   erro e etapa onde parou). Para os reprovados, liste as correções sugeridas.

Nunca publique nada no Instagram e nunca use o banco de produção.
