# Avaliação da F2 (duração real da fala): juiz de locução

Data: 09/11/2026. Branch `melhoria/f2-duracao-fala`. As saídas avaliadas foram gravadas no commit `781f199`
e registradas em `d68c39f`. Skills usadas: `referencia-radio`, `avaliar-locucao` e `llm-evaluation`.

## Entrada

| | Antes (F1, `dff4259`) | Depois (F2, `781f199`) |
|---|---|---|
| Com relógio (A para musical e popular, C para variedades) | `f1/simulacao/<perfil>/` | `f2/simulacao/<perfil>/` |
| Sem relógio | `f1/simulacao/<perfil>/sem_relogio/` | `f2/simulacao/<perfil>/sem_relogio/` |
| Estresse: voz a 120 palavras/min | — | `f2/simulacao/<perfil>/voz_120/` |

Perfis: `musical_adulto`, `popular_sertanejo` e `variedades_leves`. Todas as rodadas usam `--modo fake`,
semente 7. A estrutura foi conferida: os eventos ficam em `as_run["eventos"]` e `musica_anunciada` é uma lista.

**A bancada mudou entre as duas rodadas.**
- Na F1 (`--tts nenhum`), o dublê escreve a 145 palavras/min e a fala dura o mesmo que a estimativa.
- Na F2 (`--tts duble`), o dublê do LLM escreve a 162 palavras/min (`wpm_para` do v3 sem calibração), e a voz do
  dublê fala a 145.
- Por isso, até a 5ª amostra, cada fala dura cerca de 12% a mais do que o backend estima. É o pior caso da
  primeira hora de uma voz nova.
- O orçamento das falas do formato padrão sem relógio também mudou:
  - na F1 era o da fixture, com `fonte="formato"` (entrada 20–60 s, quadro);
  - na F2 é observação, com 15–30 s e `aplicado=false`.
- Por isso, na comparação sem relógio, a régua estável é `orcamento_ref_s`, que é igual nas duas rodadas.

## Método

1. **Script próprio.** Fica em
   `/private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/4efade71-3851-4394-9e93-629b2f839d1f/scratchpad/juiz/f2/checar.py`,
   fora do repositório. Não importa `app` nem `scripts/simulacao/metricas.py`.
   - Recalcula as métricas a partir do `as_run.json`.
   - Cruza as citações de música com o catálogo da fixture.
   - Usa um detector de promessas mais amplo que o da F0.
   - Mede a duração abaixo do mínimo e as falas de até 3 palavras.
   - Confere o resultado com o `resumo.json`.
   - Os **15 de 15** arquivos batem em todas as métricas comparadas: `fora_orcamento_pct`, `estouro_max_pct`,
     `atraso_hard_time_s`, `anuncio_sem_confirmacao`, `promessa_vencida`, `pedido_indevido`, `abertura_repetida`,
     `silencio_s` e o erro da estimativa.
2. **Controles fake.** Rodaram em `.../scratchpad/juiz/f2/controle/`, sem rede e sem gravar nada no repositório.
   - **A** (`--tts nenhum --wpm 145 --relogio-backend nenhum`): sai idêntico, evento a evento (texto, tempos,
     música, pedido), a `f1/.../sem_relogio` nos três perfis. Isso confirma a nota da bancada em `pendencias.md`.
   - **D** (padrão do CLI): reproduz `f2/simulacao/<perfil>/` sem nenhuma diferença.
   - **B** (sem relógio, dublê escrevendo a 145, `--tts duble`) e **C** (com relógio, dublê a 145): isolam o
     descompasso da bancada.

## Rubrica: não se aplica

As falas desta avaliação são texto do dublê: frases montadas de um banco fixo, com injeções deliberadas de
excesso, música citada e promessa. Notas de clareza, utilidade, coerência, continuidade, naturalidade e precisão
mediriam o dublê, não a F2. Por isso este documento traz **só as checagens automáticas**. O item 5 do portão
("juiz: nenhuma dimensão abaixo da linha de base") fica **pendente**.

**Pedido ao orquestrador: uma rodada `--modo llm`.** Ela usa a Anthropic real, então consome créditos e **exige
aprovação explícita do usuário**. Não foi rodada.
- **O que rodar:** os três perfis com relógio, antes (`dff4259`, branch `melhoria/f1-relogio`) e depois (HEAD da
  F2), com semente 7, `PYTHONHASHSEED=0` e `--confirmo-custo`.
- **Custo estimado:** cerca de 38 + 43 = 81 chamadas de LLM, pelos contadores do fake. As pastas sem relógio
  somariam cerca de 134.
- **O que medir:** a taxa real de reescrita por duração e a rubrica, com amostras embaralhadas e às cegas.
- **Depois, opcional:** uma rodada `--modo completo` (ElevenLabs), para medir o erro da estimativa com áudio real.
  São cerca de 19 mil caracteres de TTS nos três perfis com relógio.

## 1. Métricas de tempo (foco da F2)

### Com relógio (antes → depois)

| Perfil | Falas com orçamento aplicado | `fora_orcamento_pct` | `estouro_max_pct` | Acima de 130% | `atraso_hard_time_s` | Hard times perdidos | Encerramento no ar |
|---|---|---|---|---|---|---|---|
| musical_adulto | 7 → 7 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim |
| popular_sertanejo | 11 → 11 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim |
| variedades_leves | 16 → 18 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0,18 | 0 → 0 | sim → sim |

Aceite da F2: pelo menos 95% das falas dentro do orçamento e nenhuma acima de 130%. **Cumprido nos três
perfis**: 100% dentro e nenhuma acima do teto. O atraso de 0,18 s fica dentro da tolerância de 5 s da F1.

### Sem relógio (antes → depois)

| Perfil | Orçamento | `fora_orcamento_pct` | `estouro_max_pct` | Acima de 130% | Perdidos | Encerramento no ar | Segundos cortados |
|---|---|---|---|---|---|---|---|
| musical_adulto | aplicado (formato), 8 → 8 | 0 → 0 | 0 → 0 | 0 → 0 | 3 → 3 | não → não | 100,1 → 108,0 |
| popular_sertanejo | régua da fixture, 22 → 21 | 0 → 0 | 0 → 0 | 0 → 0 | 3 → 3 | não → não | 30,2 → 101,0 |
| popular_sertanejo | observação F2 (15–30 s) | — → 42,9 | — → 28,3 | — → 0 | | | |
| variedades_leves | régua da fixture, 25 → 24 | 4,0 → 4,2 | 19,3 → **32,4** | 0 → **1** | 3 → 2 | não → sim | 331,5 → 0 |
| variedades_leves | observação F2 (15–30 s) | — → 62,5 | — → 455,9 | — → 7 | | | |

**Leitura**
- **Variedades sem relógio, com a régua da fixture.** A pior fala passou de 19,3% para 32,4% acima do máximo, e
  surgiu uma fala acima de 130%: o comentário n2, com 79,45 s contra 60 s (na F1, 71,59 s). Os segundos
  cortados também mudaram.
- **A causa é a bancada, não o código da F2.**
  - O controle **B** (dublê a 145, com `--tts duble`) volta exatamente aos números da F1: 4,0 / 19,3 / 0 e
    segundos cortados de 100,1 / 30,2 / 331,6.
  - O controle **A** é idêntico à F1.
  - Por desenho, o formato padrão sem relógio só observa e não muda o prompt ("4 a 6 frases"). Em produção, o
    texto continua o mesmo.
- **Mesmo assim, fica registrado:** sem relógio, a F2 não protege o formato padrão. Pela régua de observação,
  42,9% (popular) e 62,5% (variedades) das falas passam do máximo. Isso já está em `pendencias.md` e é decisão
  da F6 (unidade de fala por formato).

### Estresse: `voz_120` (voz 26% mais lenta que o padrão do v3)

| Perfil | `fora_orcamento_pct` | `estouro_max_pct` | Acima de 130% | `atraso_hard_time_s` | Erro da estimativa: todas / depois de 5 amostras |
|---|---|---|---|---|---|
| musical_adulto | 0 | 0 | 0 | 0 | 16,2% / 0% |
| popular_sertanejo | 0 | 0 | 0 | **12,1** (intervalo de 1440 s; critério de 5 s) | 11,8% / 0% |
| variedades_leves | **14,3** (2 de 14) | 10,0 | 0 | 0 | 9,3% / 0% |

O estresse viola dois critérios antes da calibração:
- o hard time do popular atrasa 12,1 s;
- no variedades, só 85,7% das falas ficam dentro do orçamento.

Nenhuma fala passa do teto de 130%. Depois de 5 amostras, o erro vai a 0%. Fica como risco medido, não como
reprovação: em produção, a tabela `ritmos_voz` é persistente, e isso só ocorre na primeira hora de uma voz nova.

## 2. Estimativa, chamadas e ajustes (depois)

| Rodada | Erro da estimativa: todas / calibrada | Reescritas | Encurtadas | Cortadas | Acima do teto | Máximo de LLM por fala | Máximo de sínteses por fala | Ressínteses |
|---|---|---|---|---|---|---|---|---|
| musical com relógio | 7,5% / 0% | 1 | 0 | 0 | 0 | 2 | 1 | 0 |
| popular com relógio | 5,7% / 1,7% | 0 (1 revisão por duração) | 1 | 0 | 0 | 2 | 1 | 0 |
| variedades com relógio | 2,9% / 0% | 0 | 0 | 0 | 0 | 2 | 1 | 0 |
| sem relógio (três perfis) | 6,6 / 2,5 / 2,2% → 0% | 1 / 0 / 0 | 0 | 0 | 0 | 2 | 1 | 0 |

- **Invariantes da auditoria (§4.1) respeitados:** no máximo 2 chamadas de LLM e 1 síntese por fala, nenhuma
  ressíntese.
- **Custo:** as chamadas de LLM ficaram iguais à F1 no musical (8 → 8) e subiram pouco no popular (11 → 12) e no
  variedades (19 → 23). Esse aumento vem de falas a mais (16 → 18) e de uma revisão por duração.

## 3. Reprovações automáticas: antes × depois

| Rodada | `anuncio_sem_confirmacao` | `promessa_vencida` | `pedido_indevido` | Piorou pela F2? |
|---|---|---|---|---|
| musical com relógio | 1 → 1 | 0 → 0 | 1 → 1 | não |
| popular com relógio | 0 → 0 | 1 → **0** | 1 → 1 | não; a promessa sumiu por acidente (ver abaixo) |
| variedades com relógio | 0 → 0 | 0 → 0 | 3 → 3 | não |
| musical sem relógio | 1 → 1 | 0 → 0 | 1 → 1 | não |
| popular sem relógio | 0 → 0 | 1 → 1 | 1 → 1 | não |
| variedades sem relógio | 0 → 0 | 0 → 0 | 4 → 4 | não |
| voz_120 (musical / popular / variedades) | 1 / 0 / 0 | 0 / 1 / 0 | 1 / 1 / 3 | mesmos eventos de antes |

Nenhuma reprovação automática é nova, e nenhuma aumentou por causa da F2. Todas as que existem já estavam na
F1 (e na linha de base da F0), nos mesmos blocos, ouvintes e estados. Pertencem à F3 e à F4 e não reprovam a
F2, mas ficam listadas:

### F3: música anunciada sem confirmação

- **Musical com relógio, n10 (`chamada_ouvinte`):** "Pode esperar Canção do Sereno, de Lia Candeia". A faixa que
  tocou depois foi "Cais do Entardecer". É injeção do dublê (`injecao_cita_musica`).
- **Musical sem relógio, n8 (`retomada`):** a mesma injeção.

### F4: promessa vencida

- **Popular sem relógio, n6 (`chamada_ouvinte`)** e **voz_120 popular, n11:** "Daqui a pouco tem mais recado de
  ouvinte por aqui."
- **Popular com relógio, n10 (identificação).** A mesma promessa estava lá na F1 e deixou de existir na F2. O
  motivo não foi uma regra de promessa: o encurtamento deixou só "Rádio." (ver §5, item 1). O 1 → 0 não deve
  ser contado como ganho.

### F4: pedido indevido

- **Musical:** Joana Lis com estado `historico_legado`. Com relógio: "procurei a sua pedida". Sem relógio:
  "toca agora Farol Distante".
- **Popular:** Rosa Bezerra com estado `nao_atendido`.
- **Variedades:**
  - Dona Firmina citada sem pedido (`ouvinte_inexistente` = 1, igual à F1);
  - Paulo Brandão com "toca agora" em `historico_legado`;
  - Cida Morais em `historico_legado`;
  - Seu Afonso em `historico_legado` (só sem relógio).

### Falso positivo do detector do juiz

O detector mais amplo achou "logo depois" nos quadros do variedades (n16 a n19 com relógio; n8, n18 e n28 sem
relógio). O trecho é "devolve cada coisa ao lugar logo depois de usar": é uma dica, não uma promessa. Também
aparece na F1.

## 4. Outras checagens automáticas

| Métrica | Antes → depois (com relógio; sem relógio igual) |
|---|---|
| `abertura_repetida` | 0 → 0 em todas as rodadas |
| `silencio_s` (involuntário) | 0 → 0. A pausa editorial vai de 1,7 a 5,45 s. |
| `aviso_oralidade` | não se aplica: `app/live/oralidade.py` não existe (F7) |
| Falas vazias | 0 → 0 |
| Duração abaixo do mínimo do orçamento | musical 1 → 1, popular 1 → **2**, variedades 0 → 2 (9,93 s contra 10 s, marginal) |
| Falas de até 3 palavras | 0 → **1** (popular, n10: "Rádio.") |

## 5. Achados para a rodada `llm`

Sem nota, porque a rubrica não se aplica. As sugestões são originais e não imitam nenhum radialista.

1. **Popular com relógio, n10 (identificação): "Rádio."**
   - **O que aconteceu:** 0,41 s no ar, contra um orçamento de 3 a 3 s e 3,9 s até o intervalo. As quatro
     primeiras falas mediram cerca de 12% a mais que a estimativa ainda sem calibração. A grade escorregou 9,5 s.
     Sobraram 3 s antes do hard time. A reescrita e `encurtar_por_frases` ficaram com uma frase de uma palavra.
   - **Efeito:** o hard time foi cumprido, mas a fala não identifica a rádio. Fala que não cumpre a função é
     pior que não falar (regra 8).
   - **Controle:** o controle C (sem o descompasso) não reproduz o caso.
   - **Sugestão:** quando o resultado do encurtamento ficar abaixo do mínimo, ou sem o nome da rádio, não gerar
     fala e deixar a música encostar no intervalo, ou usar a vinheta de identidade. O caso já está em
     `pendencias.md` ("Encurtamento não respeita o mínimo do orçamento"). Conferir no `--modo llm` se a reescrita
     real produz algo como "Rádio Ipê Dourado, Prosa e Viola."
2. **voz_120, popular: o intervalo de 1440 s atrasa 12,1 s.** O orçamento usa a estimativa otimista antes da
   5ª amostra. A sugestão já está nas pendências: calibração progressiva ou um padrão por modelo mais
   conservador.
3. **voz_120, variedades: dois comentários acima do máximo** (198 s contra 180 s; 122,5 s contra 122 s), mas
   abaixo do teto. Mesma causa do item 2.
4. **Formato padrão sem relógio: só observação.** No variedades, o quadro n8 dura 166,8 s: cabe na unidade de
   quadro da skill (2 a 8 min), mas fica 455,9% acima da régua de observação de 30 s. O comentário n2 dura
   79,45 s, contra o máximo de 60 s da fixture (é a fala acima de 130%; no controle B, 71,59 s). É decisão da F6.
5. **Violações anteriores da F3 e da F4** (seção 3). Precisam ser zeradas nas frentes delas.

## Veredito

**APROVADO** nas checagens automáticas, com a rubrica pendente de uma rodada `--modo llm` aprovada pelo usuário.

**Por quê:**
- Nenhuma reprovação automática é nova, e nenhuma piorou por causa da F2.
- Com relógio: 100% das falas dentro do orçamento, nenhuma acima de 130% e atraso máximo de 0,18 s.
- Sem relógio: os números da F1 se mantêm quando se isola o descompasso da bancada (controles A e B).
- A estimativa calibrada chega a 0–1,7% de erro depois de 5 amostras.

**Ressalvas que não bloqueiam:**
- a fala "Rádio." (§5, item 1);
- o estresse `voz_120` (atraso de 12,1 s; 85,7% dentro do orçamento);
- as violações anteriores da F3 e da F4, listadas na seção 3.

APROVADO
