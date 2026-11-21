# F10 — Direção de som (status parcial)

Branch `melhoria/f10-direcao-som`, base `melhoria/f9-glossario`.

## Itens do plano

| Item | Estado | Motivo |
|---|---|---|
| 1. Notícia grave nunca usa trilha ou sweeper de promoção | **não feito, precisa de decisão** | A inserção de vinhetas em `app/vinhetas/estrutura.py` é por índice e não conhece a natureza do bloco. Falta dizer quais vinhetas são "promoção" (campo de categoria na `BibliotecaAudioItem`?) e se a regra é proibir adjacência ou só o sweeper. |
| 1b. Silêncio entre blocos por natureza | **já existe** | `_intervalo_transicao_ms` e `_pausa_antes_ms` em `app/live/router.py` distinguem notícia, animada, normal e música |
| 2. Fala sobre a introdução (ramp) só com início de vocal | **conceito ausente** | Não há "ramp" no código. `app/live/audio_analysis.py` acha início seguro e fim de silêncio, mas não marca início de vocal. Precisa de definição: a fala entra antes da música (regra atual) ou sobre a introdução com início de vocal medido? |
| 3. Loudness integrada por segmento (fala, vinheta, música) | **feito (módulo)** | `app/postprod/loudness.py`: `medir_loudness_lufs` (ffmpeg `ebur128`) e `diferencas_entre_segmentos`. Sem alvo universal. Não integrado ao `as_run.json` ainda. |

## Decisões pedidas

1. Item 1: quais vinhetas contam como promoção, e a regra é proibir adjacência com notícia ou só não usar sweeper?
2. Item 2: o "ramp" é fala sobre a introdução da música com início de vocal medido, ou basta a regra atual (falar antes)?
3. Item 3: onde o relatório de loudness entra: no `as_run.json` da simulação (fixtures de áudio) ou só no pós-produção?
