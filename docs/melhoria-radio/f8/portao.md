# Portão da F8 (memória e controle de repetição, passos 1 e 2b)

Branch `melhoria/f8-memoria`, HEAD `be87dd0` (commit `47e98ff` com a consolidação e a métrica).

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest -q --cov=app` (suíte completa, 774 s) | **2335 passed, 3 skipped**, 0 falhas, cobertura 89% (EXIT 0) |
| Subconjunto focado (memória, simulador, caracterização ao vivo, formatos, validação, router) | 280 passed (antes da suíte completa) |
| `as_run.json` dos três perfis (fake, `--formato programa`) | idênticos aos da F5 |
| `repeticao_estrutura` no fake | 0 nos três perfis (ver [`testes.md`](testes.md): cobertura baixa, 24 de 35 falas em "outra") |

Veredito do portão: **parcial**. Passos 1 e 2b entregues e testados. Passos 2c, 3 e 4 (correções) não feitos. O aceite
do plano (nenhuma abertura igual em 3 seguidas numa simulação LLM de 1 h) depende de `--modo llm` com aprovação de custo.
