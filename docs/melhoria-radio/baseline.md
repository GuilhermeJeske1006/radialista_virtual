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
`backend/scripts/simular_hora.py` ainda não existe. Esta seção será preenchida quando o simulador existir.
