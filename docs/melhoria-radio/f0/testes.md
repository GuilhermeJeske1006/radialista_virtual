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

## Portão da F0

Branch `melhoria/f0-bancada`, commit 76f74ca. Sem edição de código.

Comandos e resultados:
- `ruff check app tests`: All checks passed.
- `ruff check scripts/simular_hora.py scripts/simulacao`: All checks passed.
- `pytest -q --cov=app --cov-report=term`: 1142 passed, 0 falhas, 470 s (linha de base: 1120). Cobertura total 85% (11152 instruções, 1669 não cobertas; linha de base: 1682).
- Simulação `--modo fake` nos três perfis (ffmpeg 8.0.1 presente):
  - musical_adulto: rc 0, 4 s (tempo interno 0,52 s), tentativas_rede=0
  - popular_sertanejo: rc 0, 4 s (0,63 s), tentativas_rede=0
  - variedades_leves: rc 0, 5 s (0,64 s), tentativas_rede=0
  - Aceite (< 30 s, zero rede): atendido.
- Determinismo: `resumo.json` idêntico ao de `docs/melhoria-radio/f0/simulacao/<perfil>/` nos três perfis, exceto `commit` e `tempo_execucao_s`.
- Painel: `git diff --stat master...HEAD -- frontend-painel` vazio; vitest/lint dispensados.

Falhas: nenhuma. Nenhum aviso novo do ruff.

VERDE
