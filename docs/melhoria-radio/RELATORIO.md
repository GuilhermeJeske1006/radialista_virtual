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
