# Testes H0

Branch `melhoria/h0-humanizacao`, HEAD `3cabff7`.

## Comandos
1. `cd backend && .venv/bin/ruff check app tests` -> All checks passed.
2. `.venv/bin/pytest -q --cov=app --cov-report=term` -> 1 failed, 2511 passed, 3 skipped; cobertura 89%.
3. `PYTHONPATH=. .venv/bin/python scripts/simular_hora.py --modo fake --programa tests/fixtures/programas/<perfil>.json --saida <tmp>/h0/<perfil>` para musical_adulto, popular_sertanejo, variedades_leves -> os tres terminaram, encerramento no ar, 0 hard times perdidos (detalhe em `docs/humanizacao/baseline.md`).
4. `--modo llm` e `--modo completo` nao executados (sem confirmacao de custo).

## Falhas
- `tests/test_live_router_duracao.py::test_tts_com_perfil_mede_devolve_cabecalho_e_grava_ritmo`: `assert (1, 24.0, 'abertura') == (1, 24, 'padrao')`; provavel arquivo `backend/app/live/router.py` (tipo/perfil gravado no ritmo). PRE-EXISTENTE: reproduzida em `371b786`, nao torna a frente vermelha.

VERDE
