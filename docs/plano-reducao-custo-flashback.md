# Plano de redução de custo do Flashback sem perder qualidade

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
