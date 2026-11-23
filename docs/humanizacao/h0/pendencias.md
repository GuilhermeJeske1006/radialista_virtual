# Pendências da H0 (linha de base e corpus)

Fora do escopo da H0 ou dependentes de outra frente. Cada item diz quem resolve.

## Achado que bloqueia o portão §7.2 (não causado pela H0)

- **14 testes byte a byte da F5 e da F6 falham desde `301717d`** (direção de energia por programa), antes de qualquer
  mudança da H0: `test_simulacao_f5.py::test_s1_sem_dado_o_ar_e_o_da_linha_de_base` e
  `test_simulacao_f6.py::test_s1_formato_programa_e_a_f5_byte_a_byte`, nas variantes de `musical_adulto` (4 cada) e de
  `popular_sertanejo` com relógio (3 cada). O as-run de hoje grava `"tom": "calmo"` onde o arquivo de
  `docs/melhoria-radio/f5/simulacao/` tem `"neutro"`. Conferido: em `4fbd0fa` (commit anterior) os mesmos testes passam;
  em `371b786`, sem nenhuma mudança da H0, falham. A auditoria da H0 supunha esses testes verdes. A H0 não regravou
  os as-runs da F5 (regra da frente: não mexer nas fixtures da F5/F6). Decisão do orquestrador ou do usuário:
  regravar a linha de base da F5 com a direção de voz (e registrar a mudança de `tom` como intencional) ou ajustar
  `301717d`.

## Executor e adaptadores do conjunto

- **Executor ao vivo do conjunto, uma fala por entrada (H3).** O formato está em
  `docs/benchmarks/2026-11-23-humanizacao/casos.json` e a mescla (fixture do formato + persona do tom + `entrada` +
  `por_tom[tom]`) está em `_fixture_do_caso`, em `backend/tests/test_humanizacao_conjunto.py`. Quando o executor
  existir, mover a mescla para `backend/scripts/simulacao/` e reusar no teste. Não rodar uma hora de simulação por
  entrada (multiplica as chamadas reais).
- **Adaptador do conjunto para `scripts/conversa_teste.py` (H6).** As 10 entradas de WhatsApp usam a mesma chave
  `mensagens_ouvinte` do `roteiro.json`; o script hoje só lê `marketing/reels/<id>/roteiro.json`.
- **Patrocínio no conjunto:** as 10 entradas usam `popular_sertanejo`, a única fixture com `patrocinador:@spot` na
  estrutura. Se a H7 quiser patrocínio nos outros formatos, precisa de um bloco de patrocinador neles (cenário, não as
  fixtures de linha de base).

## Métricas e detectores

- **Sinais sobre os eventos `patrocinador` do as-run (H7).** `metricas_humanizacao` lê só `tipo == "fala"`; o texto do
  patrocinador lido não entra na nota.
- **Contrato de `bordoes_repetidos` (H5).** Proposto e usado pelo simulador:
  `app.live.memoria.bordoes_repetidos(falas: list[tuple[inicio_s, texto]], bordoes, *, janela_s, maximo) -> int`.
  Se a H5 mudar a assinatura, ajustar `CONFIG_METRICAS["humanizacao"]["detectores"]` e a chamada em
  `scripts/simulacao/metricas.py`.
- **Fonte de bordões cadastrados (H8).** Até lá o simulador e `recalcular_humanizacao.py` usam só o slogan da conta
  (DH0-3).
- **D4 na H5:** "Fica com a gente" (fechamento de 8 modelos do banco do dublê e `seq-fechamento-01` do corpus, com
  `bordao_repetido: null`) e a reorientação como bordão (`seq-reorientacao-01`) ficam para a H5 decidir.
- **Passo 3 da F8, reorientação permitida (H5).** `seq-reorientacao-01` tem `repeticao_estrutura` 1 hoje (detector da
  F8) e `repeticao_proibida` 0 (rótulo do que a H5 deve medir).
- **Naturalidade encenada por janela (H5, achado 3).** O corpus rotula `naturalidade_repetida` em
  `seq-naturalidade-01`; o simulador ainda não tem a métrica.
- **Piso no denominador da nota por 100 palavras (H4, fato 9).** O resumo grava `sinais_ia_falas` para ler o p90.
- **Teste direto de `_limpar_fala` (H1).** Nenhum teste chama `app/live/geracao.py::_limpar_fala`. Lembrar que o
  as-run guarda o texto depois dela: ênfase markdown (`**`, `*`, `_`, crase) já sai antes do as-run, então
  `vaz-markdown-06` a `08` só contam no corpus, não na simulação.

## Linha de base

- `docs/humanizacao/baseline.md` é do `testador-locufy` (§5.6 da auditoria): rodadas fake dos três perfis com
  `--formato fixture` e do cenário `backend/tests/fixtures/programas/cenarios/h0_popular_sinais.json`, mais a medição
  do corpus pelo pipeline atual (`_limpar_fala` e `_preparar_sintese`) num script fora do repositório.
- Na rodada fake do cenário (semente 7, `--formato fixture`, padrões do CLI), as três frases de vazamento, o sinal
  denso e os três slogans foram ao ar; nenhum validador da F3 à F6 tirou nada (`validacao_fala.blocos` 0). O teste
  `test_antes_da_h1_os_vazamentos_vao_ao_ar` deixa de rodar quando `app/live/sinais_ia.py` existir. Recomenda-se que o
  aceite da H1 inclua este cenário.
- `--modo llm` dos três perfis: pendente D9 (aprovação com estimativa).

## Corpus

- `travessao` ficou com 5 textos (a auditoria previa 4) para cumprir o mínimo de 5 por categoria de sinal. Total: 159
  textos e 8 sequências.
