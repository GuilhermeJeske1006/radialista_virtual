---
name: avaliar-locucao
description: Avalia falas geradas pelo ao vivo da Locufy (as_run.json da simulação) pelas dimensões da pesquisa de rádio — checagens automáticas e julgamento por rubrica, comparando antes e depois de uma mudança.
argument-hint: [as_run-antes.json] [as_run-depois.json]
---

# Avaliar locução

Use junto com a skill `referencia-radio` (regras) e `llm-evaluation` (método de juiz).

## Entrada

Um ou dois arquivos `as_run.json` gerados por `backend/scripts/simular_hora.py`. Cada evento tem
`inicio`, `fim`, `tipo`, `formato`, `texto`, `duracao_prevista_s`, `duracao_medida_s` (se houver),
`orcamento_s`, `musica_anunciada`, `musica_tocada`, `promessas_abertas`, `promessas_fechadas`,
`pedido_id`, `pedido_estado`.

## 1. Checagens automáticas (sem LLM, sempre)

Calcule com um script Python em pasta temporária fora do repositório e registre os números:

| Métrica | Regra |
|---|---|
| `fora_orcamento_pct` | falas com duração > máximo do orçamento |
| `estouro_max_pct` | maior razão duração / máximo |
| `atraso_hard_time_s` | maior atraso em eventos `hard_time` |
| `anuncio_sem_confirmacao` | música citada ≠ `musica_tocada` do próximo evento |
| `promessa_vencida` | promessa aberta sem fechamento nem contingência até o prazo |
| `pedido_indevido` | fala "toca agora"/nome de ouvinte com pedido fora de `selecionado` |
| `aviso_oralidade` | contagem do verificador `app/live/oralidade.py` (se existir) |
| `abertura_repetida` | mesma estrutura de abertura em 3 falas seguidas |
| `silencio_s` | soma de lacunas entre `fim` e próximo `inicio` |

Qualquer valor > 0 em `anuncio_sem_confirmacao`, `promessa_vencida` ou `pedido_indevido` reprova,
independentemente das notas.

## 2. Rubrica (julgamento, notas 1–5)

Avalie cada fala de tipo diferente de `musica` (amostra de até 30 por arquivo, estratificada por
tipo). Leia a fala em voz alta mentalmente, no contexto do evento anterior e do seguinte.

| Dimensão | 5 | 1 |
|---|---|---|
| Clareza | ideia principal entendida em uma escuta | precisa reler |
| Utilidade | informa, entretém, conecta ou orienta | só preenche tempo |
| Coerência | combina com formato e horário | quebra a promessa do programa |
| Continuidade | liga o que passou ao próximo evento correto | desconexa ou errada |
| Naturalidade | intenção muda de forma compreensível | padrão mecânico ou teatral |
| Precisão | só fatos com fonte e válidos | inventa ou infere |

Regras do juiz:
- Avalie o texto, não o modelo que gerou; não premie fala longa.
- Para comparar antes x depois, avalie as amostras misturadas e sem saber a origem (embaralhe e
  só depois revele qual é qual).
- Cite o trecho que justifica cada nota 1 ou 2.

## 3. Saída

Grave em markdown:
1. Tabela de métricas automáticas (antes, depois, diferença).
2. Média e mediana por dimensão (antes, depois).
3. Até 5 piores falas com motivo e sugestão de correção (sugestão original, sem imitar radialista).
4. Veredito: `APROVADO` (nenhuma reprovação automática e nenhuma dimensão abaixo do antes) ou
   `REPROVADO` com a lista do que bloqueou.
