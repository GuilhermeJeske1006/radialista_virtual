# Entrega da voz: por que o locutor às vezes fala estranho

Executado em 23/11/2026 com a API real (ElevenLabs TTS + Scribe v2). Pergunta: o texto gerado está
bom, mas a locução às vezes sai estranha. O que, no caminho entre o texto e o áudio, causa isso?

**Conclusão:** o que o ouvinte percebe como estranho (entonação, pronúncia e ritmo na fala inteira) é
o eleven_v3 com Paulo e Yasmin. Na escuta às cegas o v4 com as mesmas vozes teve nota 4,17 contra
2,17 do v3, e o v3 com Diego/Raquel teve 4,00 (rodada 2). O v4 virou o padrão.

**Resultado das métricas:** a direção vocal que o LLM escreve na fala causava defeitos pontuais. O prompt
pedia `[calm]` na entrada e `[excited]` "quando o assunto pegar tração", e a whitelist aceitava
`[laughs]`/`[sighs]`/`[whispers]`/`[sarcastic]` em qualquer ponto. No eleven_v3 isso vira salto
de tom na palavra logo depois da troca de emoção e risada sintética no meio da frase. Com a
direção só no início da fala (`novo`), os sinais de entrega estranha caem de 0,48 para 0,31 por
áudio (−35%), sem perder variação de entonação (faixa de pitch igual, 14,3 semitons).

**A escuta às cegas não confirmou a melhora** (ver "Escuta humana"). O ouvinte marcou como estranhos
11 de 27 takes do `atual` e 15 de 27 do `novo`, e descreveu o problema como entonação, pronúncia e
ritmo na fala inteira. As métricas automáticas não captam isso (pegaram 10 dos 26 takes marcados). A
mudança tira defeitos pontuais reais (risada sintética, salto de tom na troca de emoção, frase
quebrada pela pausa), mas o "falar estranho" que o ouvinte percebe está no modelo ou na voz. A rodada
2 (`escuta2.html`) compara modelo, ajuste e voz pelo ouvido.

## Como foi medido

Script: `backend/scripts/avaliar_entrega_voz.py` (reproduzível, consome créditos; retoma execução
interrompida). Corpus: `backend/scripts/simulacao/corpus_entrega_voz.json`, 9 falas reais geradas
pelo LLM nas simulações da H0 (`docs/humanizacao/h0/simulacao/llm/*/as_run.json`), com as tags e
`......` que o LLM escreveu. Vozes do catálogo: Paulo nas falas de locutor, Yasmin nas de locutora.
Modelo eleven_v3 (padrão das combinações Premium/Equilibrada/Voz Premium).

Cada fala foi sintetizada 6 vezes por variante: o v3 muda de take pra take mesmo com `seed` fixa
(medido: mesmos parâmetros e seed, bytes diferentes), e "às vezes" só aparece com repetição.

Por áudio, sinais que um ouvinte nota (Scribe com timestamps por palavra + pitch via `librosa.pyin`):

| Sinal | Critério |
|---|---|
| Risada/suspiro | Evento sonoro marcado pelo Scribe (`[riso]`, `(suspiro)`...) |
| Pausa no meio da frase | Silêncio ≥ 0,6 s depois de palavra sem pontuação |
| Palavra esticada | Duração por sílaba > 2,6× a mediana do áudio e > 0,55 s |
| Pico de pitch | > 3% dos quadros vozeados acima de +7 semitons da mediana do próprio áudio |
| Erro de texto | Mais de 3 palavras faltando/sobrando contra o texto enviado |

Também medidos e sem ocorrência em nenhuma variante: frase sussurrada (8 dB abaixo da mediana) e
ritmo irregular entre frases (coeficiente de variação > 0,22).

## Variantes

- `atual`: `_preparar_sintese` antes da mudança (tags do LLM em qualquer ponto, `......` → `[pause]`
  sempre, `[calm]` automático no tom calmo).
- `novo`: `_preparar_sintese` depois da mudança (ver "O que mudou").
- `sem_tags`: nenhuma tag de emoção; `......` → vírgula/ponto.
- `tag_inicial`: só a tag que abre a fala; `......` → vírgula/ponto.
- `sem_tags_natural`: `sem_tags` com stability 0,5 ("Natural" do v3).
- `novo_v4`: `novo` no eleven_v4, como referência.

## Resultado (54 áudios por variante)

| Variante | Sinais/áudio | Áudios com sinal | Risada/suspiro | Pausa no meio da frase | Palavra esticada | Pico de pitch | Erro de texto | Faixa de pitch (st) | Palavras/min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| atual | 0,48 | 20 | 3 | 2 | 4 | 11 | 6 | 14,3 | 183 |
| **novo** | **0,31** | 15 | **0** | **0** | 1 | 12 | 4 | 14,3 | 180 |
| sem_tags | 0,31 | 16 | 0 | 0 | 2 | 7 | 8 | 14,6 | 181 |
| tag_inicial | 0,35 | 16 | 0 | 0 | 3 | 10 | 6 | 14,8 | 182 |
| sem_tags_natural | 0,39 | 14 | 0 | 1 | 5 | 8 | 7 | 14,8 | 174 |
| novo_v4 | 0,81 | 40 | 0 | 0 | 6 | 34 | 4 | 17,8 | 186 |

Bootstrap reamostrando as 9 falas (4000 rodadas): P(novo < atual) = 0,86; P(sem_tags < tag_inicial)
= 0,59 (indistinguíveis). Amostra pequena: indicativo, não definitivo.

### Onde a voz saltava

Mapeando os quadros de pitch alto para as palavras da transcrição, os picos do `atual` caem logo
depois do `[excited]` que vem no meio da fala:

- "[calm] Rádio Vila Ventura, Marta Girassol aqui, [excited] **companhia** para o seu dia!" (2 de 3 takes);
- "[excited] Então tá **dado**, Cida!" (e num take o Scribe ouviu "tava há de");
- "[calm] … [excited] Vem comigo… **qual** canção vai ficar marcada".

Com a tag só no início, essa fala curta caiu de 2 para 0 em 6 takes. O total de picos não caiu: os
que restam aparecem igual em `sem_tags`, são variação do próprio v3 (ou erro de oitava do pyin na voz
masculina).

### `......` no meio da frase

Convertida em `[pause]`, a reticência dupla emendando a mesma frase fazia o v3 fechar a frase com
cadência final: o Scribe transcreveu "aqui na Rádio Ipê Dourado**.** A viola que acompanha o seu dia"
em 2 de 3 takes do `atual`, contra vírgula em 3 de 3 quando a reticência vira vírgula. A pausa não
dura 1,2 s ali (0,4 a 0,56 s medidos); o problema é a entonação de fim de frase no meio dela.

### Parâmetros que não resolvem

- **`speed` é ignorado pelo v3.** Mesmo texto, n=4: speed 0,75 → 12,68 s; speed 1,2 → 12,28 s (3%).
  Toda a calibração de ritmo por bloco e por voz em `app.tts.client` (`_VOICE_SETTINGS_POR_TIPO`,
  `_AJUSTE_SPEED_MULTIPLICADOR_POR_VOZ`) não chega ao áudio no v3; vale para Flash e v2.
- **Stability 0,5 não ajudou** (`sem_tags_natural` 0,39 contra 0,31 de `sem_tags`).
- **v4 não é solução direta:** pitch bem mais largo (17,8 st) e muito mais picos. O detector não
  distingue "mais vivo" de "estranho"; trocar de modelo por esse motivo exigiria escuta.

## O que mudou no código

- `app/tts/client.py`: whitelist de emoção reduzida a `[excited]` e `[calm]`; só a tag que abre a
  fala é mantida (`_direcao_so_no_inicio`); `......` vira `[pause]` só entre frases, vírgula quando
  a frase continua em minúscula e ponto no fim do texto (`_converter_pausas`).
- `app/tts/modelos.py`: `PAUSA_LONGA_RE`, usada também por `app/live/orcamento.py` para contar na
  duração estimada e no ritmo medido só as pausas que viram `[pause]`.
- `app/live/prompts.py` (`INSTRUCAO_TAGS_V3`) e `app/live/prompt_emissao.py`: uma tag opcional no
  início, sem troca no meio, sem risada escrita; `......` só antes de frase nova; sai a "risadinha
  breve" das reações e a instrução de `[calm]` na entrada com `[excited]` depois.
- `app/billing/combinacoes.py`: descrição da direção vocal sem "risada, suspiro".

## Escuta humana

`escuta.html` mostra 3 takes do `atual` e 3 do `novo` por fala, embaralhados, com caixa "estranho"
por take; `gabarito.json` diz qual é qual e `escuta_marcacoes.json` guarda as marcações. Os áudios
não vão para o git (`.gitignore`): a página funciona na máquina que rodou o script.

| Fala | `atual` estranho | `novo` estranho |
|---|---:|---:|
| pop_abertura | 1/3 | 2/3 |
| pop_tres_coisas | 1/3 | 1/3 |
| pop_viola_trabalho | 1/3 | 1/3 |
| pop_encerramento | 1/3 | 2/3 |
| var_id_curta | 1/3 | 2/3 |
| var_risada | 2/3 | 1/3 |
| var_musica | 1/3 | 2/3 |
| var_chamada | 1/3 | 2/3 |
| mus_abertura | 2/3 | 2/3 |
| **Total** | **11/27** | **15/27** |

A diferença está dentro do ruído de 27 takes por lado, mas não há ganho perceptível. Nenhuma
métrica separa os takes marcados dos não marcados (palavras/min, faixa e picos de pitch, ritmo,
stability: medianas iguais), e as duas vozes têm a mesma proporção (Paulo 14/30, Yasmin 12/24).

### Rodada 2: modelo, ajuste e voz

`escuta2.html` (nota de 1 a 5; `gabarito2.json`, notas em `escuta2_notas.json`): 3 falas curtas
(`pop_abertura`, `mus_abertura`, `var_musica`) × 2 takes de cada opção, embaralhados. 1 = muito
estranho, 5 = soa como locutor de verdade.

| Opção | Nota média | pop_abertura | var_musica | mus_abertura |
|---|---:|---|---|---|
| **`novo_v4`** (v4, Paulo/Yasmin) | **4,17** | 5, 5 | 3, 5 | 3, 4 |
| **`outra_voz`** (v3, Diego/Raquel) | **4,00** | 5, 4 | 5, 4 | 3, 3 |
| `v3_robusto` (stability 1,0) | 2,17 | 2, 3 | 1, 2 | 1, 4 |
| `novo` (v3, Paulo/Yasmin) | 2,17 | 2, 3 | 2, 2 | 1, 3 |
| `v3_sem_idioma` (sem `language_code`) | 2,00 | 3, 2 | 1, 2 | 2, 2 |
| `v2` (multilingual v2) | 1,17 | 1, 1 | 1, 2 | 1, 1 |

**Conclusão:** o "falar estranho" é o eleven_v3 com Paulo e Yasmin. Ajuste no v3 (stability,
idioma) não muda a nota; trocar o modelo para v4 ou a voz para Diego/Raquel resolve, e o v4 ganha
ou empata em todas as falas. As métricas automáticas apontavam o contrário (v4 com 0,81 sinais por
áudio, o pior): o detector de pico de pitch confunde voz viva com voz estranha. Para essa pergunta,
vale a escuta. Amostra pequena (1 ouvinte, 6 takes por opção), mas a diferença é grande e vai no
mesmo sentido nas 3 falas. Falas longas no v4 não foram ouvidas.

### Decisões (aprovadas pelo usuário em 23/11/2026)

- **Eleven v4 é o padrão.** `settings.elevenlabs_model` = `eleven_v4`; Premium v4 é a combinação
  recomendada e cada v4 aparece antes da v3 equivalente.
- **Programas já salvos com v3 migram uma vez** para a combinação v4 equivalente
  (`app/db/migrations/voz_v4_20261123.py`): Premium → Premium v4, Equilibrada → Equilibrada v4, Voz
  Premium → Voz Premium v4. Sem tarifa vigente do v4 no banco, a migração espera o próximo startup.
- **Diego e Raquel entram no catálogo** (`app/tts/voices.py`). Ninguém troca de voz sozinho.

## Pendências

- **Tarifa do v4 em produção.** Programa sem escolha gravada (e o WhatsApp) usa o modelo padrão; sem
  tarifa vigente do `eleven_v4`, a síntese é recusada (503). Conferir antes do deploy em
  `GET /billing/admin/tarifas/pendentes` ou se `premium_v4` aparece em `GET /billing/combinacoes`.
- **v4 com Diego/Raquel** e falas longas (comentário de 700+ caracteres) no v4 não foram ouvidos.
- **Calibração de `speed` no v3** é código morto para esse modelo; remover ou documentar fica para
  uma mudança separada.
- **"Ipê"** foi transcrito como "Ip" em 2 takes: candidato ao glossário de pronúncia da rádio.

## Custo

~152 mil caracteres de TTS (324 sínteses) mais as transcrições do Scribe, além de ~5 mil caracteres
dos testes de parâmetros.
