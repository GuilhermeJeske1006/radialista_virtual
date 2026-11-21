# Portão da F9 (glossário de pronúncia, passos 1 e 2)

Branch `melhoria/f9-glossario`, HEAD `42f325a`.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest -q --cov=app` (suíte completa, 1019 s) | **2348 passed, 3 skipped**, 0 falhas, cobertura 89% (EXIT 0) |
| Primeira rodada completa | 5 falhas (`TypeError` nos stubs de síntese em `test_live_router.py`), corrigidas em `42f325a`; a rodada seguinte é a que vale |
| Painel (`vitest`, `tsc`) | não rodado: a F9 não mexeu no painel |

Veredito do portão: **parcial**. Passos 1 e 2 entregues e testados. Passo 3 (STT) e painel (CRUD) não feitos. Detalhes em
[`testes.md`](testes.md).
