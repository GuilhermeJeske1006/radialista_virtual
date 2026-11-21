# Portão da F7 (persona e oralidade)

Branch `melhoria/f7-persona`, base `integracao/whatsapp-pos-f4` (`b400dc7` e merge do F6 `f9f120f`).

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed (após a correção dos testes) |
| `pytest -q --cov=app` (suíte completa, 783 s) | 2308 passed, 3 skipped, **1 failed**, cobertura 89% |
| Falha da rodada completa | `tests/test_simular_hora.py::test_metricas_em_as_run_artificial`: esperava `aviso_oralidade is None` (módulo ausente na F6). Corrigido: agora confere a soma do verificador |
| `pytest tests/test_simular_hora.py` (após correção) | 29 passed |
| `pytest tests/test_persona.py tests/test_oralidade.py tests/test_live_formatos_prompt.py` | 69 passed (persona 27, oralidade 16 e formatos 26) |
| Painel `npx vitest run` | 394 passed (68 arquivos) |
| Painel `npx tsc --noEmit` | sem erros |
| Simulador `musical_adulto` (sem persona) | `as_run.json` idêntico ao de `f5/simulacao/musical_adulto/` |

Honestidade do portão: a suíte completa rodou antes da correção do teste de simulador. Só o teste corrigido foi rodado de novo;
a suíte inteira não foi repetida depois dela.

## Pendências que continuam abertas

- **Juiz de clareza e naturalidade ≥ 4/5 (aceite do plano)**: exige `--modo llm` com aprovação de custo. Não rodado.
- **Redução ≥ 50% de avisos de oralidade**: exige reescrita com LLM e medição antes/depois. O fake não mede isso. Não medido.
- **Persona no painel no navegador**: não conferido.
- **Imitação de apresentador real**: o código não detecta. Fica como aviso no painel e como regra no prompt.

## Rodada final (HEAD `73bad8b`, reescrita opcional incluída)

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest -q --cov=app` (suíte completa, 788 s) | **2316 passed, 3 skipped**, 0 falhas, cobertura 89% (EXIT 0) |
| Painel `vitest run` e `tsc` | rodados antes da reescrita (394 passed, sem mudança no painel desde então) |
| Validação automática (`avaliar-locucao`, seção 1) | sem reprovação; ver [`validacao.md`](validacao.md) |

Veredito do portão: **parcial**. Persona e verificador de oralidade entregues, com testes. Reescrita opcional entregue,
desligada por padrão. Juiz (≥ 4/5) e redução (≥ 50 %) continuam pendentes de `--modo llm` com aprovação de custo.
