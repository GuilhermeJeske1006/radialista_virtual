# Portão independente da F6

Data: 20/11/2026. Branch `melhoria/f6-formatos` (HEAD `c8273ca`), rodado no worktree `locufy-radio` antes do merge com
`integracao/whatsapp-pos-f4`.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest -q --cov=app --cov-report=term` | **2266 passed, 3 skipped**, 772 s (igual ao relatório da F6) |
| Painel `npx vitest run` | **389 passed** (67 arquivos) |
| Painel `npx tsc --noEmit` | sem erros |

## Pendências que continuam abertas

- **S7, juiz com texto real (`--modo llm`, rubrica da `avaliar-locucao`)**: exige aprovação de custo. Não rodado.
- **Painel no navegador**: não conferido.

Veja [`pendencias.md`](pendencias.md).
