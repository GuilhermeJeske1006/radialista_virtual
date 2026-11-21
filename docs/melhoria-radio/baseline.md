# Linha de base da melhoria de rádio (F0)

Branch `melhoria/plano-radio` (código igual à master), registrada em 2026-11-06.

## Ambiente
- Python 3.12.13 (`backend/.venv`; `pip check` sem conflitos)
- Node v23.10.0 (painel usa Next.js 16.3.0 declarado, CLI 16.3.5)
- ffmpeg 8.0.1

## Backend
- `ruff check app tests`: All checks passed (0 avisos)
- `pytest -q --cov=app --cov-report=term`: 1120 testes, 1120 passaram, 0 falharam, 0 pularam, 273,7 s (4:33)
- Cobertura total: 85% (11152 instruções, 1682 não cobertas)

| Pasta | Instruções | Não cobertas | Cobertura |
|---|---|---|---|
| app/live | 1865 | 190 | 89,8% |
| app/llm | 902 | 181 | 79,9% |
| app/topics | 710 | 106 | 85,1% |
| app/tts | 703 | 57 | 91,9% |
| app/whatsapp | 774 | 149 | 80,7% |

(cobertura por pasta calculada somando instruções/faltas dos arquivos da tabela term)

## Falhas preexistentes
- Backend: nenhuma.
- Painel `npm run lint`: FALHA preexistente. Script `next lint` com Next 16 imprime
  `Invalid project directory provided, no such directory: .../frontend-painel/lint`
  (o comando `next lint` não existe mais no Next 16 e não há config de ESLint na pasta). Arquivo provável: `frontend-painel/package.json` (script `lint`).

## Painel (`frontend-painel/`)
- `npm run lint`: falha (ver acima), nenhum arquivo analisado
- `npm test` (vitest): 52 arquivos, 300 testes, 300 passaram, 9,4 s

## Simulação
`backend/scripts/simular_hora.py --modo fake` no commit `928aac5` (branch `melhoria/f0-bancada`): semente 7,
145 wpm, antecedência 2, preparo 90 s, corte agendado, terça 10/11/2026 das 14h às 15h (America/Sao_Paulo).
Saídas em `docs/melhoria-radio/f0/simulacao/<perfil>/{as_run,resumo}.json`. Reproduzir:

```
cd backend && PYTHONPATH=. PYTHONHASHSEED=0 .venv/bin/python scripts/simular_hora.py \
    --programa <perfil> --saida ../docs/melhoria-radio/f0/simulacao/<perfil>
```

- Tempo: 0,53 s / 0,64 s / 0,62 s de simulação; 4,1 s a 4,3 s de processo inteiro do CLI (a maior parte é o import do app).
- Rede: 0 tentativas; 0 erros HTTP. Mesmo `as_run.json` com `PYTHONHASHSEED` 0, 1 e 12345.
- Modos `llm` e `completo` não rodaram (exigem aprovação). Estimativa do CLI (falas × 1,2): 12, 28 e 32 chamadas
  de LLM; caracteres de TTS estimados: 956, 8003 e 15290.
- Relógio B não tem programa até a F5 (`--relogio B` sobre qualquer perfil).

| Métrica | musical_adulto (relógio A) | popular_sertanejo (A) | variedades_leves (C) |
|---|---|---|---|
| Chamadas `/proxima` | 27 | 26 | 27 |
| Chamadas de LLM (falas + revisões) | 11 (10 + 1) | 24 (23 + 1) | 31 (27 + 4) |
| Fala / música / outros no ar (s) | 71 / 3495 / 32 | 616 / 2891 / 90 | 1168 / 2429 / 0 |
| Previsto no relógio: fala / música / intervalo (s) | 225 / 3015 / 360 | 225 / 3015 / 360 | 1740 / 1500 / 360 |
| Hard times ok / perdidos | 1 / 3 | 1 / 3 | 1 / 3 |
| `encerramento_no_ar` | não | não | não |
| Encerramento gerado em | 3469 s (14:57:49) | 3536 s (14:58:56) | 3568 s (14:59:28) |
| Blocos gerados e não tocados / segundos cortados | 2 / 146 | 1 / 30 | 2 / 332 |
| `estouro_fim_programa_s` | 1,0 (corte) | 0,9 | 1,0 (corte) |
| `fora_orcamento_pct` / `estouro_max_pct` | 0 / 0 | 0 / 0 | 4,0 / 19,3 |
| `anuncio_sem_confirmacao` | 1 | 0 | 0 |
| `promessa_vencida` | 0 | 1 | 0 |
| `pedido_indevido` | 1 | 1 | 4 |
| `ouvinte_inexistente` | 0 | 0 | 1 |
| Pedidos: recebidos / executados / não atendidos / atendidos antes de tocar | 1 / 0 / 0 / 1 | 4 / 3 / 1 / 0 | 3 / 0 / 0 / 3 |
| `abertura_repetida` | 0 | 0 | 0 |
| `silencio_s` (pausa editorial) | 0 (2,6) | 0 (3,8) | 0 (4,4) |
| `atraso_hard_time_s` | 0 | 0 | 0 |
| `dubles.faixa_reconhecida_pct` | 100 | 100 | 100 |

Leitura da linha de base:
- **Encerramento perdido nos três perfis.** A decisão de encerrar (`minutos_restantes ≤ 3`) acontece na geração,
  dois blocos antes de ir ao ar, e o watchdog corta em `horario_fim` + 1 s. O encerramento fica gerado e não toca;
  a passagem/fechamento do relógio sai como perdida. Confirma a hipótese da auditoria (§2) e é o alvo da F1.
- **Intervalos nunca acontecem** (o backend ainda não conhece relógio): 360 s previstos, 0 executados em todos.
- **Musical fora do relógio A:** 71 s de fala contra 225 s previstos e 3495 s de música contra 3015 s.
- **Pedidos:** o fluxo legado marca o pedido como atendido na seleção, antes de tocar (1 e 3 casos); o fluxo novo
  confirma depois de tocar (3 executados), mas o pedido de música indisponível vira fala com o nome do ouvinte em
  vez de ficar na fila (`pedido_indevido` 1). Alvo da F4.
- **Injeções aparecem como esperado:** música citada no formato musical sem tocar, promessa sem evento vencida,
  excesso no formato padrão sem revisão (o backend só tem orçamento no musical, onde a revisão corrigiu o excesso)
  e ouvinte inexistente.
- **Artefatos do modo fake:** o comprimento das falas é sintético (o dublê fala dentro da meta). As 3 revisões por
  repetição de variedades vêm dos quadros longos do dublê, que compartilham vocabulário; não medem o LLM real.
