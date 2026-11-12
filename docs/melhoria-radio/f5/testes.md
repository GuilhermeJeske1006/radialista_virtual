# F5 - Testes e portão local (branch melhoria/f5-fontes)

## Passo 0: linha de base na ponta da integração

Medida em 12/11/2026 no worktree `locufy-radio`, com o código de `6ca7049` (ponta de `integracao/whatsapp-pos-f4`; o
HEAD era `afe0dbb`, que só acrescenta a auditoria). É contra esta linha de base, e não contra `f4/simulacao`, que a F5
compara.

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest -q --cov=app --cov-report=term` | **1633 passed, 3 skipped** (1636 coletados), 538 s; cobertura total **87%** |
| Cobertura dos módulos que a F5 toca | `live/contexto` 99%, `live/prompt_emissao` 99%, `live/validacao_fala` 97%, `live/promessas` 95%, `live/router` 95%, `live/geracao` 94%, `llm/prompt_builder` 98%, `llm/noticias` 95%, `news/pauta` 62%, `news/curadoria` 96%, `news/worker` 81%, `weather/client` 95%, `topics/pauta_conversa` 99% |
| Painel: `npx vitest run` | **350 passed** (63 arquivos) |
| Painel: `npx tsc --noEmit` | sem erros |

### Simulação fake (`docs/melhoria-radio/f5/simulacao/linha_de_base/`)

Três perfis × quatro variantes (com relógio, `sem_relogio`, `voz_120`, `sem_inicio_previsto`) com dublê de TTS a 145
palavras/min, mais o cenário dedicado da F4 (`cenario_f4/`, as injeções de `tests/test_simulacao_f4.py::test_s2`).
`PYTHONHASHSEED=0`, zero rede. Os 14 `as_run.json` são **idênticos byte a byte** aos gravados em `f4/simulacao/`: a
integração não mudou nada no que a simulação exercita (ela não tem clima, notícia nem pesquisa: auditoria §2, fato 7).

| Rodada (musical / popular / variedades) | Com relógio | Sem relógio | Voz 120 | Painel antigo |
|---|---|---|---|---|
| Anúncio sem confirmação | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Promessa vencida | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Pedido indevido | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Ouvinte inexistente | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| Atraso máximo em hard time (s) | 0/0,36/0 | 0/0/0 | 0/12,1/0 | 0/0/0 |
| Encerramento no ar | sim/sim/sim | não/não/sim | sim/sim/sim | sim/sim/sim |
| Fora do orçamento (%) | 0/0/0 | 0/0/0 | 0/0/6,7 | 0/0/0 |
| LLM / sínteses máximas por fala | 2 / 1 | 2 / 1 | 2 / 1 | 2 / 1 |

Cenário dedicado da F4: popular com 10% fora do orçamento e hard time atrasado 2,02 s (os mesmos números da F4);
musical sem nada fora. Nenhuma métrica de dado existe ainda: é a F5 que cria `dados`, `dado_sem_fonte`, `dado_vencido`,
`sem_integracao` e `injecao.*`.
