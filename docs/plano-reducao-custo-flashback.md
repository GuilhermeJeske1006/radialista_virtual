# Plano de redução de custo do Flashback sem perder qualidade

> **Versão validada: ver a seção 9.** As seções 1–8 são a análise original; onde os números da seção 9 diferem (A1 já resolve a fala longa, B1 e C1 reduzidos), vale a seção 9.

Base: medição de 27/11/2026 (docs/analises/2026-11-27-flashback-incidente-e-custos.md, seção 6). Valores por hora de programa no ar, em US$.

## 1. Ponto de partida e meta

| Componente | Hoje | Promessa do site |
|---|---:|---:|
| Opus (texto) | 1,82 | 0,135 |
| Haiku (classificadores) | 0,60 | 0,024 |
| Voz (US$ 0,10 por mil caracteres) | 1,27–1,47 | 0,60 |
| **Total** | **≈ 3,8** | **0,76** |

Meta em duas etapas: **≤ 2,1/h** na fase A (sem tocar no prompt) e **≈ 1,2–1,5/h** ao fim da fase C. Os números abaixo são estimativas; cada fase mede de novo antes da seguinte.

Onde o dinheiro está: entrada do Opus é ~93% do custo dele (≈ 11 mil tokens por chamada, sem cache); a voz é o maior item depois dele, e escala com **minutos de fala**, hoje ~12,5 por hora (≈ 21% do ar). A orientação editorial do projeto fala em 8–18% de fala; estamos acima.

## 2. Regra de qualidade (vale para toda alavanca)

1. Cada mudança entra **atrás de flag**, desligada por padrão.
2. Antes de ligar: rodada A/B com a skill `avaliar-locucao` (checagens automáticas e rubrica) em pelo menos 40 blocos antes/depois, mais o simulador `simular_hora.py --formato flashback` para duração e repetição.
3. Escuta humana de uma hora real da versão nova (pendente desde 26/11 também para o ramp).
4. Liga em **um programa por vez**, com a hora do Flashback como piloto; reverte se qualquer indicador de guarda piorar:
   - falas acima do teto de duração (hoje 7 de 11 comentários);
   - taxa de reescrita (hoje 1,45 chamada por bloco);
   - repetição de abertura/estrutura entre blocos consecutivos;
   - fato não sustentado (`restringir_fatos`/validação);
   - sinais de IA na rubrica;
   - blocos descartados (hoje 15%).
5. Nenhuma troca de modelo sem escuta.

## 3. Alavancas

### Fase A, sem risco editorial (1–2 dias)

| # | Alavanca | Economia/h | Risco | Como validar |
|---|---|---:|---|---|
| A0 | **Medir antes de cortar.** Log por bloco com custo (`llm_consumo` + caracteres de voz), tamanho do prompt por seção (system, histórico, fatos, regras, dinâmicos) e contagem de reescritas/descartes; gravar `usos_ia` também para conta isenta (preço zero). Sem isto o ganho das próximas fases não é verificável. | 0 | nenhum | painel/consulta com custo por hora e por bloco |
| A1 | **Aplicar `configurar_flashback` no programa 3** (prévia → `--aplicar`, fora do horário, com backup). Elimina Spotify, escolha/sugestão de faixa por LLM, classificador de gênero, músicas citadas e busca web; passa a usar o repertório curado de 36 obras. | ~0,55 (Haiku) | baixo (decisão editorial já aprovada) | comparar 1 hora com a de hoje; conferir repertório e reserva (`pecas_reserva` deixa de ser vazia) |
| A2 | **Menos descarte e reescrita:** passar `palavras_max` explícito já na primeira chamada e prompt com o teto; descartar no pré-preparo só os blocos que citam a faixa que falhou (hoje descarta tudo); não preparar blocos extras com o provedor degradado. | ~0,3–0,4 | baixo | reescritas/bloco → ~1,1; descartes < 5%; comentários ≤ teto |
| A3 | **Reduzir fala a ≤ 15% do ar (~9 min/h):** fala curta entre faixas em vez de toda faixa; comentário longo só a cada 2–3 faixas; teto de comentário de 30 s realmente aplicado (hoje 35–38 s). Também melhora a qualidade pela referência de rádio (mais música, menos tagarelice). | ~0,4–0,5 (voz) + ~0,3 (menos chamadas Opus) | médio (ritmo do programa muda) | escuta e rubrica; indicador de proporção de fala |

Estimativa ao fim da fase A: Opus ≈ 1,0, Haiku ≈ 0,05, voz ≈ 1,0 → **≈ 2,1/h**.

### Fase B, prompt (3–5 dias; mexe no texto gerado)

| # | Alavanca | Economia/h | Risco | Como validar |
|---|---|---:|---|---|
| B1 | **Prompt caching real.** O prefixo comum hoje é de 594 caracteres porque a hora (HH:MM) e outras linhas variáveis ficam no começo. Mover para o fim hora, rotações, "fala número N", posição no roteiro, memória recente e duração; dividir o `system` em bloco estático (com `cache_control`) e bloco dinâmico; só então ligar `LLM_PROMPT_CACHE`. Blocos a cada 2–4 min ficam dentro do TTL de 5 min. Cuidado: escrita custa 1,25×, leitura 0,1×; sem ordem estável o cache só encarece. | ~0,5 (≈ −55% da entrada restante) | médio-baixo (reordena linhas, não remove regra) | teste automático de prefixo comum ≥ 70% e do conjunto de regras idêntico; A/B de 40 blocos; conferir `cache_read_input_tokens` no log |
| B2 | **Enxugar o prompt de ~11k para ~7k tokens:** auditar por seção (A0), cortar duplicação de regras, limitar histórico de falas anteriores ao necessário, resumir fatos já usados. Nada de remover regra editorial sem teste. | ~0,15–0,25 | médio | mesma rubrica; nenhum aumento de violação de regra |

Estimativa ao fim da fase B: Opus ≈ 0,4 → **≈ 1,45/h**.

### Fase C, estrutura editorial (1 semana; só após escuta)

| # | Alavanca | Economia/h | Risco | Como validar |
|---|---|---:|---|---|
| C1 | **Anúncio de música e identificação sem LLM** (cerca de 75% das falas do flashback): modelo de texto com variações, preenchido com artista, título e hora; pool por tipo gerado offline (Batch API, metade do preço) e revisado; sem repetir a mesma variação em 2 h. Comentários e chamadas de ouvinte continuam no LLM. Flag `FLASHBACK_ANUNCIO_SEM_LLM`. | ~0,2–0,25 (já depois do cache) | **médio-alto** (monotonia; perde contexto da faixa) | escuta às cegas A/B; taxa de repetição de variação; só liga se a nota de naturalidade não cair |
| C2 | **Cache de TTS só para texto fixo** (vinhetas, patrocínio, anúncios padronizados) e fora do Redis para falas de LLM (acerto ~1%; hoje ocupam parte dos 256 MB). Reduz também risco operacional (cache de cota/disjuntor sendo expulso). | pequeno em custo; ganho de estabilidade | baixo | nenhum teste de áudio muda |
| C3 | **Trocas de modelo, uma por vez e com escuta:** classificadores para Haiku 5.5 (`thinking` explícito desligado, tarifa publicada); comentários para Opus 5.5 (−20% de tarifa, leitura de cache ×0,05). Exige corrigir `economia.py` (coeficientes de cache fixos, remoção de `thinking`) e atualizar tarifas. | ~0,1 + 0,05 | médio | rubrica + escuta; só entra se igual ou melhor |

### Transversal

- **Conferir o preço real da voz:** a conta usa US$ 0,10 por mil caracteres; confirmar na fatura da ElevenLabs (unidade `character-cost`, plano por créditos). Se o plano permitir tarifa menor por volume, ganho direto sem mexer em qualidade.
- **Medição fiel:** corrigir os defeitos da seção 3 do relatório (Scribe sem medição, admissão em bytes contra teto em tokens, reservas superdimensionadas, falha vira custo zero, coeficientes de cache fixos) antes de ligar cobrança real.
- **Preço e expectativa (decisão de negócio):** o simulador do site assume 6 min de fala e prompt de 1 500 tokens. Ou aproximar a operação da premissa (fase A3), ou publicar estimativa por perfil de programa (musical com pouca fala, equilibrado, falado). Hoje o realista para o Flashback é R$ 25–45/h cobrado; ao fim da fase C, R$ 12–20/h.

## 4. Resultado esperado (por hora, estimativa)

| Etapa | Opus | Haiku | Voz | Total | Redução |
|---|---:|---:|---:|---:|---:|
| Hoje | 1,82 | 0,60 | 1,40 | 3,8 | |
| Fase A | 1,0 | 0,05 | 1,0 | 2,1 | −45% |
| + Fase B | 0,4 | 0,05 | 1,0 | 1,45 | −62% |
| + Fase C | 0,2 | 0,03 | 1,0 | 1,25 | −67% |

A voz passa a ser ~80% do que sobra. Abaixo de ~US$ 1,2/h só com menos fala por hora (≈ 6–7 min, promessa do site) ou tarifa de voz menor.

## 5. Ordem e portões

1. A0 → A1 → A2 → A3, medindo entre cada passo. Portão: uma hora de escuta + rubrica sem piora.
2. B1 → B2. Portão: A/B de 40 blocos sem regressão nos indicadores de guarda.
3. C1 e C3 só depois de escuta humana; C2 a qualquer momento.
4. Reavaliar custo/h real após cada fase e atualizar este plano e o preço estimado do site.

## 6. Decisões necessárias

1. Aprovar aplicar `configurar_flashback` em produção (A1).
2. Meta de fala por hora (proposta ≤ 15%, ~9 min) e se pode mudar o ritmo do programa (A3).
3. Aceitar anúncios por modelo de texto no flashback, sujeito à escuta (C1).
4. Corrigir o preço estimado do site, ou escolher qual meta de custo defende a promessa de R$ 8,35.

## 7. Troca de modelo de texto (análise de 27/11, preços da tabela pública)

Produção usa `claude-opus-5` ($5/$25 por MTok) nas falas e `claude-haiku-4-5` ($1/$5) nos classificadores. Custo por chamada de fala com ~11 mil tokens de entrada e ~240 de saída (30 chamadas/h):

| Modelo | Preço entrada/saída | Por chamada (sem cache) | Com cache (≈ 65% do prompt estático) | Por hora (30 chamadas) |
|---|---|---:|---:|---:|
| Opus 5 (hoje) | $5 / $25 | $0,061 | — | $1,82 |
| Opus 5.5 | $4 / $20 (leitura de cache $0,20) | $0,049 | $0,022 | $1,46 → $0,66 |
| Sonnet 5.5 | $2 / $10 (leitura $0,10) | $0,024 | $0,011 | $0,73 → $0,33 |
| Haiku 5.5 | $0,10 / $0,50 | $0,0012 | — | $0,04 |

Evidência de qualidade existente (docs/benchmarks/2026-09-25-combinacoes, uma geração por caso, juiz Opus 5): Opus 5 aprovou 5/6 (fidelidade 5,00; naturalidade 4,83); Sonnet 5 aprovou 5–6/6 (fidelidade 4,83; naturalidade 4,67); Haiku 4.5 aprovou 3–4/6, acrescentou fato não informado e passou do limite de palavras. Nenhum dos modelos 5.5 foi medido nesta tarefa.

Recomendação (hipótese a validar por A/B antes de ligar):
1. Classificadores: Haiku 4.5 → **Haiku 5.5** (≈ −90%), com `thinking` explícito desligado e saída estruturada.
2. Falas curtas baseadas em dados dados no prompt (anúncio de música, identificação, chamada de ouvinte): **Sonnet 5.5**. Mantém variação de texto, ao contrário de modelo fixo, por ~40% do custo do Opus 5.5.
3. Comentários com curiosidade/história: **Opus 5.5** (mesma família, −20% de tarifa, leitura de cache a 5%), sem risco de qualidade esperado.
4. Haiku 5.5 para texto criativo só como experimento: o Haiku 4.5 inventou fato; no flashback fato inventado é o pior defeito.

Mix de 75% Sonnet 5.5 + 25% Opus 5.5: ≈ US$ 0,92/h sem cache, ≈ 0,42 com cache (hoje 1,82).

Cuidados de implementação: Opus 5.5 não aceita `thinking: disabled` (usar esforço `low`, medir tokens de raciocínio, que contam como saída); Sonnet 5.5 desliga raciocínio com `{"type": "between_tools"}` e esforço ≤ `high`; ambos rejeitam `tool_choice` forçado e `temperature`; `economia.criar_mensagem` exige tarifa em `ia_tarifas_llm` e remove `thinking` só para nomes com "haiku"; prompts escritos para modelos anteriores costumam ficar prescritivos demais; tokenizador do Haiku 5.5 conta mais tokens que o 4.5.

Protocolo: 3 candidatas (Opus 5.5, Sonnet 5.5, mix) × 40 blocos flashback com entradas fixas, juiz e checagens automáticas de `avaliar-locucao`, escuta às cegas de uma hora; custo estimado da rodada de API: poucos dólares (a confirmar antes de executar).

## 8. LLM de outro provedor (pesquisa de 27/11)

Preços vêm de agregadores e páginas dos provedores vistos por busca; **conflitam entre fontes e não foram confirmados nas páginas oficiais**. Tratar como ordem de grandeza e conferir antes de decidir. Mesmo perfil de chamada: 11 mil tokens de entrada, 240 de saída, 30 chamadas/h.

| Modelo | Preço por MTok (entrada/saída) | Por hora (sem cache) | Com cache |
|---|---|---:|---:|
| Claude Sonnet 5.5 (referência) | $2 / $10 | 0,73 | 0,33 |
| GPT-5 | $1,25 / $10 (cache $0,125) | 0,48 | 0,25 |
| GPT-5 mini | $0,25 / $2 | 0,10 | — |
| Gemini 3 Flash | $0,50 / $3 (cache $0,05) | 0,19 | 0,09 |
| Gemini 3.1 Pro | $2 / $12 | 0,75 | — |
| Sabiá-4 (Maritaca, pt-BR) | R$ 5 / R$ 20 (≈ $0,91 / $3,64) | 0,33 | — |
| Sabiazinho-4 | R$ 1 / R$ 4 | 0,07 | — |
| Mistral Large 4 | $0,70 / $2,10 | 0,25 | — |
| DeepSeek Flash | $0,15–0,30 / $0,60–1,20 | 0,05–0,11 | — |

Ressalvas de custo: GPT-5 e Gemini 3 Flash raciocinam; os tokens de raciocínio são cobrados como saída e podem dobrar o custo real; Gemini cobra armazenamento de cache por hora; busca web é paga à parte nos dois (hoje `noticias.py` usa a ferramenta `web_search` da Anthropic).

Qualidade: não achei benchmark comparável de escrita criativa em português brasileiro para estes modelos, nem taxa de alucinação. O único benchmark específico de pt-BR achado (relatório do Sabiá-4, CAPITU) não traz os números dos concorrentes nas buscas. A Artificial Analysis dá Gemini 3 Flash (raciocínio) 38 e GPT-5 mini 31, contra 42 a 53 do Sonnet 5 (outra geração, outra configuração; não é comparação direta). Para este produto (fala curta, regionalismo gaúcho, fato que não pode ser inventado, regras de oralidade longas no prompt), a qualidade só se decide com eval próprio.

Esforço e risco de integração:
- Isolamento bom: SDK da Anthropic só em 3 arquivos (`llm/client.py`, `llm/economia.py`, `llm/noticias.py`).
- Mas medição, tarifas (`ia_tarifas_llm`), reservas, cache de prompt, parâmetros de raciocínio e a busca web são específicos da Anthropic; trocar exige camada de provedor, tarifas por provedor e novo teste das 2 800 verificações de prompt.
- Prompts de ~19 mil caracteres foram afinados em Claude; migrar exige nova rodada de `avaliar-locucao` e escuta.
- LGPD: a política de privacidade lista Anthropic e ElevenLabs como operadores; um novo provedor exige atualizar a política, avaliar transferência internacional e contrato de tratamento de dados.
- DeepSeek e modelos hospedados na China: risco adicional de dados e latência a partir do Brasil.

Conta do benefício: com o plano Anthropic (Sonnet 5.5 + cache ≈ US$ 0,42/h), mudar tudo para Gemini 3 Flash economizaria no máximo ≈ US$ 0,2–0,3/h, ou ≈ US$ 10 por mês por programa de 2 h/dia (22 dias), contra ≈ US$ 62/mês só de voz. Para pagar ~5 dias de engenharia mais eval e escuta (ordem de R$ 8 mil, estimativa), seriam necessários cerca de 150 programas-mês de economia, isto é, 12 programas por um ano.

Conclusão: **não trocar de provedor para reduzir custo agora**. Duas exceções que valem estudo:
1. **Segundo provedor como contingência.** O incidente de 27/11 (50 min de vinheta com saldo zerado) pesa mais do que a diferença de preço. Um modelo barato (Gemini 3 Flash, GPT-5 mini ou Sabiá-4) só entra quando o disjuntor da Anthropic está aberto, para falas simples. Custo desprezível; exige a mesma camada de provedor e a atualização da política de privacidade.
2. **Classificadores em modelo pequeno de outro provedor** não compensam: o Haiku 5.5 ($0,10/$0,50) já custa o mesmo que GPT-5 nano ou Gemini Flash-Lite, sem nova integração.

Se a Locufy chegar a dezenas de programas, repetir esta conta; Sabiá-4 (pt-BR nativo, inferência no Brasil, sem transferência internacional) e Gemini 3 Flash são os candidatos a avaliar com eval próprio.


## 9. Plano validado (27/11) 

Validação feita contra o código e a produção (somente leitura), com a simulação gratuita `simular_hora.py --formato flashback` para medir o prompt.

### 9.1 O que a validação confirmou, corrigiu ou deixou aberto

| Premissa | Resultado | Evidência |
|---|---|---|
| Produção roda o formato `padrao`, não o flashback | **Confirmado** | `programas`: `perfil_programacao=padrao`, `pecas_reserva`=0, `estrutura_blocos` antiga |
| O formato flashback já limita a fala | **Descoberta: muda o plano** | `formatos.py` `FLASHBACK`: anúncio de música 5/10/15 s, comentário e chamada 15/22/30 s, identificação 3/6/8 s, `aplica_orcamento=True`, `faixa_fala_pct=(8, 18)`. Em produção os anúncios duram 21–28 s e os comentários 36–38 s: esses limites hoje **não estão em vigor** |
| Fala prevista com o flashback | ≈ 6,5 min/h | 8 anúncios × 10 s + comentário 22 s + identificação 6 s + chamada 22 s ≈ 130 s por ciclo de ~35 min. Hoje 12,5 min/h. Fica na premissa do site (6 min) e dentro da faixa editorial (8–18%) |
| Prompt tem ~80% de conteúdo estático | **Confirmado** | simulação flashback: 79–82% dos caracteres idênticos entre prompts; só 14 linhas dinâmicas, a primeira no caractere 483 (prefixo comum 595 de ~18 mil) |
| Cache de prompt hoje não acerta | **Confirmado** | idem; a hora (HH:MM) é a primeira linha dinâmica |
| Entrada de ~11 mil tokens por chamada | **Parcial** | simulação do flashback: ≈ 18,5 mil caracteres de system + 0,9 mil de mensagem ≈ 6–7 mil tokens (3,3 caracteres/token, estimativa). Os dados da rádio no prompt são minúsculos (bíblia 91 caracteres, conhecimento local 240); 56% do system são regras fixas no código (`_abertura_do_system`, 10,4 mil caracteres) e 18% `_REGRAS_GERAIS`. Os ~4–5 mil tokens restantes de produção devem vir das seções de jornalismo/dados/música do formato `padrao` (vazias na simulação) e do histórico das 6 últimas falas (~1 mil tokens). **A medir** depois do A1 |
| Pré-preparo descarta tudo quando a faixa falha | **Confirmado** | `useLiveEngine.ts:1351` chama `descartarPreparo()`, que cancela a fila inteira (antecedência 2 → até 2 gerações desperdiçadas por falha) |
| Haiku pesa 25% do LLM por causa do `padrao` | **Confirmado** (por inferência) | flashback desliga busca, gênero, sugestão e citadas em `configurar_flashback.py` (`pode_pesquisar=False`); ainda a confirmar nos logs após aplicar |
| Custo real ≈ 5× o prometido | **Confirmado** | seção 6 |
| Preço por mil caracteres da voz | **Aberto** | premissa US$ 0,10; confirmar na fatura da ElevenLabs |
| Tamanho mínimo de prefixo para cache do Opus/Sonnet 5.5 | **Aberto** | o prefixo estático ≈ 4,8 mil tokens; confirmar o mínimo cacheável do modelo e `cache_read_input_tokens` no primeiro dia |

### 9.2 Correções ao plano original

- **A1 vale mais do que o estimado.** Aplicar `configurar_flashback` coloca em vigor o orçamento por bloco (anúncio ≤ 15 s, comentário ≤ 30 s) e a faixa de fala 8–18%. Isso entrega quase tudo de A2 (teto de palavras na primeira chamada, menos reescrita) e de A3 (fala de 12,5 para ~6,5 min/h). **A3 deixa de ser um item separado**: vira verificação após A1.
- **C1 (anúncio sem LLM) perde prioridade.** Com A1 os anúncios já ficam em 10 s, e Sonnet 5.5 nesses blocos custa ~US$ 0,01 por chamada, sem o risco de monotonia dos modelos de texto fixo. C1 só se justifica se a escuta mostrar que Sonnet 5.5 não serve.
- **Voz domina o que sobra** (≈ US$ 0,65/h). O próximo ganho de voz só vem de tarifa menor ou de menos fala.

### 9.3 Estimativa revisada (US$ por hora; ordem de grandeza, a medir em cada passo)

| Etapa | Opus | Haiku | Voz | Total | vs hoje |
|---|---:|---:|---:|---:|---:|
| Hoje (medido) | 1,82 | 0,60 | 1,40 | 3,8 | |
| A1: flashback aplicado (≈ 22 chamadas/h, prompt 6,5–9 mil tokens, fala 6,5 min/h) | 0,95 | 0,05 | 0,65 | **≈ 1,65** (1,5–1,8) | −57% |
| + B1/B2: cache de prompt e prompt enxuto | 0,28 | 0,05 | 0,65 | ≈ 0,98 | −74% |
| + C3: Sonnet 5.5 (75%) + Opus 5.5 (25%) nas falas, Haiku 5.5 nos classificadores | 0,14 | 0,03 | 0,65 | **≈ 0,82** | −78% |

Em reais, ≈ R$ 4,5 por hora de custo, ≈ R$ 9–11 por hora cobrado a 2× (o site promete R$ 8,35; hoje seria R$ 41–43). A promessa passa a ficar a +10–30% em vez de 5×.

### 9.4 Plano final, em ordem de execução

| Passo | O que fazer | Esforço | Economia/h | Portão de qualidade (ligar só se passar) | Reversão |
|---|---|---|---:|---|---|
| 0 | Publicar a branch `fix/resiliencia-custos-flashback` (disjuntores, chave fora dos logs, 1 busca de YouTube) e recarregar crédito Anthropic com recarga automática | feito em código; push e deploy dependem de você | evita nova queda | suíte verde (2 810 testes) | reverter o deploy |
| 0b | **Rotacionar a chave do YouTube** e restringi-la ao IP do VPS | 10 min, manual | — | — | — |
| 1 | A0: log por bloco com custo, tokens de entrada por seção e contagem de reescritas/descartes; gravar `usos_ia` para conta isenta | 0,5–1 dia | 0 | — | — |
| 2 | **A1:** `configurar_flashback --programa-id 3` em prévia, depois `--aplicar` fora do horário (12–14h), com backup | 30 min | ≈ 2,1 | uma hora de escuta; fala ≤ 18% do ar; anúncios ≤ 15 s e comentários ≤ 30 s; zero fato inventado; repetição de estrutura não piora | restaurar o backup gravado em `config_backups/` |
| 3 | Medir tokens reais pós-A1 (log do passo 1) e fechar a lacuna entre 6–7 mil e 11 mil tokens | 0,5 dia | — | decide o tamanho de B2 | — |
| 4 | **B1:** reordenar o prompt (linhas dinâmicas no fim), dividir `system` em bloco estático com `cache_control` e dinâmico, só então ligar `LLM_PROMPT_CACHE` | 2–3 dias | ≈ 0,6 | teste automático: prefixo ≥ 70% e conjunto de regras idêntico; A/B de 40 blocos com `avaliar-locucao`; `cache_read_input_tokens` > 0 no log | flag desligada |
| 5 | **B2:** enxugar o prompt (regras duplicadas em `_abertura_do_system` e `_REGRAS_GERAIS`, histórico das 6 falas) | 2–3 dias | ≈ 0,05–0,1 | mesmo A/B; nenhuma regra editorial removida sem teste | flag/rollback do commit |
| 6 | Corrigir pré-preparo: descartar só blocos que citam a faixa que falhou; pular pré-aquecimento com painel ativo | 1 dia | ≈ 0,05–0,1 | testes vitest; descartes < 5% | commit isolado |
| 7 | **C3:** rodada A/B Opus 5.5 × Sonnet 5.5 × mix e Haiku 5.5 nos classificadores; ajustar `economia.py` (thinking por modelo, coeficientes de cache, tarifas) | 2–3 dias + rodada de API (alguns dólares, aprovação prévia) | ≈ 0,15–0,2 | juiz + checagens + escuta às cegas; nota de naturalidade e fidelidade ≥ Opus atual | trocar o modelo por configuração |
| 8 | Camada de provedor com segundo LLM só como contingência (disjuntor aberto) | 3–5 dias, opcional | evita queda | política de privacidade atualizada antes | desligar flag |
| 9 | Conferir fatura da ElevenLabs (preço por caractere, plano por volume); corrigir defeitos de medição (Scribe, bytes/tokens, reservas) antes de cobrar | 1–2 dias | incerta | — | — |
| 10 | Atualizar a estimativa do site com a medição final (por perfil de programa) | 0,5 dia | — | aprovação sua | — |

### 9.5 Regra de qualidade e parada

Cada passo roda em uma hora real do Flashback, com a skill `avaliar-locucao` sobre os blocos e escuta humana. Parar e reverter se: falas acima do teto > 10%, taxa de reescrita > 1,3 chamada por bloco, repetição de abertura/estrutura entre blocos, qualquer fato sem fonte, nota de naturalidade abaixo da linha de base, ou descartes de pré-preparo > 5%.

### 9.6 O que continua não validado

Qualidade de Sonnet 5.5, Opus 5.5 e Haiku 5.5 nesta tarefa (sem medição); tokens reais por chamada após o A1; preço real da voz; mínimo cacheável dos modelos; efeito do cache em blocos com tipos de fala diferentes (linhas específicas por tipo ficam no bloco estático ou dinâmico? a decidir no B1).
