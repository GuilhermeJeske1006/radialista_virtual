# Relatório da humanização da fala

Atualizado em 2026-11-23. Plano: `docs/plano-humanizacao-fala.md`. Linha de base: `docs/humanizacao/baseline.md`.

## H0: linha de base e corpus

**Estado: fechada, portão verde** (com ressalvas de cobertura de detector, listadas abaixo).

- **Branch:** `melhoria/h0-humanizacao`, a partir de `371b786`.
- **Commits da H0 (até `cbbafcb`):**
  - `251e71f` métricas de humanização no simulador, injeções e recálculo
  - `c9ebdc3` corpus rotulado de sinais de IA na fala
  - `35161ee` cenário popular com sinais injetados e teste do recálculo
  - `688a418` conjunto de 60 entradas nos tons formal e informal
  - `c0e36b5` sinais de IA nas skills, auditoria e pendências
  - `3cabff7` regravação da F5 e separação da F6 (direção de energia)
  - `cbbafcb` linha de base fake e relatório do portão
- **Commits depois de `cbbafcb`** (as alterações listadas em "Alterações desde `cbbafcb`"): `39347fb` (simulador LLM
  registra direção e aquece schemas do SDK), `9d2b2c5` (abertura do musical não promete retorno), `37142bb` (linha de
  base LLM e relatório). Integrados em `master` por `dc4dc3a` e em produção desde `9f96e1f`.
- **Validação pós-integração (23/11/2026):** a simulação fake no `master` repete número a número a linha de base desta
  frente (tabela em `baseline.md`). A falha pré-existente de `test_live_router_duracao` foi corrigida em `27e7668`, e a
  dependência do cliente HTTP do SDK no teste do freezegun em `9f96e1f`; o CI de `9f96e1f` passou inteiro.

### Portão (plano §7)

| Passo | Resultado |
|---|---|
| 1. `ruff check app tests` | Sem erro |
| 2. `pytest` completo | 2512 passam, 1 falha pré-existente (`test_live_router_duracao`); cobertura 89%, igual ao HEAD |
| 3. `vitest` / `tsc` | Não aplicável (H0 não tocou o painel) |
| 4. `simular_hora.py --modo fake` nos três perfis | Métricas iguais às do HEAD; nenhuma regressão |
| 5. Juiz de locução | Não aplicável à H0 (só H3, H4, H5) |
| 6. Este relatório | Feito |

### Métricas antes e depois

**Fake** (sem custo): idênticas ao HEAD `cbbafcb` nas métricas de orçamento, promessa, pedido e encerramento.

**LLM** (`--modo llm`, aprovado com estimativa): primeira medição de referência. Não há "antes" LLM válido; as rodadas
com falha de schema não geraram as-run.

| Métrica | musical_adulto | popular_sertanejo | variedades_leves |
|---|---|---|---|
| encerramento_no_ar | True | True | True |
| hard_times_perdidos | 0 | 0 | 0 |
| anuncio_sem_confirmacao / promessa_vencida | 0 / 0 | 0 / 0 | 0 / 0 |
| pedido_indevido | 0 | 0 | 1 |
| fora_orcamento_pct | 0.0 | 22.2 | 5.0 |
| coerencia_automatica | True | True | True |
| chamadas LLM | 7 | 11 | 27 |
| truncamentos por max_tokens | 0 | 0 | 13 |

Detalhes e leitura por perfil: `docs/humanizacao/baseline.md`, seção "Linha de base LLM".

### Decisões tomadas nesta frente

- **D-H0-1. Regravar a F5 com o campo `tom`** e separar a F6 em `docs/melhoria-radio/f6/simulacao/programa/`
  (`3cabff7`). Aprovado pelo usuário.
- **D-H0-2. Reescrever o trailer dos commits do implementador** de Opus para Haiku 5.5 (só commits locais não enviados).
  Aprovado pelo usuário.
- **D-H0-3. Abertura musical abaixo do mínimo: opção 1 + registro (opção 4).** A função `abertura` do formato musical
  passou a proibir promessa de retorno e a pedir apresentação com a companhia. O caso fica registrado em
  `docs/humanizacao/h0/pendencias.md`. Aprovado pelo usuário.

### Correções feitas nesta rodada (commitadas em `39347fb` e `9d2b2c5`)

1. **Rodada LLM falhava com `PydanticSchemaGenerationError`.** Causa: `freezegun` trocava `datetime.datetime` durante o
   `freeze_time` e o SDK anthropic montava o schema de `Container.expires_at` lazy dentro dele. Corrigido com
   `_aquecer_schemas_anthropic()` em `scripts/simular_hora.py`, com teste de regressão. Não era o pydantic.
2. **Coerência do musical sempre reprovada no LLM.** Causa: `_EspiaoTexto` não registrava a direção do formato no canal
   lateral; a medição saía 0%. Corrigido em `scripts/simulacao/dubles.py`, com teste de regressão.
3. **Abertura musical fora da unidade (34 palavras, 14,1 s, mínimo 20 s).** Causa: a validação de promessas removeu
   duas frases ("daqui a pouco", "meia hora") depois da reescrita, e a reserva neutra era mais curta, então a fala
   curta foi ao ar. Mitigado no prompt da abertura (`app/live/formatos.py`); registrado em pendências.

### Alterações desde `cbbafcb`

- `backend/app/live/formatos.py`: função `abertura` do formato musical.
- `backend/scripts/simulacao/dubles.py`: registro da direção no espião LLM.
- `backend/scripts/simular_hora.py`: aquecimento dos schemas do SDK.
- `backend/tests/test_live_formatos.py`, `backend/tests/test_live_orcamento.py`, `backend/tests/test_simular_hora.py`:
  expectativas atualizadas e testes de regressão.
- `backend/tests/fixtures/formatos/musical_adulto__abertura_primeira.txt`: snapshot regravado.
- `docs/humanizacao/baseline.md`, `docs/humanizacao/RELATORIO.md`, `docs/humanizacao/h0/pendencias.md`.
- `docs/humanizacao/h0/simulacao/llm/`: resultados das rodadas LLM (ainda não commitados).

### Pendências e ressalvas

- **Detectores ausentes.** `vazamento_grave`, `sinais_ia_media`, `sinais_ia_p90` e `bordao_repetido` são `None` até as
  frentes H1 a H5 criarem os detectores. O portão da H0 não mede sinais de IA ainda.
- **Estabilidade do musical.** A abertura ficou dentro da unidade em uma amostra (semente 7). Falta medir com outra
  semente ou outra rodada.
- **Truncamento em variedades.** 13 truncamentos por `max_tokens`, aparados na última frase. Revisar o teto de tokens do
  perfil antes de H4.
- **`fora_orcamento_pct` do popular (22,2%).** Mede blocos fora do orçamento do relógio. Não é o mesmo que
  `falas_fora_da_unidade` (medido em 0%). Decidir se o popular deve ter unidade de formato.
- **Falas fora da unidade no fake do musical.** Vem do duble, não do LLM. Decidir se o duble deve gerar abertura dentro
  da unidade.
- **Dependência de versão.** `anthropic` 0.110.0 na venv, fora do `requirements.txt` (`>=0.75.0`). Decidir o pin.
- **Teste pré-existente** `test_live_router_duracao::test_tts_com_perfil_mede_devolve_cabecalho_e_grava_ritmo`
  (`assert (1, 24.0, 'abertura') == (1, 24, 'padrao')`). Já falhava no `371b786`; não é da H0. Resolvido em `27e7668`
  (o teste passou a esperar a categoria `abertura`).
- **Custo.** Cerca de 68 chamadas LLM pagas nesta frente (incluindo tentativas com falha). O valor em dólar fica no painel
  da Anthropic.

## H1 em diante

Não iniciadas. Dependem do fechamento da H0 e da decisão sobre as pendências acima. Próxima: H1 (detector de sinais de IA),
conforme o plano §6.
