# F6 - Testes e portão local (branch melhoria/f6-formatos)

## Passo 0: linha de base na ponta da branch

Confirmada (não refeita) em 13/11/2026 no worktree `locufy-radio`, HEAD `5987eda` (só acrescenta a auditoria da F6 a
`3f9ab88`, que só acrescenta documentação ao portão da F5 em `d6bc878`). É contra esta linha de base, e não contra
`linha_de_base/`, que a F6 compara (auditoria §3 e C6).

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest --collect-only -q` | **1904 testes coletados** (o portão da F5 registrou 1901 passed, 3 skipped) |
| Python | 3.12.13 (`backend/.venv`) |

### Simulação fake: 12 rodadas contra `docs/melhoria-radio/f5/simulacao/`

Arranjo de `tests/test_simulacao_f5.py` (3 perfis × {relógio da fixture, `sem_relogio`, `voz_120`,
`sem_inicio_previsto`}), pelo CLI, dublê de TTS a 145 palavras/min, `PYTHONHASHSEED=0`, zero rede:

```
cd backend && PYTHONPATH=. PYTHONHASHSEED=0 .venv/bin/python scripts/simular_hora.py --modo fake \
    --programa <perfil> [--relogio-backend nenhum | --wpm-real 120 | --sem-inicio-previsto] --saida <scratchpad>
```

| Perfil | Relógio | Sem relógio | Voz 120 | Painel antigo |
|---|---|---|---|---|
| `musical_adulto` | igual | igual | igual | igual |
| `popular_sertanejo` | igual | igual | igual | igual |
| `variedades_leves` | igual | igual | igual | igual |

- **`as_run.json`: 12 de 12 idênticos byte a byte** aos gravados em `f5/simulacao/<perfil>/[<variante>/]`
  (`cmp`), com o registro de dados da F5 (sem tirar `dados`/`dado_legitimo`). Código de saída 0 em todas.
- `resumo.json`: iguais campo a campo, exceto `config.commit` (`6bcc0b3` → `5987eda`) e `tempo_execucao_s` (ruído).

A linha de base da F5 vale na ponta da branch: nada a refazer.

## Leva 1 (commits 0 a 4 do §7)

| Commit | O que mudou | Goldens / simulação |
|---|---|---|
| `f0ec447` | passo 0 (acima) | — |
| `2157e2b` | caracterização C2–C5, gravada no código anterior ao catálogo | 0 regravados |
| `c84afc4` | `app/live/formatos.py` (padrao, musical_adulto + alias, sete futuros); flags no lugar do booleano | 34 goldens e C2–C5 idênticos; 12 simulações byte a byte iguais |
| `8222790` | item 9: TTL e teto do cache de categoria | goldens idênticos |
| `2308549` | contrato (`perfil_programacao: str`, 422 em português, resposta tolerante), `GET /config/formatos`, gerador | goldens idênticos |

Testes primeiro em cada commit; os novos falharam pelo motivo certo antes do código (módulo inexistente, alias
tratado como padrão, settings ausentes, `Literal` antigo).

### Testes novos
| Arquivo | Testes | O que cobre (auditoria §8) |
|---|---|---|
| `tests/test_live_formatos_caracterizacao.py` | 6 | C2 (roteiro do router e puro, posições 0–20, cinco estruturas, `ultima_categoria`, sorteio fixado; `roteiro_base`), C3 (A/B/C × padrão/musical × duas peças × duas execuções, a cada 7 s), C4 (`orcamento_para`, 17 tipos × primeira × seis tetos), C5 |
| `tests/test_live_formatos.py` | 93 | U1, U2, U3 (tabela do fato 2, item a item), U4 (musical/padrão/alias/quadro/tabelas derivadas), U5, U7 (grade C3 com `formato=`, preenchimento pela flag, D8), U8 (padrão/musical, alias, D17 e D23 pela flag), D12, U9 e risco 1 (`"musical_companhia"` só em `formatos.py`/`formato.py`) |
| `tests/test_live_formatos_integracao.py` | 6 | I3 (os 3 goldens musicais com `musical_adulto` dão o mesmo retrato) e I9 |
| `tests/test_live_cache_categoria.py` | 4 | U10 |
| `tests/test_config_formatos.py` | 20 | I8, I10 e U12 |
| `tests/test_live_prompt_emissao.py` | +1 | U9 (`formatos` na lista de pureza) |

Testes existentes editados de propósito: `test_config_router.py::test_perfil_musical_persiste_e_rejeita_valor_desconhecido`
(aceita `musical_adulto`; `inexistente` continua 422).

### Fim da leva (HEAD `2308549`)
| Item | Linha de base | Leva 1 |
|---|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed | All checks passed |
| `pytest -q` | 1901 passed, 3 skipped (1904) | **2031 passed, 3 skipped** (2034, +130), 546 s |
| 12 simulações fake contra `f5/simulacao/` | — | `as_run.json` 12/12 idênticos byte a byte; `resumo.json` só com `config.commit` e `tempo_execucao_s` diferentes |
