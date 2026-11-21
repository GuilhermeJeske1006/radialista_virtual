---
name: melhoria-radio
description: Executa o plano de melhoria de formatos radiofônicos e locução da Locufy (docs/plano-melhoria-radio.md) frente por frente — audita, implementa, testa e avalia com agentes.
argument-hint: [f0|p0|p1|p2|f1..f14|tudo] [--so-auditar]
disable-model-invocation: true
allowed-tools: Agent Bash Read Write Edit Glob Grep TaskCreate TaskUpdate TaskList
---

# /melhoria-radio

Você é o orquestrador. Leia `docs/plano-melhoria-radio.md` inteiro e carregue a skill
`referencia-radio` antes de qualquer outra ação.

## Argumentos

`$ARGUMENTS` escolhe o escopo:
- vazio ou `f0`: só a linha de base e a bancada de simulação (F0).
- `p0`, `p1`, `p2`: todas as frentes daquela prioridade, na ordem do plano.
- `f1` … `f14`: uma frente.
- `tudo`: F0 → P0 → P1 → P2.
- `--so-auditar`: roda só o passo 1 (auditoria) das frentes escolhidas e para.

Se F0 ainda não foi feito (não existe `docs/melhoria-radio/baseline.md`), rode F0 primeiro,
qualquer que seja o argumento.

## Passo 0 — Preparação

1. `git status`: se houver alterações não commitadas, pare e pergunte ao usuário.
2. Crie a lista de tarefas com TaskCreate: uma tarefa por frente do escopo, cada uma com os
   subpassos auditar → implementar → testar → avaliar → registrar.
3. Crie `docs/melhoria-radio/` se não existir.

## Para cada frente, em ordem

### 1. Auditar (agente `auditor-radio`)
Passe ao agente: o id da frente, o trecho do plano dessa frente e o caminho da pesquisa
`docs/pesquisa-radio-locufy.md`. Ele grava `docs/melhoria-radio/<frente>/auditoria.md` com estado
atual confirmado (arquivo:linha), lacunas, desenho da mudança, lista de testes e riscos.
Leia a auditoria. Se ela concluir que a frente já está atendida, marque como concluída e siga
para a próxima. Se `--so-auditar`, não passe deste passo.

### 2. Implementar (agente `implementador-locufy`)
Crie a branch `melhoria/<frente>-<slug>` a partir da branch atual. Passe ao agente a auditoria e
os critérios de aceite do plano. Ele escreve primeiro os testes (incluindo testes de caracterização
quando for mover código), depois o código, e faz commits pequenos.

### 3. Testar (agente `testador-locufy`)
O agente roda o portão de qualidade do plano (ruff, pytest, vitest quando o painel mudou,
`scripts/simular_hora.py --modo fake` nos três perfis) e compara com
`docs/melhoria-radio/baseline.md`. Grava `docs/melhoria-radio/<frente>/testes.md`.

### 4. Avaliar locução (agente `juiz-locucao`, só em F2–F4, F6–F8, F13)
Passe as saídas `as_run.json` da simulação antes e depois. O juiz usa a skill `avaliar-locucao` e
grava `docs/melhoria-radio/<frente>/avaliacao.md` com notas por dimensão.

### 5. Portão
- Tudo verde → marque a tarefa como concluída e registre em
  `docs/melhoria-radio/RELATORIO.md` (frente, branch, commits, métricas antes/depois, pendências).
- Algo vermelho → devolva ao `implementador-locufy` o relatório do teste/avaliação. No máximo
  2 rodadas de correção; se continuar vermelho, pare a frente, registre o bloqueio no relatório
  e pergunte ao usuário antes de seguir.

Frentes de P0 dependem umas das outras (F3 usa F1 e F2; F4 usa F1 e F3): se uma falhar,
não comece as dependentes.

## Regras que valem para todos os agentes

- Nunca chamar APIs pagas ou externas reais (Anthropic, ElevenLabs, Stripe, WuzAPI, Spotify,
  YouTube) sem aprovação explícita do usuário no chat. `--modo llm` e `--modo completo` da
  simulação exigem essa aprovação, informando a estimativa de custo.
- Não fazer `git push`, não abrir PR, não apagar branches, não rodar migrações em banco real.
- Não editar `.env`; usar `.env.example` como referência.
- Uma frente por vez; não implementar frente fora do escopo pedido.

## Final

Responda ao usuário com: frentes concluídas, frentes bloqueadas e motivo, branches criadas, e o
caminho de `docs/melhoria-radio/RELATORIO.md`. Não repita o conteúdo dos relatórios.
