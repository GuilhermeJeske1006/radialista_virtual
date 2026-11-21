# Auditoria F6: catálogo de formatos e perfis editoriais

Branch auditada: `melhoria/f6-formatos`, criada de `melhoria/f5-fontes` (HEAD `3f9ab88`, só documentação depois do
portão da F5 em `d6bc878`), worktree `locufy-radio`. Só leitura no código. `pytest --collect-only`: **1904 testes**
(1901 passed e 3 skipped no portão da F5); vitest 354.

Fontes:
- `docs/plano-melhoria-radio.md`: F6, F2 (entrega 4), Transversal, Avaliação ("Coerência: juiz: fala x formato e
  horário (F6)"), Portão e Regras.
- `docs/pesquisa-radio-locufy.md`: §3 (mapa dos formatos), §4 (lições dos cases), §8 (banco de falas originais), §9
  (relógios A, B, C), §12.1 (perfil editorial por programa), §13 (primeiros perfis).
- Skills `referencia-radio` (unidades por formato, regras 7 a 9, reorientação) e `avaliar-locucao` (rubrica).
- `docs/auditoria.md` (item 9) e `docs/refatoracao.md` (§2, §6).
- `docs/melhoria-radio/RELATORIO.md` e as pendências de F0 a F5 que citam a F6.
- `docs/benchmarks/2026-11-06-formatos/casos.json` (35 casos; nenhum da F6).
- Simulações gravadas em `docs/melhoria-radio/f5/simulacao/`.

**Conclusão: a frente NÃO está atendida.**
- Não existe catálogo: o "formato" é um booleano (`musical_companhia(programa)`, `app/live/formato.py:22-23`) com dois
  valores (`padrao` e `musical_companhia`). Popular/sertanejo e variedades leves rodam como `padrao`, com orçamento só
  observado (15–30 s) e o mesmo texto de prompt.
- O comportamento "musical" está espalhado em mais de 20 pontos que testam `formato_musical` ou a string
  `musical_companhia` (§2, fato 2), três deles comparando a string crua.
- A identidade do programa (promessa, condução, temas que exigem revisão, política de participação, reorientação) não
  existe como dado; `publico_alvo` nem chega ao prompt do ao vivo.
- Item 9 de `docs/auditoria.md` continua aberto.

## 1. Estado atual: o plano confere com o código?

| Afirmação do plano | Situação | Evidência |
|---|---|---|
| `perfil_programacao` aceita `padrao` e `musical_companhia` | confirmado | `Literal["padrao", "musical_companhia"]` em `ProgramaRequest` (`backend/app/config/router.py:137`), herdado por `ProgramaResponse` (`:170`); coluna `String` padrão `padrao` (`app/models/programa.py:53`), criada por `garantir_colunas_programa` (`app/main.py:371`). Painel: `perfil_programacao?: "padrao" \| "musical_companhia"` (`frontend-painel/lib/types.ts:160`). Teste de contrato: `tests/test_config_router.py:975-987` (aceita `musical_companhia`, 422 para valor desconhecido). |
| `Programa` já tem `perfil` | **confirmado, com ressalva** | `programa.py:91-94`. O comentário diz "só preenche campos na criação, não trava nada em runtime", mas é lido no ar: `perfil == "esportivo"` desliga a pauta RSS (`app/live/contexto.py:525`) e liga a pesquisa esportiva (`app/llm/noticias.py:159`); `jornalismo`/`religioso` escolhem a trilha da vinheta (`app/vinhetas/trilha.py:86-90`). É uma taxonomia diferente do formato: `musical, jornalismo, esportivo, variedades, religioso, comunitario` (`config/router.py:159`). |
| `Programa` já tem `dose_noticia` | confirmado | `programa.py:96-101`; usado em `roteiro.py:144-153`, `contexto.py:289`, `router.py:1836`, `news/pauta.py:123`. |
| `Programa` já tem `publico_alvo` | **confirmado, mas fora do ao vivo** | `programa.py:103-107`. Só o banco de assuntos lê (`app/topics/matcher.py:189`, `app/topics/reserva.py:63-64`). Não entra em `montar_system_prompt` nem em `prompt_emissao`. |
| `Programa` já tem `densidade_assunto` | **diferente: campo morto** | `programa.py:109-112`, `config/router.py:167`, `main.py:379`. Nenhum código de `app/` ou `scripts/` lê o valor (`git grep densidade`). |
| `Programa` já tem `quadros_fixos`, `generos_musicais` | confirmado | `programa.py:74`, `:56`; quadros em `contexto.py:283-284`, `:586-587`; gêneros em `prompt_builder.py:233`. |
| `app/llm/tipos_radio.py` existe | **confirmado, mas é outra coisa** | 139 linhas (`tipos_radio.py:8-139`): catálogo de **tipo de rádio da conta** (`Account.tipo_radio`, `app/models/account.py:37-39`), oito valores (sertaneja, gospel, jovem_pop…), usado só como contexto da geração por IA (`app/llm/config_generator.py:104`) e na rota `GET /config/tipos-radio` (`config/router.py:591-593`). Não é lido no ao vivo e não tem unidade de fala, roteiro nem relógio. |
| (Pontos de partida) `formato.py` com `ROTEIRO_PADRAO`, `ROTEIRO_MUSICAL`, `ORCAMENTOS`, `musical_companhia`, `orcamento_fala`, `direcao_musical` | confirmado | `formato.py:8`, `:10`, `:13-19`, `:22-23`, `:26-30`, `:43-66` (66 linhas). |
| (Pontos de partida) `orcamento.py` com tabela por formato e `FORMATOS_APLICADOS` | confirmado | `ORCAMENTOS_POR_FORMATO` (`orcamento.py:36-39`, chaves `musical_companhia` e `padrao`), `FORMATOS_APLICADOS = frozenset({"musical_companhia"})` (`:41`), `formato_do_programa` (`:96-97`), `orcamento_para` (`:108-125`). O comentário de `:32-35` já diz que a F6 troca a fonte "mantendo a assinatura de `orcamento_para`". |
| `direcao_musical` vira `direcao_formato(formato, tipo, primeira)` | a fazer | Única chamada de produção: `prompt_emissao.py:576-579`. Testes leem o texto exato: `tests/test_live_orcamento.py:35-63` e `tests/test_live_prompt_promessas.py:105-107`. O dublê da F0 lê a frase "X a Y segundos, no máximo N palavras" (`scripts/simulacao/dubles.py:49`). |
| Painel: seleção do formato com descrição da promessa | **diferente: parcial** | Select "Formato do programa" com duas opções e texto fixo do musical (`frontend-painel/components/EditarProgramaForm.tsx:635-668`), separado do select "Perfil do programa" (`:590-633`). Não há promessa vinda do backend. |
| Separar identidade da rádio (`RadioConfig`) da identidade do programa | **diferente: `RadioConfig` é o locutor** | `RadioConfig` guarda nome, personalidade, biografia, traços e voz do **locutor** (`app/models/radio_config.py:9-18`, `:27-48`). A identidade da **rádio** está em `Account` (`account.py:26-51`: nome, slogan, frequência, telefone, endereço, cidade, tipo, conhecimento local, bíblia), editada em `/configuracoes` (`GET/PUT /config/radio`, `config/router.py:596-613`). `docs/refatoracao.md` §6 registra esse vocabulário de três camadas e não recomenda renomear. No prompt, rádio, locutor e programa saem misturados de `montar_system_prompt` (`prompt_builder.py:224-340`), que o WhatsApp também usa. |

## 2. Fatos do código que mudam o desenho

1. **Três taxonomias convivem e nenhuma é o formato da pesquisa.**
   - `Account.tipo_radio`: oito tipos, só para a geração por IA.
   - `Programa.perfil`: seis presets de criação, com três efeitos no ar (§1).
   - `Programa.perfil_programacao`: dois valores, o único que muda o comportamento do ao vivo.

   O catálogo da F6 deve morar em `perfil_programacao` (D1) e não mudar o significado dos outros dois (§6.15).
2. **O comportamento musical está em mais de 20 pontos, três com a string crua.**

   | Onde | O que o booleano decide hoje |
   |---|---|
   | `router.py:2430` | `EntradaEmissao.formato_musical = musical_companhia(programa)` |
   | `router.py:726-742` (`_tipo_proximo_bloco`) e `roteiro.py:67-84` (`tipo_na_posicao`, cópia pura da F4) | ciclo musical (abertura só na largada, sem comentário sorteado, sem a regra de "abertura fora de lugar") e roteiro padrão |
   | `contexto.py:594`, `vinhetas/estrutura.py:62-65` | `ROTEIRO_MUSICAL` × `ROTEIRO_PADRAO` com estrutura vazia |
   | `contexto.py:346` | multivoz desligado |
   | `contexto.py:401` | bloco de música sem fala (sem pedido) |
   | `contexto.py:610`, `:615-617` | expressão regional, mudança de ideia, imperfeição (sorteios) |
   | `contexto.py:628-631` | hora certa e marco de tempo (sorteios) |
   | `contexto.py:642` | convite ao ouvinte só no bloco de chamada |
   | `contexto.py:309`, `:692` | agenda com música; citadas não resolvidas no bloco de música |
   | `contexto.py:647-651` via `orcamento.py:96-97` | orçamento aplicado sem relógio |
   | `geracao.py:258`, `router.py:2093` | uma faixa por bloco |
   | `router.py:2170` | tom do TTS `neutro` |
   | `router.py:2501-2503` | `duracao_alvo_segundos` sem relógio |
   | `prompt_emissao.py:108` | "meta específica" × "4 a 6 frases" |
   | `prompt_emissao.py:190` | recursos de fala natural (maneirismo, hesitação) |
   | `prompt_emissao.py:471` | aviso de que música citada toca |
   | `prompt_emissao.py:576-579` | `direcao_musical` |
   | `relogio.py:704-709` | unidade = menor entre `ConfigRelogio.unidades` e `ORCAMENTOS` |
   | `relogio.py:715-719` | `bloco_musical` × `bloco_padrao` (link, curadoria, conversa, quadro, entrevista, resumo viram `retomada`) |
   | `relogio.py:835`, `:868` | link de preenchimento proibido no musical |
   | **String crua:** `formato.py:23`, `app/llm/prompt_builder.py:400` (liberdade de inserir blocos, também no WhatsApp), `scripts/simulacao/fixtures.py:218-219` | — |

   Um valor canônico novo (`musical_adulto`) que não passe por um resolvedor quebra em silêncio
   `prompt_builder.py:400`: o prompt passaria a dizer "fique livre pra inserir blocos extras" no formato musical.
3. **O musical já é um formato completo; os outros dois não têm nada.**
   - O musical tem roteiro (`formato.py:10`), orçamento aplicado (`orcamento.py:41`), direção (`formato.py:43-66`) e
     tratamento no relógio.
   - Popular e variedades são `padrao`: orçamento só observado, 15–30 s (`orcamento.py:38`).
   - Na simulação da F5 sem relógio, 38,1% (popular) e 62,5% (variedades) das falas passam dessa observação.
   - A F2 deixou a decisão para a F6 (`f2/pendencias.md`: "A unidade de fala por formato é decisão da F6").
4. **`ORCAMENTOS` do musical diverge da pesquisa e é a linha de base de quatro frentes.**
   - Valores atuais: retomada 6–12 s, identificação 3–7 s (`formato.py:13-19`); a pesquisa propõe link de 10–35 s
     (§3; `f0/auditoria.md:355`).
   - O relógio usa o menor dos dois (`relogio.py:704-709`, F1 D5).
   - Os goldens musicais, `test_live_orcamento.py:17-32`, `test_live_relogio.py:256`, `:348` e as simulações da F2 à
     F5 dependem desses números.
   - Para o alias ser alias, `musical_adulto` herda os números (D5).
5. **Unidades do relógio × unidades do formato: no musical, "formato vence" é igual a "menor dos dois".**
   - Conferi cada par usado pelo musical (evento → bloco): abertura, retomada, link, curadoria, retorno, participação,
     conversa, quadro, serviço, notícia, atualização, entrevista, passagem, encerramento, resumo e música. Em todos,
     `ORCAMENTOS` ≤ `UNIDADES_PADRAO` (`relogio.py:202-229`) nos dois extremos.
   - Logo, a regra "unidade do formato, limitada pela etapa" (D8) mantém o musical idêntico e dá aos formatos novos
     unidade própria. Com "menor dos dois", o popular ficaria igual ao padrão (link 10–35).
6. **Relógio padrão.** Os presets são três (`relogio.py:171-195`; `PresetRelogio.id: Literal["A", "B", "C"]`, `:172`;
   `RelogioHora.preset`, `:120`), a pesquisa só tem A, B e C (§9) e a fixture do popular usa A desde a F0. O relógio é
   opcional por programa desde a F1 (programa sem relógio segue `estrutura_blocos`).
7. **O dublê do LLM não lê o formato, só a meta.**
   - Ignora o prompt, exceto tipo, a frase da meta (`META_BLOCO_RE`, `dubles.py:49`), a revisão e o bloco de dados.
   - Sem meta no prompt, usa a referência da fixture (`dubles.py:288-300`), escolhida por
     `fixture.formato_musical` (`fixtures.py:218-219`).
   - O texto vem de um banco fixo (`scripts/simulacao/banco_falas.py`), igual para todo formato.
   - Consequência: no modo fake a rubrica de coerência mede o banco, não o sistema. A coerência automática precisa
     medir o que o backend decide: blocos, durações, distribuição de fala, reorientação, convites e a assinatura do
     formato no prompt (§9).
8. **As fixtures já anunciam o formato que o backend não tem.**
   - Campo `formato` = `musical_adulto` / `popular_sertanejo` / `variedades_leves`, com `unidade_fala` e
     `orcamento_ref_s` da skill (`tests/fixtures/programas/*.json`).
   - Mas `programa.perfil_programacao` é `musical_companhia` / `padrao` / `padrao`. Os cenários da F5
     (`cenarios/f5_popular_b.json`, `f5_variedades_c.json`) também usam `padrao`.
   - `tests/test_simulacao_f5.py` (e F3/F4) comparam as_runs com as linhas de base gravadas: trocar o
     `perfil_programacao` das fixtures quebra essas comparações (D19).
9. **Contrato do programa.**
   - O PUT grava todos os campos do corpo (`config/router.py:1385-1386`) e o POST cria com `**dados.model_dump()`
     (`:1137`).
   - `ProgramaResponse` herda o `Literal` e qualquer validador de `ProgramaRequest`: um valor fora dele no banco
     derruba a leitura (500), ao contrário de `relogio_hora`, que tem leitura tolerante (`:179-189`).
   - A geração por IA valida contra `ProgramaRequest` e remove o campo inválido, que cai no padrão com
     `campos_corrigidos` (`_construir_com_defaults`, `:264-288`).
   - O prompt do gerador oferece só `padrao`/`musical_companhia` (`config_generator.py:19`, `:57-60`), e os três
     exemplos usam `padrao` (`exemplos_config.py:23`, `:46`, `:70`).
10. **Painel.**
    - Compara a string crua em três arquivos de produção: `EditarProgramaForm.tsx:641-751`,
      `components/live/ProximosBlocosPanel.tsx:133` e `hooks/useLiveEngine.ts:165`.
    - Mantém um espelho de `ROTEIRO_MUSICAL` em `lib/formatoPrograma.ts:1-12` e o roteiro padrão em
      `ProximosBlocosPanel.tsx:21`.
    - O select é controlado: um painel antigo em cache que receba `popular_sertanejo` mostra a primeira opção, mas
      reenvia o valor guardado no estado ao salvar.
11. **Lições dos cases que viram campo do catálogo.**

    | Case (§4) | Lição | Campo |
    |---|---|---|
    | 4.4 Alpha FM | períodos em que a melhor decisão é deixar a música tocar; medir interrupção | `comportamento.musica_sem_fala`, métrica `maior_sequencia_musical_s`, `interrupcoes_por_hora` |
    | 4.5 Antena 1 | intervenção curta com curiosidade verificável; sem biografia a cada faixa | `funcoes["musica"]`, unidade do musical |
    | 4.7 Hora do Ronco | quadros que o público antecipa; momentos para quem acaba de sintonizar | `reorientacao_s`, quadros (variedades) |
    | 4.8 Nativa | mesma identidade popular, energia ajustada ao horário | `conducao` do popular; o perfil por horário (`prompt_builder.py:85-100`) continua |
    | 4.2 Estúdio CBN, 4.14 Viva Maria | transições claras entre serviço e cultura; serviço que representa necessidade concreta | `conducao` e `funcoes` de variedades |
    | 4.9, 4.15, 4.1, 4.10/4.11 | esporte separa fato e opinião; religioso segue tradição e roteiro aprovado; jornal sustentado por produção; morning de elenco | `requer` dos formatos não implementados |
12. **Item 9 continua aberto.**
    - `_classificar_bloco_customizado` faz `hset` no hash global `cache:categoria_bloco_customizado` sem `expire`
      (`router.py:867-880`).
    - O cliente é `redis_sessao` (`router.py:25`), cujo `PADROES_SESSAO` (`app/config/redis_client.py:88-93`) tem
      `expire`, mas não `hlen`.
    - O golden `comentario_quadro_fixo.json:102` grava o conteúdo do hash (via `hgetall`, `test_live_proxima_caracterizacao.py:490`),
      não o TTL: um `expire` não muda nenhum golden.

## 3. Linha de base

**Portão da F5 (13/11/2026):** ruff limpo; pytest 1901 passed, 3 skipped (1904 coletados agora), cobertura 88%; vitest
354; `tsc` ok. O HEAD `3f9ab88` só acrescenta documentação ao `d6bc878` do portão, então o passo 0 é confirmar (não
refazer): rodar `pytest --collect-only` e uma simulação por perfil e comparar com `f5/simulacao/`.

**Simulação (F5, fake, `docs/melhoria-radio/f5/simulacao/`), números de coerência medidos nesta auditoria** (script
descartável sobre os as_runs gravados):

| Perfil / variante | Falas | Fala no ar | % da hora | Maior trecho só de música | Falas com nome da rádio ou do programa | Maior intervalo sem reorientação | Falas com convite |
|---|---|---|---|---|---|---|---|
| musical / relógio A | 6 | 67,9 s | 1,9% | 1166 s | 6 | 1175 s | 1 |
| musical / sem relógio | 8 | 72,0 s | 2,0% | 552 s | 7 | 586 s | 0 |
| popular / relógio A | 10 | 243,7 s | 6,8% | 775 s | 5 | 1612 s | 1 |
| popular / sem relógio | 21 | 650,5 s | 18,1% | 282 s | 1 | 3600 s | 1 |
| variedades / relógio C | 18 | 1149,5 s | 31,9% | 778 s | 4 | 3459 s | 3 |
| variedades / sem relógio | 24 | 1284,8 s | 35,7% | 274 s | 6 | 1159 s | 5 |

Leitura:
- O popular sem relógio fala antes de cada música (12 de 21 falas são de música) e passa a hora inteira sem
  reorientar.
- O variedades com relógio C fica quase uma hora sem dizer o nome do programa.

São as lacunas de coerência que o catálogo ataca (roteiro padrão, política de reorientação).

**Benchmark:** `casos.json` tem 5 casos com a dimensão `coerencia`, todos ligados a F3/F4/F5/F8, e nenhum da F6.

## 4. Testes existentes que tocam a F6

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_live_orcamento.py` | 20 | Retrato de `ORCAMENTOS`/`orcamento_fala` (`:17-32`) e do texto inteiro de `direcao_musical` por tipo (`:35-63`); `orcamento_para` com e sem relógio para `musical_companhia` e `padrao` (`:145-185`). |
| `tests/test_live_relogio.py` | 35 | `planejar(..., formato_musical=)` (`:38-41`); link no musical vira `retomada` (6, 12) com 25 palavras (`:245-256`); nenhum plano abaixo do mínimo em A/B/C × musical (`:259-270`); encerramento musical (10, 18) (`:348`); paridade dos presets com as fixtures (`:85`). |
| `tests/test_live_relogio_proxima.py` | 17 | `/proxima` com relógio, inclusive musical (`:72`). |
| `tests/test_live_router.py` | 138 | Ciclo musical: sequência sem LLM, repete sem reabrir, revisão da retomada longa, pedido anunciado, encerramento (`:2979-3075`); roteiro padrão e personalizado; classificação de bloco customizado com cache (`:97-122`). |
| `tests/test_live_router_duracao.py` | 23 | Orçamento musical aplicado, reescrita, encurtamento, `orcamento_para("musical_companhia", ...)` (`:311`). |
| `tests/test_live_prompt_emissao.py` | 16 | Pureza dos módulos de `app/live` (`:18-34`, lista onde `formatos` deve entrar); musical não resolve citadas (`:112-125`). |
| `tests/test_live_promessas.py`, `test_live_prompt_promessas.py`, `test_live_pedido_indisponivel.py` | 49 / 7 / — | Agenda sem relógio por roteiro, musical × padrão (`test_live_promessas.py:163-195`); "Não prometa retorno" no encerramento musical (`test_live_prompt_promessas.py:97-107`); musical vira só música (`test_live_pedido_indisponivel.py:91`). |
| `tests/test_live_validacao_fala.py` | — | Constrói `ContextoEmissao` à mão com `formato_musical=True` (`:55`): campo novo precisa de padrão. |
| `tests/test_live_proxima_caracterizacao.py` | 35 (34 goldens) | 31 cenários no formato `padrao` e 3 musicais (`musical_retomada_com_excesso`, `musical_identificacao`, `musical_musica_pedido`, `:234-240`, `:373-378`); prompt inteiro, resposta, Redis e sorteios. |
| `tests/test_llm_prompt_builder.py` | 42 | Linha da estrutura de blocos com e sem liberdade da IA (`:208-219`); nenhum teste com `musical_companhia` em `prompt_builder.py:400`. |
| `tests/test_config_router.py` | 48 | Contrato de `perfil_programacao` (`:975-987`); `GET /config/tipos-radio` (`:42`). |
| `tests/test_config_relogio.py` | 7 | Presets somam uma hora; PUT do programa preserva o relógio; leitura tolerante. |
| `tests/test_llm_config_generator.py` | 13 | Geração e sanitização; nenhum teste de `perfil_programacao`. |
| `tests/test_programa_migration.py` | 1 | Coluna `perfil_programacao` criada com `padrao`. |
| `tests/test_vinhetas.py` | 40 | `roteiro_base` com estrutura vazia = `ROTEIRO_PADRAO` (`:179`). |
| `tests/test_simular_hora.py`, `test_simular_hora_f2.py`, `test_simulacao_f3/f4/f5.py` | 29 / 10 / 4 / 14 / 20 | Fixtures válidas (`:86-130`); dublê respeita o orçamento musical (`:146-190`); casos de avaliação têm as chaves das regras (`:575`); linhas de base byte a byte. |
| Painel: `components/__tests__/EditarProgramaForm.test.tsx` | — | Seleciona `musical_companhia`, aplica a sequência musical, desliga blocos extras (`:65-77`). |
| Painel: `components/live/__tests__/ProximosBlocosPanel.test.tsx` | — | Prévia musical (`:93-107`) e padrão (`:19-55`). |
| Painel: `hooks/__tests__/useLiveEngine.continuidade.test.ts` | — | Programa `musical_companhia` (`:24`). |

**Não coberto:**
- formato além de musical e padrão;
- alias;
- `prompt_builder.py:400` com formato musical;
- unidade de fala por formato fora do musical;
- relógio com unidades de outro formato;
- TTL do cache de categoria;
- qualquer métrica de coerência com o formato.

## 5. Itens de `docs/auditoria.md` e `docs/refatoracao.md`

| Item | Situação | Na F6 |
|---|---|---|
| auditoria 9: cache de categoria sem TTL | **aberto** (`router.py:867-880`; a auditoria citava `:1069-1081`) | Corrigir em commit isolado (D18). A F6 também garante, por teste, que todo bloco de roteiro do catálogo é classificado por prefixo, sem LLM, e portanto não alimenta o hash. |
| auditoria 10: telefone em log | aberto | Logs novos só com ids e códigos (`live_formato_aviso programa_id=… formato=… avisos=[…]`), nunca trecho de fala. |
| auditoria 6: Redis | resolvido (F3) | `hlen` entra em `PADROES_SESSAO` se o teto do hash usar esse comando. |
| auditoria 1, 3, 4, 5, 7 | 3, 4 e 5 resolvidos; 1 e 7 abertos, fora do rádio | Nada. |
| refatoração §2: texto de prompt misturado com código | aberto | A F6 tira do código o texto de formato (promessa, condução, funções por bloco) e o põe no catálogo, sem reescrever `montar_system_prompt`. |
| refatoração §1: `config_generator.py` grande | aberto | Só editar as duas frases do formato e o exemplo; não refatorar. |
| refatoração §6: `radialista`/`radio_config`/`locutor` | decidido: não renomear | A F6 trata "identidade da rádio" como `Account` e "identidade do locutor" como `RadioConfig`; não renomeia tabela nem modelo. |

## 6. Desenho da mudança

### 6.1 Princípios

1. **Um catálogo, um resolvedor.** Todo ponto que hoje testa `formato_musical` ou a string `musical_companhia` passa a
   ler o `Formato` resolvido do programa. Nenhuma comparação de string crua sobra no backend, no simulador nem no
   painel.
2. **Programa sem formato novo não muda.** `padrao` reproduz o comportamento atual do não musical, e
   `musical_adulto` reproduz o do musical. Com isso os 34 goldens e as 12 simulações da F5 ficam idênticos até o
   commit que muda texto de propósito.
3. **Alias de verdade.** `musical_companhia` e `musical_adulto` produzem prompt, resposta, Redis e as_run idênticos.
4. **Números em configuração.** Unidades, faixas de coerência e frequência de reorientação são hipóteses da pesquisa
   e da skill, ficam no catálogo e nunca viram constante solta.
5. **Sem LLM novo, sem migração.** Continuam valendo no máximo 2 chamadas de LLM e 1 síntese por fala. A coerência é
   medida por funções puras. A coluna já existe (D1).
6. **Contratos só ampliam.** A API aceita mais valores e ganha uma rota de leitura. A resposta do programa não muda
   de forma.
7. **Commits que mudam comportamento ficam separados** dos que só reorganizam; goldens regravados uma vez, com diff
   revisado.

### 6.2 Módulos

- **Novo `backend/app/live/formatos.py`** (puro: não importa o router, o banco nem o Redis; entra na lista de
  `test_live_prompt_emissao.py:18`):
  - o catálogo `FORMATOS`;
  - `resolver_formato(valor) -> Formato` (alias → canônico; vazio, desconhecido ou não implementado → `padrao`);
  - `formato_do_programa(programa) -> Formato`;
  - `unidade(formato, tipo, primeira, quadro=False) -> Unidade`;
  - `direcao_formato(formato, tipo, primeira=False, orcamento=None) -> str`;
  - `linhas_do_formato(formato, ctx_minimo) -> list[str]` (§6.9);
  - `coerencia(...)` (§6.14).
- **`formato.py` vira camada de compatibilidade.**
  - Continua dono das constantes do musical (`ROTEIRO_MUSICAL`, `ROTEIRO_PADRAO`, `ORCAMENTOS`) e dos utilitários
    (`contar_palavras`, `_tipo_fala`), de onde o catálogo as lê sem copiar números, como a F2 fez em
    `orcamento.py:32-37`.
  - `musical_companhia(programa)` passa a `formato_do_programa(programa).comportamento.ciclo == "musical"`.
  - `direcao_musical(...)` passa a `direcao_formato("musical_adulto", ...)`, com importação tardia, para não criar
    ciclo.
  - Os testes de caracterização que importam esses nomes não mudam.
- **Grafo de importação sem ciclo:** `formato` ← `formatos` ← `orcamento` ← `relogio`; `formatos` ← `relogio`,
  `contexto`, `roteiro`, `prompt_emissao`, `config/router`, `config_generator`, `prompt_builder`,
  `vinhetas/estrutura`. O id do relógio padrão é uma string, conferida por teste contra `relogio.PRESETS`.

### 6.3 Estruturas

```python
@dataclass(frozen=True)
class Unidade:
    min_s: float
    alvo_s: float
    max_s: float
    max_palavras: int | None = None      # teto do formato; None = só pelo ritmo da voz

@dataclass(frozen=True)
class Comportamento:                      # substitui cada uso de formato_musical (§2, fato 2)
    ciclo: Literal["musical", "padrao"]   # _tipo_proximo_bloco / tipo_na_posicao
    musica_sem_fala: bool                 # contexto.py:401
    uma_faixa_por_bloco: bool             # geracao.py:258, router.py:2093, resolve_citadas
    multivoz: bool                        # contexto.py:346
    naturalidade_encenada: bool           # contexto.py:610-617, prompt_emissao.py:190
    hora_e_marco: bool                    # contexto.py:628-631
    convite: Literal["qualquer_bloco", "so_chamada"]   # contexto.py:642
    tom_tts: str | None                   # router.py:2170 ("neutro" no musical)
    ia_pode_adicionar_blocos: bool        # prompt_builder.py:400, router.py:745, painel
    preenchimento_relogio: bool           # relogio.py:835, :868
    abertura_apos_intervalo: bool         # D17 (pendência da F0)

@dataclass(frozen=True)
class Formato:
    id: str
    nome: str                             # painel
    promessa: str                         # §3 "Promessa"
    conteudo: str                         # §3 "Conteúdo"
    conducao: str                         # §3 "Condução sugerida" (texto de prompt)
    unidade_principal: str                # §3/skill, para o painel ("link de 10 a 35 s")
    unidades: Mapping[str, Unidade]       # papel do bloco -> unidade; "*" obrigatório
    aplica_orcamento: bool                # False só no padrao (observa, F2)
    comportamento: Comportamento
    roteiro_padrao: tuple[str, ...]       # estrutura vazia
    relogio_padrao: str | None            # "A" | "B" | "C" (sugestão no painel, D7)
    blocos_relogio: Mapping[str, str]     # tipo de evento -> bloco (sobrescreve RegraBloco.bloco_padrao)
    funcoes: Mapping[str, str]            # papel -> função do bloco no prompt
    temas_revisao: tuple[str, ...]        # declarados; a revisão humana é da F12
    participacao: str                     # política em uma frase (prompt e painel)
    reorientacao_s: int | None            # intervalo alvo entre reorientações ("Você está no...")
    faixa_fala_pct: tuple[float, float]   # coerência: fala / hora esperada (simulação)
    aliases: tuple[str, ...] = ()
    implementado: bool = True
    requer: str = ""                      # condição para implementar (formatos futuros)
    fonte: str = "docs/pesquisa-radio-locufy.md §3; skill referencia-radio"
```

- **Papel do bloco**, que é a chave de `unidades`:
  1. `"quadro"`, se o bloco é quadro fixo (`programa.quadros_fixos[tipo]`) e o formato declara `quadro`;
  2. senão `_tipo_fala(tipo)`, a regra atual (`formato.py:37-40`), com `abertura` fora da largada → `retomada`
     (`orcamento.py:102-104`);
  3. senão `"*"`.

  No musical isso é exatamente o lookup de hoje: `ORCAMENTOS` não tem `quadro`.
- **`ContextoEmissao` e `EntradaEmissao`** ganham `formato: Formato`, com padrão `FORMATOS["padrao"]` no fim da
  dataclass. `formato_musical: bool` continua como campo derivado (`formato.comportamento.ciclo == "musical"`) até
  todos os usos migrarem. Assim `test_live_validacao_fala.py:55` não quebra.

### 6.4 Os formatos

Valores são hipóteses de projeto (skill `referencia-radio` e pesquisa §3), em segundos (mín / alvo / máx).

| | `padrao` (livre, legado) | `musical_adulto` (alias `musical_companhia`) | `popular_sertanejo` | `variedades_leves` |
|---|---|---|---|---|
| Promessa (§3) | — | Acompanhar com curadoria | Companhia e reconhecimento | Ajudar na vida cotidiana, com leveza |
| Condução (§3) | — | Discreta, acolhedora, sem pressa artificial | Próxima e afetiva | Prática e inclusiva |
| Unidade principal (§3) | — | link de 10–35 s | entrada de 20–60 s | quadro de 2–8 min |
| `aplica_orcamento` | não (observa 15–30 s) | sim | sim | sim |
| abertura (1ª) | — | 20 / 25 / 30 (≤ 65 palavras) | 20 / 40 / 60 | 30 / 60 / 90 (pergunta do dia) |
| retomada | — | 6 / 9 / 12 (≤ 25) | 15 / 25 / 40 | 15 / 25 / 40 |
| identificação | — | 3 / 5 / 7 (≤ 14) | 3 / 6 / 10 | 3 / 6 / 10 |
| música (anúncio) | — | 4 / 6 / 8 (≤ 18) | 8 / 15 / 25 | 8 / 15 / 25 |
| chamada_ouvinte | — | `*` | 20 / 40 / 60 (recados) | 20 / 40 / 60 (respostas reais) |
| comentário | — | `*` | 20 / 35 / 60 (história, vida local) | 20 / 45 / 60 (conversa) |
| quadro | — | `*` | `*` | 60 / 120 / 180 por fala (o quadro inteiro, 2–8 min, é a soma no relógio C) |
| encerramento | — | 10 / 14 / 18 (≤ 38) | 15 / 30 / 45 | 20 / 35 / 45 |
| `*` | 15 / 22,5 / 30 (observação) | 10 / 15 / 20 (≤ 45) | 20 / 35 / 60 | 20 / 35 / 60 |
| ciclo | padrão | musical | padrão | padrão |
| Roteiro padrão (estrutura vazia) | `ROTEIRO_PADRAO` | `ROTEIRO_MUSICAL` | `musica, chamada_ouvinte, musica, comentario, musica, retomada` | `musica, comentario, musica, chamada_ouvinte, musica, retomada` |
| Relógio padrão (sugestão) | — | A | A (D6) | C |
| Blocos do relógio | `RegraBloco.bloco_padrao` | `bloco_musical` (link, curadoria, conversa, quadro, entrevista, resumo → `retomada`) | padrão | padrão (`quadro` → `@quadro`) |
| Música sem fala (sem pedido) | não (com relógio, sim: F1 D2) | sim | não (com relógio, sim) | não (com relógio, sim) |
| Multivoz / naturalidade encenada / hora e marco | sim / sim / sim | não / não / não | sim / sim / sim | sim / sim / sim |
| Convite ao ouvinte | qualquer bloco | só na chamada | qualquer bloco | só na chamada (pergunta do dia na abertura) |
| Tom do TTS | por bloco | `neutro` | por bloco | por bloco |
| IA pode inserir blocos | flag do programa | nunca | flag do programa | flag do programa |
| Abertura depois do intervalo | regra atual (vira comentário) | — | permitida (D17) | permitida (D17) |
| Temas que exigem revisão | — | notícia grave ou tragédia, saúde e medicamento, política, religião | luto em recado, saúde e medicamento, dívida, empréstimo e aposta, política, religião | saúde, finanças e investimento, orientação jurídica e de consumo, alimentação com promessa de saúde, política, religião |
| Participação | — | pedido real anunciado no bloco de música; sem pedido, nada (a música fala) | recados e pedidos reais pelo nome autorizado; sem recado, convite genérico (§8 "Quando não há pedido") | pergunta do dia na abertura e leitura só de respostas reais; convite só com retorno agendado (F4) |
| Reorientação (`reorientacao_s`) | — | 900 (a identificação de cada volta) | 1200 e no retorno de cada intervalo | 900 e em cada quadro |
| `faixa_fala_pct` | — | 1–8% | 4–20% | 15–45% |

Formatos com `implementado=False`, com promessa, conteúdo, condução e unidade principal do §3 e da skill, e `requer`:

| Formato | `requer` |
|---|---|
| `hits` | — (link 10–40 s) |
| `regional` | vocabulário local aprovado (entrada 20–90 s) |
| `noturno` | regra 9 da skill (não pressupor solidão) (entrada 15–45 s) |
| `religioso` | tradição e roteiro aprovados (§4.15) (reflexão 1–5 min) |
| `morning` | bancada com papéis (F13), relógio C (conversa 2–6 min) |
| `esportivo` | fontes esportivas e separação fato × opinião × rumor (§4.9) (debate 3–10 min) |
| `jornalistico` | fontes e validade (F5, **concluída**), relógio B (nota 20–60 s; reportagem 1–4 min) |

O resolvedor nunca devolve um formato não implementado: cai em `padrao`, com log `formato_nao_implementado`.

### 6.5 Alias e compatibilidade (`musical_companhia` → `musical_adulto`)

- **Banco:** nada é reescrito. O valor gravado continua `musical_companhia` e é resolvido na leitura (D2).
- **API:**
  - `ProgramaRequest.perfil_programacao` passa a `str` com `field_validator`: aceita `padrao`, os ids implementados e
    os aliases; o resto dá 422 em português ("Formato desconhecido ou ainda não disponível: …").
  - **`ProgramaResponse` redeclara `perfil_programacao: str` sem o validador.** Validadores de campo são herdados pela
    subclasse; sem a redeclaração, a leitura de um valor fora do catálogo daria 500 (§2, fato 9).
  - A resposta ecoa o valor gravado, e por isso um painel antigo em cache continua vendo `musical_companhia`.
- **Geração por IA:**
  - o prompt do gerador (`config_generator.py:19`, `:57-60`) passa a listar os formatos implementados e quando usar
    cada um;
  - `musical_companhia` vindo do LLM continua válido;
  - um formato não implementado ou inventado cai em `padrao` por `_construir_com_defaults`, com o campo em
    `campos_corrigidos`, como hoje;
  - o exemplo sertanejo (`exemplos_config.py:23`) passa a `popular_sertanejo`; o jornalismo e o noturno continuam
    `padrao`.
- **Painel:**
  - o select mostra o canônico para o alias e só grava o canônico quando o usuário troca a opção;
  - um programa musical antigo salvo sem mexer no formato continua `musical_companhia`;
  - nenhuma comparação de string crua sobra: helper `formatoDe(programa)` e `ehMusical(programa)` em
    `lib/formatoPrograma.ts`.
- **Simulador:** `fixture.formato_musical` passa a perguntar ao backend (`resolver_formato(...).comportamento.ciclo`).
- **WhatsApp:** `prompt_builder.py:400` usa `formato_do_programa(programa).comportamento.ia_pode_adicionar_blocos`.
  Para o alias, o texto é o mesmo de hoje.

### 6.6 Como o catálogo alimenta cada consumidor

| Consumidor | Hoje | Depois |
|---|---|---|
| Roteiro sem estrutura (`router.py:726-742`, `roteiro.py:67-84`, `contexto.py:593-595`, `vinhetas/estrutura.py:62-65`) | `ROTEIRO_MUSICAL` × `ROTEIRO_PADRAO` pelo booleano | `formato.roteiro_padrao` e `formato.comportamento.ciclo` (os dois laços continuam onde estão; sem unificar). `abertura_apos_intervalo` acrescenta `patrocinador` às categorias anteriores aceitas para abertura/retomada (`router.py:748-753`) só nos formatos que pedem. |
| Orçamento (`orcamento.py:36-41`, `:96-125`) | tabela de dois formatos | `ORCAMENTOS_POR_FORMATO` e `FORMATOS_APLICADOS` derivados do catálogo, exportados com os mesmos nomes; `orcamento_para` resolve o alias e aceita `quadro=`; assinatura igual. `formato_do_programa` (string) devolve o id canônico. O alvo vem de `Unidade.alvo_s` (no musical, o ponto médio de hoje). |
| Relógio (`relogio.py:704-719`, `:835`, `:868`, `:932`) | `formato_musical: bool` | `planejar(..., formato: Formato | None = None, formato_musical: bool | None = None)`: o booleano vira o formato (musical/padrão) quando o formato não vem. `unidade()`: com `aplica_orcamento`, a unidade do formato para o papel do bloco, limitada pela etapa e pelo espaço (D8); sem, `cfg.unidades`. `_bloco()` lê `formato.blocos_relogio`. Preenchimento lê a flag. |
| Contexto (`contexto.py`, linhas do fato 2) | booleano | flags do `Comportamento`, **na mesma ordem de chamadas e sorteios** de hoje. |
| Prompt (`prompt_emissao.py:108`, `:190`, `:471`, `:572-590`) | booleano e `direcao_musical` | "meta específica" quando `aplica_orcamento` ou relógio; recursos de fala natural pela flag; `_duracao` chama `direcao_formato` para todo formato com `aplica_orcamento` (com e sem relógio) e acrescenta a linha de agenda da F4 como o musical já faz; `padrao` com relógio segue em `_instrucao_relogio`. Nova seção `_formato(ctx)` (§6.9). |
| Geração e resposta (`geracao.py:258`, `router.py:2093`, `:2170`, `:2501-2503`) | booleano | flags; `duracao_alvo_segundos` sem relógio = `(orcamento.min_s, orcamento.max_s)` quando `aplica_orcamento` (no musical, os mesmos números de `orcamento_fala`). |
| Prompt do WhatsApp (`prompt_builder.py:400`) | string crua | flag (§6.5). |
| Painel | string crua e espelho do roteiro | `GET /config/formatos` (§6.10). |
| Simulador | `perfil_programacao == "musical_companhia"` | resolvedor do backend; métricas de coerência por `formatos.coerencia` (§6.14). |

### 6.7 Relógio

- **Relógio padrão é sugestão (D7).** O painel oferece "Usar o relógio sugerido do formato" no `RelogioHoraEditor`.
  Programa sem relógio continua sem relógio (regra de compatibilidade da F1).
- **Popular usa o preset A (D6).** O relógio efetivo é distinto do musical: no link, `comentario` de 20–35 s contra
  `retomada` de 6–12 s; no retorno, recado de 20–60 s contra 10–20 s; na curadoria, `comentario` contra `retomada`;
  na passagem, 3–10 s contra 3–7 s. O teste do aceite compara o relógio efetivo (preset, sequência de
  `(etapa, tipo_bloco, orcamento_s)` em uma hora), não só o id do preset. Alternativa (B): preset original "D,
  popular com participação" (dois recados por hora, fala 6 min, música 48 min, intervalos 6 min, soma 3600 s), que
  amplia `Literal["A","B","C"]` (`relogio.py:120`, `:172`; `lib/types.ts:210`, `:219`).
- **Unidade no relógio (D8).** "Unidade do formato, limitada pela duração da etapa e pelo espaço até o hard time"; o
  musical fica idêntico (§2, fato 5). `ConfigRelogio.unidades` continua como teto do formato `padrao` e da
  `fechamento_curto`.
- O relógio personalizado completo (editar tipo, natureza e hard time no painel, `f1/pendencias.md`) **não** entra
  (§10).

### 6.8 `FORMATOS_APLICADOS` e o perfil `padrao`

- `FORMATOS_APLICADOS = frozenset(f.id for f in FORMATOS.values() if f.implementado and f.aplica_orcamento) | aliases`:
  `{"musical_adulto", "musical_companhia", "popular_sertanejo", "variedades_leves"}`.
- `padrao` continua fora: orçamento só observado sem relógio (decisão da F2 mantida).
- `padrao` não desaparece (D3). É "Livre (sem formato)" no painel, o padrão da API e do formulário, e o formato de
  todo programa existente que não é musical. Nada muda para ele: sem linha nova no prompt, mesma ordem do `random`.

### 6.9 Prompt: `direcao_formato` e a seção do formato

**`direcao_formato(formato, tipo, primeira=False, orcamento=None) -> str`**
- `musical_adulto`: o texto de hoje, byte a byte (`formato.py:56-66`).
- `padrao`: string vazia.
- Formatos novos, mesma forma do musical:
  - cabeçalho com o nome do formato ("FORMATO POPULAR/SERTANEJO: a companhia e o reconhecimento do ouvinte ocupam o
    centro.");
  - função do bloco (`formato.funcoes`, a partir das estruturas de intenção do §8, sem frase pronta);
  - **a frase da meta no formato que o dublê lê**: "Meta de locução: X a Y segundos, no máximo N palavras.";
  - condução;
  - a regra de promessa ("Não prometa intervalo, retorno ou conteúdo futuro sem programação confirmada");
  - "Mantenha as regras factuais e de atendimento dos pedidos reais."
- Nenhuma fala de exemplo imita apresentador real (§8 e regra 7 da skill).

**`_formato(ctx)`**, nova seção de `montar_prompt`, só para `formato.id != "padrao"` (D10):
1. "Programa {nome}, formato {formato.nome}. Promessa: {promessa}. Público: {publico_alvo}". O público entra só
   quando preenchido; hoje não chega ao ao vivo (§1).
2. "A promessa do formato prevalece sobre o perfil do horário." `_perfil_editorial` (`prompt_builder.py:92-93`) sugere
   "serviço e utilidade pública" das 9h às 11h, o que contradiz o musical.
3. Política de participação em uma frase.
4. "Temas que exigem revisão humana neste formato: …; sem conteúdo aprovado, não trate deles."
5. Nos blocos de retomada, identificação, retorno e quadro: "Reoriente quem acabou de chegar: nome do programa e da
   rádio em uma frase." A frequência com estado (memória) é da F8.

A seção do musical muda os 3 goldens musicais uma vez (§7, commit 5). Os 31 goldens de `padrao` não mudam.

**Identidade da rádio × do programa:** a seção acima é o "programa". A rádio continua vindo de `montar_system_prompt`
(nome, frequência, slogan, conhecimento local), que não muda porque o WhatsApp a usa.

### 6.10 Contratos e API

- `ProgramaRequest.perfil_programacao: str = "padrao"` com validador do catálogo (§6.5). `ProgramaResponse` redeclara
  o campo como `str` sem validador: a forma do JSON não muda, sem campo novo nem removido.
- **Nova rota `GET /config/formatos`**, autenticada como `/relogios/presets` (`config/router.py:1392`), devolvendo
  `list[FormatoResponse]`:
  - identificação e textos: `id`, `nome`, `promessa`, `conteudo`, `conducao`, `unidade_principal`;
  - estrutura: `roteiro_padrao`, `relogio_padrao`, `ia_pode_adicionar_blocos`;
  - política: `participacao`, `temas_revisao`, `reorientacao_s`;
  - estado: `aliases`, `implementado`, `requer`.

  Inclui os não implementados, para o painel saber o que vem.
- `LiveProgramResponse` não muda. `orcamento_fala_s.fonte` já diz `formato`/`observacao`/`relogio`.
- Rollback: um backend anterior à F6 lendo um programa com `popular_sertanejo` falha a validação da resposta (o
  `Literal` antigo). Documentar no relatório o SQL de volta (`UPDATE programas SET perfil_programacao='padrao' WHERE
  perfil_programacao IN ('popular_sertanejo','variedades_leves')` e `'musical_adulto'` → `'musical_companhia'`).

### 6.11 Painel

- `lib/types.ts`: `perfil_programacao?: string`, tipo `FormatoPrograma` (resposta da rota) e `normalizarPrograma` sem
  mudança de valor.
- `lib/formatoPrograma.ts`: `formatoDe`, `ehMusical`, `roteiroDoFormato` (lê a lista da rota e cai no espelho atual se
  ela faltar).
- `EditarProgramaForm.tsx`:
  - select "Formato do programa" com os implementados mais "Livre (sem formato)";
  - abaixo do select: promessa, condução, unidade principal e política de participação;
  - botões "Usar sequência sugerida" (roteiro padrão) e "Usar relógio sugerido" (preset);
  - checkbox de blocos extras pela flag do formato.
- **Separação de identidade:**
  - cartão somente-leitura "Identidade da rádio" (nome, slogan, cidade, frequência de `/config/radio`, com link "editar
    em Configurações");
  - seção "Identidade do programa" (nome, descrição, formato e promessa, público), antes de "Persona e conteúdo";
  - nenhuma tela nova.
- `ProximosBlocosPanel.tsx`: prévia pelo ciclo e roteiro do formato.
- `useLiveEngine.ts:165`: `ehMusical(programa)`. Junto, D22: as frases de `gerarFalaLocal` que prometem conteúdo
  (`:190`, `:192`) viram a reorientação neutra (pendência da F5).
- vitest e `tsc`.

### 6.12 Geração por IA de config

- O prompt lista os formatos implementados com uma linha de uso cada:
  - musical adulto: programa predominantemente musical, poucas intervenções;
  - popular/sertanejo: música com recados, histórias e vida local;
  - variedades leves: conversa, quadro fixo e serviço leve;
  - `padrao`: jornalismo, esporte, entrevista, debate, religioso e noturno (ainda sem formato próprio).
- `tipo_radio` da conta pode sugerir o formato (sertaneja e popular_mix → popular; mpb_variedades e
  regional_flashback → musical adulto) como dica no prompt, não como regra.
- Sem chamada real nos testes (dublê, como hoje).

### 6.13 Item 9 (cache de categoria)

- `hset` seguido de `expire(chave, settings.cache_categoria_bloco_ttl_s)` (padrão 30 dias, renovado a cada gravação).
- Teto `settings.cache_categoria_bloco_max` (padrão 5000): ao passar, apaga o hash antes de gravar.
- `hlen` entra em `PADROES_SESSAO` (padrão 0).
- Commit isolado; goldens idênticos (o TTL não entra no retrato).

### 6.14 Simulador e coerência automática

- `simular(..., formato=None)` e CLI `--formato {programa,fixture,<id>}`, padrão `programa` (D19).
  - `fixture` aplica o campo `formato` da fixture em `programa.perfil_programacao`, como `injecoes_extra` faz.
  - As fixtures de linha de base e as rodadas da F3 à F5 ficam intocadas.
  - As rodadas da F6 (e das frentes seguintes) usam `--formato fixture`.
  - Relógio: o da fixture (A, A, C), igual ao `relogio_padrao` do catálogo.
- `fixtures.py:218-219` e `emissao.py:345-366`: a referência de orçamento passa a vir do catálogo quando o formato
  aplica orçamento; a da fixture fica só para `padrao`.
- Dublê, canal lateral:
  - registra por bloco se o system tinha o cabeçalho do formato esperado e se tinha cabeçalho de outro formato (como
    os contadores de injeção da F5, `dubles.py:282-285`);
  - injeções novas: `debate_longo` (fala de 90 s num bloco do musical), `convite` (convite ao WhatsApp numa retomada
    do musical) e `tema_revisao` (frase sobre medicamento).
- `metricas.py`: bloco `formato` no `resumo.json`, calculado por `app.live.formatos.coerencia` (importação tardia,
  padrão S3 da F3–F5). Métricas no §9.

### 6.15 O que não muda

- Programa `padrao`: prompt, resposta, Redis, sorteios e simulações idênticos.
- Programa `musical_companhia`/`musical_adulto`: idêntico até o commit 5, que acrescenta a seção do formato.
- `Programa.perfil`, `Account.tipo_radio`, `densidade_assunto` (continua sem uso; não ligar nesta frente),
  `montar_system_prompt`, WhatsApp, relógios A/B/C, `ConfigRelogio`, F4 e F5.

## 7. Ordem de commits e impacto nos goldens

| # | Commit | Comportamento | Goldens (34 em `tests/fixtures/caracterizacao_proxima/`) |
|---|---|---|---|
| 0 | Passo 0: confirmar a linha de base (coleta, uma simulação por perfil contra `f5/simulacao/`); `f6/testes.md` | — | — |
| 1 | Caracterização C2–C5 (só testes) | igual | 0 |
| 2 | `formatos.py` com `padrao`, `musical_adulto` (+ alias) e os sete não implementados; `formato.py` como compatibilidade; `orcamento.py` derivado; relógio, roteiro, contexto, prompt, geração, router, `prompt_builder.py:400` e vinhetas pelas flags | **igual** | 0; 12 simulações byte a byte |
| 3 | Item 9: TTL e teto do cache de categoria | igual | 0 |
| 4 | Contrato (validador na requisição, campo sem validador na resposta, `GET /config/formatos`) e gerador por IA (prompt, exemplo, alias) | igual no ao vivo | 0 |
| 5 | Seção `_formato(ctx)` (promessa, temas, participação, reorientação) e a linha "promessa prevalece" | **muda** só o musical | **3** (`musical_retomada_com_excesso`, `musical_identificacao`, `musical_musica_pedido`), diff revisado |
| 6 | `popular_sertanejo` e `variedades_leves` (unidades, roteiros, flags, `direcao_formato`, `abertura_apos_intervalo`); snapshots das instruções; goldens novos | muda só para quem escolhe o formato | 0 existentes; **6 novos**: `formato_popular_comentario`, `formato_popular_chamada_recado`, `formato_popular_relogio_a_link`, `formato_variedades_quadro`, `formato_variedades_relogio_c_quadro`, `formato_musical_adulto_identificacao` (igual ao alias, exceto o valor do campo) |
| 7 | Simulador: `--formato`, resolvedor, referência do catálogo, canal lateral, injeções, métricas de coerência; `tests/test_simulacao_f6.py` | — | — |
| 8 | Benchmark: casos F6 em `casos.json` e chaves novas em `regras.esperado` | — | — |
| 9 | Painel (§6.11) | — | — |
| 10 | Rodadas, `RELATORIO.md`, `f6/pendencias.md`, `f6/testes.md`, `docs/plano.md` §7 | — | — |

Se a regravação do commit 5 mostrar diferença fora das linhas novas do formato (ordem do `random`, Redis, banco),
parar e investigar.

## 8. Testes, nesta ordem

**Caracterização** (antes de mover código)
- **C1.** Os 34 goldens idênticos nos commits 1 a 4 e 6; o commit 5 regrava só os 3 musicais.
- **C2.** Tabela de `_tipo_proximo_bloco` e `tipo_na_posicao` nas posições 0 a 20 para `padrao` e
  `musical_companhia`, com:
  - estrutura vazia, personalizada, com `abertura` e `encerramento` no meio e com vinheta/patrocinador;
  - `ultima_categoria` em {None, música, patrocinador, comentário};
  - o sorteio do comentário extra fixado.

  Mais `vinhetas.estrutura.roteiro_base`. Gravar antes do commit 2.
- **C3.** `planejar` para A, B, C × {padrão, musical}, a cada 7 s na hora (como `test_live_relogio.py:259`),
  gravando `(acao, tipo_bloco, orcamento_s, palavras_max)` num JSON de referência. O commit 2 não pode mudar uma linha.
- **C4.** `orcamento_para` para `padrao` e `musical_companhia` × todos os tipos × `primeira` × {sem teto, teto 4,
  14, 35}: tabela idêntica. Amplia `test_live_orcamento.py:145-185`.
- **C5.** `montar_system_prompt` com `musical_companhia` e `ia_pode_adicionar_blocos=True` dá "siga estritamente"
  (hoje sem teste, `prompt_builder.py:400`).
- **C6.** Simulação: 3 perfis × 4 variantes, `--formato programa`, com `as_run.json` byte a byte igual aos gravados
  em `f5/simulacao/<perfil>/` (não `linha_de_base/`, que não tem o registro de dados da F5). O arranjo é o de
  `test_simulacao_f5.py`.

**Unitários**
- **U1, `test_live_formatos.py`, integridade do catálogo:**
  - todo formato tem os campos obrigatórios;
  - `min ≤ alvo ≤ max` e `"*"` em `unidades`;
  - `relogio_padrao` existe em `relogio.PRESETS`;
  - todo bloco de `roteiro_padrao` é classificado por prefixo, com `classificar_categoria_bloco` trocado por um que
    falha;
  - aliases únicos e sem colisão com ids;
  - implementados = {padrao, musical_adulto, popular_sertanejo, variedades_leves};
  - os não implementados têm promessa e unidade do §3.
- **U2, resolvedor:** alias → canônico; vazio, `None`, desconhecido e não implementado → `padrao`; espaços e caixa.
- **U3, flags:** `padrao` = comportamento atual do não musical e `musical_adulto` = do musical, item a item da tabela
  do §2, fato 2.
- **U4, `unidade`/`orcamento_para`:**
  - musical igual a `ORCAMENTOS`;
  - popular e variedades aplicados (fonte `formato`);
  - quadro só com `quadro=True`;
  - teto do relógio;
  - alias;
  - `FORMATOS_APLICADOS` derivado.
- **U5, `direcao_formato`:**
  - `musical_adulto` == texto de `direcao_musical` hoje, e o alias também;
  - `padrao` vazio;
  - os novos contêm a frase que `META_BLOCO_RE` casa, a condução e a regra de promessa, e não contêm "4 a 6 frases"
    nem nome de apresentador.
- **U6, snapshot das instruções (aceite), `tests/test_live_formatos_snapshot.py`:**
  - para cada formato × papel (abertura primeira, retomada, identificação, música com pedido, chamada, comentário,
    quadro no variedades, encerramento), `montar_prompt(ctx)` sobre um `ContextoEmissao` montado à mão (como
    `test_live_validacao_fala.py:55`);
  - extrair as linhas do formato (direção e `_formato`) e comparar com `tests/fixtures/formatos/<formato>__<papel>.txt`
    (`ATUALIZAR_GOLDEN=1`);
  - para o mesmo papel, os três textos são distintos dois a dois.
- **U7, relógio:**
  - `planejar` com `formato=musical_adulto` == com `formato_musical=True`;
  - popular no link de A → `comentario` (20, 35); variedades no quadro de C;
  - preenchimento pela flag;
  - **relógio efetivo distinto**: para os três formatos com o relógio padrão, a sequência de
    `(etapa, tipo_bloco, orcamento_s)` em uma hora é distinta dois a dois;
  - nenhum plano abaixo do mínimo, com os formatos novos acrescentados ao parametrize de `test_live_relogio.py:259`.
- **U8, roteiro:** `tipo_na_posicao`/`_tipo_proximo_bloco` com o roteiro de cada formato; abertura depois de
  patrocinador permitida nos novos e igual no `padrao` (pendência da F0).
- **U9, pureza:** `formatos` na lista de `test_live_prompt_emissao.py:18`.
- **U10, cache de categoria:** TTL > 0 depois do `hset`; teto apaga e regrava; Redis fora (disjuntor) sem exceção.
- **U11, coerência:** `formatos.coerencia`, com positivo e negativo para cada aviso (`fora_da_unidade`,
  `bloco_fora_do_formato`, `convite_fora_da_politica`, `tema_revisao`, `reorientacao`) e os casos F6 do benchmark.
- **U12, gerador:**
  - prompt lista os formatos implementados;
  - LLM devolvendo `musical_companhia` grava;
  - `hits` (não implementado) ou inventado vira `padrao` com `campos_corrigidos`;
  - o exemplo sertanejo usa `popular_sertanejo`.

**Integração** (HTTP, patches por nome em `app.live.router`)
- **I1.** Popular sem relógio, comentário:
  - direção do popular no system;
  - `orcamento_fala_s` com `fonte="formato"`, `aplicado=true`, 20–60;
  - `duracao_alvo_segundos` preenchido;
  - excesso dá uma reescrita (máximo de 2 LLM).
- **I2.** Variedades, bloco de quadro fixo: unidade `quadro`; convite só na chamada.
- **I3.** Alias: o mesmo cenário com `musical_companhia` e `musical_adulto` dá prompt, resposta, Redis e sorteios
  idênticos.
- **I4.** `padrao`: goldens (C1).
- **I5.** Popular com relógio A (link → comentário 20–35) e variedades com C.
- **I6.** Multivoz permitido no popular e no variedades, desligado no musical.
- **I7.** Painel antigo (sem `inicio_previsto`) com cada formato novo: sem erro, hard time dentro de 5 s.
- **I8.** Contrato:
  - PUT/GET com cada id implementado e com o alias (ecoa o gravado);
  - 422 para `hits` e `inexistente`;
  - `GET /config/formatos` com os campos e os não implementados marcados;
  - commit de programa gerado por IA com formato novo.
- **I9.** WhatsApp: `montar_system_prompt` igual para `musical_adulto` e `musical_companhia`
  (`test_whatsapp_webhook.py` intacto).
- **I10.** `GET /config/programas` com um valor fora do catálogo gravado direto no banco responde 200 (ecoa o valor;
  confere a redeclaração do campo na resposta).

**Simulação** (`tests/test_simulacao_f6.py`)
- **S1.** = C6: `--formato programa`, idêntico à F5.
- **S2.** Três perfis × {relógio da fixture, `sem_relogio`, `voz_120`, `sem_inicio_previsto`} com `--formato fixture`:
  - critérios herdados: 0% fora do orçamento com relógio, hard time ≤ 5 s, encerramento no ar, anúncio sem
    confirmação, promessa vencida, pedido indevido, ouvinte inexistente, `dado_sem_fonte` e `dado_vencido` em 0,
    ≤ 2 LLM e 1 síntese por fala;
  - coerência dentro dos limites do §9.
- **S3.** Alias: musical com `musical_adulto` e com `musical_companhia` dá as_run byte a byte igual.
- **S4.** Distinção: os três formatos dão `formato.instrucao_no_prompt_pct = 100`, relógio efetivo distinto e
  orçamentos distintos no as_run.
- **S5.** `metricas` não tem detector próprio de coerência (espião, como o S3 da F3–F5).
- **S6.** Injeções `debate_longo` e `convite` no musical e `tema_revisao` no popular: a métrica correspondente ≥ 1
  (o detector funciona). Os avisos não removem nada (D21).
- **S7.** `--modo llm`, só com aprovação explícita de custo: o juiz pontua coerência com o formato ≥ 4/5 por perfil
  (o aceite do plano); falsos positivos de `coerencia` com texto real.

**Testes existentes editados de propósito** (registrar em `f6/testes.md`): os 3 goldens musicais (commit 5);
`test_config_router.py:975-987` ganha ids novos, mas `inexistente` continua 422; `EditarProgramaForm.test.tsx:65-77` e
`ProximosBlocosPanel.test.tsx:93-107` passam pelo helper. O retrato de `direcao_musical` (`test_live_orcamento.py:35-63`)
**não** muda.

## 9. Métricas novas do simulador (`resumo.json["formato"]`)

Os limites são hipóteses do catálogo (`faixa_fala_pct`, `reorientacao_s`, unidades); a primeira rodada da F6 calibra e
registra.

| Métrica | O que mede | Aceite (fake) |
|---|---|---|
| `id`, `relogio_padrao` | formato resolvido pelo backend | informativo |
| `instrucao_no_prompt_pct` | blocos de fala cujo system tinha o cabeçalho do formato (canal lateral do dublê) | 100 nos três; `padrao` 0 |
| `instrucao_de_outro_formato` | blocos com cabeçalho de outro formato | 0 |
| `fala_pct` | tempo de fala no ar / duração do programa | dentro de `faixa_fala_pct` (musical 1–8%, popular 4–20%, variedades 15–45%) |
| `falas_fora_da_unidade` | falas não reduzidas pelo relógio com duração < mín ou > máx × (1 + tolerância) da unidade do papel | ≤ 5% |
| `blocos_fora_do_formato` | falas de bloco que o formato não prevê (comentário ou notícia no musical) | 0 |
| `maior_sequencia_musical_s` e `interrupcoes_por_hora` | promessa musical (§4.4) | musical: ≥ 540 s; interrupções ≤ 10 por hora |
| `reorientacoes`, `maior_intervalo_sem_reorientacao_s` | falas com o nome do programa ou da rádio e o maior intervalo entre elas | maior intervalo ≤ 1,5 × `reorientacao_s` |
| `convites`, `convites_fora_da_politica` | convites ao ouvinte e os que estão fora do bloco permitido | fora da política = 0 |
| `temas_revisao_no_ar` | falas no ar com tema que o formato manda revisar | 0 nas fixtures; ≥ 1 só com a injeção (S6) |
| `coerencia_automatica` | `true` quando todos os itens acima estão dentro | `true` nos três perfis com relógio e sem relógio |

**Sobre o aceite "juiz ≥ 4/5":** no modo fake o texto vem do banco do dublê, que ignora o prompt (§2, fato 7). O juiz
usa as métricas acima como critério automático da dimensão Coerência (APROVADO = `coerencia_automatica` em todos os
perfis e nenhuma dimensão herdada abaixo da F5). A nota 1–5 da rubrica fica para S7, como em F2–F5 (D20).

## 10. Riscos e o que não fazer

- **Quebra silenciosa do alias.** Uma comparação de string esquecida faz o musical canônico se comportar como padrão,
  e o caso mais provável é `prompt_builder.py:400`, porque o WhatsApp também passa por ali. Mitigação: U3, I3, I9, S3
  e um teste que procura `"musical_companhia"` fora de `formatos.py`/`formato.py`.
- **Validador herdado pela resposta.** Pôr o validador do catálogo em `ProgramaRequest` sem redeclarar o campo em
  `ProgramaResponse` faz a listagem dar 500 para qualquer valor fora do catálogo no banco. Mitigação: §6.5 e I10.
- **Ordem dos sorteios.** As flags precisam ser lidas na mesma ordem das condições de hoje (`contexto.py:610-642`).
  Uma mudança na ordem muda os goldens do `padrao`. Mitigação: C1 e C6 no commit 2.
- **Unidades novas são hipóteses.** Popular e variedades passam a reescrever sem relógio (mais chamadas de LLM, dentro
  do teto de 2). O quadro de até 180 s por fala aumenta custo e latência do TTS. Mitigação: números no catálogo;
  medir `ajustes_fala` e `chamadas_llm` em S2; `--modo llm`/`completo` só com aprovação.
- **Popular com o relógio A** pode não parecer "popular" para quem usa relógio (um recado por hora). O D6 deixa a
  alternativa do preset D registrada.
- **Prosódia por bloco** (`prompts.py:46-60`: abertura "animada, exclamação, ritmo mais rápido") contradiz a condução
  do musical. É conflito conhecido para a F7 (persona e oralidade); a F6 não mexe.
- **Perfil por horário** (`prompt_builder.py:85-100`) contradiz formatos. A F6 põe a linha "promessa prevalece" e não
  altera o perfil (31 goldens).
- **Painel antigo em cache** mostra a opção errada para formato novo (cosmético; o valor é preservado ao salvar).
- **Rollback do deploy** com programas em formato novo: o backend antigo falha a leitura. SQL de volta no relatório
  (§6.10).
- **Conflito de texto com F7 e F8** (mesmas seções do prompt): a F6 regrava os goldens uma vez; reorientação com
  estado e repetição por estrutura ficam na F8.
- **PII:** logs com ids e códigos de aviso, nunca trecho de fala, nome ou telefone.
- **Não fazer nesta frente:**
  - implementar `hits`, `regional`, `noturno`, `religioso`, `morning`, `esportivo` ou `jornalistico` (só estrutura);
  - aplicar o relógio do formato automaticamente, ou reescrever valores gravados no banco (sem migração de dados);
  - mudar `ORCAMENTOS` do musical (a divergência com o link de 10–35 s é decisão separada);
  - mudar o significado de `perfil` ou `tipo_radio`, ligar `densidade_assunto`, renomear `RadioConfig`;
  - persona configurável (F7), memória e frequência de reorientação com estado (F8), revisão humana de temas (F12);
  - remover frase ou reescrever por coerência (só medir e logar, D21);
  - editor completo do relógio (tipo, natureza e hard time) e seleção de faixa por duração-alvo (pendências da F1);
  - refatorar `montar_system_prompt`, `config_generator.py` ou unificar `_tipo_proximo_bloco` com `tipo_na_posicao`;
  - mexer nas fixtures de linha de base.

## 11. Decisões em aberto (nenhuma bloqueia; o implementador segue o PADRÃO)

- **D1. Onde guardar o formato.** (A) Ampliar `perfil_programacao` (coluna `VARCHAR` já existente); (B) coluna nova
  `formato`. **PADRÃO: A**, sem migração. Com (B), o PUT que ecoa o programa inteiro apagaria o campo, o problema que a
  F1 contornou para `relogio_hora`.
- **D2. Alias.** **PADRÃO:** sem reescrita no banco; resolvido na leitura; API aceita e ecoa; painel exibe o canônico e
  só grava canônico quando o usuário troca.
- **D3. Perfil `padrao`.** **PADRÃO:** continua como "Livre (sem formato)", com o comportamento atual; padrão da API e
  do formulário; não vira variedades.
- **D4. Forma do catálogo.** **PADRÃO:** Python (dataclasses congeladas) em `app/live/formatos.py`, com `formato.py`
  como compatibilidade. Alternativa: JSON por formato, como os relógios.
- **D5. Unidades.** **PADRÃO:** a tabela do §6.4. O musical herda `ORCAMENTOS` sem mudança; alinhar o musical ao link
  de 10–35 s fica para decisão do usuário, porque muda a linha de base de quatro frentes.
- **D6. Relógio padrão do popular.** **PADRÃO:** preset A, com unidades e blocos do formato; o aceite mede o relógio
  efetivo. Alternativa: preset D original (§6.7).
- **D7. Relógio do formato.** **PADRÃO:** sugestão no painel; nunca aplicado automaticamente.
- **D8. Unidade no relógio.** **PADRÃO:** unidade do formato limitada pela etapa e pelo espaço quando o formato aplica
  orçamento; `ConfigRelogio.unidades` no `padrao`.
- **D9. Orçamento sem relógio nos formatos novos.** **PADRÃO:** aplicado (reescrita única e encurtamento da F2).
- **D10. Texto.** **PADRÃO:** `direcao_formato("musical_adulto")` byte a byte igual a hoje; a seção `_formato(ctx)`
  entra nos três formatos (3 goldens musicais regravados) e nunca no `padrao`.
- **D11. `FORMATOS_APLICADOS` e `ORCAMENTOS_POR_FORMATO`.** **PADRÃO:** derivados do catálogo, mesmos nomes exportados,
  `orcamento_para` resolve o alias.
- **D12. `formato_musical`.** **PADRÃO:** flags do `Comportamento` em todos os usos; o booleano fica derivado no
  contexto e na entrada.
- **D13. Formatos não implementados.** **PADRÃO:** no catálogo com `implementado=False`, 422 na API, fora do painel e
  do gerador. O jornalístico tem a F5 concluída, mas fica para uma frente própria.
- **D14. Contrato.** **PADRÃO:** `perfil_programacao: str` validado na requisição e redeclarado sem validador na
  resposta; rota `GET /config/formatos`. Alternativa: campo `formato` canônico na resposta.
- **D15. Gerador por IA.** **PADRÃO:** lista os implementados com uso de cada um, aceita alias, exemplo sertanejo em
  `popular_sertanejo`, `tipo_radio` como dica.
- **D16. Identidade.** **PADRÃO:**
  - rádio = `Account`, locutor = `RadioConfig`, programa = `Programa` com o formato;
  - no painel, cartão somente-leitura da rádio e seção "Identidade do programa";
  - no ao vivo, `_formato(ctx)` com promessa e público;
  - `montar_system_prompt` intacto.
- **D17. Abertura depois do intervalo** (pendência da F0). **PADRÃO:** permitida nos formatos novos; `padrao` igual.
- **D18. Item 9.** **PADRÃO:** TTL de 30 dias renovado a cada gravação, teto de 5000 entradas, `hlen` no
  `PADROES_SESSAO`, valores em `settings`.
- **D19. Simulador.** **PADRÃO:** fixtures intocadas; `--formato {programa,fixture,<id>}` com padrão `programa`;
  rodadas da F6 e seguintes com `fixture`.
- **D20. Coerência no modo fake.** **PADRÃO:** métricas binárias do §9 e `coerencia_automatica`; nada de nota 1–5
  sintética; rubrica só em `--modo llm`.
- **D21. Coerência no `/proxima`.** **PADRÃO:** só log `live_formato_aviso`; sem reescrita nem remoção.
- **D22. `gerarFalaLocal` do painel.** **PADRÃO:** além do helper do musical, trocar as frases que prometem conteúdo
  pela reorientação neutra (pendência da F5, mesma função).
- **D23. Blocos extras da IA.** **PADRÃO:** só o musical ignora `ia_pode_adicionar_blocos`; os outros formatos
  respeitam a flag do programa.

## 12. Pendências de frentes anteriores atribuídas à F6

| Origem | Pendência | Tratamento |
|---|---|---|
| F0, auditoria 9 | TTL ou teto do hash de categoria | §6.13, D18, U10 |
| F0/F2 | Musical: retomada 6–12 s e identificação 3–7 s × link 10–35 s | D5: mantido; decisão do usuário |
| F0/F1 | No padrão, a abertura de cada volta vira comentário depois do patrocinador; o popular perde a abertura da 2ª volta | D17, só nos formatos novos |
| F1 | Unidades de fala por tipo de evento no catálogo | §6.7, D8 |
| F1 | Relógio personalizado completo no painel | fora (§10); continua pendente |
| F1/F3 | Seleção de faixa por duração-alvo | fora (§10) |
| F2 | "Unidade de fala por formato é decisão da F6"; padrão sem relógio só observa | §6.4, D3, D9 |
| F2 | `ORCAMENTOS_POR_FORMATO` passa a sair do catálogo mantendo a assinatura | §6.6, D11 |
| F5 | Perfil jornalístico (relógio B) | estrutura `implementado=False` (D13) |
| F5 | `gerarFalaLocal` ainda promete conteúdo | D22 |

## 13. Dependências e tamanho

- Nenhuma bloqueia: F0 a F5 concluídas, e a F5 é a base desta branch.
- Modos `llm` e `completo` só com aprovação explícita de custo; o S7 (juiz ≥ 4/5) depende disso, como nas frentes
  anteriores.

**Tamanho:** médio a grande.
- Código novo: cerca de 450 a 600 linhas em `app/live/formatos.py`, mais a rota e o modelo de resposta.
- Arquivos alterados:
  - backend: `formato.py`, `orcamento.py`, `relogio.py`, `roteiro.py`, `contexto.py`, `prompt_emissao.py`,
    `geracao.py`, `router.py`, `llm/prompt_builder.py`, `llm/config_generator.py`, `llm/exemplos_config.py`,
    `config/router.py`, `config/settings.py`, `config/redis_client.py`, `vinhetas/estrutura.py`;
  - simulador: `scripts/simular_hora.py`, `scripts/simulacao/{fixtures,dubles,emissao,metricas}.py`;
  - painel: `lib/types.ts`, `lib/formatoPrograma.ts`, `components/EditarProgramaForm.tsx`,
    `components/live/ProximosBlocosPanel.tsx`, `hooks/useLiveEngine.ts`;
  - benchmark: `docs/benchmarks/2026-11-06-formatos/casos.json`.
- Testes: cerca de 90 a 120 novos (backend), 10 a 15 no painel, 6 goldens novos e 3 regravados.
- 10 commits mais o passo 0.

PRONTA PARA IMPLEMENTAR
