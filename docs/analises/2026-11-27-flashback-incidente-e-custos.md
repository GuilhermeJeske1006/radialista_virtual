# Flashback do Meio-Dia (27/11/2026): incidente de créditos e custos

Consulta em 27/11/2026 ~13h35 BRT, produção OVH (somente leitura: SELECTs em transação read-only e `docker compose logs`). Conta 1, programa 3, Rick Vallejo. Análise de código por subagente (somente leitura).

## 1. O que aconteceu hoje

| Hora (BRT) | Fato | Fonte |
|---|---|---|
| 11:58 | Pré-preparo inicia; abertura confirmada 12:00 | `as_run_eventos`, `blocos_reproduzidos` |
| 12:00–12:27 | Programa normal: 5 músicas (A-ha, Al Green, Roupa Nova, Stevie B, Pat Benatar), 4 comentários, 2 chamadas de ouvinte | idem |
| ~12:26 | Anthropic: `Your credit balance is too low` → backend converte em 503 "falta de créditos no provedor" | logs, `llm_saldo_insuficiente` |
| 12:27–13:16+ | Nenhuma fala nem música. Só vinhetas em loop (25), incluindo "Meio-dia em ponto!" às 13h | `as_run_eventos` |

Volume de chamadas nas 15h–16h UTC: **391 chamadas Anthropic com erro 400** (sem backoff), 124 buscas YouTube OK + **~600 respostas 429** (quota diária de 10 000 unidades estourada), **504 erros do yt-dlp** ("Sign in to confirm you're not a bot").

Por que só vinheta: o painel retenta `/proxima` a cada 5–30 s (~100+/h); cada tentativa busca música/YouTube/Spotify antes do LLM; no 503 o painel cai em `/reserva`, que devolve sempre a vinheta de passagem mais nova, sem rodízio e sem filtro de horário. `pecas_reserva` do programa 3 está vazio.

## 2. Qualidade do que foi ao ar (12:00–12:27)

- 7 de 11 falas medidas passaram do teto de 30 s (comentários de 35,7–37,8 s; abertura 31,6 s; chamada 33,8 s). Melhor que o 26/11 (27 de 48 acima), mas o teto de 30 s ainda é violado em todo comentário.
- Blocos 101 (chamada) e 103 (música/Depeche Mode) preparados 12:00–12:01 **nunca tocaram** (`interrompido`, `preparo_expirado` às 12:41). O painel descartou o pré-preparo após "Take on Me" não iniciar no player (`nao_iniciou`) e regenerou. 2 de ~13 gerações (Opus + TTS) pagas e descartadas.
- Título com entidade HTML: `Al Green - Let&#39;s Stay Together` (não desescapado). Faixa sem artista: `I Wanna Be the One`.
- Programa 3 **ainda no formato `padrao`** (`perfil_programacao`, `estrutura_blocos` antigo, `pecas_reserva` = 0). O formato flashback (repertório curado de 36 obras, sem busca/LLM de gênero) **não está aplicado em prod**. Evidência extra: 141 `live_musica_fora_do_genero` hoje, 56 deles do mesmo vídeo lixo ("A história da melhor música brasileira…") vindo da busca genérica.
- Mesmo com créditos, a entrada ainda tinha falhas: 139 `Falha ao classificar genero` por hora (classificador falha fechado), `Falha ao escolher faixa pelo contexto`, `ia_fila_prazo_excedido` no pool Haiku.

## 3. Custos: batem?

**Não há como conferir pelo banco.** `usos_ia` = 0 linhas, `tarifas_ia` = 0 linhas, `faturas_consumo` = 0. Conta 1 é `cobranca_isenta=true`: `consumo_ia.reservar` retorna sem registrar (`consumo_ia.py:13-14`) e a medição está desligada por padrão. `contas_consumo` tem ciclo vencido em 14/11 (sem efeito enquanto isenta). Custo real só aparece nos consoles Anthropic/ElevenLabs.

Estimativa do código (preços públicos 11/2026; TTS conforme `settings.py`, confirmar com fatura):

| Cenário | US$/h | US$/dia (2 h) | US$/mês (22 dias) |
|---|---:|---:|---:|
| Flashback configurado, baixo | 1,3 | 2,6 | ~58 |
| Flashback configurado, base | 2,5 | 4,9–6,9 | 109–150 |
| Flashback configurado, alto | 8,4 | 16,8 | ~370 |
| Produção atual (`padrao`, dados 26/11) | ~3,2 | ~6,5 | ~140 |

Composição: Opus 5 em ~20 blocos/h × ~10 mil tokens de entrada ≈ US$ 0,054 por chamada; entrada = ~93% do custo de LLM. Haiku < US$ 0,03/h no flashback. TTS US$ 0,46–1,20/h a US$ 0,10 por mil caracteres.

Medição/preço (quando ligada): fórmula `economia.py:118` e tarifas de referência batem com o preço público; retentativas usam uma reserva só; hit de cache TTS não cobra. Problemas:

1. Scribe do ramp (`audio_analysis.py:326`) sem medição; modelo `scribe_v2` não aceito pelo endpoint de tarifas (`consumo_router.py:158,172`, só `scribe_v1`).
2. Admissão mede entrada em **bytes** do JSON contra teto de 40 000 **tokens**/min (`economia.py:19-34`, `settings.py:79`): balde esvazia 3–4× rápido, chamadas grandes são recusadas.
3. Reserva superdimensionada (~2,35× entrada) pode dar 402 precoce.
4. Timeout/stream interrompido vira custo 0 (`falhar`), mas o provedor pode ter cobrado.
5. Coeficientes de cache fixos (0,1 / 1,25); errados para Opus/Sonnet 5.5 ou TTL 1 h.
6. Trocar de modelo exige tarifa em `ia_tarifas_llm` (503 mesmo com medição desligada) e ajuste de `thinking` (Opus 5.5 rejeita `disabled`).
7. Unidade `character-cost` do TTS a conferir (possível subcontagem 2× em Flash/Turbo).
8. Ligar medição com `tarifas_ia` vazia derruba toda geração de contas não isentas (503).

### Custo real medido (log `llm_consumo`, 11:55–12:27 BRT, antes do saldo acabar)

O log `llm_consumo` registra tokens e USD por chamada mesmo na conta isenta, então há custo real nos logs (não no banco):

| Modelo | Chamadas | Entrada (tokens) | Saída (tokens) | USD |
|---|---:|---:|---:|---:|
| claude-opus-5 | 16 | 175 258 | 3 839 | 0,972 |
| claude-haiku-4-5 | 47 | 174 456 | 4 653 | 0,318 |
| **Total LLM** | 63 | 349 714 | 8 492 | **1,29 (≈ US$ 2,4/h)** |

Opus: ~11 mil tokens de entrada por chamada, ~1,45 chamada por bloco falado. Haiku pesa 25% do LLM (classificação de gênero, escolha de faixa, notícias) porque o programa ainda está no formato `padrao`; o formato flashback tira quase tudo isso. TTS vem por fora (ElevenLabs), então o custo total real fica acima de US$ 2,4/h, coerente com a faixa base da estimativa.

## 4. Melhorias propostas (ordem de prioridade)

**A. Fazer agora (ops, sem código)**
1. Recarregar créditos Anthropic e **ligar recarga automática + alerta de saldo** no Console.
2. **Rotacionar a chave da YouTube Data API** (aparece em URL nos logs do httpx e vai ao Sentry) e restringi-la à API e ao IP do VPS.
3. Aplicar `python -m app.live.configurar_flashback --account-id 1 --programa-id 3` (prévia) e `--aplicar` fora do horário do programa (recusa com player ativo, faz backup). Tira Spotify, gênero, citadas, busca web e comentário extra.

**B. Código: resiliência**
4. Disjuntor Redis em `criar_mensagem` para crédito/401/403/limite (TTL 2→15 min), um log por transição, `notificar_admins` + regra Sentry em `llm_saldo_insuficiente`. Corta 100–200 chamadas/h inúteis.
5. Modo degradado em `/proxima` com LLM fora: música com anúncio por modelo de texto ou só música (`_resposta_so_musica`), pular comentário/chamada, usar `pecas_reserva`; registrar música como tocada só depois de montar a resposta.
6. `/reserva` com rodízio (contador Redis) e excluindo textos com hora; banner no painel para `ia_indisponivel`.
7. Classificador de gênero: não falhar fechado para repertório aprovado; teto de 2 resoluções novas por bloco.
8. YouTube: 1 busca por resolução em vez de 2 (`music.py:622-623`, −50% cota); cache negativo (`sem_correspondencia`, 7 d) e de 403/429; disjuntor até meia-noite PT; **pré-resolver offline as 36 faixas de `RESERVA`** (video_id, duração, cortes, início do vocal gravados em `Musica`; ~7 300 unidades uma vez).
9. yt-dlp bloqueado por IP de datacenter: o recurso de cortes/ramp/fala-sobre-intro hoje não funciona em prod. Calcular offline em IP residencial para o repertório curado; disjuntor (3 erros de bot → 1 h) e TTL de falha 6–24 h; atualizar yt-dlp (`2025.6.9`) e avaliar PO token.
10. Mascarar `key=` nos logs (`logging.getLogger("httpx").setLevel(WARNING)` + filtro, `before_send` no Sentry) ou usar header `X-goog-api-key`.
11. Pré-preparo: descartar só blocos que citam a faixa que falhou; não preparar 2 à frente com disjuntor aberto.
12. Desescapar entidades HTML em títulos; não cachear "" por 30 dias quando o contexto da música falha.

**C. Código: custo**
13. Anúncio de música e identificação sem LLM no flashback (modelo de texto / pool offline): ~75% das falas, **−US$ 1,0–1,1/h (~45%)**; resolve anúncios longos.
14. Prompt caching real: mover hora/rotações/contagem para o fim do prompt (prefixo comum hoje só 594 caracteres); dois blocos de system com `cache_control` no estático; só então ligar `LLM_PROMPT_CACHE`. −55–65% da entrada restante. Passar por `avaliar-locucao`.
15. Passar `palavras_max` explícito na 1ª chamada (−10–25% das reescritas); teto de comentário de 30 s está sendo violado.
16. Haiku 5.5 nos classificadores (−90% deles, com `thinking` desabilitado explícito); Opus 5.5 nas falas (−20%) depois de escuta/juiz.
17. TTS: não cachear no Redis falas do LLM (hit ~1%, Redis 256 MB `allkeys-lru` expulsa estado); cachear só textos fixos em S3; tirar `texto_anterior` da chave.
18. Ligar medição de custo interno também para contas isentas (registrar sem cobrar) e semear `tarifas_ia` (`publicar_tarifas_referencia.py`), para ter custo real no banco.

## 5. Limites

- Sem escuta de áudio. `confirmado` = player reportou fim.
- Logs de prod só desde 26/11 21:37 UTC (reinício); 26/11 do programa vem do relatório anterior.
- Estimativas de custo são do código/preço público, não de fatura.
- Itens 13–17 têm percentuais estimados; confirmar com `cache_read_input_tokens` e log `llm_consumo`.

## 6. Custo real × promessa comercial (verificação de 27/11)

**Promessa** (landing `config.js`/`index.html`, `backend/app/billing/combinacoes.py`, `docs/simulacao-plano-consumo.md`): Opus + ElevenLabs v4 ≈ **R$ 8,35 por hora de programa**, a fatura "segue o uso medido". A conta reproduz-se assim: 6 min de fala nova por hora = 12 gerações/h de 1 500 entrada / 150 saída tokens, 36 classificações Haiku de 500/32, 6 000 caracteres de voz, câmbio R$ 5,50, acréscimo de 100%.

Recalculado: Opus US$ 0,135 + Haiku US$ 0,024 + TTS US$ 0,60 = US$ 0,76/h = R$ 4,17/h de custo → R$ 8,35/h cobrado. A conta fecha.

**Medido no Flashback** (programa 3, conta 1; `blocos_reproduzidos` e log `llm_consumo`):

| Variável | Prometido | Medido | Razão |
|---|---:|---:|---:|
| Blocos falados por hora | 12 | ~24 (26/11: 48 em 2 h) | 2,0× |
| Caracteres de voz por hora | 6 000 | 12 700 (26/11) a 14 700 (27/11) | 2,1–2,5× |
| Minutos de fala nova por hora | 6 | ~12,5 | 2,1× |
| Tokens de entrada por chamada Opus | 1 500 | ~11 000 | 7,3× |
| Custo por chamada Opus | US$ 0,011 | US$ 0,061 | 5,4× |
| Chamadas Haiku por hora | 36 (500 tokens) | ~88 (3 700 tokens) | 2,4× em número, 7× em tamanho |

| Custo por hora | Prometido (US$) | Medido (US$) | Razão |
|---|---:|---:|---:|
| Opus | 0,135 | 1,82 | 13× |
| Haiku | 0,024 | 0,60 | 25× |
| Voz (US$ 0,10 por mil caracteres) | 0,60 | 1,27–1,47 | 2,1–2,5× |
| **Total** | **0,76** | **≈ 3,7–3,9** | **≈ 5×** |

Em reais, ≈ R$ 20–21/h de custo; **cobrado a 2× seria ≈ R$ 41–43/h contra os R$ 8,35 prometidos**. Em 44 h/mês (2 h × 22 dias), ≈ R$ 1 800–1 900 de uso contra ≈ R$ 370 estimados no simulador do site. A conta 1 é isenta, então hoje nada é cobrado; o desvio é de margem e de expectativa, não de fatura emitida.

Origem do desvio, em ordem de peso: (1) prompt do Opus 7× maior que o simulado (contexto de programa, histórico, regras; sem cache); (2) formato `padrao` ainda ativo no programa 3, que paga classificadores Haiku que o flashback dispensa; (3) o dobro da fala nova prevista (formato musical com fala entre quase todas as faixas); (4) 15% dos blocos gerados são descartados (2 de 13 hoje) e custam LLM + voz; (5) reescritas por teto de tempo (1,45 chamada por bloco).

Limites: amostra pequena (32 min de LLM medidos em 27/11; 3 ocorrências de blocos), sem fatura da ElevenLabs para confirmar o preço por caractere, e o Haiku de hoje ainda inclui o formato `padrao`. A ordem de grandeza (~5×) é robusta; o valor exato não.

**Caminho para aproximar da promessa** (sem trocar modelo): flashback configurado (tira o Haiku, ~US$ 0,6/h); anúncios e identificações sem LLM (−70–75% das chamadas Opus); prompt caching real (entrada −55–65%); menos descarte de pré-preparo. Estimativa otimista: ~US$ 1,0–1,3/h (R$ 5,5–7/h de custo, R$ 11–14/h cobrado) — ainda acima de R$ 8,35, porque a voz com 12 min de fala por hora já consome US$ 1,0+. Fechar a conta exige uma de duas decisões de negócio: reduzir a fala para ~6 min/h, ou **revisar o preço estimado do site** para programas musicais com fala frequente (faixa realista hoje: R$ 25–45/h; após as otimizações, R$ 12–20/h).
