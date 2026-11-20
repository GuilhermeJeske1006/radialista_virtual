# F8 — Memória e controle de repetição (status parcial)

Branch `melhoria/f8-memoria`, base `melhoria/f7-persona` (HEAD `cc0d692` antes desta frente).

## Passos do plano

| Passo | Estado | Onde |
|---|---|---|
| 1. Consolidar a memória em `app/live/memoria.py`, sem mudar comportamento | **feito** | `app/live/memoria.py`; `contexto.py` e `geracao.py` reexportam os nomes privados antigos |
| 2a. Classificar a construção da fala (abertura e fechamento) | **feito** | `abertura_da_fala`, `fechamento_da_fala` |
| 2b. Medir repetição por estrutura no `resumo.json` | **feito** | `repeticao_estrutura` (janelas de 3 falas com a mesma abertura reconhecida) |
| 2c. Evitar a mesma estrutura em N falas (no prompt ou na reescrita) | **não feito** | próxima etapa; usaria a reescrita única com flag desligada por padrão, como a oralidade |
| 3. Reorientação periódica por formato, contada como exceção | **não feito** | `reorientacao_s` já existe no catálogo (`app/live/formatos.py`), sem a contagem com memória |
| 4. Persistir promessas e correções | **parcial** | promessas já persistidas desde a F4 (`PromessaNoAr`); correções não encontrei persistência |

## Testes

- `backend/tests/test_memoria.py`: classes de abertura (identificação, retomada, agradecimento, saudação, chamada,
  pergunta, outra), caixa e acento, classes de fechamento, troca só do nome continua mesma abertura, contagem de janelas
  igual à `abertura_repetida`, "outra" não conta, e os nomes privados antigos continuam funcionando.
- `backend/tests/test_simular_hora.py`: o teste de métricas agora confere `repeticao_estrutura` contra a função.

## Medição no simulador fake (passo 2b)

Três perfis, mesmos parâmetros da F5/F6, `--formato programa`.

| Perfil | Falas | Classificadas | `repeticao_estrutura` |
|---|---|---|---|
| musical_adulto | 8 | 4 (de 8) | 0 |
| popular_sertanejo | 13 | 3 (de 13) | 0 |
| variedades_leves | 18 | 8 (de 18) | 0 |

Leitura: o valor 0 é real para o banco fixo do dublê, mas a cobertura do classificador é baixa (24 de 35 falas caem em
"outra", que não conta). Enquanto houver muita fala em "outra", a métrica diz pouco. O aceite "nenhuma abertura igual em
3 seguidas" na simulação LLM continua por medir, e depende de `--modo llm` com aprovação de custo.

Os `as_run.json` dos três perfis ficaram idênticos aos da F5 (a métrica não muda o comportamento).
