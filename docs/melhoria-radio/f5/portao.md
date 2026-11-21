# Portão independente da F5

Data: 20/11/2026. Branch `integracao/whatsapp-pos-f4`, HEAD `d6bc878` (árvore limpa antes desta rodada). Rodado de novo
fora do relatório do implementador, com os comandos abaixo.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` (`backend/.venv`) | All checks passed |
| `pytest -q --cov=app --cov-report=term` | **1901 passed, 3 skipped**, 88%, 628 s |
| Painel `npx vitest run` | **354 passed** (65 arquivos) |
| Painel `npx tsc --noEmit` | sem erros |
| Reprodução `musical_adulto` (relógio A, semente 7, `PYTHONHASHSEED=0`, `--modo fake`) | `as_run.json` idêntico ao de `f5/simulacao/musical_adulto/`; `resumo.json` com `dado_sem_fonte` 0, `dado_vencido` 0, `atraso_hard_time_s` 0, `anuncio_sem_confirmacao` 0 |

## Pendências que continuam abertas

- **Juiz de locução, rubrica (`--modo llm`)**: exige aprovação de custo. Não rodada.
- **S4 da F5 (falsos positivos com texto real de LLM)**: mesma razão. Não rodada.

Sem essas duas, o portão local e o independente estão verdes. Veja [`pendencias.md`](pendencias.md).
