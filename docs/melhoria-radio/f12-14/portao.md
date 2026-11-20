# Portão da F12–F14 (expansão, parcial)

Branch `melhoria/f12-14-expansao`, HEAD `9d45550`.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed (módulo e testes novos) |
| `pytest -q --cov=app` (suíte completa, 1732 s) | **2375 passed, 3 skipped**, 0 falhas, cobertura 89% (EXIT 0) |
| `tests/test_roteamento_revisao.py` | 18 passed |

Veredito do portão: **parcial**. F12: roteamento por categoria entregue; `aguardando_revisao` gravado, tela e integração ao
router pendentes. F13: não feita, aguarda decisões e aprovação de custo (juiz). F14: não feita, aguarda decisões e o
as-run persistente da F11. Detalhes em [`auditoria.md`](auditoria.md).
