# Relatório — plano de melhoria de rádio

Execução de [`docs/plano-melhoria-radio.md`](../plano-melhoria-radio.md) frente por frente
(auditar → implementar → testar → avaliar → portão). Branches encadeadas, sem push.

Linha de base: [`baseline.md`](baseline.md) — ruff 0 avisos, pytest 1120/1120, cobertura 85%,
vitest 300/300. `npm run lint` do painel já falhava antes do plano (`next lint` não existe no
Next 16); não conta como regressão.

## Itens transversais (`docs/auditoria.md`)

| Item | Estado | Frente |
|---|---|---|
| 4 — rate limit dos endpoints pagos | resolvido; resta sessão de 7 dias não revogada na troca de senha (segurança, fora do plano) | — |
| 5 — race condition na fila | resolvido (`router.py:1796`) | — |
| 6 — timeout do Redis | aberto | F3 |
| 9 — TTL do cache de categoria | aberto | F6 |

## Frentes

### F0 — Linha de base e bancada de testes — CONCLUÍDA

- Branch: `melhoria/f0-bancada` (a partir de `melhoria/plano-radio`).
- Commits: `db47401`, `2a18262`, `3356c13`, `f258b20`, `928aac5`, `76f74ca` (+ registro do portão).
- Entregas: `backend/scripts/simular_hora.py` + `backend/scripts/simulacao/`, fixtures de três
  perfis e relógios A/B/C, `docs/benchmarks/2026-11-06-formatos/casos.json` (35 casos),
  `backend/tests/test_simular_hora.py`.
- Portão: ruff limpo; pytest 1142/1142 (+22), cobertura 85%; simulação fake 4–5 s por perfil
  (CLI), zero rede, determinística. Painel intocado.
- Linha de base da simulação (fake):

| | musical | popular | variedades |
|---|---|---|---|
| Encerramento no ar | não | não | não |
| Hard times perdidos (de 4) | 3 | 3 | 3 |
| Anúncio sem confirmação | 1 | 0 | 0 |
| Promessa vencida | 0 | 1 | 0 |
| Pedido indevido | 1 | 1 | 4 |
| Fora do orçamento | 0% | 0% | 4% |

- Achado principal: o player gera cada bloco dois blocos antes de tocar e corta em
  `horario_fim`; o encerramento é gerado ~1–3 min antes do fim e não vai ao ar. Alvo da F1.
- Pendências: [`f0/pendencias.md`](f0/pendencias.md). Modos `llm`/`completo` não rodados
  (exigem aprovação de custo).
- Correção posterior (feita na F1): o `musical_adulto` da linha de base foi gravado com o `random`
  global contaminado pela thread do Sentry. Referência corrigida:
  `f1/simulacao/musical_adulto/sem_relogio/` (segundos cortados 100,1, não 146,1).

### F1 — Relógio, espelho e hard time — CONCLUÍDA

- Branch: `melhoria/f1-relogio` (a partir de `melhoria/f0-bancada`).
- Commits: `f89571d`, `137f57c`, `b61c5c2`, `870e6cb`, `91b02df`, `60711c1`, `74e4948`,
  `4b0061c`, `aa74241`, `6f90d9e`, `dff4259`, `87859df` (+ registro do portão).
- Entregas: coluna `programas.relogio_hora` (migração aditiva `relogio_20261107.py`); presets A/B/C
  em `app/live/relogios/` (fonte de verdade, paridade com as fixtures); `app/live/relogio.py`
  (etapa, próximo compromisso, `segundos_ate_hard_time`, backtiming, feriado, meia-noite);
  `app/live/orcamento.py` com `estimar_duracao_s` (fórmula única, wpm 145 em `ConfigRelogio`);
  `/proxima` consulta o relógio no horário previsto de ir ao ar (`inicio_previsto`, opcional);
  rotas próprias `PUT/DELETE /config/programas/{id}/relogio` e `GET /config/relogios/presets`;
  painel envia o horário previsto, inicia o programa agendado na hora exata e tem editor do relógio.
- Portão: 1 rodada de correção (teste dependente de ordem: a thread do Sentry sorteava no `random`
  global durante a simulação; simulador ganhou RNG isolado). Rodada 2: ruff limpo; pytest
  1211/1211, cobertura 86%; vitest 318/318; `tsc` ok.
- Simulação fake (relógio A para musical/popular, C para variedades):

| | musical | popular | variedades |
|---|---|---|---|
| Encerramento no ar | não → sim | não → sim | não → sim |
| Hard times perdidos (de 4) | 3 → 0 | 3 → 0 | 3 → 0 |
| Atraso máximo em hard time | — → 0 s | — → 0 s | — → 0 s |
| Falas abaixo do mínimo | 0 | 0 | 0 |
| Segundos cortados no fim | 100 → 0 | 30 → 0 | 332 → 0 |

- Programa sem relógio: comportamento idêntico ao anterior (caracterização dos cinco caminhos).
- Decisões adotadas por padrão, a confirmar: intervalo sem patrocinador vira música (deixa de ser
  hard time); fechamento de 2 min (B e C) dividido em resumo + despedida de até 45 s; estender
  `inicio_previsto` a programas sem relógio fica para decisão do usuário (D4).
- Pendências: [`f1/pendencias.md`](f1/pendencias.md) — painel antigo sem `inicio_previsto` atrasa
  hard time até 412 s (F3).
