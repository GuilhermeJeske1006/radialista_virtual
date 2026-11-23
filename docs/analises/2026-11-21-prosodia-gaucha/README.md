# Plano e validação da prosódia e das gírias gaúchas

21/11/2026. Código inspecionado: `2ee8b28`, com as alterações locais existentes preservadas.

A prioridade é fazer a voz padrão interpretar gírias gaúchas, pontuação e mudanças de emoção com naturalidade. A inspeção confirmou limitações no caminho que transforma a intenção editorial em parâmetros e tags de voz. Elas justificam corrigir a integração antes de aumentar indiscriminadamente a quantidade de exclamações, gírias ou efeitos no áudio. A contribuição de cada limitação para o problema ouvido continua sendo uma hipótese até a comparação auditiva.

**Validação concluída:** 191 testes técnicos passaram e 96 payloads foram inspecionados sem rede. **Validação pendente:** pronúncia gaúcha, preferência humana e expressividade do áudio. Nenhuma síntese paga foi executada e nenhum comportamento da aplicação foi alterado.

## Escopo e relação com o plano existente

O usuário confirmou problema na **voz padrão do catálogo**, especialmente com **gírias gaúchas**. O nome da voz, o modelo efetivo e as preferências da conta em que ouviu o problema ainda precisam ser identificados. O catálogo possui Paulo, Will, Yasmin Alves e Scheila; a descrição em português brasileiro não certifica interpretação gaúcha. A seleção por conta e por voz pode sobrescrever o modelo padrão do servidor.

Este trabalho complementa [o plano de humanização](../../plano-humanizacao-fala.md), sem substituir suas frentes H0–H9. Esse plano trata principalmente do texto, de repetições e de sinais de chatbot, e se baseia em outro commit. Para a queixa atual, antecipar uma avaliação específica de áudio e a revisão das capacidades dos modelos. Melhorar a nota de um detector de texto ou passar em testes com respostas simuladas não comprova melhoria da locução.

## Evidências e hipóteses

| Achado confirmado no código | Evidência | Implicação para o plano |
|---|---|---|
| Flash recebe o mesmo perfil para calmo e enérgico; suas tags são removidas | `backend/app/tts/client.py:242–244,310–312`; sondagem com jitter zerado confirma payloads idênticos para o mesmo texto | A direção por esses parâmetros não diferencia a emoção nesse caminho. A pontuação e o texto ainda podem influenciar o resultado. |
| v4 e v4 Turbo recebem `speed` e `style`, mas perdem `similarity_boost` por serem agrupados com v3 | `backend/app/tts/client.py:160,267–269`; payloads em `diagnostico.json` | Há divergência com a documentação atual: separar capacidades por modelo. Não presumir que mover o controle de velocidade terá efeito no v4. |
| Enérgico não recebe tag automática; calmo pode receber `[calm]` | `backend/app/tts/client.py:99–108,302–309` | A retirada de `[excited]` foi deliberada por relatos de respiração excessiva. Testar alternativas contidas; não simplesmente restaurar a tag em toda fala. |
| A lista de tags é compartilhada e estreita | `backend/app/tts/client.py:115–135`; `[curious]` e `[short pause]` desaparecem na sondagem | Instruções novas podem ser removidas antes da API. Manter lista validada por modelo, com testes de payload e de escuta. |
| O tom integrado vem sobretudo da categoria do bloco, com exceções editoriais | `backend/app/live/router.py:609–646,2208`; formato pode fixar `tom_tts` | Um comentário tende a sair calmo mesmo quando pede surpresa. Testar intenção por trecho sem acrescentar uma chamada exclusiva de classificação ao LLM. |
| Persona e expressões regionais entram no roteiro; o glossário altera a pronúncia no texto enviado | `backend/app/live/persona.py`, `backend/app/live/contexto.py:572`, `backend/app/tts/profiles.py`, `backend/app/numeros.py:101` | A infraestrutura existe. Falta calibrar um conjunto gaúcho com a voz escolhida; a pronúncia não é validada pela simples presença da gíria. |
| Há instruções conflitantes de canal e ritmo | `backend/app/live/contexto.py:563`; `backend/app/llm/prompt_builder.py:282,341`; `backend/app/live/prompt_emissao.py:252–265` | O prompt do ao vivo herda instruções de WhatsApp e desencoraja frases curtas. Hipótese de prejuízo à interpretação; comparar textos antes de fixar uma regra universal de tamanho de frase. |
| Alguns perfis de pós-produção alteram pitch e adicionam ruído; `radio_fm` não faz isso | `backend/app/postprod/naturalness.py`; `backend/app/postprod/perfis/*.json` | Comparar primeiro o áudio bruto e, depois, o final. Variação aleatória não demonstra naturalidade emocional. |

A documentação atual do fornecedor descreve v4 e v4 Turbo com Stability e Similarity; Style e Speed não estão disponíveis. Essa é uma incompatibilidade de configuração confirmada pela inspeção, não uma medição do impacto acústico. [ElevenLabs — Eleven v4](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4).

O fornecedor orienta dirigir a entrega com estrutura do texto, pontuação e tags, testadas na voz escolhida; v3 e v4 não usam SSML de pausa. Isso dá suporte ao experimento, sem garantir que uma tag produza sempre a emoção pretendida. [ElevenLabs — Best practices](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices).

## Ordem de execução

### 1. Registrar a configuração e a falha real

- Identificar, por leitura da configuração do programa/conta, voz, modelo e perfil efetivos, glossário e pós-produção. O valor padrão do servidor é insuficiente para isso.
- Guardar três a cinco falas problemáticas com texto original, texto enviado e áudio, quando disponíveis. Usar essas falas como conjunto de regressão além dos textos originais deste corpus.
- Marcar separadamente erro de pronúncia, gíria usada fora do contexto, emoção inadequada, pausa ruim e alteração de timbre. “Capaz!” como surpresa precisa de contexto; soletrar a palavra corretamente não resolve sua interpretação.
- Fixar a configuração atual como controle. Preservar as preferências da conta durante a avaliação.

**Aceite:** cada amostra tem procedência e configuração conhecidas. Até lá, o diagnóstico vale para os caminhos de código inspecionados, não para uma voz de produção identificada.

### 2. Corrigir a adaptação por modelo

- Representar separadamente suporte a tags, contexto, velocidade, estilo e similaridade em `app/tts/modelos.py`. Compartilhar suporte a tags não implica compartilhar todos os parâmetros.
- Preparar payloads específicos em `app/tts/client.py`, respeitando também `perfil="natural"`. No v4, remover parâmetros sem efeito e permitir Similarity conforme a API atual; calibrar seu valor por escuta.
- Atualizar os testes de v4 que hoje exigem a remoção de Similarity: eles verificam o comportamento local existente, não o contrato atual do fornecedor.
- Fazer a intenção calma/energética chegar ao modelo por controles compatíveis. Para Flash, criar perfil próprio apenas após medição; para modelos com tags, testar poucas direções, sem obrigar toda fala a ter uma tag.
- Usar a mesma adaptação em síntese embutida, endpoint avulso, streaming e multivoz. Manter o teto atual de chamadas do roteiro e os controles de cobrança.
- Versionar a chave do cache quando o comportamento do adaptador mudar. A chave atual não contém uma versão dos presets: áudio antigo pode esconder a correção. Em experimentos, usar `reutilizar_audio=False`, preservando os demais controles de orçamento.

**Aceite técnico:** payload contém apenas os parâmetros esperados por modelo; a direção solicitada chega à requisição; nenhuma tag vira palavra falada nos casos aprovados. O aceite acústico depende da etapa 4.

### 3. Preparar interpretação gaúcha por contexto

- Usar um conjunto pequeno de expressões aprovadas: bah, tchê, tri, capaz, chimas e te aprochega. O conjunto é inicial; evitar colocar regionalismos em toda fala.
- Diferenciar pronúncia, significado e ocasião de uso. Uma notícia séria não recebe a mesma interpretação de uma chamada musical, mesmo contendo a mesma expressão.
- Aproveitar o glossário existente por rádio/voz. Adicionar uma grafia alternativa apenas quando uma gravação comprovar o erro e a alternativa melhorar a fala sem alterar o sentido. Conservar o texto original mostrado ao operador.
- Testar afirmação, pergunta e exclamação com as mesmas palavras, além de contraste de calma e entusiasmo dentro de um bloco. Não usar caixa alta, reticências ou exclamações como intensificadores globais.
- Separar instruções de WhatsApp e de locução no prompt. Usar exemplos curtos de interpretação aprovados para a persona, mantendo fatos, nomes e regras editoriais.
- Começar sem jitter artificial de pitch e sem ruído de sala. Aplicar o acabamento de rádio somente depois de aprovar a voz bruta; comparar os dois estágios com volume equivalente.

O projeto já aplica aliases locais. Dicionários do fornecedor podem ser avaliados se necessário; suporte a fonemas varia por modelo e idioma, portanto IPA para português não deve ser presumido em todos os modelos. [ElevenLabs — Pronunciation dictionaries](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/pronunciation-dictionaries).

**Aceite:** ouvintes gaúchos entendem e reconhecem o uso das expressões sem regionalismo teatral ou pausas que separem a gíria do restante da frase.

### 4. Executar o piloto de escuta

O [corpus](corpus.json) contém 12 textos originais: quatro com gírias, três variantes de pontuação, dois de entusiasmo, dois de calma/serviço e uma transição emocional. P1–P3 são microtestes deliberadamente curtos; repetir o contraste em uma fala completa antes de generalizar para a rádio.

**Desenho:** uma voz padrão, um modelo, duas condições (atual e candidata), duas gerações independentes por condição e caso: **48 sínteses**. Manter as mesmas palavras nas duas condições; registrar qualquer diferença de pontuação e tags. Quando o experimento estudar apenas pontuação, manter também os parâmetros idênticos. A correção do adaptador e as direções propostas formam a candidata; ainda não foram implementadas.

Usar cinco avaliadores, incluindo pelo menos três falantes gaúchos familiarizados com esse registro. Não contatar terceiros sem instrução do usuário. Apresentar 24 pares A/B por pessoa, com ordem aleatória e identidade das condições oculta; permitir empate. Cada avaliador dá notas de 1 a 5 para naturalidade, pronúncia, adequação da gíria, emoção e pausas. Na primeira escuta de P1–P3, perguntar se ouviu afirmação, pergunta ou convite enfático sem exibir o texto. O mapa dos pares fica separado das respostas.

Equalizar o volume de apresentação dos pares e conservar os originais. Medir primeiro byte, síntese completa, duração, falhas, consumo reportado pelo provedor e erros de conteúdo. Se o caminho real do ao vivo aguarda áudio completo, primeiro byte isolado não representa o tempo até a reprodução. A primeira etapa usa leitura humana para conferir o texto; STT opcional não substitui essa verificação e exige orçamento separado.

**Metas propostas para o piloto, ainda não atingidas:**

| Dimensão | Critério para avançar |
|---|---|
| Preferência | Candidata escolhida em pelo menos 70% das avaliações, contando empates no denominador; apresentar também o resultado por caso e avaliador. |
| Qualidade | Mediana de pelo menos 4/5 para pronúncia, naturalidade e emoção; nenhum caso com mediana abaixo de 3. |
| Gírias | Pelo menos 90% das avaliações regionais julgam aceitáveis pronúncia e uso contextual dos casos G1–G4. |
| Intenção | Pelo menos 80% das classificações reconhecem corretamente cada intenção de P1–P3; emoção aprovada nas duas gerações, não só no melhor take. |
| Conteúdo | Nenhuma palavra de direção lida em voz alta, omissão de informação essencial ou alteração de nome, número ou sentido. |
| Operação | Sem falhas adicionais no piloto; latência e custo dentro do orçamento acordado para o ao vivo. Exibir diferenças absolutas e relativas ao controle. |

Os 120 julgamentos A/B compartilham frases e avaliadores: não são 120 observações independentes. O piloto indica direção, sem provar equivalência à fala humana. Se a mudança agrupada melhorar, isolar depois tags, pronúncia e parâmetros para saber o que contribuiu. Comparar outro modelo ou outra voz em uma rodada separada, mantendo o texto e o protocolo e recalculando o orçamento.

**Volume estimado:** 889 caracteres de texto normalizado por passagem; aproximadamente **4.324 caracteres enviados** nas 48 sínteses, supondo até 32 caracteres extras de tags por caso apenas na candidata. A estimativa não inclui transcrição, alterações de texto, tentativas extras nem mudança de voz/modelo. Não representa cobrança confirmada. Calcular o valor com a tarifa efetiva da conta antes de executar; não usar o desconto de lançamento registrado no benchmark de outubro.

### 5. Confirmar no fluxo completo

- Depois de aprovar os pares, reproduzir blocos com música, locução e transições no player. Comparar áudio bruto, pós-produzido e ouvido no fluxo final.
- Exercitar serviço, notícia e mudanças de assunto, para verificar se entusiasmo não invade conteúdo sério. Conferir também as durações e a calibração de ritmo após alterar o perfil.
- Liberar a mudança por flag, primeiro para o programa de teste. Guardar um caminho de retorno ao perfil anterior e separar caches por versão.
- Integrar as evidências às frentes H2, H3, H8 e H9 do plano existente. Não aprovar a voz pela redução de uma pontuação textual de “sinais de IA”.

## Validação realizada

### Testes existentes

Executados em `backend/`, com os serviços externos simulados pelas fixtures:

```sh
.venv-test/bin/python -m pytest -q tests/test_tts_client.py tests/test_tts_profiles.py tests/test_tts_quality.py tests/test_tts_voices.py tests/test_numeros.py tests/test_oralidade.py tests/test_oralidade_reescrita.py tests/test_postprod_client.py tests/test_postprod_audio_io.py tests/test_live_ritmo_voz.py
.venv-test/bin/python -m pytest -q tests/test_live_router.py -k 'tom_integrado or prompt_oferece_expressao_regional or tom_explicito'
```

Resultados: **189 passaram** na primeira seleção e **2 passaram, 137 não selecionados** na segunda. Não foi executada a suíte completa. Esses testes validam integração local, normalização, configuração e processamento; não avaliam a qualidade perceptiva das gírias.

### Inspeção reproduzível dos payloads

Da raiz do projeto:

```sh
backend/.venv-test/bin/python docs/analises/2026-11-21-prosodia-gaucha/reproduzir.py
```

O script bloqueia conexões de rede, carrega o isolamento de testes e zera o jitter para comparar payloads. Inspeciona quatro modelos × dois perfis × 12 casos, totalizando **96 payloads**, sem consultar uma voz real ou sintetizar áudio. As oito sondagens de comportamento foram confirmadas; a gíria permanece intacta no texto sem aliases, o que não permite concluir que seja pronunciada corretamente.

Resultado detalhado: [diagnostico.json](diagnostico.json). O conjunto não usa os multiplicadores de velocidade de Paulo ou Yasmin, pois a voz específica do relato ainda não foi identificada. O script registra a revisão do código para permitir comparar o diagnóstico depois das correções.

## Próxima entrega

Implementar a adaptação por modelo e preparar os 24 pares de escuta com a voz efetiva do programa. A decisão de publicar a mudança depende da avaliação auditiva acima; a revisão técnica está concluída e não determina ainda uma configuração vencedora.
