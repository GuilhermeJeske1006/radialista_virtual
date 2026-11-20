# Portão da F11 (produção antes, durante e depois, parcial)

Branch `melhoria/f11-producao`, HEAD `5e55978`.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest -q --cov=app` (suíte completa, 1199 s) | **2357 passed, 3 skipped**, 0 falhas, cobertura 89% (EXIT 0) |
| `tests/test_relatorio_programa.py` | 4 passed (inclui o resumo real do popular do simulador, sem alertas) |

Veredito do portão: **parcial**. Item 2 entregue (relatório pós-programa como função pura). Itens 1 (as-run persistente) e
3 (contingência com peça de reserva aprovada) aguardam decisão. Detalhes em [`auditoria.md`](auditoria.md).
