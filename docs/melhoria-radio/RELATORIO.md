# Relatório — plano de melhoria de rádio

Execução de [`docs/plano-melhoria-radio.md`](../plano-melhoria-radio.md) frente por frente
(auditar → implementar → testar → avaliar → portão). Branches encadeadas, sem push.

Linha de base: [`baseline.md`](baseline.md) — ruff 0 avisos, pytest 1120/1120, cobertura 85%,
vitest 300/300. `npm run lint` do painel já falhava antes do plano (`next lint` não existe no
Next 16); não conta como regressão.

## Itens transversais (`docs/auditoria.md`)

| Item | Estado | Frente |
|---|---|---|
| 4 — rate limit dos endpoints pagos | resolvido; resta sessão de 7 dias não revogada na troca de senha (segurança, fora do plano) | — |
| 5 — race condition na fila | resolvido (`router.py:1796`) | — |
| 6 — timeout do Redis | resolvido na F3 (timeouts, disjuntor `redis_sessao`; travas do WhatsApp ainda no cliente cru) | F3 |
| 9 — TTL do cache de categoria | aberto | F6 |

## Frentes

### F0 — Linha de base e bancada de testes — CONCLUÍDA

- Branch: `melhoria/f0-bancada` (a partir de `melhoria/plano-radio`).
- Commits: `db47401`, `2a18262`, `3356c13`, `f258b20`, `928aac5`, `76f74ca` (+ registro do portão).
- Entregas: `backend/scripts/simular_hora.py` + `backend/scripts/simulacao/`, fixtures de três
  perfis e relógios A/B/C, `docs/benchmarks/2026-11-06-formatos/casos.json` (35 casos),
  `backend/tests/test_simular_hora.py`.
- Portão: ruff limpo; pytest 1142/1142 (+22), cobertura 85%; simulação fake 4–5 s por perfil
  (CLI), zero rede, determinística. Painel intocado.
- Linha de base da simulação (fake):

| | musical | popular | variedades |
|---|---|---|---|
| Encerramento no ar | não | não | não |
| Hard times perdidos (de 4) | 3 | 3 | 3 |
| Anúncio sem confirmação | 1 | 0 | 0 |
| Promessa vencida | 0 | 1 | 0 |
| Pedido indevido | 1 | 1 | 4 |
| Fora do orçamento | 0% | 0% | 4% |

- Achado principal: o player gera cada bloco dois blocos antes de tocar e corta em
  `horario_fim`; o encerramento é gerado ~1–3 min antes do fim e não vai ao ar. Alvo da F1.
- Pendências: [`f0/pendencias.md`](f0/pendencias.md). Modos `llm`/`completo` não rodados
  (exigem aprovação de custo).
- Correção posterior (feita na F1): o `musical_adulto` da linha de base foi gravado com o `random`
  global contaminado pela thread do Sentry. Referência corrigida:
  `f1/simulacao/musical_adulto/sem_relogio/` (segundos cortados 100,1, não 146,1).

### F1 — Relógio, espelho e hard time — CONCLUÍDA

- Branch: `melhoria/f1-relogio` (a partir de `melhoria/f0-bancada`).
- Commits: `f89571d`, `137f57c`, `b61c5c2`, `870e6cb`, `91b02df`, `60711c1`, `74e4948`,
  `4b0061c`, `aa74241`, `6f90d9e`, `dff4259`, `87859df` (+ registro do portão).
- Entregas: coluna `programas.relogio_hora` (migração aditiva `relogio_20261107.py`); presets A/B/C
  em `app/live/relogios/` (fonte de verdade, paridade com as fixtures); `app/live/relogio.py`
  (etapa, próximo compromisso, `segundos_ate_hard_time`, backtiming, feriado, meia-noite);
  `app/live/orcamento.py` com `estimar_duracao_s` (fórmula única, wpm 145 em `ConfigRelogio`);
  `/proxima` consulta o relógio no horário previsto de ir ao ar (`inicio_previsto`, opcional);
  rotas próprias `PUT/DELETE /config/programas/{id}/relogio` e `GET /config/relogios/presets`;
  painel envia o horário previsto, inicia o programa agendado na hora exata e tem editor do relógio.
- Portão: 1 rodada de correção (teste dependente de ordem: a thread do Sentry sorteava no `random`
  global durante a simulação; simulador ganhou RNG isolado). Rodada 2: ruff limpo; pytest
  1211/1211, cobertura 86%; vitest 318/318; `tsc` ok.
- Simulação fake (relógio A para musical/popular, C para variedades):

| | musical | popular | variedades |
|---|---|---|---|
| Encerramento no ar | não → sim | não → sim | não → sim |
| Hard times perdidos (de 4) | 3 → 0 | 3 → 0 | 3 → 0 |
| Atraso máximo em hard time | — → 0 s | — → 0 s | — → 0 s |
| Falas abaixo do mínimo | 0 | 0 | 0 |
| Segundos cortados no fim | 100 → 0 | 30 → 0 | 332 → 0 |

- Programa sem relógio: comportamento idêntico ao anterior (caracterização dos cinco caminhos).
- Decisões adotadas por padrão, a confirmar: intervalo sem patrocinador vira música (deixa de ser
  hard time); fechamento de 2 min (B e C) dividido em resumo + despedida de até 45 s; estender
  `inicio_previsto` a programas sem relógio fica para decisão do usuário (D4).
- Pendências: [`f1/pendencias.md`](f1/pendencias.md) — painel antigo sem `inicio_previsto` atrasa
  hard time até 412 s (F3).

### F2 — Duração real da fala — CONCLUÍDA

- Branch: `melhoria/f2-duracao-fala` (a partir de `melhoria/f1-relogio`).
- Commits: `07a27ef`, `830cbcb`, `68560e6`, `2c6f2e6`, `3f16e4f`, `9ece2f0`, `dffebbb`, `781f199`,
  `d68c39f` (+ registro do portão). `2c6f2e6` e `3f16e4f` sozinhos deixam testes da F1 vermelhos
  (corrigido em `9ece2f0`); não usar como ponto de bisseção.
- Entregas: duração do mp3 final medida (`duracao_mp3_s`) e devolvida (`duracao_fala_s`,
  `duracao_fala_estimada_s`, `orcamento_fala_s`, `fala_ajuste`, cabeçalho `X-Duracao-Fala-S` no `/tts`,
  todos opcionais); estimativa única em `app/live/orcamento.py` (pausas e números) com
  `orcamento_para(formato, tipo, primeira, teto_relogio_s)`; reescrita única acima de 115% e
  encurtamento por frases sem LLM; ritmo por voz na tabela `ritmos_voz` (migração aditiva
  `ritmo_voz_20261109.py`) e cadeia `wpm_para` (voz calibrada → modelo → `fala_wpm_padrao = 150`).
  O 145 da F1 saiu do código.
- Limite de desenho: no caminho do painel o texto sai antes do `/tts`, então o excesso medido no áudio
  só calibra; a decisão de reescrever é tomada antes, pela estimativa calibrada.
- Portão: ruff limpo; pytest 1280/1280, cobertura 86% (live 93%); vitest 318/318; `tsc` ok.
- Simulação fake (com relógio): 100% das falas dentro do orçamento nos três perfis, estouro máximo 0%,
  atraso máximo em hard time 0,18 s, no máximo 2 chamadas de LLM por fala e nenhuma ressíntese.
  Erro da estimativa cai a 0–1,7% após a 5ª amostra da voz.
- Juiz: APROVADO (só métricas automáticas; rubrica exige `--modo llm`). Nenhuma reprovação automática
  nova; as já existentes pertencem à F3 (anúncio sem confirmação no musical) e à F4 (promessa vencida,
  pedido indevido).
- Fora da meta, aceito como limite conhecido: voz nova 26% mais lenta que o padrão (estresse
  `voz_120`) atrasa um hard time em 12 s e deixa 85,7% das falas no orçamento até a 5ª amostra.
- Achado do juiz levado à F3: o encurtamento pode deixar um fragmento ("Rádio.", 0,4 s) no ar.
- Pendências: [`f2/pendencias.md`](f2/pendencias.md). Peça de reserva não implementada (sem
  catálogo de reservas ainda — F11).

### F3 — Estado confiável da emissão — IMPLEMENTADA (aguarda portão e juiz)

- Branch: `melhoria/f3-contexto-emissao` (a partir de `melhoria/f2-duracao-fala`).
- Commits: `3edddaf` (caracterização), `2ac1497` (portas e textos de prompt), `bdda108` (RNG próprio dos
  goldens), `d3e268a` (divisão de `gerar_proxima_fala`), `1d73585` (validador), `c0eaa55` (citadas),
  `049a4b2` (Redis), `e3b2794` (painel antigo) e o registro da simulação. Todos com a suíte verde.
- Entregas: `gerar_proxima_fala` cai de 1245 para 115 linhas: `roteiro.decidir_bloco`,
  `contexto.resolver_musica_e_pedidos`/`montar_contexto` (`ContextoEmissao` congelado, sorteios e rotações na
  ordem de antes), `prompt_emissao.montar_prompt(ctx)` puro e `geracao.gerar_fala` (reescrita única, momentos A
  e B); o router fica com HTTP, TTS, registros e resposta. Portas com ligação tardia (`app/live/portas.py`)
  mantêm os patches por nome dos testes e do simulador. Validador `app/live/validacao_fala.py` (V1 na reescrita
  única, V2 antes do TTS, `validacao_fala` opcional na resposta, modo `corrigir`/`avisar`); o fragmento abaixo
  do mínimo não vai ao ar; citada descartada pelo relógio não fica registrada; Redis com timeouts e disjuntor
  (`redis_sessao`), rate limit fechado só nas rotas públicas de autenticação (D5); painel antigo com horário
  estimado pela cadeia no servidor (`origem_instante`). Sem migração; campos novos só opcionais.
- Caracterização: 28 goldens de `/proxima` (system e mensagem inteiros, resposta, Redis, banco, sorteios)
  gravados antes de mover código e idênticos nos passos de extração; regravados só os 3 com relógio no passo
  do painel antigo (campo novo e chave da cadeia). Ficam permanentes (D6).
- Benchmark `casos.json`: 7 de 7 anúncios sem confirmação detectados, 0 falsos positivos nas outras 63 falas.
- Testes existentes editados por mudança intencional: `test_simular_hora::test_injecoes_aparecem_nas_metricas`
  (a injeção agora é removida) e `test_live_relogio_proxima::test_i1_i11` (cliente antigo agora é estimado).
- Portão local: ruff limpo; pytest 1379/1379 (+99); vitest 318/318; `tsc` ok.
- Simulação fake com dublê de TTS ([`f3/simulacao/`](f3/simulacao/)), F2 → F3:

| | musical | popular | variedades |
|---|---|---|---|
| Anúncio sem confirmação (relógio / sem relógio / voz 120) | 1/1/1 → 0/0/0 | 0/0/0 → 0/0/0 | 0/0/0 → 0/0/0 |
| Ação do validador (com relógio) | menção removida (injeção) | fala neutra no lugar de "Rádio." | — |
| Atraso máximo em hard time (com relógio) | 0 → 0 s | 0 → 0,36 s | 0,18 → 0,18 s |
| Painel antigo (`--sem-inicio-previsto`): atraso / encerramento / cortados | — → 0 s / sim / 0 | 412 s / não / 74 s (F1) → 0 s / sim / 0 | — → 0,18 s / sim / 0 |
| Fora do orçamento (com relógio) | 0% | 0% | 0% |

- Demais métricas iguais às da F2 (incluindo o estresse `voz_120`: popular 12,1 s e variedades 14,3% fora,
  limites conhecidos da F2). No máximo 2 chamadas de LLM e 2 sínteses por fala.
- Pendências: [`f3/pendencias.md`](f3/pendencias.md). Falsos positivos do validador com texto real só no
  `--modo llm` (não rodado, exige aprovação de custo); travas do WhatsApp ainda no cliente Redis cru.
