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

## Ordem seguida
1. **Linha de base** (`69ecc9a`), antes de qualquer código.
2. **Módulos puros com testes, comportamento igual** (goldens intactos): `DadoVerificavel` e `ConfigDados`, com a
   janela da pauta movida para a configuração e a caracterização C2 gravada antes (`fd5d2e2`); limpeza de texto
   externo (`844f16a`); detector e `checar_fala` (`97ce304`); conversores, bloco de dados, leitura de clima com
   horário, porta, dublê e fixture autouse (`7c56c3c`). Suíte inteira verde no snapshot de `7c56c3c` (1826 passed).
3. **Mudanças de comportamento em commits próprios**, cada uma com o teste novo vermelho antes do código:
   - checagem no ar (`2de9754`): goldens e as 12 simulações idênticos; suíte 1840 passed;
   - bloco de dados na mensagem e textos de prompt (`e3efda1`): a única regravação de goldens, diff revisado;
   - curadoria (`62570b1`) e agenda pela data do evento (`f7dc1b2`, D12 isolada): suíte 1881 passed;
   - correção de um falso negativo achado na simulação do cenário dedicado (`3fcb872`).
4. **Simulador** (`b96022c`) e **painel** (`6bcc0b3`).

## Testes novos
| Arquivo | O que cobre (auditoria §8) |
|---|---|
| `tests/test_news_pauta_janela.py` (30) | C2: cada categoria na borda da janela (dentro, na borda, fora) e o assunto derivado pela mesma janela |
| `tests/test_dados_verificavel.py` (41) | U1: estado nos cinco valores, validade efetiva por tipo, janela por categoria igual à de antes, idade máxima, horário falado (meio-dia, meia-noite, "catorze e dez", fuso, virada do dia), números da `ConfigDados` |
| `tests/test_dados_texto_externo.py` (33) | U2: título do benchmark perde a ordem, dez formas de ordem embutida, oito manchetes legítimas intactas, controle, quebras, aspas, limite, `nome_seguro` |
| `tests/test_dados_checagem.py` (56) | U3: cada categoria com positivo e negativo, número igual e diferente, vencido com e sem horário, idade máxima só "de momento", placar sem contexto, isentas, cobertura extra, radical; **benchmark 6/6 e 1/1 sem falso positivo; 0 achados nas falas gravadas; goldens só afirmam dado nos blocos com pauta e clima** |
| `tests/test_dados_fontes.py` (28) | U4: cada conversor (tipo por categoria, fonte, horários, validade, limpeza com alerta e log sem trecho, não aprovado), pesquisa não ok sem dado, domínio fora das fontes, bloco JSON válido, ordenado e estável, vencido só com política e idade |
| `tests/test_weather_client.py` (+7) | U5: horário da observação em UTC, cache v2, última leitura com horário e TTL, Redis fora, WhatsApp sem a última leitura, testes sem rede por padrão |
| `tests/test_dados_proxima.py` (14) | U7, U8 e I2, I3, I4 (obediência), I6, I8, I10, I11 pela rota |
| `tests/test_dados_prompt.py` (15) | U6 (módulos puros, regra geral), I1 (clima com horário e fonte, trava de 45 min), I2 (vencido marcado), I4 (título fora do system, limpo na mensagem, log com id), apuração na mensagem e D9, I5 (legado com ordem na mensagem e no nome), texto autorizado do fluxo novo, I7, I9, C3/I12 |
| `tests/test_dados_agenda.py` (16) | D12/U9: fim do evento com e sem hora, sem data a janela, outra categoria ignora, curadoria devolve ISO ou vazio, worker guarda, evento passado não vira pauta |
| `tests/test_news_curadoria.py` (+3), `tests/test_news_worker.py` (+2) | D11/U9: frase de isolamento, item com ordem descartado sem LLM e log sem título, manchete legítima segue; retificação limpa e a que era só ordem não marca |
| `tests/test_simulacao_f5.py` (20) | S1 (12 rodadas iguais à linha de base fora o registro; guardrail sem integração por perfil), S2 (dois cenários dedicados), S3 (espião), D18 |
| Goldens novos | `clima_valido`, `clima_vencido_com_horario`, `noticia_titulo_injetado` |
| Painel | `lib/__tests__/reservaNeutra.test.ts` (D16), `lib/__tests__/liveTypesDados.test.ts` |

## Goldens regravados (só em `e3efda1`, diff revisado no commit)
Nada mudou em Redis, banco, sorteios, buscas de música nem temas. Mudou só o texto das chamadas ao LLM e, nos quatro
goldens com notícia, a resposta (campo `dados`):
- os 31: a linha da regra geral e o gancho que retoma "o assunto" em vez de "o clima"; 26 (são de segunda-feira): o
  texto da segunda sem "jogo"; `abertura_primeira`: o exemplo da abertura sem "recorde de calor";
- `escalada`, `noticia_pauta_com_retry`, `noticia_correcao`, `noticia_pesquisa_ok`: a lauda, a escalada, a correção e
  a apuração viram instrução que aponta para o dado; o fato vai ao bloco; apuração sem "atribuindo ao veículo";
- `chamada_abraco`, `chamada_recorrente`, `chamada_recorrente_dias`, `relogio_a_retorno_cumpre`: a mensagem do ouvinte
  sai da instrução e vai ao bloco; `pedido_novo_texto_autorizado`: o texto autorizado também;
- `musica_com_citada`, `musica_com_faixa`, `musical_musica_pedido`, `pedido_legado`, `pedido_novo_texto_autorizado`:
  o contexto da faixa vai ao bloco (dado `faixa`).

## Testes existentes editados de propósito
O texto externo agora está na mensagem, não no system; as asserções passaram a conferir as duas coisas:
- `test_news_pauta.py`: `test_montar_lauda_nao_cita_fonte_inclui_angulo_e_servico`,
  `test_montar_escalada_lista_manchetes_numeradas`, `test_montar_lauda_correcao_prioriza_frase_de_correcao`;
- `test_news_integracao_router.py`: escalada, notícia que não se repete e correção pendente;
- `test_topics_integracao_router.py`: assunto casado e música que puxa assunto;
- `test_topics_pauta_conversa.py::test_ponte_persistida_e_neutra_de_eixo_gera_falas_diferentes` (o briefing e a pergunta
  vão ao dado);
- `test_live_router.py`: notícia pesquisada (2 parâmetros) e contexto real da faixa;
- `test_atendimento_ouvintes.py::test_fala_nova_usa_apenas_conteudo_aprovado`;
- harness dos goldens: patch da porta nova do clima (`app.live.router.obter_leitura_clima`).

## Portão local (HEAD `6bcc0b3`, snapshot da árvore commitada)
| Item | Linha de base (passo 0) | F5 |
|---|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed | All checks passed |
| `pytest -q --cov=app --cov-report=term` | 1633 passed, 3 skipped; 87% | **1901 passed, 3 skipped** (+268); **88%**, 647 s |
| Cobertura de `app/dados` | — | `verificavel` 100%, `fontes` 98%, `texto_externo` 98%, `checagem` 97% |
| Cobertura dos módulos tocados | `news/pauta` 62%, `weather/client` 95%, `live/promessas` 95% | `news/pauta` 93%, `weather/client` 97%, `live/promessas` 97%; os demais iguais ou maiores |
| Painel: `npx vitest run` | 350 passed | **354 passed** (65 arquivos) |
| Painel: `npx tsc --noEmit` | sem erros | sem erros |

Cada commit de comportamento rodou a suíte inteira num snapshot da árvore antes de entrar (os dois testes que
falharam no snapshot de `e3efda1` eram asserções sobre texto que mudou de lugar e foram editados no mesmo commit).

## Simulação fake depois da F5 (`docs/melhoria-radio/f5/simulacao/`)
Mesmos comandos do passo 0 (dublê de TTS a 145 palavras/min, `PYTHONHASHSEED=0`, zero rede), mais os cenários
dedicados da F5 (`cenario_f5/`) e o guardrail sem integração (`guardrail_sem_integracao/`, três afirmações inventadas
por perfil nas falas 2 a 4, com relógio).

**S1, sem dado:** as 12 rodadas e o cenário da F4 têm `as_run.json` igual byte a byte à linha de base depois de tirar o
registro novo (`dados`, `dado_legitimo`); só três eventos o ganham (assunto puxado pela música nas variantes sem
relógio do popular e do variedades). Os critérios herdados são os da linha de base, número por número:

| Rodada (musical / popular / variedades) | Linha de base | F5 |
|---|---|---|
| `dado_sem_fonte` / `dado_vencido` no ar | — | 0 / 0 em todas |
| Anúncio sem confirmação, promessa vencida, pedido indevido, ouvinte inexistente | 0 em todas | 0 em todas |
| Atraso máximo em hard time (s): relógio / sem relógio / voz 120 / painel antigo | 0/0,36/0; 0/0/0; 0/12,1/0; 0/0/0 | igual |
| Encerramento no ar (relógio e painel antigo) | sim | sim |
| Fora do orçamento (%): relógio / voz 120 | 0/0/0; 0/0/6,7 | igual |
| LLM / sínteses máximas por fala | 2 / 1 | 2 / 1 |
| `validacao_fala.regras` (popular sem relógio, ex.) | `promessa_sem_evento: 2` | `promessa_sem_evento: 1` (D18: a contagem antiga era o dobro) |

**S1, guardrail sem integração** (musical "faz trinta graus lá fora", popular "ganhando por dois a zero", variedades
"trânsito parado na avenida principal"): `injecao_dado` 6 em cada perfil, `validacao_fala.regras.dado_sem_fonte` 3,
`dado_sem_fonte` e `dado_vencido` no ar 0, `sem_integracao` 0 em todas as categorias, critérios herdados mantidos
(hard time 0 s, encerramento no ar, 0% fora do orçamento, 2 LLM por fala).

**S2, cenários dedicados:**

| | `f5_variedades_c` (relógio C, pitada) | `f5_popular_b` (relógio B, notícias) |
|---|---|---|
| Blocos com dado; estados | 25; 17 válidos, 11 vencidos (clima depois de 14h30) | 60; 59 válidos, 7 vencidos |
| Falas com dado ditas pelo dublê obediente; `dado_legitimo_removido` | 30; 0 | 79; 0 |
| `vencido_com_horario` | 20 ("Na última atualização, hoje, às treze e trinta…") | 6 |
| `dado_sem_fonte` / `dado_vencido` no ar | 0 / 0 (validador tirou 2 sem fonte e 2 vencidos) | 0 / 0 (tirou 2 sem fonte) |
| `injecao`: no system / fora do bloco / removidas / obedecida no ar | 0 / 0 / 1 / 0 | 0 / 0 / 1 / 0 |
| Notícia fora da janela no bloco | nunca | — |
| Hard time / encerramento / fora do orçamento / LLM por fala | 0 s / sim / 4,0% / 2 | 0,22 s / sim / 0% / 2 |

O cenário variedades achou um falso negativo do validador (o radical de "parado" casava "para" no slogan da rádio, a
cobertura extra deixava passar a frase de trânsito inventada): corrigido em `3fcb872`, com teste.

**S3:** `metricas` não tem detector próprio de dado (espião em `app.dados.checagem`). **S4** (`--modo llm`) não rodado:
exige aprovação de custo.

## Critérios de aceite
| Critério (plano F5) | Resultado |
|---|---|
| Tipo comum `DadoVerificavel {valor, fonte, atualizado_em, valido_ate, local, aprovado}` | `app/dados/verificavel.py`, montado em memória para pauta, correção, apuração, assunto e clima (sem migração) |
| Dado vencido omitido ou dito com horário, nunca como atual | bloco só com válidos e o clima vencido marcado com o horário (D4); `dado_vencido` reescreve e tira a frase (I2, S2: 0 no ar) |
| Sem integração, não falar de temperatura, trânsito ou placar (guardrail) | I3 pela rota e S1 por perfil: a frase sai, 0 no ar |
| Conteúdo externo em bloco delimitado de dados, não em instruções (auditoria 3) | U6, I1, I4, I5, I7 e os goldens: nada de texto externo no system; `injecao.no_system` 0 |
| Testes: dado dentro e fora da validade, sem fonte e injeção em título | U1, U3, U4, I1, I2, I3, I4, golden `noticia_titulo_injetado`, S2 |
| Herdados F1-F4 | hard time ≤ 5 s, 0% fora com relógio, anúncio sem confirmação 0, promessa vencida 0, pedido indevido 0, ouvinte inexistente 0, ≤ 2 LLM por fala |

## Portão independente (testador-locufy, 2026-11-13, HEAD d6bc878)

### Comandos executados
- `backend/`: `.venv/bin/ruff check app tests scripts/simular_hora.py scripts/simulacao`; `ffmpeg -version` (8.0.1);
  `.venv/bin/pytest -q --cov=app --cov-report=term` (Python 3.12.13).
- `backend/`: `PYTHONPATH=. PYTHONHASHSEED=0 .venv/bin/python scripts/simular_hora.py --modo fake --programa <perfil>
  [--relogio-backend nenhum] --saida <scratchpad>/f5-portao/{relogio,sem_relogio}/<perfil>` para `musical_adulto`,
  `popular_sertanejo` e `variedades_leves` (6 rodadas; nunca `--modo llm`/`completo`).
- `frontend-painel/`: `npx vitest run`, `npx tsc --noEmit`, `npm run lint`.

### Linha de base (passo 0) x resultado
| Item | Linha de base | Portão independente |
|---|---|---|
| ruff | All checks passed | All checks passed |
| pytest | 1633 passed, 3 skipped, 538 s | **1901 passed, 3 skipped, 0 failed**, 645,57 s |
| Cobertura total | 87% | **88%** (17104 linhas, 2027 sem cobrir) |
| `app/dados/*` | - | `__init__` 100%, `verificavel` 100%, `fontes` 98%, `texto_externo` 98%, `checagem` 97% |
| `live/contexto` | 99% | 99% |
| `live/validacao_fala` | 97% | 97% |
| `live/geracao` | 94% | 94% |
| `live/router` | 95% | 95% |
| `llm/prompt_builder` | 98% | 97% (-1 ponto) |
| `news/pauta` | 62% | 93% |
| `news/curadoria` | 96% | 97% |
| `news/worker` | 81% | 81% |
| `weather/client` | 95% | 97% |
| vitest | 350 passed (63 arquivos) | **354 passed** (65 arquivos) |
| tsc --noEmit | sem erros | sem erros (rc=0) |
| `npm run lint` | falha preexistente (F0) | mesma falha (`next lint` inexistente no Next 16; "Invalid project directory .../lint") |

### Simulação fake (6 rodadas, rc=0 em todas)
Chaves reais: `dado_sem_fonte`, `dado_vencido`, `dado_legitimo_removido`, `injecao.no_system`, `sem_integracao.*`
(temperatura, condicao_tempo, previsao, placar, transito, comercial), `tentativas_rede`, `destinos_rede`,
`orcamento_fala.max_chamadas_llm_por_fala`.

| Rodada | atraso hard time (s) | encerr. no ar | fora orçam. % | anúncio s/ conf. | promessa venc. | pedido indev. | ouvinte inex. | dado s/ fonte | dado venc. | s/ integração (todas as chaves) | injeção no system | LLM/fala máx | rede |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| relógio musical_adulto | 0,0 | sim | 0,0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| relógio popular_sertanejo | 0,36 | sim | 0,0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| relógio variedades_leves | 0,0 | sim | 0,0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| sem relógio musical_adulto | 0,0 | não | 0,0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| sem relógio popular_sertanejo | 0,0 | não | 0,0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| sem relógio variedades_leves | 0,0 | sim | 0,0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |

`destinos_rede` vazio e `erros_http` 0 em todas. `dado_legitimo_removido` 0. Encerramento "não" sem relógio é o esperado
(igual à linha de base). Os 3 `resumo.json` com relógio batem com `docs/melhoria-radio/f5/simulacao/<perfil>/` campo a
campo; só diferem `config.commit` (`d6bc878` x `6bcc0b3`) e `tempo_execucao_s` (ruído).

### Falhas
Nenhuma. Única ressalva preexistente: `npm run lint` (F0).

### Divergências contra o portão local do implementador
Nenhuma nos números: 1901 passed / 3 skipped, 88%, vitest 354, tsc limpo, ruff limpo, tempo 645 s x 647 s, cobertura
dos módulos igual (`prompt_builder` 97% aqui; o texto do portão local não o cita). Observação: ao final da execução,
`git status` mostrava `docs/plano.md` modificado (2 linhas na seção 7, sobre F3/F4/F5), alteração que não é deste
portão e não afeta os testes.

VERDE
