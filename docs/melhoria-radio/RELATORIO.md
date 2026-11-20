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
| 9 — TTL do cache de categoria | resolvido na F6 (`8222790`: TTL de 30 dias renovado a cada gravação, teto de 5000 entradas, `hlen` no `PADROES_SESSAO`) | F6 |

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

### F3 — Estado confiável da emissão — CONCLUÍDA

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
  limites conhecidos da F2). No máximo 2 chamadas de LLM e 1 síntese por fala.
- Pendências: [`f3/pendencias.md`](f3/pendencias.md). Falsos positivos do validador com texto real só no
  `--modo llm` (não rodado, exige aprovação de custo); travas do WhatsApp ainda no cliente Redis cru.
- Portão independente (testador, 12/11/2026, worktree `locufy-radio`): VERDE. ruff limpo; pytest 1379/1379,
  cobertura 87% (F2: 86%); vitest 318/318; `tsc` ok; 12 simulações (3 perfis × 4 variantes) com `as_run.json`
  idêntico byte a byte aos gravados. Detalhe em [`f3/testes.md`](f3/testes.md).
- Juiz: APROVADO (só métricas automáticas, régua própria que não importa o detector do backend; rubrica exige
  `--modo llm`, pendente de aprovação de custo, como na F2). 31 citações confirmadas preservadas, nenhuma emenda
  solta, nenhuma dimensão abaixo da F2. Detalhe em [`f3/avaliacao.md`](f3/avaliacao.md).
- Ressalvas aceitas: fala neutra no popular atrasa o hard time em 0,36 s (escolhida pelo orçamento da geração,
  não pelo espaço real no ar); o validador só agiu sobre uma frase injetada nos as-runs, então a evidência de
  "100%" vem do benchmark `casos.json`.
- Achados do juiz levados à F4: ouvinte inventado ("Dona Firmina") no variedades; "toca agora" e nome de ouvinte
  com pedido fora de `selecionado`; promessa "daqui a pouco tem mais recado" vencida no popular (com relógio só
  some porque o encurtamento corta a frase); o detector provisório de promessa da F0 fecha promessa que não é de
  música quando a mesma fala anuncia música.
- Os registros do portão e do juiz da F3 foram commitados na branch `melhoria/f4-promessas` (a branch da F3
  estava em uso na árvore principal por outra sessão).

### F4 — Promessas, chamadas e participação de verdade — CONCLUÍDA

- Branch: `melhoria/f4-promessas` (a partir de `melhoria/f3-contexto-emissao`), worktree `locufy-radio`.
- Commits: `44e1ee9` (auditoria), `b1a35de`, `cb1d7e5`, `9ed9152`, `0639ef0`, `5f591b6`, `30ddc8f`, `b70144b` (D2),
  `81943cf` (D7), `122d2a3` (caracterização do legado), `835d8e4` (D1), `4281825`, `b216d65`, `93a438c`, `4153bf3`,
  `17f9cf9` (+ registro do portão).
- Entregas: `app/live/promessas.py` e `participacao.py` (detectores puros, sem LLM), `promessas_repo.py`, tabela
  `promessas_no_ar` (migração aditiva `promessas_20261112.py`, apagada na exclusão de programa e radialista);
  agenda de chamadas pelas etapas seguintes do relógio (sem relógio, pelo roteiro, sem consumir sorteio);
  checagens de promessa e participação na mesma reescrita única e remoção de frase da F3; registro sobre o texto
  que vai ao ar, depois do TTS; cumprimento no bloco-alvo, contingência com frase fixa garantida pelo código,
  vencimento resolvido na fala seguinte e no encerramento; relógio com `planejar(obrigacoes)` (lista vazia = plano
  idêntico); textos de prompt sem promessa fora da agenda; simulador mede pelos detectores do backend. Contrato e
  painel só com campos opcionais.
- Decisões: D1 confirmada pelo usuário em 12/11/2026 (opção A): o fluxo legado de pedidos passa a ser selecionado
  com token e confirmado pelo player depois de tocar. D2 a D12 adotadas pelo padrão da auditoria, a confirmar
  ([`f4/pendencias.md`](f4/pendencias.md)); as de maior efeito: D2 (pedido de música indisponível não vai ao ar com
  o nome do ouvinte) e D3 (promessas só no banco, sem Redis).
- Goldens de `/proxima`: idênticos nas extrações; regravados com diff revisado 1 na D2, 8 na D1 e os 31 no commit
  dos textos de prompt; 3 novos de promessa.
- Portão independente (testador): VERDE. ruff limpo; pytest 1515/1515 (+136), cobertura 88%; vitest 318/318;
  `tsc` ok; 12 simulações e o cenário dedicado com `as_run.json` idêntico byte a byte.
- Simulação fake, F3 → F4 (com relógio / sem relógio / voz 120 / painel antigo):

| | musical | popular | variedades |
|---|---|---|---|
| Promessa vencida | 0/0/0/0 → 0 | 0/1/1/1 → 0 | 0/0/0/0 → 0 |
| Pedido indevido | 1/1/1/1 → 0 | 1/1/1/1 → 0 | 3/4/3/3 → 0 |
| Ouvinte inexistente | 0 → 0 | 0 → 0 | 1/1/1/1 → 0 |
| Participações legítimas no ar | 0/0/0/0 → 0/1/0/0 | 2/3/2/2 → igual | 0/0/0/0 → 2/3/2/2 |
| Atraso máximo em hard time (com relógio) | 0 → 0 s | 0,36 → 0,36 s | 0,18 → 0 s |

- Demais critérios herdados mantidos: 0% fora do orçamento com relógio, encerramento no ar, anúncio sem
  confirmação 0, no máximo 2 chamadas de LLM e 1 síntese por fala. Estresse `voz_120`: popular segue em 12,1 s
  (limite da F2), variedades cai de 14,3% para 6,7% fora do orçamento.
- Juiz: APROVADO (só métricas automáticas, régua própria; rubrica exige `--modo llm`, pendente de aprovação de
  custo). Pedido atendido antes de tocar 13 → 0; nenhum pedido selecionado e executado perdeu o nome no ar.
  Detalhe em [`f4/avaliacao.md`](f4/avaliacao.md).
- Ressalvas do juiz, não bloqueiam:
  - D2 fecha como "música indisponível" um pedido cuja faixa existe e só tinha tocado na mesma hora; o pedido sai
    da fila, e a pesquisa §10 pede manter o status. Ouvintes reais citados caem de 26 para 19 por causa da D2.
  - A frase de contingência repete o convite ("o WhatsApp ... segue aberto. O WhatsApp ... está aberto") e afirma
    "ainda não chegou recado" um minuto depois de um pedido chegar.
  - No cenário dedicado do popular, a identificação vai ao ar como "Rádio. Daqui a pouco tem mais recado..." (4,55 s
    para máximo de 4 s; hard time atrasa 2,02 s, dentro dos 5 s).
  - Fim antecipado do musical sobe de 8,5 para 37,4 s (meta: 60 s).
  - No simulador, `validacao_fala.regras` conta cada violação duas vezes por remoção e `falas_abaixo_minimo`
    não mede o que o nome diz.
- Pendências: [`f4/pendencias.md`](f4/pendencias.md) — falsos positivos com texto real não medidos (`--modo llm`);
  estado marcado na geração, não na reprodução (F11); pedido legado selecionado sem confirmação fica preso até a
  equipe reenfileirar; fallback do painel em `useLiveEngine.ts` ainda diz "já volto com mais uma novidade".

### F5 — Fontes, validade e dados verificáveis — CONCLUÍDA (portão local e independente verdes; rubrica do juiz e S4 pendentes de custo)

- Branch: `melhoria/f5-fontes` (a partir de `integracao/whatsapp-pos-f4`, `6ca7049`), worktree `locufy-radio`.
- Integração solicitada pelo usuário: o merge com `f1efbba` incorpora também o fechamento documental da integração pós-F4; todo o código de WhatsApp, conversas, contexto e demais frentes já está nesta F5. Histórico e validação em [árvore de commits](../arvore-commits.md).
- Commits: `afe0dbb` (auditoria), `69ecc9a` (linha de base), `fd5d2e2`, `844f16a`, `97ce304`, `7c56c3c`, `2de9754`,
  `e3efda1`, `62570b1` (D11), `3fcb872`, `f7dc1b2` (D12), `b96022c`, `6bcc0b3` (+ registro do portão).
- Linha de base refeita na ponta da integração ([`f5/testes.md`](f5/testes.md)): pytest 1633 passed e 3 skipped,
  cobertura 87%; vitest 350; as 12 simulações e o cenário da F4 iguais byte a byte aos da F4.
- Entregas:
  - `backend/app/dados/` (puros): `DadoVerificavel` e `ConfigDados` com a regra única de validade (janela da notícia por
    categoria, validade do clima e da apuração, idade máxima da afirmação, fim do evento na agenda); `limpar` e
    `nome_seguro` para texto externo; detector `afirmacoes` e `checar_fala` (temperatura, tempo, previsão, trânsito,
    placar, comercial); conversores e o bloco de dados.
  - Ao vivo: `ctx.dados` preenchido depois dos sorteios; `checar_dados` na reescrita única e na remoção de frase da
    F3 (`dado_sem_fonte`, `dado_vencido`, `settings.validacao_dados_modo`); promessa de informação com só dado vencido
    vira a contingência da F4 (`fonte_desatualizada`); nome do ouvinte saneado.
  - Item 3 de `docs/auditoria.md` fechado: pauta, escalada, correção, apuração, assunto, clima, mensagem do ouvinte e
    contexto da faixa vão limpos num bloco JSON da mensagem; o system só tem regras e a referência ao dado. Clima fora
    do prompt base do ao vivo, com horário da observação e última leitura quando a API cai (o WhatsApp segue igual).
    Textos que convidavam dado sem integração editados; apuração atribui a quem informou, não ao veículo.
  - Curadoria trata o item do feed como dado e descarta ordem embutida; retificação limpa; agenda com data do evento.
  - Contrato e painel: `dados` opcional na resposta; reserva do painel sem promessa (pendência da F4, D16).
- Goldens: idênticos nos commits 1 a 5 e na checagem no ar; regravados uma vez, no commit do bloco de dados, com o diff
  revisado (os 31: regra geral e gancho; 26: texto da segunda; e os de notícia, ouvinte e faixa); 3 novos.
- Portão local: ruff limpo; pytest **1901 passed**, 3 skipped (+268), cobertura **88%**; vitest **354**; `tsc` ok.
- Portão independente (testador, 13/11/2026, HEAD `d6bc878`, worktree `locufy-radio`): VERDE. ruff limpo; pytest
  1901 passed, 3 skipped, 0 failed (645 s); cobertura 88% (`app/dados`: 100/98/98/97%; `news/pauta` 62% → 93%;
  `llm/prompt_builder` 98% → 97%, única queda, de um ponto); vitest 354/354; `tsc` ok; `npm run lint` com a falha
  preexistente da F0. Seis simulações fake (3 perfis × com e sem relógio), 0 tentativas de rede: `dado_sem_fonte`,
  `dado_vencido`, `dado_legitimo_removido`, `sem_integracao.*` e `injecao.no_system` em 0; herdados em 0 (hard time
  máximo 0,36 s no popular com relógio; `fora_orcamento_pct` 0 nas seis; ≤ 2 LLM por fala; encerramento no ar com
  relógio). Os `resumo.json` com relógio batem com os gravados em `f5/simulacao/` (só `config.commit` e
  `tempo_execucao_s` diferem). Nenhuma divergência contra o portão local. Detalhe em [`f5/testes.md`](f5/testes.md).
- Juiz: não exigido para a F5 (o portão do plano pede juiz em F2–F4, F6–F8 e F13; a dimensão "Precisão" da F5 é
  medida pelas métricas automáticas de dado acima, como a F1 fez com "Tempo"). A rubrica com texto real continua
  dependendo de `--modo llm`, pendente de aprovação de custo.
- Simulação fake ([`f5/simulacao/`](f5/simulacao/)): as 12 rodadas sem dado iguais à linha de base fora o registro novo
  dos dados (três eventos ganham o assunto puxado pela música), critérios herdados número por número iguais. Guardrail
  por perfil: afirmação de temperatura, placar e trânsito inventadas saem, 0 no ar. Cenários dedicados (variedades com
  relógio C e popular com relógio B, notícias semeadas, clima que vence com a API fora, título com ordem embutida):
  `dado_sem_fonte` 0, `dado_vencido` 0, vencido só com o horário (20 e 6 falas), nenhum dado legítimo removido (30 e
  79 falas com dado no ar), texto externo nunca no system nem fora do bloco, a ordem do título não foi ao ar.
- Benchmark `casos.json`: `dado_sem_fonte` 6/6, `dado_vencido` 1/1, nenhum falso positivo nas outras 63 falas.
- D18: `validacao_fala.regras` do simulador contava o dobro em toda remoção; os números da F3 e da F4 relatados por essa
  chave eram o dobro (ex.: `promessa_sem_evento: 2` → 1).
- Decisões D1 a D18 adotadas pelo padrão da auditoria, a confirmar; uma escolha minha fora do texto: o contexto da faixa
  conta como cobertura extra (D17), a mensagem do ouvinte não.
- Portão independente: [`f5/portao.md`](f5/portao.md) (1901 passed, 3 skipped, 88%; vitest 354; tsc ok; reprodução do musical idêntica).
- Pendências: [`f5/pendencias.md`](f5/pendencias.md) — falsos positivos com texto real não medidos (`--modo llm`);
  cobertura por tipo larga (clima válido cobre qualquer condição); o WhatsApp reaproveita a fala confirmada sem a
  validade dos dados; `gerarFalaLocal` do painel ainda promete conteúdo.

### F6 — Catálogo de formatos e perfis editoriais — CONCLUÍDA (juiz com texto real pendente de custo)

- Branch: `melhoria/f6-formatos` (a partir de `melhoria/f5-fontes`, `3f9ab88`), worktree `locufy-radio`. Três levas,
  sem push.
- Commits: `5987eda` (auditoria), `f0ec447` (linha de base); leva 1 `2157e2b` (caracterização C2–C5), `c84afc4`
  (catálogo sem mudar comportamento), `8222790` (item 9), `2308549` (contrato, `GET /config/formatos`, gerador),
  `d59dcd9` (registro); leva 2 `8ebecc0` (seção do formato no prompt), `67e4c46` (popular e variedades), `7cb526e`
  (simulador `--formato` e coerência), `913fc19` (benchmark), `aeeb19d` (registro e rodadas); leva 3 `3ba3ed0`
  (helpers do painel), `3fb469d` (prévia dos blocos), `f1a05d4` (fala local, D22), `bbe3d9f` (formulário e
  identidade) e este registro.
- Linha de base confirmada na ponta da F5 ([`f6/testes.md`](f6/testes.md)): pytest 1901 passed e 3 skipped, vitest
  354, 12 simulações byte a byte iguais a `f5/simulacao/`.
- Entregas:
  - Catálogo declarativo `app/live/formatos.py` (dataclasses congeladas): por formato, promessa, conteúdo, condução,
    unidade de fala por papel (min/alvo/máx), roteiro e relógio sugeridos, comportamento (ciclo, blocos extras,
    abertura depois do intervalo, multivoz), participação, temas que exigem revisão, reorientação e limites de
    coerência. Implementados `padrao` ("Livre"), `musical_adulto` (alias `musical_companhia`, byte a byte igual ao
    antigo até o commit 5), `popular_sertanejo` e `variedades_leves`; `hits`, `regional`, `noturno`, `religioso`,
    `morning`, `esportivo` e `jornalistico` só na estrutura (`implementado=False`, 422 na API). `formato.py`,
    `ORCAMENTOS_POR_FORMATO` e `FORMATOS_APLICADOS` derivados do catálogo, mesmos nomes.
  - `direcao_musical` → `direcao_formato(formato, tipo, primeira, quadro=)`; seção `_formato(ctx)` no prompt
    (programa, formato, promessa, público, "a promessa do formato prevalece sobre o perfil do horário",
    participação, temas que exigem revisão e reorientação nos papéis do catálogo), nunca no `padrao`.
  - Relógio: unidade do formato limitada pela etapa e pelo espaço quando o formato aplica orçamento (D8); o relógio
    do formato é só sugestão (D7). Popular e variedades aplicam orçamento sem relógio (D9) e aceitam abertura depois
    do patrocinador (D17); só o musical ignora `ia_pode_adicionar_blocos` (D23).
  - Contrato: `perfil_programacao: str` validado na requisição (implementados e aliases) e sem validador na
    resposta; `GET /config/formatos`; gerador por IA lista os quatro com o uso de cada um e usa `tipo_radio` como
    dica (`sertaneja`/`popular_mix` → popular; `mpb_variedades`/`regional_flashback` → musical).
  - Simulador: `--formato {programa,fixture,<id>}` (padrão `programa`, fixtures de linha de base intocadas),
    referência de orçamento do catálogo, canal lateral do dublê (cabeçalho do formato esperado e de outro formato),
    injeções `debate_longo`, `convite` e `tema_revisao`, bloco `resumo.json["formato"]` por
    `app.live.formatos.coerencia`; no `/proxima`, só o log `live_formato_aviso` com códigos, nunca trecho (D21).
  - Benchmark: 13 casos F6 em `casos.json` e as chaves novas em `regras.esperado` (96 falas).
  - Painel: `lib/formatoPrograma.ts` (`formatoDe`, `ehMusical`, `roteiroDoFormato`, `formatosImplementados`;
    espelho estrutural dos quatro, textos só da rota); select com os implementados e "Livre (sem formato)",
    promessa/conteúdo/condução/unidade/participação/temas do catálogo, "Usar relógio sugerido (A|C)" e "Usar
    sequência sugerida", blocos extras pela flag do formato; alias exibido como canônico e preservado ao salvar
    (D2); cartão somente leitura "Identidade da rádio" e seção "Identidade do programa" (D16); prévia dos próximos
    blocos e fala local pelo formato; `gerarFalaLocal` sem promessa de conteúdo (D22, pendência da F5).
  - Item 9 de `docs/auditoria.md` fechado (D18).
- Goldens: idênticos nos commits 1 a 4; regravados uma vez no commit 5 (3 musicais, só as linhas da seção do
  formato, diff revisado); 6 novos no commit 6; os 31 do `padrao` nunca mudaram. 22 snapshots das instruções
  (aceite do plano: os três formatos distintos dois a dois no mesmo papel).
- Portão local (HEAD `bbe3d9f`, 16/11/2026): ruff limpo; pytest **2266 passed**, 3 skipped (+365 sobre a F5; rodado
  em `aeeb19d`, o backend não mudou na leva 3); vitest **389** (+35); `tsc` ok; `npm run lint` com a falha
  preexistente da F0. Simulação: 12 rodadas `--formato programa` byte a byte iguais a `f5/simulacao/`; 12 rodadas
  `--formato fixture` em [`f6/simulacao/`](f6/simulacao/) (3 perfis × relógio, sem relógio, voz 120, painel antigo),
  0 tentativas de rede, hard time máximo 2,09 s, ≤ 2 LLM por fala, herdados em 0.
- Coerência medida no fake (`resumo.json["formato"]`, [`f6/testes.md`](f6/testes.md)): instrução do formato em 100%
  dos blocos de fala e nenhuma de outro formato nas 12; fala dentro da faixa do formato (musical 1,9–2,2%, popular
  8,0–17,9%, variedades 24,5–30,8%); nenhum bloco fora do formato nem tema de revisão no ar; no musical, maior
  sequência musical 552–1194 s e 6–8 interrupções por hora. `coerencia_automatica` verdadeira em 4 de 12; os itens
  fora (uma fala fora da unidade no musical, reorientação no popular voz 120 e no variedades com C, convites do
  banco do quadro) têm hipótese registrada e valor medido fixado em `test_simulacao_f6.py::MEDIDO_FORA_DO_LIMITE`;
  quase todos vêm do banco do dublê, não da decisão do backend. Contra a linha de base: popular sem relógio passou
  de 3600 s para 1197 s sem reorientação (D17).
- Portão independente: [`f6/portao.md`](f6/portao.md) (2266 passed, 3 skipped; vitest 389; tsc ok).
- Juiz: o aceite "coerência ≥ 4/5 em cada perfil" é o S7 (`--modo llm`, rubrica da `avaliar-locucao`) e depende de
  aprovação de custo; no fake, as métricas binárias acima são o proxy (D20: nenhuma nota sintética).
- Rollback: um backend anterior à F6 falha a leitura de programas com os ids novos. SQL de volta:
  `UPDATE programas SET perfil_programacao='musical_companhia' WHERE perfil_programacao='musical_adulto';`
  `UPDATE programas SET perfil_programacao='padrao' WHERE perfil_programacao IN ('popular_sertanejo','variedades_leves');`
- Decisões D1 a D23 adotadas pelo padrão da auditoria, a confirmar; desvios registrados em
  [`f6/pendencias.md`](f6/pendencias.md) (validador herdado no pydantic 2, papel `quadro` só pelo quadro fixo, log
  no commit 7, identidade do programa no topo do formulário em vez de antes de "Persona", D22 em três frases).
- Pendências: [`f6/pendencias.md`](f6/pendencias.md) — S7 com texto real; dublê obediente ao formato e "primeira"
  pela meta; teto de palavras na identificação dos formatos novos; `ORCAMENTOS` do musical × link de 10–35 s (D5);
  reorientação com memória no `/proxima` (F8); `ehMusical` do painel é pelo id (um formato futuro com ciclo musical
  pede atualização do painel); painel não conferido no navegador.
