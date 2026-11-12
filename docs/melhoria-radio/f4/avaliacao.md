# Avaliação da F4 (promessas, chamadas e participação de verdade): juiz de locução

Data: 12/11/2026. Branch `melhoria/f4-promessas`, HEAD `17f9cf9`. As saídas foram gravadas com o código de `4153bf3`;
`17f9cf9` só acrescenta documentação e as próprias saídas. Skills usadas: `referencia-radio`, `avaliar-locucao` e
`llm-evaluation`.

## Entrada

| | Antes (F3, `c382859`) | Depois (F4, `17f9cf9`) |
|---|---|---|
| Com relógio (A no musical e no popular, C no variedades) | `f3/simulacao/<perfil>/` | `f4/simulacao/<perfil>/` |
| Sem relógio | `f3/simulacao/<perfil>/sem_relogio/` | `f4/simulacao/<perfil>/sem_relogio/` |
| Estresse: voz a 120 palavras/min | `f3/simulacao/<perfil>/voz_120/` | `f4/simulacao/<perfil>/voz_120/` |
| Painel antigo (sem `inicio_previsto`) | `f3/simulacao/<perfil>/sem_inicio_previsto/` | `f4/simulacao/<perfil>/sem_inicio_previsto/` |
| Cenário dedicado (S2) | não existe | `f4/simulacao/cenario_f4/{popular_sertanejo,musical_adulto}/` |

- Perfis: `musical_adulto`, `popular_sertanejo` e `variedades_leves`. Todas as rodadas usam `--modo fake`, semente 7.
- **A bancada é a mesma da F3:** `--tts duble`, LLM dublê a 162 palavras/min, voz dublê a 145, os mesmos relógios,
  `antecedencia` 2 e as mesmas fixtures (nenhum commit da F4 tocou `tests/fixtures/programas/`).
- **Reprodução:** rodei de novo as 12 variantes pela CLI e o cenário dedicado pela API do simulador, com os mesmos
  parâmetros de `tests/test_simulacao_f4.py`. As saídas foram gravadas em pasta temporária. Os 14 `as_run.json` saíram
  idênticos aos registrados. Nos `resumo.json`, só `tempo_execucao_s` e o hash do commit mudam.

## Método

1. **Régua própria, independente do backend.**
   - O script fica em
     `/private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/90d4eff0-6fe1-4f02-8ce6-b92d53a2561e/scratchpad/juiz-f4/checar.py`.
     Ele não importa `app` nem `scripts/simulacao/metricas.py` e lê só JSON.
   - Tempo e continuidade vêm de `base_f3.py`, cópia do script do juiz da F3 (régua de catálogo).
   - **Por que outra régua.** Desde a F4, o simulador mede promessas e participação com
     `app.live.promessas.detectar` e `app.live.participacao.mencoes_participacao`. Usar essa conta seria o validador
     corrigindo a si mesmo.
   - **Participação.** A régua usa:
     - **nomes de ouvinte:** os pedidos do as-run e as injeções `cita_ouvinte`;
     - **nome desconhecido:** qualquer sequência com inicial maiúscula numa frase de participação, **inclusive no
       começo da frase** (o backend descarta a primeira palavra), menos rádio, programa, locutor, quadros, títulos e
       artistas do catálogo;
     - **mensagem simulada:** "chegou (uma) mensagem", "acabei de receber", "uma ouvinte pediu", "muita gente pediu"…,
       ignorando a negação ("Ainda não chegou…");
     - **classificação de cada menção:**
       - **legítima:** o pedido é o do bloco, foi `selecionado` na seleção, terminou `executado`, foi confirmado
         depois de tocar e, se for de música, é a faixa seguinte;
       - **D8:** ouvinte já atendido, citado sem construção de execução;
       - **indevida:** qualquer outro caso.
   - **Promessas.** A régua usa:
     - **marcadores, mais amplos que os do backend:** "já já", "em instantes", "a seguir", "na sequência", "em
       seguida", "volto já", "já volto", "logo depois", "na volta", "daqui a pouco", "logo logo", "não sai daí",
       "depois do intervalo", "depois dos comerciais", "mais tarde", "logo mais", "ainda hoje", "ainda neste
       programa", "amanhã", "até a próxima", "até breve", "até logo"…;
     - **casamento:** cada frase com marcador é casada com `as_run["promessas"]` pelo trecho. Não precisa de casamento:
       - a despedida ou a volta do programa (D9: `dias_semana` vazio = todo dia);
       - o anúncio de música confirmada;
     - **desfecho:** para cada registrada, a régua confere:
       - se o alvo está no relógio;
       - o estado;
       - se a fala de resolução cita um pedido `executado` (quando o estado é cumprida) ou traz a contingência no texto
         que foi ao ar (quando é cancelada);
       - se o trecho registrado está no texto que foi ao ar.
   - **Teste de sanidade** (`sanidade.py`). A régua:
     - acusa ouvinte inventado no meio e no começo da frase ("Dona Zuleica mandou…");
     - acusa mensagem simulada;
     - acusa pedido em fila citado e legado consumido antes de tocar;
     - aceita o pedido selecionado;
     - não acusa a contingência "Ainda não chegou recado…";
     - pega "daqui a pouco", "depois do intervalo", "já já", "ainda hoje", "volto já" e "mais tarde";
     - ignora "logo depois de usar".
   - Ela também marca "três músicas na sequência" como promessa: é a ambiguidade conhecida, e o juiz confere esses
     casos na leitura.
2. **Comparação texto a texto, F3 → F4** (`difftextos.py`, mesma pasta), por variante.
3. **Leitura dirigida** das falas que o validador alterou, das que sumiram e do cenário dedicado. Esta leitura **não é
   a rubrica** e **não foi às cegas**: eu conhecia a origem de cada fala.

## Rubrica: não se aplica

As falas são texto do dublê: frases de um banco fixo com injeções deliberadas. O dublê ignora instruções do prompt
(auditoria, fato 12), e o banco não tem tease nenhum (`test_simular_hora`). Notas de clareza, utilidade, coerência,
continuidade, naturalidade e precisão mediriam o dublê, não a F4. Este documento traz **só as checagens automáticas e
a leitura dirigida**. O item 5 do portão ("juiz: nenhuma dimensão abaixo da linha de base") continua **pendente**, como
na F2 e na F3.

**Pedido ao orquestrador: uma rodada `--modo llm` (S4 da auditoria).** Ela usa a Anthropic real, consome créditos e
**exige aprovação explícita do usuário**. Não foi rodada.

- **O que rodar:**
  - os três perfis com relógio, antes (`c382859`) e depois (`17f9cf9`);
  - semente 7, `PYTHONHASHSEED=0` e `--confirmo-custo`;
  - opcional: `--sem-inicio-previsto` e `--relogio-backend nenhum` na F4.
- **Custo estimado pelos contadores do fake:**
  - antes: 8 + 11 + 23 = 42 chamadas;
  - depois: 7 + 11 + 23 = 41;
  - sem relógio na F4: mais 11 + 29 + 31 = 71.
  - O cenário dedicado depende das injeções do dublê: não tem equivalente no modo `llm`.
- **O que medir:**
  - **Falsos positivos dos detectores com texto real** (o principal):
    - `promessa_sem_evento` com "a seguir", "na sequência" e "em seguida" em outro sentido;
    - `ouvinte_nao_autorizado` com palavra de inicial maiúscula em frase de participação;
    - `participacao_simulada`.
  - **Quantos teases legítimos o LLM faz** quando há linha de agenda, e quantos o validador remove (risco de o
    programa ficar sem chamada nenhuma).
  - **Contingência:** se o LLM a parafraseia e o código ainda insere a frase exata (duplicação); se ela se repete com o
    convite da própria fala (ver §2.3).
  - **Ações do validador:** `pedido_sem_mencao` (D10), cortes de oração "e também para…" e emendas depois de remoção.
  - **A rubrica**, com amostras embaralhadas e às cegas, dando atenção a continuidade, naturalidade e precisão.

## 1. Participação (foco da F4)

### 1.1 Números (régua do juiz = `resumo.json`)

Cada célula mostra as quatro variantes nesta ordem: com relógio / sem relógio / `voz_120` / painel antigo.

| Perfil | `pedido_indevido` | `ouvinte_inexistente` | Atendido antes de tocar | Participações legítimas no ar | Ouvintes reais citados no ar |
|---|---|---|---|---|---|
| musical_adulto | 1/1/1/1 → **0/0/0/0** | 0 → 0 | 1/1/1/1 → **0** | 0/0/0/0 → 0/**1**/0/0 | 1/1/1/1 → 0/1/0/0 |
| popular_sertanejo | 1/1/1/1 → **0/0/0/0** | 0 → 0 | 0 → 0 | 2/3/2/2 → 2/3/2/2 | 3/4/3/3 → 2/3/2/2 |
| variedades_leves | 3/4/3/3 → **0/0/0/0** | 1/1/1/1 → **0** | 2/3/2/2 → **0** | 0/0/0/0 → **2/3/2/2** | 2/3/2/2 → 2/3/2/2 |
| **Total (12 rodadas)** | **21 → 0** | **4 → 0** | **13 → 0** | **9 → 19** | **26 → 19** |

O cenário dedicado tem 0 indevido, 0 inexistente e 0 atendido antes de tocar. No popular, as duas participações
legítimas são as de Lurdinha Campos e Seu Ditinho.

**Leitura:**
- **Nenhuma fala da F4 cita ouvinte sem pedido.** A régua ampla, que pega nome inclusive no começo da frase, não achou
  nenhum nome desconhecido em frase de participação nas 14 rodadas.
- **Nenhuma mensagem foi simulada.** O único "chegou…" com pedido é o da F3 ("Chegou mensagem de Seu Ditinho"), e ele
  tinha pedido real.
- **"Toca agora" com nome só com o pedido do bloco em `selecionado`, e a faixa seguinte é a pedida.** São os casos:
  - Lurdinha Campos ("Café de Coador"): quatro variantes do popular e o cenário;
  - Paulo Brandão ("Patins Amarelos"): quatro variantes do variedades;
  - Joana Lis ("Farol Distante"): musical sem relógio.
  - Em todos, a confirmação (`executado`) veio depois de tocar. Exemplo: Paulo Brandão tocou em 1199,8 s e foi
    confirmado em 1475,6 s.
- **Nenhum pedido executado ficou sem o nome no ar:** D10 não precisou agir.
- **Não houve fala de volta a um ouvinte já atendido** (D8): o caso não aparece nas rodadas.

### 1.2 Os casos antigos: como sumiram

| Caso (F3) | Onde | O que aconteceu na F4 | Emenda ou fala sem sentido? | Perda de participação real? |
|---|---|---|---|---|
| **Dona Firmina** (injeção `cita_ouvinte`) | variedades: n6 com relógio, `voz_120` e painel antigo; n5 sem relógio | **Com relógio, `voz_120` e painel antigo:** a V2 removeu a última frase ("Um abraço também para Dona Firmina.", `ouvinte_nao_autorizado`), e a fala termina em "A conversa fica por aqui." (de −2,5 a −3 s, dentro do orçamento). **Sem relógio:** a reescrita única (V1) regenerou a chamada, que virou convite genérico ("Tem um recado guardado aí? Pode mandar pelo WhatsApp da Rádio Vila Ventura…"). | Não: a frase removida era a última, e não sobrou conectivo | Não: a ouvinte não existe |
| **Paulo Brandão**, **Cida Morais** (legado) | variedades, quatro variantes | O texto ficou igual. O pedido passou a `selecionado` com token e virou `executado` depois de tocar (D1). | — | Não. A participação continua no ar e passou a contar como legítima |
| **Seu Afonso** (legado) | variedades sem relógio, n25 | Idem: "Quem escreveu foi Seu Afonso…", agora `selecionado` → `executado` | — | Não |
| **Joana Lis** (legado, faixa indisponível) | musical: n12 com relógio, `voz_120` e painel antigo ("procurei a sua pedida e ela não está disponível por aqui"); n14 sem relógio ("toca agora Farol Distante") | **Com relógio, `voz_120` e painel antigo:** o pedido vira `nao_atendido` ("Música indisponível") antes da geração (D2), e o bloco vira só música, sem fala. **Sem relógio:** o texto ficou igual, com `selecionado` → `executado`. | Não: não há fala, e o formato musical dispensa a fala (regra 8) | **Sim, por decisão (D2):** o nome deixa de ir ao ar em 3 rodadas. Ver a ressalva abaixo |
| **Rosa Bezerra** (fluxo novo, música fora do acervo) | popular: n13, n19, n12 e n12 ("Recebi o seu pedido, Rosa Bezerra, mas essa música não está no acervo. Vai Estrada de Chão Batido…") | D2 nos quatro. **Com relógio, `voz_120` e painel antigo:** bloco só música. **Sem relógio:** anúncio normal da automática ("Com você, Neném do Cerrado, cantando Laço de Fita Amarela.") | Não: o anúncio é inteiro e não sobrou "para compensar" | **Sim, por decisão (D2):** 4 rodadas |

**Saldo da participação:**
- As 7 menções que deixaram o ar (Joana ×3, Rosa ×4) são todas de pedido de música que não ia tocar.
- Nenhuma participação legítima, isto é, pedido selecionado e executado, perdeu o nome no ar.
- As participações no estado correto subiram de 9 para 19, porque o legado agora confirma depois de tocar.
- Os pedidos que ficaram em fila no fim são os mesmos da F3:
  - Valdo Cunha, no popular com relógio, `voz_120` e painel antigo;
  - Seu Afonso, no variedades com relógio, `voz_120` e painel antigo.
  - A hora acabou antes; não é perda causada pela F4.

**Ressalva sobre a D2** (adotada por padrão, ainda **a confirmar** pelo usuário, segundo `f4/pendencias.md`):
- **Quem escreveu e teve o pedido recusado não ouve nada no ar.** A §10 da pesquisa pede "não anunciar execução
  imediata; manter status na fila". O texto da F3 ("procurei a sua pedida e ela não está disponível") não anunciava
  execução. O benchmark, porém, o rotula como indevido. A escolha é editorial e cabe ao usuário.
- **No musical com relógio, o motivo registrado não é verdadeiro.** "Farol Distante" está no acervo: tocou às 0:25 da
  mesma hora. A busca do pedido evita as faixas já tocadas (`evitar_video_ids=ids_tocadas`, `app/live/contexto.py:351-359`),
  e o pedido é fechado como "Música indisponível". A equipe vê um motivo que não corresponde ao fato, e o pedido sai da
  fila, em vez de ficar nela.
  - **Sugestão:** um motivo próprio ("já tocou nesta hora") e manter o pedido na fila para a próxima ocorrência.

### 1.3 Emendas e cortes

- **Emendas soltas causadas pela F4: 0.** Todas as remoções da F4 tiram uma frase inteira, que estava no fim da fala ou
  era a injeção depois da V1.
- O script aponta "E quando alguém de fora repara…" e "E ritual pequeno…" no comentário do variedades. São frases do
  banco do dublê e estão idênticas na F3, então não vêm de remoção.
- **O corte de oração ("e também para X") não foi exercitado** nas simulações: a injeção é uma frase isolada. Ele só
  tem cobertura nos testes U8 e I9. Isso fica para a bancada (§5, item 9).

## 2. Promessas (foco da F4)

### 2.1 Linha de base (três perfis × quatro variantes)

| Rodada | `promessa_vencida` F3 → F4 | `promessa_sem_registro` F4 | O que a régua do juiz achou no texto da F4 |
|---|---|---|---|
| musical (4 variantes) | 0 → 0 | 0 | só despedidas: "Obrigado e até logo.", "Até amanhã, no mesmo horário." e a vinheta "Amanhã tem mais." (D9, livres) |
| popular: com relógio / sem relógio / `voz_120` / painel antigo | 0/**1/1/1** → **0/0/0/0** | 0 | só despedidas ("até logo", "até a próxima") |
| variedades (4 variantes) | 0 → 0 | 0 | só despedidas ("até a próxima", "até amanhã") |

**Como a injeção "Daqui a pouco tem mais recado de ouvinte por aqui." sumiu:**
- **Sem relógio, `voz_120` e painel antigo:** a V1 reescreveu com a agenda, o dublê devolveu a injeção, e a V2 removeu a
  frase (`promessa_sem_evento`).
  - A fala inteira saiu nova: "Se quiser participar, manda sua mensagem para o WhatsApp da rádio…" e "Um alô especial
    para Seu Ditinho. Que bom ter você por perto…".
  - Seu Ditinho, o pedido do bloco, continua citado.
  - A fala ficou de 4 a 9 s mais curta e continua dentro do orçamento.
- **Com relógio:** como na F3, o encurtamento da identificação cortou a frase e entrou a reorientação neutra ("Você está
  na Rádio Ipê Dourado.").

**Teases cortados em excesso? Sem evidência nas saídas, e também sem como medir no fake.**
- O banco do dublê não tem tease, e a F3 também não tinha nenhum além da injeção.
- O que a F4 removeu é exatamente a injeção sem evento.
- Os convites de participação ("O WhatsApp da rádio está aberto…") continuam em todas as rodadas.
- No cenário dedicado, as três promessas com evento foram mantidas (§2.2).
- O risco de o LLM real deixar de chamar o que está agendado, por causa da regra mais dura no prompt, só aparece na
  rodada `llm`.

### 2.2 Cenário dedicado (S2)

| Perfil | Fala | Promessa ou injeção | Alvo | Desfecho | Conferência do juiz |
|---|---|---|---|---|---|
| popular | n5 `comentario` (779,6 s) | "Mais tarde a gente lê os recados de ouvinte." (fim) | `etapa:0:1620`, Retorno e participação | **cumprida** em n12 (1472,4 s): "Alô, Seu Ditinho, obrigado por escrever para a rádio. Abraço enviado, com carinho." | Pedido `selecionado` → `executado`, nome no ar, antes do prazo |
| popular | n10 `identificacao` (1437,1 s) | "Daqui a pouco tem mais recado de ouvinte por aqui." (injeção da fixture; curto) | o mesmo | **cumprida** em n12, 35 s depois | ok (ver a ressalva da identificação) |
| popular | n16 `comentario` | "Daqui a pouco tem receita de bolo." | nenhum | **removida** (`promessa_sem_evento`). A fala termina em "É assim que a gente vive." | Sem emenda; não foi registrada |
| popular | n20 `identificacao` | "Chegou agora uma mensagem de uma ouvinte pedindo um beijo para a mãe." | — | **removida** (`participacao_simulada`) | Sem emenda; 9,1 s, abaixo do mínimo de 15 s do orçamento (aceitável numa identificação) |
| musical | n6 `retomada` (772,4 s) | "Mais tarde a gente lê os recados por aqui." (fim) | `etapa:0:1620` | **cancelada com contingência** em n10 (1560,1 s), sem abraço na fila | A frase está no texto que foi ao ar; obrigação do relógio ativa de n7 a n10 |

Nas duas rodadas: 0 vencida, 0 aberta no fim, 0 registrada sem ir ao ar e 0 sem registro.

### 2.3 A fala de contingência

Texto que foi ao ar (musical, n10, 18,2 s de 10 a 20 s):

> "Ainda não chegou recado para ler agora; o WhatsApp da Rádio Serra Clara segue aberto. O WhatsApp da Rádio Serra
> Clara está aberto para o seu recado. Áudio curto também vale. Respira fundo, ajeita a cadeira e vem com a gente.
> Manda o seu."

**Coerência com a §10 da pesquisa: sim, no essencial.**
- Ela informa a mudança no lugar do conteúdo prometido.
- Não inventa ouvinte (§8, "Quando não há pedido").
- Não faz nova promessa nem diz "fica para depois".
- Mantém o canal aberto.
- Sai na etapa-alvo, antes do prazo.

**Dois problemas de texto, que não reprovam a F4:**
1. **Repetição em frases vizinhas.** O código insere a contingência no início (D5), e o convite seguinte repete a mesma
   ideia e o nome da rádio: "o WhatsApp da Rádio Serra Clara segue aberto. O WhatsApp da Rádio Serra Clara está
   aberto…". Numa fala de 18 s, quem ouve percebe a repetição.
   - **Sugestão:** quando a fala já tem convite, `garantir_contingencia` insere só a primeira oração ("Ainda não chegou
     recado para ler agora."). Outra saída é a frase de contingência terminar sem o convite.
2. **A frase afirma uma ausência.** "Ainda não chegou recado" pode ser falso quando chegou mensagem que não está
   aprovada ou que é de outro tipo.
   - Nesta mesma rodada, o pedido de Joana Lis chegou às 25:00, um minuto antes, e foi recusado no mesmo instante.
   - **Sugestão de texto original:** informar a mudança sem afirmar ausência. Por exemplo: "A leitura de recados não
     entra agora; o WhatsApp da Rádio Serra Clara segue aberto para você."

**Ressalva do cenário popular: a identificação que perdeu a identidade.**
- Texto: "Rádio. Daqui a pouco tem mais recado de ouvinte por aqui." Dura 4,55 s para um orçamento de 3 a 4 s (+13,7%,
  dentro da tolerância de 15%) e atrasa o intervalo em **2,02 s** (critério: 5 s).
- O fragmento "Rádio." é o mesmo artefato do encurtamento pelo dublê que a F3 resolveu com a fala neutra. Aqui, a
  promessa válida empurra a duração acima do mínimo, e a troca não acontece.
- **Resultado:** a vaga de identificação vai ao ar sem o nome da rádio, ocupada por um tease.
- **Sugestão:**
  - checagem de função na identificação: ela precisa conter a rádio ou o programa, independentemente da duração;
  - ou não aceitar promessa em fala com teto de poucos segundos (limiar em configuração).

## 3. Regressão: tempo, continuidade e chamadas

### 3.1 Tempo (F3 → F4)

| Rodada | `fora_orcamento_pct` | `estouro_max_pct` | Abaixo do mínimo | `atraso_hard_time_s` | Perdidos | Cortados (s) | Encerramento no ar | Fim antecipado (s, meta ≤ 60) |
|---|---|---|---|---|---|---|---|---|
| musical, com relógio | 0 → 0 | 0 → 0 | 1 → 1 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim | 8,47 → **37,44** |
| musical, painel antigo | 0 → 0 | 0 → 0 | 1 → 1 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim | 8,47 → **37,44** |
| musical, `voz_120` | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim | 5,8 → **25,3** |
| musical, sem relógio (formato) | 0 → 0 | 0 → 0 | 1 → 1 | — | 3 → 3 | 103,83 → 103,83 | não → não | — |
| popular, com relógio | 0 → 0 | 0 → 0 | 2 → 2 | 0,36 → 0,36 | 0 → 0 | 0 → 0 | sim → sim | 2,72 → 4,44 |
| popular, painel antigo | 0 → 0 | 0 → 0 | 2 → 1 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim | 4,38 → 3,13 |
| popular, `voz_120` | 0 → 0 | 0 → 0 | 1 → 1 | 12,1 → 12,1 | 0 → 0 | 0 → 0 | sim → sim | 73,16 → **0,86** |
| popular, sem relógio (observação) | 42,9 → 38,1 | 28,3 → 29,7 | 0 → 0 | — | 3 → 3 | 101,03 → **72,62** | não → não | — |
| variedades, com relógio | 0 → 0 | 0 → 0 | 2 → 1 | 0,18 → **0** | 0 → 0 | 0 → 0 | sim → sim | 3,32 → 2,08 |
| variedades, painel antigo | 0 → 0 | 0 → 0 | 2 → 1 | 0,18 → **0** | 0 → 0 | 0 → 0 | sim → sim | 3,32 → 2,08 |
| variedades, `voz_120` | 14,3 → **6,7** | 10,0 → 10,0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | sim → sim | 2,0 → 3,65 |
| variedades, sem relógio (régua da fixture) | 4,2 → 4,2 | 32,4 → 32,4 | 0 → 0 | — | 2 → 2 | 0 → 0 | sim → sim | — |
| cenário: popular / musical | 10 / 0 | 13,7 / 0 | 1 / 1 | **2,02** / 0 | 0 / 0 | 0 / 0 | sim / sim | 2,78 / 29,98 |

**Leitura:**
- **Com relógio e no painel antigo, os critérios da F1 a F3 continuam cumpridos:**
  - 100% das falas dentro do orçamento e nenhuma acima de 130%;
  - atraso máximo de 0,36 s (critério: 5 s);
  - encerramento no ar;
  - fim antecipado ≤ 60 s.
- O atraso de 12,1 s no popular `voz_120` é idêntico ao da F3: é o limite conhecido da voz sem calibração (F2).
- **Melhoras:**
  - popular `voz_120`: o fim antecipado cai de 73,16 s, que estava **acima** da meta, para 0,86 s;
  - variedades: hard time de 0,18 para 0 s;
  - variedades `voz_120`: fora do orçamento de 14,3% para 6,7%;
  - popular sem relógio: cortados de 101 para 73 s.
- **Piora, dentro da meta: o fim antecipado do musical** (com relógio e painel antigo: 8,5 → 37,4 s; `voz_120`: 5,8 →
  25,3 s).
  - **Causa:** sem a fala de Joana Lis (D2, −5,3 s), o relógio escolheu outras faixas. A última termina 37,6 s antes da
    passagem, e nenhuma cabe no espaço: os catálogos fictícios têm faixas de 187 a 285 s (`f1/pendencias.md`).
  - É a granularidade do catálogo, não um defeito da lógica da F4. Mesmo assim, são 37 s de "buraco" no fim da hora
    (F1, auditoria §5.5) que não existiam na F3.
- O estouro de observação do popular sem relógio (28,3 → 29,7%) vem de frases diferentes sorteadas pelo dublê. É só
  observação, e o formato padrão sem relógio é da F6.
- O cenário dedicado fica dentro dos critérios (2,02 s; 13,7% abaixo da tolerância de 15%). O custo é o da ressalva da
  §2.3.

### 3.2 Continuidade

- **`anuncio_sem_confirmacao`: 0 nas 14 rodadas da F4**, pela régua de catálogo da F3. Não há título fora do catálogo,
  artista sem título nem citada registrada fora do bloco.
- **Citações confirmadas: 31 → 28.** As 3 que faltam são "Vai Estrada de Chão Batido… no lugar da pedida", da fala de
  Rosa Bezerra, que saiu com a D2 no popular com relógio, `voz_120` e painel antigo. O validador não removeu nenhuma
  citação confirmada.
- **A ordem das faixas** só muda onde uma fala saiu ou foi regenerada:
  - no musical com relógio, `voz_120` e painel antigo, depois do bloco de Joana;
  - no popular `voz_120`: no fim da hora, uma faixa a mais ("Moreninha do Sítio") entra no lugar de duas reservas;
  - no variedades `voz_120`, na última faixa.
  - Nenhuma dessas faixas foi anunciada.

### 3.3 Chamadas de LLM e sínteses

- **No máximo 2 chamadas de LLM e 1 síntese por fala**, nas 14 rodadas. O invariante é de 2 e 2.
- O popular no painel antigo passa de 1 para 2 no máximo, por causa da V1 da promessa.
- **Total nas 12 rodadas: 188 → 186.**
  - Musical: 8 → 7 em três variantes, porque a fala de Joana saiu.
  - Popular sem relógio: 27 → 29 (V1 da promessa e revisões de duração das falas regeneradas).
  - Popular `voz_120`: 12 → 9.
  - Variedades: sem relógio 30 → 31; `voz_120` 17 → 18.
- **Média por fala:** de 1,00 a 1,28 na F3 e de 1,10 a 1,33 na F4.
- **Falas:** 155 → 149.

### 3.4 Outras checagens

- `abertura_repetida` 0 e `silencio_s` 0 em todas as rodadas, sem sobreposição.
- Pausa editorial: de 1,7 a 5,4 s, como na F3.
- Nenhuma fala vazia e nenhuma de até 3 palavras.
- Agradecimento genérico a "quem mandou recado" só aparece em rodadas em que houve recado lido.
- `aviso_oralidade`: não se aplica, porque `app/live/oralidade.py` ainda não existe (F7).

## 4. Conferência dos `resumo.json`

Rodei a régua do juiz nos **26 arquivos**: 12 da F3, 12 da F4 e 2 do cenário. Os 26 batem em:
- `fora_orcamento_pct`, `estouro_max_pct`, `atraso_hard_time_s`, `hard_times_perdidos`, `segundos_cortados`,
  `encerramento_no_ar`;
- `anuncio_sem_confirmacao`, `promessa_vencida` e `pedido_indevido`;
- `abertura_repetida`, `silencio_s`, `validacao_fala.acoes`;
- `ouvinte_inexistente`, `pedidos.atendidos_antes_de_tocar`;
- e, na F4, `promessa_sem_registro` e `promessas.{registradas, cumpridas, canceladas_com_contingencia, vencidas,
  abertas_no_fim}`.

Na primeira passada, a régua do juiz acusou a contingência "Ainda não chegou recado…" como mensagem simulada. O falso
positivo era da régua: corrigi a negação e refiz a contagem.

**Diferenças de definição, não de resultado:**
- `validacao_fala.regras` conta cada violação da F4 **duas vezes** por remoção (fase "pre" e fase "final"). Exemplos:
  `promessa_sem_evento: 2`, `ouvinte_nao_autorizado: 2`, `participacao_simulada: 2`. A lista `violacoes` do evento
  também traz a entrada repetida. As ações (`acoes`) estão certas: uma por fala.
  - **Sugestão:** deduplicar por (regra, trecho) antes de contar.
- `falas_abaixo_minimo` do resumo vale 0 nas 26 rodadas, inclusive na F3. Pela régua do juiz (duração menor que o
  mínimo do orçamento aplicado): 12 na F3 e 9 na F4, mais 1 em cada cenário. Não houve piora; o nome da métrica do
  simulador é que não diz o que ela conta.

## 5. Achados para frentes futuras

Sem nota, porque a rubrica não se aplica. As sugestões são originais e não imitam nenhum radialista.

1. **D2 a confirmar pelo usuário** (§1.2). Ela tira do ar 7 menções a ouvintes reais em 12 rodadas. No musical, fecha
   como "Música indisponível" um pedido de faixa que existe e só já tinha tocado.
   - **Sugestão:** um motivo próprio ("já tocou nesta hora") e manter o pedido na fila para a próxima ocorrência, como
     diz a §10.
2. **Contingência inserida pelo código** (§2.3):
   - evitar a repetição com o convite da própria fala;
   - não afirmar ausência ("não chegou recado") quando pode ter chegado mensagem não aprovada;
   - na rodada `llm`, medir a duplicação quando o LLM parafraseia a frase e o código ainda insere a exata.
3. **Identificação sem identidade** (cenário popular, §2.3). Falta checagem de função: a identificação precisa citar a
   rádio ou o programa. O fragmento "Rádio." continua no ar quando outra frase empurra a duração acima do mínimo. É da
   F3 residual ou da F7.
4. **Buraco no fim da hora no musical** (37 s, dentro da meta). Vigiar na F11, com catálogo real e peça de reserva de
   duração variável.
5. **Contagem dupla em `validacao_fala.regras`** (§4).
6. **Promessa e participação marcadas na geração, não na reprodução** (pendência registrada). Um bloco que não vai ao
   ar pode registrar ou resolver uma promessa. É da F11.
7. **Legado `selecionado` sem confirmação** fica preso até a equipe reenfileirar (pendência registrada). Sugestão:
   expirá-lo ao abrir outra ocorrência (F11/F12).
8. **Reserva do painel** `useLiveEngine.ts:1358` ainda diz "ja volto com mais uma novidade" (pendência registrada).
   É uma promessa sem evento fora do alcance do validador.
9. **Evidência estreita no simulador.**
   - Dona Firmina é uma frase isolada no fim da fala; a promessa também.
   - **Sugestão para a bancada:** injeções com o nome no meio da frase ("Um abraço para Cida Morais e também para a
     Dona Firmina"), no começo ("Dona Firmina mandou…") e no multivoz. Promessa com "a seguir" em sentido não temporal.
     Pedido recente do legado (D7). Ouvinte já atendido citado de novo (D8).

## Veredito

**APROVADO** nas checagens automáticas. A rubrica fica pendente de uma rodada `--modo llm`, que exige aprovação do
usuário.

**Por quê:**
- Pela régua independente do juiz, nas 12 rodadas da F4 e no cenário dedicado:
  - `pedido_indevido` cai de 21 para 0;
  - ouvinte inexistente cai de 4 para 0;
  - atendido antes de tocar cai de 13 para 0;
  - `promessa_vencida` cai de 3 para 0;
  - `anuncio_sem_confirmacao` continua 0.
- Toda promessa detectável no texto que foi ao ar tem evento-alvo e desfecho: 2 cumpridas e 1 cancelada com
  contingência no ar. As demais são despedidas permitidas.
- Nenhuma emenda solta.
- As participações legítimas no ar sobem de 9 para 19. Nenhum pedido selecionado e executado perdeu o nome.
- Com relógio, os critérios de tempo da F1 a F3 continuam cumpridos, e as chamadas ficam em no máximo 2 por fala.
- Os 14 as-runs da F4 se reproduzem byte a byte, e os 26 resumos batem com a régua do juiz.

**Ressalvas que não bloqueiam:**
- a D2 tira do ar 7 menções a pedidos recusados, e um deles tem motivo impreciso (item 1);
- a contingência repete o convite e afirma uma ausência (item 2);
- no cenário dedicado, a identificação vai ao ar só com "Rádio." e atrasa o hard time em 2,02 s (item 3);
- o fim antecipado do musical sobe para 37 s, ainda dentro da meta de 60 s (item 4);
- a evidência no fake é estreita, e os falsos positivos dos detectores com texto real não foram medidos (item 9 e
  rodada `llm`).

APROVADO
