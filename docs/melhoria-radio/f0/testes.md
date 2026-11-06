# Testes F0 (linha de base)

Comandos executados (nenhum chama API paga; suíte usa mocks):
1. `cd backend && .venv/bin/python --version` -> 3.12.13; `node --version` -> v23.10.0; `ffmpeg -version` -> 8.0.1
2. `.venv/bin/pip check` -> sem conflitos
3. `.venv/bin/ruff check app tests` -> All checks passed
4. `.venv/bin/pytest -q --cov=app --cov-report=term -p no:cacheprovider` -> 1120 passed, 0 failed, 0 skipped, 273,7 s; cobertura 85%
5. `cd frontend-painel && npm run lint` -> falha preexistente (`next lint` inexistente no Next 16)
6. `cd frontend-painel && npm test` -> 52 arquivos, 300 testes passaram
7. `scripts/simular_hora.py` -> não existe ainda (não executado)

Falhas preexistentes: `npm run lint` do painel (script `next lint` quebrado, `frontend-painel/package.json`). Nenhuma falha de teste.

VERDE
