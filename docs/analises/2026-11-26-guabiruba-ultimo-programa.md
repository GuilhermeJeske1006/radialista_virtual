# Avaliação dos últimos programas da Rádio Guabiruba FM

Consulta em 26/11/2026. Horários em America/Sao_Paulo.

## Escopo e procedência

A análise usa o PostgreSQL **local**, conta 1, os logs locais de 25/11 e o código do repositório. O acesso SSH ao servidor de produção não autenticou; portanto, não se afirma que esses registros sejam os mais recentes de produção.

Há duas interpretações de “último programa gerado”:

| Recorte | Programa | Evidência |
|---|---|---|
| Última configuração criada pela IA | Rock e Notícia com Tiago Brennand, programa 3 | Geração 2, aceita, em 24/11 às 10h27; cadastro às 10h28 |
| Última execução registrada | Baile de Bandinha, programa 2 | Blocos gerados em 25/11 entre 17h22 e 17h56; última confirmação às 17h59 |

Não foi localizada uma gravação final para escuta. A avaliação cobre texto parcial, seleção musical, configuração, confirmação do player e duração medida nos logs. Não permite julgar timbre, pronúncia, expressividade, mixagem ou silêncios reais.

O histórico `as_run_eventos` guarda **até 500 caracteres por bloco** (`backend/app/live/as_run.py`). Frases terminando abruptamente nesse registro não demonstram corte na fala original. Confirmação do player também não comprova transmissão ou recepção na emissora.

## Resultado observado

| Programa e data | Blocos enviados | Confirmados pelo player | Sem confirmação | Falhas registradas |
|---|---:|---:|---:|---:|
| Baile de Bandinha, 25/11 | 16 | 9 | 7 | 0 |
| Rock e Notícia, 24/11 | 29 | 22 | 7 | 0 |

Blocos sem confirmação podem ter sido antecipados, descartados, interrompidos ou ter perdido o retorno do player. Os números não medem taxa de falha de reprodução. Há múltiplas aberturas no mesmo dia, compatíveis com reinícios, mas falta identificação de sessão para separá-las com segurança.

Pontos positivos: identidade da emissora reconhecível; transições que recuperam o bloco anterior; chamadas à participação sem necessidade de inventar ouvintes nos exemplos lidos; pauta relacionada à região; atribuição de fontes em vários textos. Nas 11 sínteses do Baile com duração medida nos logs de 25/11, nenhuma ultrapassou o teto informado no respectivo registro. Isso vale para áudios sintetizados, incluindo os não confirmados pelo player.

## Melhorias prioritárias

### 1. Preservar o repertório do programa quando a busca falha — alta prioridade

No Baile, o evento 96 está confirmado e anuncia Natiruts, “Quero Ser Feliz Também”. O histórico musical 51 registra `origem=auto` e a consulta **“sucessos musica brasileira”**. Não era um pedido de ouvinte registrado nessa seleção. A mesma faixa e consulta aparecem nas seleções do Baile em 23/11 e do Rock em 24/11; esta última não tem confirmação de reprodução.

O código define essa consulta como último recurso em `backend/app/live/router.py`, `QUERY_MUSICA_GENERICA`. Nos logs há falhas repetidas de classificação de gênero, incluindo `JSONDecodeError: Extra data`. Em `backend/app/llm/client.py`, `itens_fora_do_genero` devolve conjunto vazio quando a classificação falha; `_fora_do_genero` acaba tratando isso como ausência de incompatibilidade. São evidências de uma fragilidade concreta, embora não expliquem isoladamente por que todas as alternativas anteriores da seleção falharam.

Proposta: repertório de reserva aprovado por programa, busca alternativa dentro dos gêneros configurados e estado explícito “gênero não verificado”. Falha na classificação deve conduzir a uma faixa aprovada ou à intervenção do operador. Corrigir o tratamento de JSON e validar a estrutura da resposta, sem aceitar resposta ambígua como aprovação musical.

Aceite: a indisponibilidade da busca ou uma classificação inválida não introduzem uma faixa de outro estilo no Baile.

### 2. Distinguir citação cultural de intenção de tocar — alta prioridade

O serviço do evento 102 cita a canção “Noite Feliz” como parte da programação de uma cantata. O histórico 54 registra uma faixa desse título, do canal Frei Gilson - Topic, com `origem=citada_locutor`, vinculada ao mesmo bloco por `video_id=kdcysXQJqAI`. O encerramento gerado em seguida começa “com a Noite Feliz ainda no ar”. Ambos os blocos ficaram sem confirmação: houve seleção e continuidade textual, mas não há comprovação de execução.

O extrator em `backend/app/llm/client.py` pede músicas que o locutor “cita, comenta, recomenda ou promete tocar”. Esse critério é amplo demais para agenda cultural e notícia.

Proposta: classificar a menção como anúncio, pedido, referência histórica ou informação de agenda. Apenas uma intenção explícita de tocar deve acrescentar faixa. A continuidade deve considerar reprodução confirmada e a ordem planejada de execução, separando-as do simples histórico de seleção.

Aceite: uma notícia sobre apresentações de “Noite Feliz” não acrescenta automaticamente essa canção à fila.

### 3. Encurtar e variar os comentários — prioridade editorial

Os eventos confirmados 97 e 98 são comentários consecutivos: 51,36 s e 49,36 s nas medições correlacionadas por horário. Somam **100,72 s** de locução, sem bloco musical entre os dois no histórico confirmado. Os textos insistem em salão, cozinha, instrumentos e memória de baile.

Proposta: experimentar comentários de 20–30 s, uma curiosidade por entrada, seguida de música. Variar a função da fala: informação sobre a banda, detalhe de instrumento, serviço local ou participação. Reduzir referências repetidas ao “salão”. O sotaque gaúcho faz parte da configuração atual; eventual redução de “bah”, “tchê” e “prenda” deve respeitar essa escolha de personagem.

Aceite: duas entradas seguidas acrescentam informações diferentes e respeitam um orçamento combinado de fala.

### 4. Sincronizar configuração e horário — prioridade de consistência

O Rock foi proposto e aceito para 10h30–12h; o cadastro atual está em 12h–13h, mas mantém descrição de programa da manhã e saudação “Bom dia”. Portanto, a geração respeitou o horário originalmente pedido; a inconsistência aparece entre o cadastro atual e os textos mantidos. Não há evidência suficiente para atribuir a mudança de horário à IA.

O Baile está em 17h–18h, mas sua saudação cadastrada também diz “bom dia” e “bota o pé pra fora da cama”. Seu encerramento gerado fala “foi uma noite”, apesar da faixa de fim de tarde.

Os dois programas usam `perfil_programacao=popular_sertanejo` e não têm relógio da hora. Esse perfil regula condução e orçamento; os gêneros musicais são configurados separadamente. O nome do perfil, sozinho, não demonstra a causa do Natiruts.

Proposta: revisar saudações e descrição quando o horário muda, definir público-alvo, selecionar conscientemente o formato e montar um relógio compatível com a proporção desejada de música, notícia e comentário.

### 5. Guardar material suficiente para avaliar o resultado sonoro

O relatório atual perde o restante de falas longas e não separa sessões. O exportador `backend/app/live/gravacao.py` converte a gravação da aba, entrega o MP3 e apaga os temporários; esse caminho não constitui um arquivo permanente de programas.

Proposta: guardar, com política de acesso e retenção definida, gravação final, roteiro completo, sessão, horários de início/fim de reprodução, descartes, duração, configuração efetiva e fontes utilizadas. Preservar a distinção entre gerado, selecionado e reproduzido.

Aceite: uma edição pode ser reaberta com áudio e roteiro sincronizados, inclusive para avaliar encerramento, pausas, volume e pronúncia.

## Limites e encaminhamento

Não foram verificadas externamente as notícias, datas de eventos ou informações musicais citadas. Atribuição de fonte no texto é um sinal positivo, mas não comprova exatidão ou atualidade. Para o Rock, convém também substituir atribuições vagas, como “segundo o órgão responsável pelo transporte da carga”, pela fonte identificada e seu horário de atualização.

A prioridade recomendada é corrigir seleção de reserva e falhas de classificação, depois intenção de tocar, continuidade e cadência editorial. Não há evidência sonora suficiente para recomendar troca de voz ou de modelo de síntese.

Esta entrega é uma avaliação; nenhuma configuração de programa ou código de aplicação foi alterado. As alterações preexistentes no diretório de trabalho foram preservadas.
