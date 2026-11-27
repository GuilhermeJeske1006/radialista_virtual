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
