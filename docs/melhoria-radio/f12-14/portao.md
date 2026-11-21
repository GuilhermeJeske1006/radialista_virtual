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

## Portão final (F12, F13 e F14 — HEAD `3ac5511`)

| Item | Resultado |
|---|---|
| `ruff check app tests` | All checks passed |
| `pytest -q` (suíte completa, 1100 s) | **2435 passed, 3 skipped**, 0 falhas, EXIT 0 |
| Testes novos da frente | `test_roteamento_revisao` (18), `test_revisao_fala` (10), `test_bancada` (9), `test_narrativo_cortes` (8) |

Veredito: **parcial**. Backend das três frentes entregue e testado; painel (aprovação, papel de bancada, cortes, narrativo)
e a avaliação do juiz com LLM (F13, aceite ≥ 4/5, precisa de aprovação de custo) continuam pendentes.
