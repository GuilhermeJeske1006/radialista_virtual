# F2 - Portão de qualidade (branch melhoria/f2-duracao-fala, commit d68c39f)

## Comandos e resultados
- `ruff check app tests scripts/simular_hora.py scripts/simulacao`: All checks passed.
- `pytest -q --cov=app --cov-report=term` (ffmpeg 8.0.1 presente): **1280 passed**, 0 falhas, 373 s. Saída completa: /private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/4efade71-3851-4394-9e93-629b2f839d1f/scratchpad/sim/f2/pytest.txt
- Cobertura total: **86%** (12444 stmts, 1708 miss). F1: 1211 testes, 86%.
- app/live: 3044 stmts, 219 miss, 93%
- app/llm: 902 stmts, 180 miss, 80%
- app/topics: 710 stmts, 106 miss, 85%
- app/tts: 711 stmts, 56 miss, 92%
- app/whatsapp: 774 stmts, 148 miss, 81%
- Painel (só lib/liveTypes.ts mudou): `npm test` 56 arquivos, **318 passed** (igual à F1); `npx tsc --noEmit` sem erros. Lint ignorado (quebrado desde a baseline).

## Simulação --modo fake --tts duble (saída em /private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/4efade71-3851-4394-9e93-629b2f839d1f/scratchpad/sim/f2/<perfil>[/sem-relogio])
| perfil | relógio | fora_orcamento_pct | estouro_max_pct | acima_teto | falas_abaixo_minimo | atraso_hard_time_s | hard_times_perdidos | chamadas LLM máx/fala |
|---|---|---|---|---|---|---|---|---|
| musical_adulto | fixture | 0.0 | 0.0 | 0 | 0 | 0.0 | 0 | 2 |
| popular_sertanejo | fixture | 0.0 | 0.0 | 0 | 0 | 0.0 | 0 | 2 |
| variedades_leves | fixture | 0.0 | 0.0 | 0 | 0 | 0.18 | 0 | 2 |
| os 3, `--relogio-backend nenhum` | nenhum | 0.0 | 0.0 | 0 | 0 | 0.0 | 3 / 3 / 2 (comportamento F0 sem relógio, esperado) | 2 |

Determinismo: os 6 resumo.json (3 perfis x padrão/sem relógio) são idênticos aos de docs/melhoria-radio/f2/simulacao (ignorando commit/tempo).

## Critérios
- F2: 95% das falas dentro do orçamento (obtido 100%), nenhuma acima de 130% do máximo (0): ok.
- F1 mantidos com relógio: 0 hard time atrasado > 5 s, 0 falas abaixo do mínimo: ok.
- Campos de API só opcionais: painel tipa e 318 testes + tsc passam.

## Falhas
Nenhuma.

VERDE
