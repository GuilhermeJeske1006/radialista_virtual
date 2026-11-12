# Avaliação da F3 (estado confiável da emissão): juiz de locução

Data: 12/11/2026. Branch `melhoria/f3-contexto-emissao`, HEAD `c382859`. As saídas avaliadas foram gravadas no
commit `e3b2794` e registradas em `c382859`; o testador as reproduziu byte a byte hoje (`f3/testes.md`). Skills
usadas: `referencia-radio`, `avaliar-locucao` e `llm-evaluation`.

## Entrada

| | Antes | Depois (F3, `e3b2794`) |
|---|---|---|
| Com relógio (A para musical e popular, C para variedades) | F2 `f2/simulacao/<perfil>/` (`781f199`) | `f3/simulacao/<perfil>/` |
| Sem relógio | F2 `f2/simulacao/<perfil>/sem_relogio/` | `f3/simulacao/<perfil>/sem_relogio/` |
| Estresse: voz a 120 palavras/min | F2 `f2/simulacao/<perfil>/voz_120/` | `f3/simulacao/<perfil>/voz_120/` |
| Painel antigo (sem `inicio_previsto`) | F1 `f1/simulacao/popular_sertanejo/sem_inicio_previsto/` (só popular) | `f3/simulacao/<perfil>/sem_inicio_previsto/` |

- Perfis: `musical_adulto`, `popular_sertanejo` e `variedades_leves`.
- Todas as rodadas usam `--modo fake`, semente 7.
- **A bancada não mudou entre F2 e F3.** As duas rodadas usam `--tts duble`, LLM dublê a 162 palavras/min, voz
  dublê a 145, o mesmo relógio e `antecedencia` 2 (conferido no `config` de cada `resumo.json`). Ao contrário
  da comparação F1 → F2, aqui toda diferença vem do código.

## Método

1. **Script próprio, com régua independente.** O script fica em
   `/private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/90d4eff0-6fe1-4f02-8ce6-b92d53a2561e/scratchpad/juiz-f3/checar.py`,
   fora do repositório. Ele não importa `app` nem `scripts/simulacao/metricas.py` e lê só JSON (as-runs, resumos
   e fixtures).
   - **Por que a régua precisa ser outra.** Desde a F3, o simulador calcula `anuncio_sem_confirmacao` com o
     mesmo detector do backend (`app.live.validacao_fala.mencoes_musica`). Usar essa conta seria o validador
     corrigindo a si mesmo. Por isso, o juiz usa uma régua própria:
     - **Títulos citados:** procura no texto os títulos do catálogo da fixture e os das injeções.
     - **Confirmada:** a faixa citada está no bloco da própria fala ou é a próxima faixa tocada.
     - **Back-announce:** a faixa citada já tocou antes.
     - **Fora do catálogo:** procura um trecho com iniciais maiúsculas depois de um marcador de anúncio
       ("toca agora", "agora vem", "vem aí", "a seguir", "na sequência", "pode esperar", "vamos de", "vai"…).
     - **Artista sem título:** procura o nome de um artista citado sem o título, que pode sobrar de uma remoção.
   - **Teste de sanidade.** A régua acha título fora do catálogo depois de um marcador, a ordem artista-título e
     o artista citado sozinho. Não acusa o nome da rádio nem o do locutor.
   - **Conferência com o `resumo.json`.** Rodei os **28 arquivos** (F1, F2 e F3). Os 28 batem em todas as
     métricas comparadas: `fora_orcamento_pct`, `estouro_max_pct`, `atraso_hard_time_s`, `hard_times_perdidos`,
     `segundos_cortados`, `encerramento_no_ar`, `anuncio_sem_confirmacao`, `promessa_vencida`, `pedido_indevido`,
     `abertura_repetida`, `silencio_s` e `validacao_fala.acoes`.
   - **Hard time sem relógio.** Sem relógio no backend, o script casa os hard times por `corresponde_a`, a
     regra da F0, que o simulador também usa.
2. **Comparação texto a texto, F2 → F3** (`.../scratchpad/juiz-f3/difftextos.py`). Ela alinha as falas, as
   vinhetas e os intervalos de cada variante e compara a ordem das faixas.
3. **Leitura dirigida** das falas que o validador alterou. Procurei emenda solta, frase pendurada e perda de
   função. Esta leitura **não é a rubrica** e **não foi às cegas**: eu já conhecia a origem de cada fala ao
   calcular as métricas.

## Rubrica: não se aplica

As falas são texto do dublê: frases tiradas de um banco fixo, com injeções deliberadas. Neste conjunto, só uma
injeção cita música: "Pode esperar Canção do Sereno, de Lia Candeia, nesta tarde." As notas de clareza,
utilidade, coerência, continuidade, naturalidade e precisão mediriam o dublê, não a F3. Por isso este documento
traz **só as checagens automáticas** e a leitura dirigida. O item 5 do portão ("juiz: nenhuma dimensão abaixo da
linha de base") fica **pendente**, como na F2.

**Pedido ao orquestrador: uma rodada `--modo llm`.** Ela usa a Anthropic real, consome créditos e **exige
aprovação explícita do usuário**. Não foi rodada.

- **O que rodar:**
  - os três perfis com relógio, antes (ponta de `melhoria/f2-duracao-fala`, `930c796`) e depois (`c382859`);
  - semente 7, `PYTHONHASHSEED=0` e `--confirmo-custo`;
  - opcional: `--sem-inicio-previsto` na F3.
- **Custo estimado pelos contadores do fake:**
  - antes (F2): 8 + 12 + 23 = 43 chamadas de LLM;
  - depois (F3): 8 + 11 + 23 = 42 chamadas;
  - painel antigo, se rodar: mais 41;
  - para fechar também a rubrica que ficou pendente na F2, a F1 (`dff4259`) soma cerca de 38.
- **O que medir:**
  - **Falsos positivos do validador com texto real.** É a pendência principal da F3. Hoje só há 7/7 e 0 falsos
    positivos no `casos.json`.
  - **Contagem de ações:** `mencao_removida`, `fala_neutra` e `fala_removida`.
  - **Emendas soltas** depois da remoção ("E essa…", "Ela…").
  - **Falas que a remoção deixa abaixo do mínimo**, sobretudo no popular e no variedades, onde a entrada vai de
    20 a 60 s.
  - **A rubrica**, com amostras embaralhadas e às cegas, dando atenção à dimensão Continuidade.

## 1. Continuidade (foco da F3)

### Música anunciada sem confirmação (régua do juiz = `resumo.json`)

| Perfil | Com relógio | Sem relógio | `voz_120` | Painel antigo |
|---|---|---|---|---|
| musical_adulto | 1 → **0** | 1 → **0** | 1 → **0** | — → 0 |
| popular_sertanejo | 0 → 0 | 0 → 0 | 0 → 0 | 0 (F1) → 0 |
| variedades_leves | 0 → 0 | 0 → 0 | 0 → 0 | — → 0 |

- **O validador não removeu nenhuma citação confirmada.** As 12 rodadas da F3 têm **31 citações confirmadas**, e
  todas continuam no texto. Exemplos:
  - "Lurdinha Campos pediu pelo WhatsApp, e toca agora Café de Coador, com Tonho Varjão" (pedido `selecionado`;
    a faixa seguinte é essa);
  - "Vai Estrada de Chão Batido, de Irmãos Taquara, no lugar da pedida";
  - "toca agora Patins Amarelos";
  - nas rodadas sem relógio, uma citação por bloco de música.
- **Nenhum título fora do catálogo e nenhum artista sem título**, nas 12 rodadas.
- **Citada registrada fora do bloco** (correção `c0eaa55`): musical 1/1/1 → 0/0/0.
  - Na F2, a fala n10 registrava "Canção do Sereno" em `musicas_citadas` sem que a faixa entrasse no bloco.
  - Na F3, a lista sai vazia.
- **A ordem das faixas não mudou**, exceto no musical `voz_120`.
  - Lá, uma identificação deixou de existir: a grade ficou cerca de 5 s adiantada depois da remoção.
  - No fim da hora, "Rio Sem Margem" deu lugar a "Porto das Gaivotas".
  - Nenhuma das duas foi anunciada.
- **Ressalva sobre o tamanho da evidência.**
  - Nos as-runs, a remoção de música sempre pega a mesma frase injetada, nas quatro rodadas do musical.
  - A afirmação "100% dos casos" do aceite vem do benchmark (`casos.json`: 7 de 7, sem falso positivo nas outras
    63 falas), não destas saídas.
  - Ordens e construções diferentes só aparecem no benchmark e nos testes unitários.

### Ações do validador (`validacao_fala` no as-run)

Foram 5 ações nas 12 rodadas: 4 `mencao_removida` e 1 `fala_neutra`. Nenhuma `fala_removida` e nenhuma
`reescrita` motivada pelo validador. A V1 não disparou: as falas afetadas têm 1 chamada de LLM e nenhuma revisão,
tudo saiu pela V2, e o total de chamadas não mudou (musical 8 → 8).

| Rodada / evento | Ação e regra | Texto que foi ao ar | Duração / orçamento | Leitura |
|---|---|---|---|---|
| Musical, com relógio, n10 `chamada_ouvinte` (igual em `voz_120` e no painel antigo) | `mencao_removida` (`musica_nao_confirmada`: "Pode esperar Canção do Sereno, de Lia Candeia, nesta tarde.") | "O WhatsApp da Rádio Serra Clara está aberto para o seu recado. Áudio curto também vale. Respira fundo, ajeita a cadeira e vem com a gente. Manda o seu." | 12,0 s (antes 16,14) / 10–20 s; em `voz_120`, 14,5 s | Sem emenda: a frase removida era a última, e "Manda o seu." fecha o convite. A chamada continua cumprindo a função. O áudio foi sintetizado depois da remoção: os caracteres de TTS caem 988 → 945. |
| Musical, sem relógio, n8 `retomada` | `mencao_removida` (mesma frase) | "Tarde Serena segue com você. Seguimos sem pressa nenhuma. Aproveita." | 4,14 s (antes 8,28) / 6–12 s, orçamento do formato | Sem emenda: a fala está inteira e reorienta com o nome do programa. Ficou abaixo do mínimo, mas em faixa musical a fala curta preserva o formato (regra 8). Mantê-la segue o desenho: `fragmento()` só troca o texto pela reserva neutra quando ela é mais longa ou quando vem só música. |
| Popular, com relógio, n10 `identificacao` | `fala_neutra` (`fala_abaixo_do_minimo`: "Rádio.") | "Você está na Rádio Ipê Dourado." | 2,48 s (antes 0,41) / 3–3 s | Resolve o achado 1 da F2: agora a fala identifica a rádio. O nome do programa ficou de fora porque não cabia no máximo de 3 s. Custo: 2,07 s a mais (ver Tempo). |

**Emendas soltas: 0.** Conferi de forma automática e na leitura:
- nenhuma frase começa com conectivo ou anáfora sem antecedente;
- nenhuma fala termina pendurada;
- nenhum trecho removido continua no texto;
- não sobrou nome de artista;
- nenhuma fala ficou vazia.

## 2. Tempo

### Com relógio (F2 → F3)

| Perfil | Falas com orçamento aplicado | `fora_orcamento_pct` | `estouro_max_pct` | Acima de 130% | Abaixo do mínimo | `atraso_hard_time_s` | Perdidos | Encerramento no ar | Fim antecipado (meta ≤ 60 s) |
|---|---|---|---|---|---|---|---|---|---|
| musical_adulto | 7 → 7 | 0 → 0 | 0 → 0 | 0 → 0 | 1 → 1 | 0 → 0 | 0 → 0 | sim → sim | 5,99 → 8,47 |
| popular_sertanejo | 11 → 10 | 0 → 0 | 0 → 0 | 0 → 0 | 2 → 2 | 0 → **0,36** | 0 → 0 | sim → sim | 5,28 → 2,72 |
| variedades_leves | 18 → 18 | 0 → 0 | 0 → 0 | 0 → 0 | 2 → 2 | 0,18 → 0,18 | 0 → 0 | sim → sim | 3,32 → 3,32 |

- **Popular: atraso de 0,36 s no intervalo (hard time em 1440 s).**
  - **Na F2:** a fala "Rádio." durava 0,41 s, e o intervalo entrou 1,71 s adiantado.
  - **Na F3:** a fala neutra dura 2,48 s e começa em 1437,53 s. Com a pausa de 0,35 s, o intervalo entra em
    1440,36 s.
  - **Por quê:** a reserva escolhida cabe no máximo do orçamento (3 s), calculado na geração. O que restava até o
    hard time na hora de ir ao ar era 2,47 s. A grade já tinha escorregado pela estimativa ainda sem calibração;
    a F2 explicou o mecanismo.
  - **Leitura:** fica dentro da tolerância de 5 s da F1. É uma troca consciente: 2 s a mais em troca de uma
    identificação que cumpre a função.
- **Popular: 11 → 10 falas.**
  - Na F2, a identificação n26 era uma reserva para 4,43 s de espaço antes da passagem.
  - Na F3, a grade chega 2 s mais tarde, sobram 2,36 s, e a reserva não é gerada.
  - O encerramento ganha esse espaço (19–29 s) e nomeia a rádio ("Obrigado por deixar a Rádio Ipê Dourado
    ligada"). A identidade continua no ar.
- **Musical: fim antecipado de 5,99 → 8,47 s.**
  - A remoção encurtou a n10 em 4,14 s, e o encerramento passou a começar 2,78 s antes da passagem.
  - Continua bem abaixo da meta de 60 s.
- **Erro da estimativa calibrada:** musical 0 → 0, popular 1,7 → 2,1%, variedades 0 → 0.
- **Chamadas e sínteses:** no máximo 2 chamadas de LLM e 1 síntese por fala, nenhuma ressíntese.
- **Total de chamadas de LLM:** 8 → 8, 12 → 11 e 23 → 23.

### Sem relógio (F2 → F3)

| Perfil | `fora_orcamento_pct` | `estouro_max_pct` | Abaixo do mínimo | Perdidos | Segundos cortados | Encerramento no ar |
|---|---|---|---|---|---|---|
| musical_adulto (formato aplicado) | 0 → 0 | 0 → 0 | 0 → **1** (n8, acima) | 3 → 3 | 107,97 → 103,83 | não → não |
| popular_sertanejo (observação 15–30 s) | 42,9 → 42,9 | 28,3 → 28,3 | 0 → 0 | 3 → 3 | 101,03 → 101,03 | não → não |
| variedades_leves (régua da fixture) | 4,2 → 4,2 | 32,4 → 32,4 | 0 → 0 | 2 → 2 | 0 → 0 | sim → sim |

- **Popular e variedades:** idênticos à F2, fala a fala.
- **Musical:** a única diferença é a remoção na n8, que adianta a grade em 4,14 s.
- **Limites conhecidos:** sem relógio, o formato padrão continua só em observação (F6).

### Estresse `voz_120` (F2 → F3)

| Perfil | `fora_orcamento_pct` | `estouro_max_pct` | `atraso_hard_time_s` | Abaixo do mínimo | Fim antecipado |
|---|---|---|---|---|---|
| musical_adulto | 0 → 0 | 0 → 0 | 0 → 0 | 1 → 0 | 23,5 → 5,8 |
| popular_sertanejo | 0 → 0 | 0 → 0 | 12,1 → 12,1 | 1 → 1 | 73,16 → 73,16 |
| variedades_leves | 14,3 → 14,3 | 10,0 → 10,0 | 0 → 0 | 0 → 0 | 2,0 → 2,0 |

Popular e variedades são idênticos à F2: são os limites conhecidos da voz nova ainda sem calibração. O musical
melhora levemente. A identificação de 6 s, abaixo do mínimo de 7 s, sai da grade, e o encerramento entra
2,8 s antes da passagem, em vez de 20,5 s antes.

### Painel antigo (`--sem-inicio-previsto`)

| Perfil | Atraso | Perdidos | Cortados | Encerramento no ar |
|---|---|---|---|---|
| popular_sertanejo (F1 → F3) | 412,21 → **0** | 2 → 0 | 73,67 → 0 | não → **sim** |
| musical_adulto (F3) | 0 | 0 | 0 | sim |
| variedades_leves (F3) | 0,18 | 0 | 0 | sim |

- No musical e no variedades, a rodada do painel antigo é **idêntica, evento a evento** (texto e tempos), à
  rodada com relógio. O horário vem da cadeia no servidor (`origem_instante = "estimado"`).
- No popular, a grade difere, mas cumpre os mesmos critérios.

## 3. Reprovações automáticas: antes × depois

| Rodada | `anuncio_sem_confirmacao` | `promessa_vencida` | `pedido_indevido` | Piorou pela F3? |
|---|---|---|---|---|
| musical: com relógio / sem relógio / `voz_120` | 1/1/1 → **0/0/0** | 0/0/0 → 0/0/0 | 1/1/1 → 1/1/1 | não |
| musical, painel antigo | — → 0 | — → 0 | — → 1 | — |
| popular: com relógio / sem relógio / `voz_120` | 0/0/0 → 0/0/0 | 0/1/1 → 0/1/1 | 1/1/1 → 1/1/1 | não |
| popular, painel antigo (F1 → F3) | 0 → 0 | 0 → 1 | 1 → 1 | não (ver abaixo) |
| variedades: com relógio / sem relógio / `voz_120` | 0/0/0 → 0/0/0 | 0/0/0 → 0/0/0 | 3/4/3 → 3/4/3 | não |
| variedades, painel antigo | — → 0 | — → 0 | — → 3 | — |

- **Escopo da F3:** zero anúncio sem confirmação nas 12 rodadas, pela régua independente do juiz.
- **F4 (promessa vencida e pedido indevido):** os números são iguais aos da F2 em toda rodada comparável. Eles
  ficam listados na seção 5 e não reprovam a F3.
- **O 0 → 1 do popular no painel antigo** é a mesma promessa injetada, que caiu em outra fala.
  - Na F1, ela estava na n7, um bloco de música. A regra da F0 "fechou" a promessa porque a mesma fala anunciava
    a faixa seguinte.
  - Na F3, ela está na n11 (`chamada_ouvinte`).
  - O 0 da F1 era um artefato do detector, não uma promessa cumprida. O detector do juiz acha a promessa nas duas.

## 4. Outras checagens automáticas

| Métrica | F2 → F3 |
|---|---|
| `abertura_repetida` | 0 → 0 em todas as rodadas |
| `silencio_s` (involuntário) | 0 → 0. Nenhuma sobreposição. Pausa editorial de 1,7 a 5,4 s (popular com relógio: 3,25 → 2,9, uma fala a menos). |
| `aviso_oralidade` | não se aplica: `app/live/oralidade.py` não existe (F7) |
| Falas vazias | 0 → 0 |
| Falas de até 3 palavras | 1 → **0** ("Rádio." saiu) |
| Detector de promessa do juiz | "logo depois de usar" (dica dos quadros do variedades) descartado como falso positivo; o padrão não atravessa ponto final ("terminar logo. Depois, …") |

## 5. Achados para a F4 e outras frentes

Sem nota, porque a rubrica não se aplica. As sugestões são originais e não imitam nenhum radialista.

### F4: participação e promessa (não reprovam a F3)

1. **Ouvinte simulado, a violação mais grave (regra 2).**
   - **Onde:** variedades, n6 (com relógio, `voz_120` e painel antigo) e n5 (sem relógio).
   - **O texto:** "Um abraço também para Dona Firmina."
   - **O problema:** não existe pedido nem mensagem dessa ouvinte. É a injeção `cita_ouvinte`.
   - **Sugestão:** uma checagem `ouvinte_sem_participacao` em `CHECAGENS_POS_GERACAO`, com nomes autorizados
     vindos só de pedidos aprovados.
2. **"Toca agora" e nome de ouvinte fora de `selecionado`:**
   - **Paulo Brandão** (`historico_legado`, variedades): "Quem pediu foi Paulo Brandão, e toca agora Patins
     Amarelos". A faixa tocou. O problema é só o estado do pedido.
   - **Joana Lis** (`historico_legado`, musical):
     - com relógio: "procurei a sua pedida e ela não está disponível por aqui";
     - sem relógio: "toca agora Farol Distante".
   - **Cida Morais** (`historico_legado`, variedades) e **Seu Afonso** (só sem relógio).
   - **Rosa Bezerra** (`nao_atendido`, popular): "Recebi o seu pedido, Rosa Bezerra, mas essa música não está no
     acervo. Vai Estrada de Chão Batido…". O texto é a contingência honesta. A F4 deve decidir se esse caso conta
     como indevido.
3. **Promessa vencida:** "Daqui a pouco tem mais recado de ouvinte por aqui."
   - **Onde aparece:** popular sem relógio n6, `voz_120` n11 e painel antigo n11.
   - **Com relógio:** a promessa sumiu só porque o encurtamento cortou a frase e o validador pôs a fala neutra no
     lugar. Não foi uma regra de promessa que a tirou.
   - **Sugestão:** registrar a promessa em `Chamadas.promessas` e exigir um evento no relógio (`ctx.tempo.plano`).
     Sem evento, remover a frase com o mesmo `remover_frases`.
4. **Trocar o detector provisório de promessa (F0).**
   - Hoje ele fecha uma promessa que não é de música quando a mesma fala anuncia música (o artefato do painel
     antigo na F1).
   - O detector amplo do juiz confunde "logo depois de usar" com promessa.

### F3 residual, F11 e bancada

5. **A reserva neutra olha o orçamento da geração, não o espaço na hora de ir ao ar** (+0,36 s no popular).
   - Dentro da tolerância.
   - Com uma voz nova sem calibração, o escorregamento pode ser maior.
   - **Sugestões:**
     - escolher a reserva com folga: ela é a mais longa que cabe, e poderia ser a mais curta que identifica;
     - ou usar a vinheta de identidade quando houver catálogo de reservas (F11).
6. **Remoção que deixa a fala abaixo do mínimo sem trocá-la** (musical sem relógio, n8, 4,14 s contra 6 s).
   - No musical, é aceitável.
   - No popular e no variedades (entrada de 20 a 60 s), uma remoção pode deixar uma fala bem abaixo da unidade
     do formato sem nenhuma ação.
   - Medir na rodada `llm` antes de decidir.
7. **Evidência estreita no simulador.**
   - A única injeção de música é "Pode esperar X, de Y, nesta tarde.", no fim da fala.
   - **Sugestão para a bancada:** injeções com a ordem artista-título, com "agora vem…" no meio da fala e no
     multivoz. Assim o simulador exercita a emenda solta, que é a pendência registrada.
8. **Documentação.**
   - `f3/testes.md` diz "0 falsos positivos em 70 falas" numa tabela e "0 FP em 63" na outra. São 70 falas, das
     quais 63 negativas, então os dois números são compatíveis, mas convém unificar.
   - `RELATORIO.md` diz "2 sínteses por fala". Os as-runs mostram no máximo 1, o que está dentro do invariante.

## Veredito

**APROVADO** nas checagens automáticas. A rubrica fica pendente de uma rodada `--modo llm`, que exige aprovação
do usuário.

**Por quê:**
- Pela régua independente do juiz, `anuncio_sem_confirmacao` cai de 1/1/1 para 0 no musical e fica em 0 nas 12
  rodadas da F3.
- As 31 citações confirmadas foram preservadas, e nenhuma remoção deixou emenda solta.
- A fala "Rádio." virou uma identificação que cumpre a função.
- Com relógio, 100% das falas ficam dentro do orçamento, nenhuma passa de 130%, e o atraso máximo é de 0,36 s
  (critério: 5 s).
- O painel antigo vai de 412 s de atraso para 0.
- Nenhuma reprovação automática da F4 é nova ou aumentou por causa da F3.

**Ressalvas que não bloqueiam:**
- o hard time do popular passou de 0 para 0,36 s (item 5);
- a fala do musical sem relógio ficou abaixo do mínimo (item 6);
- a evidência nos as-runs é estreita, e os falsos positivos com texto real não foram medidos (item 7 e rodada
  `llm`);
- as violações da F4 listadas na seção 5.

APROVADO
