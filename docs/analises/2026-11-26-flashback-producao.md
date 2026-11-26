# Flashback do Meio-Dia — avaliação de produção

Avaliação em 26/11/2026, para a Rádio Guabiruba FM. Horários em America/Sao_Paulo.

## Parecer

O programa tem identidade e material para funcionar: apresenta clássicos reconhecíveis, conversa com o público local e confirmou o encerramento perto das 14h. A edição ainda precisa de ajustes em seleção musical, diversidade, precisão das curiosidades e distribuição da fala antes de servir de referência para uma operação sem acompanhamento.

A recomendação é melhorar escrita, música e condução juntas. Encurtar o texto não resolve uma faixa inadequada, assim como uma playlist correta não resolve cinco comentários em sequência.

## Procedência e limites

- Ambiente: produção, backend na revisão `62f9a3afc09bd65d3c2a039de6ac296bbbc7c324`.
- Conta 1, programa 3, **Flashback do Meio-Dia**, com **Rick Vallejo**.
- Grade cadastrada: segunda a sexta, 12h–14h. Ocorrência `3:2026-11-26`.
- Fontes internas: consultas com transação somente leitura a `programas`, `as_run_eventos`, `blocos_reproduzidos`, `musica_historico`, contagens de pedidos e promessas, biblioteca do programa e logs de aplicação.
- Os cálculos sobre textos completos foram realizados no servidor, sem exportar os textos integrais, perfis, tokens, identificação do player ou mensagens de ouvintes.
- A cópia integral para arquivo temporário foi bloqueada pela revisão automática. A avaliação prosseguiu por consultas restritas, agregados e trechos editoriais curtos; não depende daquela cópia.
- `as_run_eventos.texto` tem limite de 500 caracteres, mas `blocos_reproduzidos.fala` preserva textos maiores. A análise de repetição usou esta segunda fonte. Nenhum texto truncado foi tratado como corte de áudio.
- Não foi localizada gravação final nas fontes consultadas. A biblioteca vinculada ao programa contém três vinhetas. Não foi feita escuta do programa completo; timbre, expressividade, mixagem, volume e silêncios reais permanecem sem avaliação.
- Confirmação significa conclusão reportada pelo player, sem comprovar transmissão na antena ou recepção pelo ouvinte.

## O que os registros comprovam

| Indicador | Resultado |
|---|---:|
| Blocos enviados | 62 |
| Blocos confirmados pelo player | 58 |
| Blocos com falha | 1 |
| Blocos sem confirmação no as-run | 3 |
| Blocos musicais confirmados | 18 |
| Faixas identificadas em blocos confirmados | 20, incluindo duas acrescentadas por citação |
| Falas concluídas, excluindo vinhetas | 47 |
| Comentários concluídos | 14 |
| Chamadas ao ouvinte concluídas | 8 |
| Identificações concluídas | 4 |
| Sínteses com duração medida | 48, incluindo a introdução do bloco que falhou |
| Sínteses acima do teto informado nos logs | 27 de 48 |
| Sínteses mais de 30% acima do teto | 7 de 48 |
| Tempo somado dos áudios de fala medidos | 25min02s; não equivale a tempo confirmado de voz no ar |
| Conclusão do encerramento | 13h59min54,57s |

O bloco de **Blue Monday**, do New Order, recebeu estado `falhou` às 13h35min56s. O registro não fornece motivo técnico nem duração de eventual silêncio. Não se atribui esse problema a conteúdo bloqueado, rede ou autoplay sem evidência adicional.

Os três eventos sem confirmação são vinhetas. Na tabela de reprodução, dois continuam `preparado` e um ficou `reproduzindo` desde o início da edição. Isso pede reconciliação de estados; não representa três falhas de áudio comprovadas.

## 1. Escrita: preservar a proximidade e diminuir os automatismos

Nos textos completos das 47 falas concluídas, sem vinhetas:

| Expressão | Ocorrências | Falas que a contêm |
|---|---:|---:|
| pista | 36 | 33 |
| malharia | 15 | 15 |
| olha só | 9 | 9 |
| e já que | 6 | 6 |
| e falando | 2 | 2 |

“Pista” combina com o conceito dançante, e “malharia” localiza a conversa. A repetição faz quase toda entrada começar ou terminar no mesmo imaginário. As transições com “e já que” mantêm uma ligação superficial, mas não garantem que o novo assunto mereça interromper a música.

O verificador heurístico de oralidade sinalizou 66 frases longas e 17 frases com múltiplas ideias. São sinais para revisão, não erros confirmados por escuta. Anos por extenso também geraram muitos avisos de número longo; essa contagem não deve levar à retirada automática das datas em um flashback.

Mudanças propostas:

1. Uma intenção por entrada: anunciar, contar uma curiosidade, identificar a emissora ou convidar o público.
2. Anúncios mais diretos, com artista e título reconhecíveis logo no começo.
3. Uma curiosidade verificável por comentário, sem acumular data, álbum, produtor e descrição abstrata da memória do ouvinte.
4. Manter referências locais quando acrescentarem contexto; limitar a repetição das mesmas imagens e construções.
5. Evitar declarações coletivas sem base, como a cidade inteira cantando ou uma pista efetivamente lotada. Podem soar como metáfora, mas não devem substituir uma interação real.

Exemplo de identificação proposta, sem substituir nada em produção:

> Guabiruba FM, oitenta e sete ponto cinco. Flashback do Meio-Dia, com Rick Vallejo.

Exemplo de anúncio curto para uma faixa já confirmada na fila:

> Cyndi Lauper, Time After Time. Daquelas que a gente reconhece nos primeiros segundos. Segue com o Flashback do Meio-Dia!

### Precisão das informações

No evento 79, confirmado, o comentário atribui a produção de “Like a Prayer” a Bill Bottrell sem distinguir a versão. A página oficial credita a produção principal a Madonna e Patrick Leonard, e apresenta Bottrell em produção adicional/remix. A versão precisa ser identificada para fazer essa atribuição corretamente. [Créditos oficiais do single](https://www.madonna.com/products/like-a-prayer-single).

No evento 55, a fala diz “duas vezes por semana” e chama 12h37 de “segunda metade”, enquanto a grade consultada está em segunda a sexta, 12h–14h. A frequência deve vir do cadastro efetivo, e a metade do programa ocorre às 13h. Não há snapshot histórico de todas as edições da grade para excluir uma alteração posterior, mas a expressão sobre a metade é incompatível com a duração anunciada na própria fala.

## 2. Música: validar obra, artista, época e versão

A configuração pede sucessos entre 1970 e 1999, com preferência por gravações originais de estúdio ou radio edit e variedade de artista, década e idioma.

Problemas comprovados no histórico de seleção e nos blocos confirmados:

| Consulta desejada | Resultado associado ao bloco confirmado | Implicação |
|---|---|---|
| Tony! Toni! Toné! — Feels Good | Tony Bennett e Amy Winehouse — Body and Soul | Mudou artista e obra. A própria locução apresenta a gravação como de 2011. |
| sucessos musica brasileira | Zé Felipe e Ana Castela — Sua Boca Mente | A própria locução apresenta a gravação como de 2025, fora do recorte solicitado. |
| Cyndi Lauper — Girls Just Want to Have Fun | Cyndi Lauper — Time After Time | A faixa encontrada difere da desejada. O anúncio final acompanha Time After Time; não se comprovou anúncio de título errado nesse bloco. |
| Furacão 2000 — Dreamin | I'm Still Waiting | Não é correspondência exata do título consultado. Precisa validação antes de tratar como substituição aceitável. |
| Milli Vanilli — Blame It on the Rain | Medley de quatro músicas, incluindo Girl You Know It's True | A seleção não preservou a obra pedida. A locução apresentou o medley encontrado. |
| Michael Jackson — Billie Jean | Billie Jean (1981 Home Demo) | Versão de demonstração em lugar da gravação consagrada; a fala reconhece que é demo. |

Há também apresentações de TV e materiais de show. Gravações remasterizadas de músicas antigas não devem ser rejeitadas apenas porque o título contém “2024 Remaster” ou outra data moderna: ano da obra, ano da gravação e ano da remasterização são dados diferentes.

O repertório inclui quatro entradas relacionadas a Milli Vanilli, entre elas um medley. Ainda que sejam vídeos diferentes, a concentração enfraquece a variedade. Algumas músicas reaparecem dentro do medley e em faixa individual.

O backend de produção mantém `QUERY_MUSICA_GENERICA = "sucessos musica brasileira"`; a seleção de “Sua Boca Mente” registra exatamente essa consulta. Existem falhas repetidas de classificação de gênero nos logs do dia. No código consultado, uma exceção nessa classificação devolve lista de incompatibilidades vazia, confundindo falha de verificação com aprovação. É uma fragilidade concreta, embora não explique isoladamente por que cada alternativa anterior de busca falhou.

Mudanças propostas:

1. Resolver identidade da obra e do artista antes da locução; resultados aproximados não podem substituir silenciosamente a faixa pedida.
2. Separar identidade musical de versão: padrão de estúdio/radio edit; demo, cover, medley, versão de TV ou show entram por decisão editorial explícita.
3. Usar catálogo de reserva validado para o flashback. Sem correspondência confiável, escolher outro clássico aprovado.
4. Tratar falha de classificação como “não verificado”, com alternativa aprovada, em vez de liberar qualquer faixa.
5. Medir repetição por artista, obra e componentes de medley, além de vídeo.
6. Distinguir citação histórica de intenção explícita de acrescentar música. Os comentários sobre Take on Me e a demo de Billie Jean geraram faixas extras; isso precisa obedecer ao desenho do programa.

## 3. Condução: desenhar a progressão das duas horas

O encerramento perto do horário é um acerto. Há, porém, três problemas de ritmo:

- Os anúncios de música medidos duram em média 27,25 s; as identificações, 26,26 s. Mesmo sem um comentário completo, o ouvinte recebe outra entrada relativamente longa.
- Cinco comentários consecutivos, eventos 87–91, somam **189,28 s de áudio sintetizado**, aproximadamente **3min09s**. Todos constam como concluídos. Houve 3min13,63s entre o fim confirmado da identificação anterior e o fim do quinto comentário; esse intervalo inclui transições e não é medição de silêncio.
- A primeira abertura falada conclui às 12h08min37s, após quatro vinhetas confirmadas. Houve outras vinhetas preparadas e seleções antecipadas. Isso sugere verificar tentativas de início e reinícios; não permite concluir que houve oito minutos de silêncio.

O formato atual é `padrao`, sem relógio da hora e com adição de blocos pela IA habilitada. Os logs mostram `fonte=observacao aplicado=False` em várias falas acima de 30 s: esse teto está sendo observado, sem ajuste efetivo nesse caminho. Perto do fim, o planejamento de fechamento aplica limites próprios. Isso explica por que cumprir o horário final pode coexistir com pouca disciplina no restante do programa.

### Proposta integrada para experimentar

Manter o Rick, o caráter local e a energia do almoço. Adotar um ciclo editorial testável:

1. Duas músicas, com anúncios de 8–15 s quando necessários.
2. Uma entrada de 20–30 s: curiosidade confirmada **ou** participação real **ou** convite específico.
3. Mais duas músicas, variando artista e intensidade.
4. Identificação de 5–8 s e continuação do ciclo.

Uma chamada deve ter uma pergunta concreta que possa render resposta posteriormente. As oito chamadas registradas não têm pedidos associados na fila musical consultada; isso não prova ausência de mensagens nos outros canais. O indicador útil é quantas participações recebidas foram aproveitadas, sem inventar demanda para preencher o espaço.

Para o piloto, sugere-se como hipótese editorial:

- uma curiosidade por entrada;
- nenhum comentário consecutivo, salvo quadro deliberado;
- artista separado por 45–60 minutos, com exceções explícitas;
- consulta histórica apoiada em fonte ou metadado validado;
- abertura com promessa do que vai tocar, retomadas breves e encerramento sem repetir um resumo imediatamente anterior;
- planejamento da hora com orçamento de fala por função, sem simplesmente mudar para um formato que proíba comentários ou notícias desejados pela rádio.

Esses intervalos são propostas a testar, não padrões universais de rádio nem preferências já confirmadas pelo usuário.

## Sequência recomendada e critérios de validação

| Etapa | Entrega | Como avaliar |
|---|---|---|
| 1. Repertório confiável | Validação de artista, obra, época e versão; reserva por programa | Nenhuma substituição de obra/artista ou entrada fora do recorte sem decisão explícita; demo e medley só quando previstos. |
| 2. Escrita e ritmo | Orçamento efetivo, revisão de repetição e ciclo de músicas/entradas | Sem sequência acidental de comentários; identificações e anúncios dentro dos limites escolhidos; redução da repetição sem apagar o personagem. |
| 3. Precisão e participação | Fatos vinculados à fonte, grade consistente e aproveitamento de recados reais | Sem frequência inventada, informação histórica ambígua ou promessa sem execução. |
| 4. Resultado sonoro | Gravação da próxima edição e revisão com marcação de tempo | Conferir pronúncia de nomes, energia, mixagem, entradas sobre música, falhas e eventuais silêncios. |

Antes de comparar edições, separar tempo de geração, áudio sintetizado, início/fim de reprodução e confirmação. A falha de Blue Monday deve registrar motivo e acionar reserva, e estados abandonados devem ser reconciliados.

Nenhum código, cadastro ou serviço de produção foi alterado nesta avaliação. As modificações locais preexistentes foram preservadas. Esta entrega apresenta diagnóstico e proposta para revisão conjunta, sem aplicar automaticamente as preferências editoriais sugeridas.
