# Portão da F10 (direção de som, parcial)

Branch `melhoria/f10-direcao-som`, HEAD `a9faee3`.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed (módulo e testes novos) |
| `pytest -q --cov=app` (suíte completa, 1221 s) | **2353 passed, 3 skipped**, 0 falhas, cobertura 89% (EXIT 0) |
| `tests/test_loudness.py` | 5 passed (ffmpeg disponível; testes de ffmpeg pulam se não houver) |

Veredito do portão: **parcial**. Item 3 entregue: loudness integrada por segmento com ffmpeg, sem alvo universal. Itens 1
e 2 aguardam decisão de produto (quais vinhetas são promoção; o que é "ramp"). Detalhes em [`auditoria.md`](auditoria.md).
Relatório de loudness ainda não entra no `as_run.json`.
