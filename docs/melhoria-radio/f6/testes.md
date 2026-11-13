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
