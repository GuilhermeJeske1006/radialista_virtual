---
name: humanizar-fala
description: Executa o plano de humanização da fala da Locufy (docs/plano-humanizacao-fala.md) frente por frente — audita, implementa, testa e avalia com os agentes do /melhoria-radio.
argument-hint: [h0..h9|fase1|fase2|fase3|tudo] [--so-auditar]
disable-model-invocation: true
allowed-tools: Agent Bash Read Write Edit Glob Grep TaskCreate TaskUpdate TaskList
---

# /humanizar-fala

Você é o orquestrador. Leia `docs/plano-humanizacao-fala.md` inteiro e o documento de origem
`docs/Locufy — Plano de humanização da fala.md`. Carregue a skill `referencia-radio` antes de
qualquer outra ação.

## Argumentos

`$ARGUMENTS` escolhe o escopo:
- vazio ou `h0`: só a linha de base e o corpus (H0).
- `fase1`: H1, H2, H3, H6. `fase2`: H4, H5, H7. `fase3`: H8, H9.
- `h1` … `h9`: uma frente.
- `tudo`: H0 → fase 1 → fase 2 → fase 3.
- `--so-auditar`: roda só o passo 1 das frentes escolhidas e para.

Se `docs/humanizacao/baseline.md` não existir, rode H0 primeiro, qualquer que seja o argumento.

## Passo 0 — Preparação

1. `git status`: com alterações não commitadas, pare e pergunte ao usuário.
2. Leia a seção 3 do plano (decisões D1–D9) e `docs/humanizacao/RELATORIO.md`, se existir. Use a
   decisão registrada; sem registro, o padrão provisório, e anote isso no relatório.
3. TaskCreate: uma tarefa por frente, com os subpassos auditar → implementar → testar → avaliar →
   registrar.

## Para cada frente, em ordem

Os agentes foram escritos para o `/melhoria-radio`. Sempre diga no prompt deles: "o plano desta
execução é `docs/plano-humanizacao-fala.md`, frente <Hn>; grave em `docs/humanizacao/<hn>/`, não em
`docs/melhoria-radio/`; a linha de base é `docs/humanizacao/baseline.md`".

1. **Auditar** (`auditor-radio`): passe o trecho da frente, a seção 1 e a seção 2 do plano. Saída:
   `docs/humanizacao/<hn>/auditoria.md`. `JÁ ATENDIDA` → concluir e seguir. `BLOQUEADA` → registrar
   e perguntar ao usuário.
2. **Implementar** (`implementador-locufy`): crie `melhoria/<hn>-<slug>` a partir da branch atual.
   Passe a auditoria, o aceite da frente e as regras da seção 8 do plano.
3. **Testar** (`testador-locufy`): portão da seção 7. Na H0, ele grava a linha de base.
4. **Avaliar** (`juiz-locucao`, só em H3, H4, H5): as-run antes e depois, com a dimensão
   "Soa como pessoa" de `avaliar-locucao`. Com saída de `--modo fake`, só métricas automáticas.
5. **Portão:** verde → registrar em `docs/humanizacao/RELATORIO.md` (frente, branch, commits,
   métricas antes/depois, decisões provisórias, pendências). Vermelho → até 2 rodadas de correção
   com o `implementador-locufy`; depois disso, parar a frente e perguntar.

Dependências: H4 usa o módulo da H1; H5 usa H4 para os recursos de naturalidade; H8 alimenta H4 e
H5 (que funcionam sem ela). Se uma frente falhar, não comece as dependentes.

## Regras para todos os agentes

- Nenhuma chamada real a Anthropic, ElevenLabs ou WuzAPI sem aprovação explícita no chat. Antes de
  pedir, informe o número de chamadas e o custo estimado. Isso inclui `simular_hora.py --modo llm`,
  as skills `text-to-speech`, `speech-to-text` e `conversa-teste`.
- O teto de duas chamadas de LLM por fala não muda.
- Não fazer `git push`, não abrir PR, não apagar branch, não rodar migração em banco real, não
  editar `.env`.
- Uma frente por vez; ideia fora do escopo vai para `docs/humanizacao/<hn>/pendencias.md`.

## Final

Responda com: frentes concluídas, frentes bloqueadas e motivo, decisões provisórias usadas,
branches criadas e o caminho de `docs/humanizacao/RELATORIO.md`.
