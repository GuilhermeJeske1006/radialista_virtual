# Locufy — Plano de humanização da fala

Nov 20, 2026 · @Guilherme

## Objetivo

Fazer o locutor virtual soar como uma pessoa falando no rádio, e não como um chatbot lendo um texto escrito. O plano usa os padrões do guia [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) da Wikipedia, adaptados para fala em PT-BR, em três frentes:

1. **Gerar melhor**: prompt de persona com regras de oralidade e contexto concreto da rádio (módulos `llm` e `live`).
2. **Barrar o que escapar**: um detector de sinais de IA, com reescrita automática antes do áudio sair (`guardrails`).
3. **Falar como gente**: o texto passa a ser preparado para a voz, não para a leitura (`tts`).

Meta da primeira fase: zero vazamentos graves no ar (placeholder, recusa, markdown, frase de chatbot) e queda de 50% na pontuação média de sinais de IA em um conjunto fixo de testes.

## Contexto: onde a fala soa como IA

O guia da Wikipedia trata de texto escrito em inglês. No Locufy, o mesmo vício aparece em dois canais, e os dois têm custos diferentes:

- **No ar (LLM → ElevenLabs)**: o ouvinte não vê o texto, só ouve. Erros de formatação viram áudio estranho ("asterisco", emoji lido, colchete de placeholder). Frases longas e enumerações cansam mais ditas do que lidas. A repetição de bordões ao longo de horas é o sinal mais perceptível.
- **WhatsApp (respostas ao ouvinte)**: aqui o texto é lido. O risco é o tom de atendimento automático ("Olá! Que ótimo receber sua mensagem! 😊"), listas, negrito e fechamentos prontos.

Nos dois canais, o maior sinal de humanidade é o mesmo que a Wikipedia aponta: especificidade. Um locutor de verdade cita o nome do ouvinte, o bairro, a música que acabou de tocar, a chuva lá fora. Uma IA sem esse contexto preenche o vazio com adjetivos.

## Padrões aplicáveis ao Locufy

Dos cerca de 60 padrões do guia, 18 se aplicam a um locutor de rádio. A coluna Gravidade define a ação do guardrail: **bloqueio** impede o áudio, **reescrita** dispara uma segunda geração e **pontuação** só soma na nota.

| Padrão (Wikipedia) | Como aparece no Locufy | Ação | Gravidade |
| --- | --- | --- | --- |
| Placeholders e frases-modelo | "Um abraço para \[NOME DO OUVINTE\]", "\[INSERIR DATA\]" | Regex de colchetes e maiúsculas; nunca vai ao ar | Bloqueio |
| Recusa do modelo | "Desculpe, não posso ajudar com isso" lido no ar | Detectar e trocar por fala de transição segura | Bloqueio |
| Data de corte do conhecimento | "Segundo minhas informações até 2025…" | Proibir no prompt; detector | Bloqueio |
| Markdown e erros de marcação | Asteriscos, #, listas e links que o TTS lê em voz alta | Remover antes do TTS; proibir no prompt | Bloqueio no ar |
| Comunicação dirigida ao usuário | "Espero ter ajudado!", "Posso ajudar em algo mais?", "Como IA…" | Lista de frases proibidas + reescrita | Reescrita |
| Ressalvas e hedging | "É importante lembrar que…", "Vale ressaltar…" | Léxico + reescrita | Reescrita |
| Ênfase exagerada em importância e legado | "Um marco histórico para nossa cidade", "um verdadeiro testemunho" | Léxico + regra no prompt | Reescrita |
| Linguagem promocional e publicitária | Patrocínio lido como folheto: "ambiente aconchegante e moderno" | Roteiro de patrocínio com fatos concretos | Reescrita |
| Vocabulário de IA | "Além disso", "crucial", "vibrante", "mergulhar", "jornada" | Léxico ponderado (seção abaixo) | Pontuação |
| Paralelismo negativo | "Não é apenas música, é emoção" | Regex "não (é )?(apenas\|só)… mas" | Pontuação |
| Regra de três | "Alegria, energia e muita música" em toda fala | Contar tríades por fala | Pontuação |
| Evitar o verbo "é" | "Se destaca como", "representa", "serve como" | Léxico | Pontuação |
| Atribuições vagas | "Muita gente diz que…", "especialistas apontam…" | Exigir fonte (jornal, órgão) ou cortar | Reescrita |
| Análise superficial com gerúndio | "…, reforçando a importância de…", "destacando…" | Regex de gerúndio no fim de frase | Pontuação |
| Conclusão-resumo | "Em resumo…", "Desafios e perspectivas" no fim de cada bloco | Proibir fechamento-resumo | Pontuação |
| Emojis e negrito | Emoji no WhatsApp a cada frase; negrito em palavras soltas | No ar: remover. No WhatsApp: no máximo 1 emoji, conforme o tom | Pontuação |
| Travessões em excesso | Travessão vira pausa estranha no TTS | Trocar por vírgula ou ponto na normalização | Pontuação |
| Variação elegante | "A canção… a faixa… o hit… a obra" na mesma fala | Detector de sinônimos em sequência | Pontuação |

O padrão "mudança brusca de estilo" vira um item próprio: a memória de repetição (módulo `live`), que compara a fala atual com as últimas horas.

## O que não corrigir

A Wikipedia lista indicadores que **não** provam uso de IA. Eles valem como trava contra a correção exagerada:

- **Gramática correta e tom formal**: o modo formal de uma rádio de notícias é legítimo. O detector não pode punir formalidade, só os vícios.
- **Palavras de transição isoladas**: um "além disso" sozinho não é problema. O peso vem da densidade e da repetição.
- **Mistura de casual e formal**: é natural no rádio e não deve ser corrigida.

O guia também avisa que corrigir só a superfície (trocar palavras) esconde o problema sem resolvê-lo. Por isso o plano prioriza contexto concreto no prompt, e não apenas uma lista negra.

Descartados por não se aplicarem: citações, DOI e ISBN, wikitexto, resumos de edição, revisão AfC, páginas de usuário e permissões.

## Mudanças por módulo

O fluxo de cada fala passa a ser: contexto → geração → detector → (reescrita, no máximo 1 vez) → normalização para voz → TTS. Se a reescrita falhar, entra uma fala curta de transição, nunca o texto ruim.

### `llm`: prompt de persona falada

- Reescrever o system prompt como um guia de estilo de locução, não de redação. Regras: frases de até 15 palavras, uma ideia por frase, falar com uma pessoa ("você"), sem listas nem markdown, sem fechamento-resumo.
- No modo informal, permitir oralidade: "tá", "pra", "a gente", "olha só". No modo formal, manter a norma culta, mas com frases curtas.
- Incluir de 3 a 5 exemplos de pares ruim → bom por tipo de fala (recado, pedido de música, aniversário, previsão do tempo, patrocínio).
- Proibir no prompt as frases de chatbot e o léxico de alto peso (seção abaixo).
- Variar a abertura: passar ao modelo as 5 últimas aberturas usadas, com a instrução de não repetir.

### `live`: contexto concreto e memória de repetição

- Injetar em toda geração: hora local, dia da semana, clima, música anterior e próxima, nome e bairro do ouvinte (quando houver) e um evento local do dia.
- Guardar no Redis as falas das últimas 3 horas por rádio. Medir as aberturas, os fechamentos e os bordões repetidos.
- Limitar cada bordão a no máximo 1 vez a cada 30 minutos (valor configurável por rádio).

### `guardrails`: detector de sinais de IA

- Detector determinístico (regex + léxico, sem chamada de LLM) que devolve uma nota de 0 a 100 e a lista de violações.
- Bloqueios: placeholder, recusa, data de corte, markdown no texto para o ar.
- Acima de um limite (sugestão inicial: 30), pedir reescrita ao modelo, enviando as violações específicas ("remova 'além disso' e o fechamento 'espero que tenham gostado'").
- Registrar nota e violações de cada fala para medição.

### `tts`: texto preparado para a voz

- Normalizar antes do ElevenLabs: remover emojis e markdown; trocar travessão por vírgula; escrever por extenso horários, telefones, preços e siglas ("18h30" → "seis e meia da tarde"; "R$ 19,90" → "dezenove e noventa").
- Usar pausas curtas entre ideias (tags de pausa do ElevenLabs) e evitar parágrafos longos em uma única chamada.
- Ajustar `stability` e `style` por tom: estabilidade menor no modo informal, para dar mais variação de entonação.

### `whatsapp`: respostas ao ouvinte

- Responder primeiro e cumprimentar depois, se for o caso. Máximo de 2 frases curtas.
- Espelhar o registro do ouvinte: se ele escreve "kkk vlw", a resposta pode ser leve.
- Sem listas e sem negrito. No máximo 1 emoji, e só se o ouvinte usou algum.
- Proibir: "Olá! Que ótimo receber sua mensagem!", "Fico à disposição", "Posso ajudar em algo mais?".

### `patrocinadores`: leitura comercial sem tom de folheto

- Cadastro do patrocinador com fatos, não adjetivos: endereço, oferta da semana, horário, diferencial concreto.
- Prompt de patrocínio: 1 fato + 1 chamada para ação, no máximo 1 adjetivo por frase.
- Rodar de 3 a 4 estruturas de leitura diferentes para o mesmo patrocinador.

### `config` e `onboarding`: guia de estilo por rádio

- No onboarding, coletar nome do locutor, bordões permitidos, gírias regionais, palavras proibidas e 2 ou 3 trechos de locução real da rádio para usar como exemplo de estilo.
- No painel: controle de tom (formal ↔ informal), limite de repetição de bordões e lista de palavras proibidas editável.

## Léxico inicial de alerta (PT-BR)

Ponto de partida com equivalentes em português do vocabulário de IA do guia, mais vícios comuns de chatbot em PT-BR. Os pesos devem ser calibrados com as falas reais do sistema.

| Categoria | Expressões | Peso |
| --- | --- | --- |
| Fala de chatbot | "espero ter ajudado", "fico à disposição", "posso ajudar em algo mais", "ótima pergunta", "como inteligência artificial" | 25 |
| Importância inflada | "um verdadeiro testemunho", "marco histórico", "papel fundamental", "legado duradouro", "rica herança cultural" | 10 |
| Ressalvas | "é importante ressaltar", "vale ressaltar", "vale destacar", "é fundamental lembrar" | 8 |
| Conectivos de redação | "além disso" (no início da frase), "ademais", "outrossim", "nesse sentido", "em suma", "em resumo" | 5 |
| Vocabulário de IA | "crucial", "vibrante", "mergulhar", "jornada", "cenário" (sentido abstrato), "tapeçaria", "robusto", "intrínseco", "sublinhar", "potencializar", "fomentar" | 4 |
| Evitar o "é" | "se destaca como", "se configura como", "representa", "serve como", "se posiciona como" | 3 |
| Folheto publicitário | "ambiente acolhedor", "experiência única", "de tirar o fôlego", "qualidade e excelência" | 4 |

A nota soma os pesos e é dividida pelo tamanho da fala (por 100 palavras), para não punir falas longas. Cada rádio pode acrescentar termos pelo painel.

## Como medir

- **Conjunto fixo de testes**: 60 entradas (10 por tipo: recado, pedido de música, aniversário, clima e trânsito, patrocínio, resposta no WhatsApp), nos tons formal e informal. Rodar a cada mudança de prompt, como teste de regressão.
- **Nota média do detector** nesse conjunto, antes e depois de cada fase.
- **Vazamentos graves no ar**: contagem semanal de bloqueios em produção. A meta é que todos sejam barrados (zero no ar).
- **Taxa de repetição**: percentual de falas com abertura ou bordão repetido em uma janela de 3 horas.
- **Teste cego**: 20 falas do Locufy misturadas a 20 de locutores humanos, avaliadas por pessoas da equipe de uma rádio cliente. A meta é acerto perto de 50%, ou seja, não conseguirem diferenciar.
- **Sinal do cliente**: quantas falas o operador da rádio pula ou edita manualmente no painel.

## Fases e entregas

São três fases em cerca de 5 semanas. A fase 1 é a que mais reduz risco, porque elimina o que é constrangedor no ar.

| Fase | Duração estimada | Entregas | Critério para avançar |
| --- | --- | --- | --- |
| 1. Travas e prompt | 1 semana | Bloqueios no `guardrails` (placeholder, recusa, markdown); normalização no `tts`; novo system prompt com exemplos; frases proibidas no WhatsApp | Zero vazamentos graves no conjunto de testes |
| 2. Detector e memória | 2 semanas | Nota de sinais de IA com reescrita; léxico PT-BR; memória de repetição no Redis; contexto concreto no `live`; roteiro de patrocínio | Nota média 50% menor que a da linha de base |
| 3. Personalização e medição | 2 semanas | Guia de estilo por rádio no onboarding; controles no painel; teste cego; registro de notas e edições manuais | Teste cego com acerto entre 40% e 60% |

Antes da fase 1: rodar o conjunto de testes com o sistema atual para ter a linha de base.

## Riscos e pendências

- **Código não revisado**: o plano parte da descrição do projeto e da lista de módulos. O repositório `radialista_virtual` não estava acessível nesta sessão. Próximo passo: ler o prompt atual e o `guardrails` existente para ajustar nomes e pontos de integração.
- **Latência no ao vivo**: a reescrita adiciona uma segunda chamada ao Claude. Mitigação: detector local (sem LLM), modelo rápido para a reescrita e fala de transição pronta como reserva.
- **Correção exagerada**: proibir palavras demais deixa a fala sem sabor. Mitigação: pesos baixos para palavras isoladas e revisão mensal do léxico.
- **Custo do TTS**: falas reescritas ou partidas em blocos aumentam as chamadas ao ElevenLabs. Medir na fase 2.
- **Pergunta aberta**: o modo formal deve aceitar contrações como "pra" e "tá"? Definir com as primeiras rádios clientes.

Fonte: [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), consultada em 20/11/2026.
