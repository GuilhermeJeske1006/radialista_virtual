# Referência Talkplay / Manhã Play: análise e proposta para o Locufy

A principal característica a reproduzir é a proporção entre música e locução: uma sequência musical longa, identificada por vinhetas curtas, com intervenções pontuais da apresentadora. A prioridade proposta é criar um perfil de programa musical de companhia, com tempo de fala controlado, continuidade entre faixas e identidade sonora consistente.

## Método e limites

Arquivo: `talkplay_manhaplay_bloco_01.mp3.mpeg`, fornecido pelo usuário. Duração: **34min18s**. Análise do arquivo integral com FFmpeg e transcrição local, seguida de nova transcrição de seis janelas de fala. A inferência foi executada no computador, com o modo offline ativado, usando [Whisper no MLX](https://github.com/ml-explore/mlx-examples/tree/main/whisper) e o modelo small. A tentativa anterior de envio para a integração de STT do projeto foi bloqueada antes do upload; nenhum resultado veio desse serviço.

Esta é uma análise estrutural e técnica apoiada em reconhecimento de fala, sem avaliação perceptiva direta do timbre. O reconhecimento apresentou erros e repetições sobre as músicas e algumas vinhetas; esses trechos não foram interpretados como falas reais, nem usados para avaliar repetição do roteiro. As marcações abaixo são aproximadas. Não há medição exata da proporção fala/música nem da separação entre vozes. A informação de que o programa foi produzido por IA vem do usuário.

O código local foi consultado para identificar possibilidades e limitações do Locufy; não foi realizada uma nova gravação do sistema nem uma comparação auditiva entre os programas. Nenhuma configuração ou código de produção foi alterado nesta análise.

## O que caracteriza a referência

| Tempo aproximado | Conteúdo reconhecido | Aplicação no Locufy |
| --- | --- | --- |
| 00:00–00:13 | Identificação de início, nome do programa e assinatura | Abertura com identidade sonora própria |
| 00:13–00:41 | Apresentadora se identifica como Marcela, acolhe o ouvinte e apresenta a seleção musical | Uma abertura principal que estabelece o clima do programa |
| 05:18–05:24 | Vinheta com nome e assinatura do programa | Identificar a sequência sem exigir uma fala longa |
| 13:34–13:42 | Vinheta associada a clássicos e viagem no tempo | Variantes curtas dentro da mesma identidade |
| 16:35–16:44 | Retomada breve, acolhimento e identificação da rádio | Presença da apresentadora em cerca de nove segundos |
| 26:52–26:59 | Vinheta sobre sucessos de diferentes gerações | Reforçar o perfil musical durante a sequência |
| 33:56–34:12 | Comentário sobre a música e chamada para uma breve interrupção | Saída de bloco, preservando a expectativa de retorno |
| 34:12–34:18 | Vinheta de fechamento | Encerrar o bloco com acabamento sonoro |

As três intervenções principais reconhecidas duram aproximadamente **28 s, 9 s e 16 s**. O restante inclui música e identificações. Os limites de algumas vinhetas variaram entre as duas transcrições; a tabela serve como mapa de referência, não como lista de cortes prontos para edição.

O roteiro estabelece companhia para trabalho, deslocamento e começo do dia; apresenta clássicos e sucessos, e retoma a marca sem desenvolver longos assuntos. Nos trechos falados identificados não aparece uma conversa entre apresentadores. Portanto, ampliar diálogos não é a primeira mudança para reproduzir este exemplo.

## O que melhorar também em relação à referência

Algumas expressões reconhecidas têm registro formal ou genérico: “eleve ligeiramente o volume”, “grata por estar com a gente” e “peças como essa”. Para um programa de companhia, proponho uma linguagem mais direta, com frases que a pessoa diria numa conversa.

Exemplo de abertura original para o Locufy, usando nomes fictícios:

> Bom dia! Eu sou a Ana e está começando o Manhã Musical. Pra quem já está no trabalho, no caminho ou começando o dia em casa: vem com a gente. Tem uma sequência de clássicos chegando, aqui na Rádio Exemplo.

Exemplo de retomada curta:

> Você está no Manhã Musical. Bom ter a sua companhia! A sequência de clássicos continua aqui na Rádio Exemplo.

Exemplo de saída, condicionado a existir outro bloco preparado:

> A gente faz uma pausa e já volta com mais música. Continue com a gente, aqui na Rádio Exemplo.

Evitar emendar adjetivos como “incrível”, “memorável” e “inesquecível” em toda intervenção. Quando houver metadados confiáveis, uma informação simples sobre a faixa ou uma ligação com o momento do ouvinte dá mais conteúdo à fala. Não inventar pedidos, participações, clima, fatos sobre artistas nem um retorno que não esteja programado.

## Proposta em ordem de prioridade

### 1. Perfil “musical de companhia” com orçamento de fala

Separar as funções de abertura, retomada, anúncio musical, vinheta e saída de bloco. Hoje, o caminho de voz única pede genericamente quatro a seis frases em `backend/app/live/router.py:1715`. Isso não representa a retomada de nove segundos encontrada na referência.

Faixas iniciais propostas para um piloto, não medidas universais:

- Abertura: 20–30 segundos de locução, além da identificação inicial.
- Retomada: 6–12 segundos, uma ou duas frases.
- Anúncio de faixa: 4–8 segundos, apenas quando acrescentar algo.
- Vinheta: 3–7 segundos, com algumas variantes da mesma identidade.
- Saída de bloco: 10–18 segundos.
- Presença do apresentador guiada pelo relógio do programa, evitando uma fala obrigatória antes de cada música.

Planejar primeiro um bloco de 30–35 minutos com as durações reais das faixas. Reservar espaço para abertura, retomada, saída e vinhetas; distribuir a música no tempo restante. A lista atual de `estrutura_blocos` e o suporte a várias músicas por bloco oferecem parte dessa base. O complemento necessário é planejar e validar a duração, em vez de apenas percorrer categorias em loop.

A faixa de palavras deve ser estimada a partir da velocidade medida da voz escolhida. Depois da síntese, conferir a duração real e encurtar o texto quando ultrapassar o limite. Evitar acelerar artificialmente o áudio para compensar excesso de roteiro.

### 2. Continuidade de reprodução e transições intencionais

O código possui duas esperas cumulativas: `intervalo_ms` de 900–3400 ms, conforme a transição, e uma pausa adicional de 350–600 ms no player. Ver `backend/app/live/router.py:522`, `frontend-painel/hooks/useLiveEngine.ts:30`, `:996` e `:1076`. A presença da cama musical significa que essas esperas não são necessariamente silêncio absoluto; ainda assim, podem alongar a passagem entre conteúdos.

Proponho um único controle da transição, baseado no conteúdo que está terminando e no próximo item. Testar intervalos curtos nas emendas musicais e preservar pausas maiores apenas quando houver intenção editorial. Não zerar todas as pausas indiscriminadamente.

Também há um detalhe de semântica: o backend calcula `intervalo_ms` a partir do bloco anterior e do atual, mas o frontend o aplica depois do atual. Revisar esse contrato para que o intervalo descreva a transição em que será efetivamente usado.

Os fades e o preparo antecipado já existem. O ganho esperado está em coordená-los. Locução sobre introdução musical pode entrar numa segunda etapa, apenas com pontos de entrada conhecidos e evitando sobreposição com o canto. O fluxo atual de anúncio seguido de música é sequencial; esse encaixe exige suporte explícito no player.

### 3. Vinhetas e cama musical como parte do programa

Preparar uma família pequena de vinhetas: abertura, identificação curta, passagem e saída. Variar o texto mantendo a mesma assinatura musical e o mesmo padrão de volume. O Locufy já possui biblioteca de áudio e blocos de vinheta; aproveitar esses recursos.

Durante diálogos opcionais, manter a cama baixa durante o conjunto de falas. Hoje, `reproduzirAudioPreparado` manda baixá-la no início e subi-la no fim de cada clipe (`frontend-painel/hooks/useLiveEngine.ts:368–425`), inclusive nas linhas sucessivas. Isso cria condições para oscilação de volume entre interlocutores; o efeito audível precisa ser verificado.

Nos programas musicais, controlar a relação entre voz, cama, vinheta e faixa principal com amostras reais. Os valores atuais de volume do player, 18 e 6, não garantem a mesma relação de intensidade para arquivos diferentes.

### 4. Direção vocal por função, com validação auditiva

Manter uma apresentadora ou um apresentador principal estável para este formato; reservar as outras vozes para identidade sonora ou quadros que peçam diálogo. Abertura acolhedora, retomada breve e saída de bloco precisam de intenções diferentes, sem exigir energia máxima o tempo todo.

O projeto já tem ajustes de voz por tipo de bloco. Avaliar inicialmente a voz existente com textos mais curtos e direção mais precisa. Só decidir uma troca de modelo depois de ouvir os mesmos textos, na mesma voz e com volumes equiparados. O benchmark anterior mede latência e preservação do texto, mas não demonstra equivalência de expressividade.

O perfil `radio_fm` já mantém ruído artificial, variação aleatória de afinação e reverb desligados. Não há evidência nesta referência que justifique ligá-los para simular naturalidade.

### 5. Acabamento do programa completo

| Medida no arquivo original integral | Resultado |
| --- | --- |
| Formato | MP3 estéreo, 44,1 kHz, 320 kb/s |
| Loudness integrado | −8,92 LUFS |
| Faixa de loudness | 1,80 LU |
| Pico verdadeiro estimado | +0,06 dBTP |
| Silêncios detectados abaixo de −40 dB por pelo menos 0,5 s | Nenhum |

A referência tem intensidade alta e pouca variação de loudness. Não copiar automaticamente esse nível: o pico deixa praticamente nenhuma margem, e aumentar o volume pode enviesar uma comparação de qualidade. Nenhum silêncio detectado não significa ausência de pausas na locução, já que música e efeitos também compõem o sinal.

O perfil do Locufy mira −16 LUFS e −2 dBTP **na voz**; a referência foi medida **na mistura completa**. Portanto, não há base para afirmar que o programa do Locufy é exatamente sete decibéis mais baixo. A melhoria proposta é medir também a saída completa e a consistência entre voz, músicas e vinhetas, conforme o destino de reprodução.

## Piloto recomendado e critérios de avaliação

Produzir um bloco de 30–35 minutos com seleção musical coerente, uma abertura, uma retomada central, vinhetas espaçadas e uma saída. A grade exata deve respeitar a duração das faixas disponíveis. Preparar as falas antes da reprodução, usando o mecanismo de antecipação já existente.

Comparar o piloto com a referência em volume percebido equivalente. Avaliar:

1. Se a voz cabe nos tempos definidos e transmite companhia sem excesso de texto.
2. Se músicas e identificações mantêm continuidade, sem palavras cortadas ou esperas injustificadas.
3. Se a relação entre voz e música permite entender a locução sem grandes saltos de volume.
4. Se os nomes, números e títulos são pronunciados corretamente.
5. Se as retomadas variam e preservam a identidade do programa.
6. Se a saída corresponde ao que realmente vai tocar depois.

Aumento do número de falas em diálogos fica para outro perfil de programa. No código atual, o prompt limita o diálogo a duas a quatro linhas (`backend/app/llm/prompt_builder.py:380`), mas mudar esse limite não é necessário para reproduzir o formato desta referência.

## Evidências locais

Arquivos de trabalho em `/tmp/locufy-talkplay-analysis/`: `metadata.json`, `measurements.json`, `silence.log`, `transcript-local.json`, `speech-verified.json` e os seis recortes de conferência. A transcrição integral contém erros sobre canto e não deve ser usada como roteiro ou transcrição editorial publicada. O áudio original permanece intacto.
