# Plano de implementação: mensalidade + cobrança pelo uso

Data: 24/09/2026. Revisão conforme orientação do responsável: ajustes dos clientes existentes serão feitos manualmente por ele. Este documento especifica a implementação; não altera a cobrança em produção.

## 1. Modelo de negócio definido

Um único plano de acesso, **Locufy Flex**, com mensalidade de **R$ 69,90** e cobrança mensal pós-paga do consumo. O usuário escolhe os modelos disponíveis, utiliza as funcionalidades e paga o uso apurado no ciclo.

O acréscimo definido é **100% sobre o custo de referência**, equivalente a multiplicar o custo por dois. Esse percentual não representa a margem líquida da empresa.

```text
Custo de cada uso = soma das quantidades medidas × respectivas tarifas unitárias
Custo em reais = custo na moeda de origem × câmbio registrado
Preço do uso = custo em reais × (1 + acréscimo / 100)
Com acréscimo de 100%: preço do uso = custo em reais × 2
Cobrança mensal = R$ 69,90 + soma dos preços dos usos concluídos no ciclo
```

A fatura pode incluir ajustes identificados quando necessários, como correção de uma cobrança. O cálculo normal é mensalidade mais consumo. Sem consumo, cobra-se apenas a mensalidade.

O sistema novo terá uma regra comercial única. O responsável ajustará manualmente as poucas contas e assinaturas existentes. Não criar ferramenta de transferência de clientes, coexistência automática de contratos, campanhas de transição, conversão automática de pacotes ou comparação entre regimes antigos e novos.

## 2. O que o sistema precisa registrar

O núcleo é um registro de uso por cliente, com **funcionalidade, modelo, quantidade e tarifa**, suficiente para reproduzir o preço cobrado.

| Campo | Finalidade |
|---|---|
| ID único do uso | Impedir lançamento repetido |
| Cliente/conta | Identificar quem utilizou e quem será cobrado |
| Funcionalidade | Atendimento WhatsApp, roteiro, locução, transcrição, interpretação de imagem, pesquisa, música gerada etc. |
| Canal e contexto | WhatsApp, programa, vinheta ou tarefa automática; ID do programa/conversa quando aplicável |
| Operação e etapa | Relacionar as chamadas que compõem uma ação, sem cobrar novamente o total da operação |
| Provedor, modelo e versão | Aplicar a tarifa correspondente ao serviço efetivamente utilizado |
| Quantidades e unidades | Tokens de entrada/saída/cache, caracteres, segundos, consultas ou outras unidades contratuais |
| Tarifa e versão da tabela | Preservar o preço válido quando o uso foi autorizado |
| Moeda e câmbio | Reproduzir a conversão em reais |
| Custo de referência | Custo calculado antes do acréscimo |
| Percentual aplicado | Inicialmente 100%; registrado para não alterar o passado |
| Preço final | Valor faturável da operação ou etapa |
| Data e ciclo | Determinar em qual fechamento o uso entra |
| Estado | Em andamento, concluído/faturável, falha ou cancelado |
| Vínculo com fatura | Distinguir o que ainda será faturado do que já foi cobrado |

Não basta contar chamadas ou mensagens. Uma chamada pode ter muitos tokens; áudio tem duração; modelos podem ter preços diferentes para entrada e saída. Guardar cada quantidade necessária para o cálculo real.

Cada etapa paga gera seu próprio registro. A operação principal agrupa essas etapas para exibição; não gera outro débito pelo mesmo custo. IDs de requisição do provedor ajudam a conciliar tentativas e faturas.

## 3. Tabela de tarifas e cálculo

Manter cadastro administrável com funcionalidade/tipo de serviço, provedor, modelo, unidade tarifada, preço de referência, moeda, câmbio, vigência e acréscimo. Uma alteração vale para novos usos, não para operações já autorizadas ou concluídas.

| Serviço | Quantidade usada na precificação |
|---|---|
| Geração de texto | Tokens de entrada e saída, com preços separados |
| Cache do provedor de texto | Tokens de escrita/leitura quando houver cobrança contratual distinta |
| Síntese de voz | Caracteres ou créditos realmente tarifados pelo contrato |
| Transcrição | Segundos/minutos processados, convertidos para a unidade da tarifa |
| Interpretação de imagem | Unidades de imagem/tokens medidas pelo provedor |
| Busca/pesquisa | Consultas e tokens, somente quando cobrados |
| Música gerada | Duração ou unidade contratual efetivamente utilizada |

A unidade da tabela precisa ser explícita. Exemplo: uma tarifa por milhão de tokens exige dividir a quantidade por 1.000.000 antes de multiplicar pelo preço. Normalizar duração da mesma forma, sem cobrar segundos como minutos.

Tarifas de referência publicadas em reais podem usar câmbio congelado por vigência, registrado em cada uso. Explicar essa regra ao cliente; não chamar de repasse exato da fatura do provedor quando houver diferença cambial. Confirmar tarifas contratadas antes de publicar a tabela.

O controle atual `ConsumoIA.custo` já contém reserva interna de 15%. Separar custo bruto e reserva antes de criar a precificação comercial. A reserva serve ao controle financeiro interno e não entra como uso do cliente nem recebe outro multiplicador.

Usar valores monetários de alta precisão e regra de arredondamento consistente na fatura. Não arredondar cada token para um centavo. O total exibido deve bater com a soma das linhas faturadas.

## 4. WhatsApp completo

Liberar as funcionalidades de WhatsApp existentes no produto, com a conexão atual por conta: atendimento automático, participação dos ouvintes, integração com programas, processamento de texto, transcrição de áudio e interpretação de imagem quando suportados.

Não haverá franquia mensal de mensagens, bloqueio por quantidade contratada, compra de pacotes de mensagens ou cobrança fixa adicional pelo acesso ao WhatsApp. A contagem de mensagens serve para estatísticas. O preço resulta do processamento utilizado, do modelo e das quantidades medidas.

| Ação | Tratamento |
|---|---|
| Apenas receber uma mensagem, sem processamento pago | Sem cobrança de IA |
| Processar/responder com IA | Registrar modelo e unidades realmente utilizadas |
| Transcrever áudio ou interpretar imagem | Registrar a etapa e suas unidades |
| Gerar uma fala para o programa a partir da participação | Registrar a nova síntese, sem duplicar as etapas já cobradas |
| Repetir evento recebido ou reutilizar resultado exato já pronto | Não cobrar a mesma geração novamente |

Custos fixos da conexão pertencem à operação coberta pela mensalidade. Se houver tarifa variável específica do provedor de mensagens, só incluí-la quando comprovada e divulgada na tabela; não inventar preço por mensagem.

Manter controles técnicos contra abuso e o limite financeiro escolhido para a conta. WhatsApp completo significa funcionalidades liberadas e ausência de franquia comercial de mensagens.

## 5. Escolha de modelos e exemplos

O usuário escolhe o modelo de texto e o modelo de voz separadamente por programa. O atendimento do WhatsApp tem sua própria seleção de texto. Classificadores e outros serviços auxiliares usam opções compatíveis administradas pelo sistema, informadas na composição do consumo.

O catálogo deve mostrar nome do modelo, preço por unidade, indicação de uso sustentada pelas avaliações, limitações e exemplos. Não prometer equivalência de qualidade apenas porque duas opções executam a mesma tarefa.

- Texto: comparar respostas para o mesmo pedido, com custo daquela amostra.
- Voz: ouvir o mesmo texto com a mesma voz compatível em cada modelo.
- Exemplos do catálogo: previamente gerados e gratuitos para reproduzir.
- Teste com conteúdo personalizado: mostrar estimativa antes de executar e faturar o processamento realizado.
- Alteração de escolha: vale para próximas gerações; operações iniciadas mantêm modelo e tarifa autorizados.

Os benchmarks anteriores não aprovaram substituição universal dos modelos. Validar fidelidade factual, instruções, pronúncia e audição antes de habilitar cada combinação. Não alterar automaticamente para um modelo mais caro sem autorização.

## 6. Regras para decidir o que é faturável

Cobrar processamento concluído e disponibilizado, inclusive etapas auxiliares de uma funcionalidade habilitada. Nova versão solicitada pelo usuário é outro uso. Resultado reaproveitado integralmente do cache e reprodução de áudio pronto não são nova geração paga.

Falhas internas e tentativas técnicas sem entrega ficam no custo interno, não na fatura do cliente. Em operação parcial, cobrar somente a etapa concluída e entregue como resultado utilizável; por exemplo, texto salvo para o cliente mesmo se a síntese falhar. Reservas de orçamento e tarefas apenas agendadas não são consumo realizado.

Todas as chamadas pagas precisam passar pela mesma medição: WhatsApp, roteiros, ao vivo, pré-geração, notícias, vinhetas, transcrição e workers. Tarefas automáticas habilitadas também entram no extrato com sua funcionalidade identificada.

Correções financeiras são lançamentos vinculados ao original. Não editar silenciosamente usos já faturados.

## 7. Apuração e cobrança mensal por cliente

Usar o ciclo individual da assinatura. Cada cliente possui um fechamento que agrupa seu uso por **funcionalidade + modelo + unidade + versão da tarifa**. Não misturar quantidades de serviços diferentes nem períodos de outras contas.

1. Identificar o ciclo encerrado e seus usos concluídos ainda não faturados.
2. Conferir operações em andamento, duplicidades e falhas; não transformar estimativas em cobrança efetiva.
3. Somar preços calculados com as tarifas registradas em cada uso.
4. Adicionar a mensalidade de R$ 69,90 e ajustes discriminados, quando houver.
5. Vincular o demonstrativo a uma única fatura do cliente e enviá-la ao mecanismo recorrente de cobrança.
6. Confirmar o pagamento por evento do provedor e registrar sucesso ou pendência.

O sistema de billing realiza a cobrança recorrente. A medição de uso não deve gerar uma cobrança de cartão a cada operação, nem manter uma segunda rotina paralela cobrando o mesmo ciclo.

Manter uma chave única por conta/assinatura/período e por uso faturado. Reprocessar um fechamento ou webhook não pode acrescentar o mesmo item novamente. Estados de fechamento, fatura emitida e pagamento recebido são distintos.

Operações pertencem ao ciclo em que foram autorizadas/iniciadas. Antes da emissão, reconciliar as que cruzarem o corte. Configurar a finalização da fatura para aguardar essa conferência. Eventos confirmados depois da emissão exigem ajuste identificado pelo período original; não alterar fatura finalizada silenciosamente. No cancelamento, fechar o consumo restante sem criar mensalidade de um período futuro não contratado.

A proposta de calendário permanece: primeira mensalidade na adesão; em cada renovação, mensalidade do próximo período junto do consumo do período encerrado. Identificar os períodos na fatura. O consumo é sempre pós-pago.

Exemplo ilustrativo de um fechamento, com custos hipotéticos já apurados a partir das unidades:

| Funcionalidade | Custo de referência | Acréscimo | Preço ao cliente |
|---|---:|---:|---:|
| Atendimento WhatsApp | R$ 20,00 | 100% | R$ 40,00 |
| Roteiros | R$ 10,00 | 100% | R$ 20,00 |
| Locução | R$ 50,00 | 100% | R$ 100,00 |
| Transcrição | R$ 5,00 | 100% | R$ 10,00 |
| Mensalidade | — | — | R$ 69,90 |
| **Total da fatura** | **R$ 85,00 de consumo** | | **R$ 239,90** |

Esses custos são apenas exemplo de soma, não preços unitários dos modelos. A fatura real será calculada com as quantidades medidas e a tabela vigente.

## 8. Painel e operação

O cliente visualiza o consumo acumulado, a previsão da próxima fatura, o período e o detalhamento por funcionalidade/modelo. O histórico mostra unidades, tarifa aplicada, preço e estado do pagamento. O administrador visualiza também custo interno, falhas absorvidas e contribuição estimada.

Manter um limite financeiro configurável e reserva atômica antes de chamadas pagas, para que operações simultâneas não excedam o autorizado. Sem franquias artificiais de mensagens ou minutos. Valores ainda não pagos continuam contando na exposição da conta após a virada do ciclo.

Em caso de inadimplência, suspender novas operações pagas e permitir regularização da mesma fatura. Não emitir uma nova dívida para cada tentativa de pagamento. Disponibilizar extrato e acesso a arquivos conforme o período de acesso contratado.

Conferir pagamentos versus faturas e usos versus custos dos provedores. A reserva interna de risco, taxas e despesas operacionais servem para avaliar margem; não devem aparecer como consumo fictício do usuário. Os 10% tributários usados nas simulações são hipótese, não taxa a adicionar automaticamente à cobrança. Validar tratamento fiscal e emissão documental com a contabilidade; eventual Stripe Tax exige cobertura e registros ativos verificados.

## 9. Implementação necessária no código

| Entrega | Escopo |
|---|---|
| 1. Registro de uso e tarifas | Evoluir `models/consumo_ia.py` e `billing/consumo_ia.py`; separar custo da reserva e registrar funcionalidade, modelo, unidades e preço congelado |
| 2. Medição de todas as funcionalidades | Propagar conta, operação, canal e etapa em LLM, TTS, STT, pesquisa, música, WhatsApp e workers; impedir duplicação |
| 3. Seleção de modelos | Catálogo e configuração por conta/programa/WhatsApp; adaptar parâmetros e chaves de cache ao modelo efetivo |
| 4. WhatsApp completo | Retirar cotas e venda de excedentes em webhook, limites, upsell e painel; autorizar pelo orçamento financeiro antes do gasto |
| 5. Fechamento e cobrança | Consolidar por conta/ciclo, gerar demonstrativo, vincular fatura e tratar renovação, pagamento, falha e ajuste idempotentemente |
| 6. Interface | Exemplos, seleção, estimativa, extrato e histórico de faturas |
| 7. Oferta única | Atualizar catálogo comercial, checkout e página de preços para mensalidade + uso; ajustes das contas existentes feitos manualmente pelo responsável |

O cliente de LLM atual usa configuração global: a escolha precisa ser resolvida por operação sem afetar outras contas. O cliente de voz já aceita modelo por chamada, mas essa escolha deve percorrer todos os fluxos relevantes.

Revisar a integração de cobrança existente: a deduplicação de webhooks depende de Redis e o tratamento atual de `invoice.paid` ignora renovações. A nova apuração exige persistência durável, repetição segura e tratamento de todo o ciclo de pagamento. Homologar SDK/API e assinatura de eventos antes da cobrança real.

Não criar um projeto de migração comercial nem ferramentas para mover clientes entre contratos. As alterações de estrutura de banco necessárias à medição continuam fazendo parte da implementação normal e devem ser versionadas e verificadas.

## 10. Validação e liberação

- Precificação: quantidades e divisores corretos para cada unidade, tarifas de entrada/saída, câmbio, acréscimo aplicado uma única vez e total das linhas igual à fatura.
- Histórico: mudança de tarifa ou modelo não altera usos anteriores; custo com reserva de 15% não vira base comercial por engano.
- Separação por cliente: uma conta não acessa nem paga uso de outra; cada chamada e cada fechamento têm identificação própria.
- Duplicidades: repetição de webhook, tarefa, botão ou fechamento não repete cobrança; cache integral não gera nova cobrança de IA.
- Funcionalidades: WhatsApp acima das antigas contagens de mensagens continua funcionando dentro do limite financeiro; texto, áudio e imagem são medidos pelas unidades corretas.
- Ciclo: zero uso, mudança de mês, chamada cruzando o corte, evento atrasado, cancelamento e crédito/correção de cobrança.
- Pagamento: primeira cobrança, renovação, autenticação adicional, falha, nova tentativa na mesma fatura e confirmação recebida em duplicidade.
- Qualidade: exemplos comparáveis e configurações aprovadas por tarefa, com validação humana do áudio.

Sequência: implementar medição e precificação; validar os totais em ambiente de teste; homologar um ciclo completo de cobrança; ajustar manualmente as contas existentes; habilitar a cobrança real. O responsável administra os ajustes das contas, sem dependência de uma campanha ou ferramenta de transição.

## 11. Referências

- [Simulação de 18 cenários](simulacao-plano-consumo.md) e [dados dos cenários](simulacao-plano-consumo.json).
- [Avaliações de qualidade](benchmarks/2026-09-24-economia/README.md).
- [Stripe: faturas de assinatura](https://docs.stripe.com/billing/invoices/subscription) e [eventos de assinatura](https://docs.stripe.com/billing/subscriptions/webhooks), consultados em 24/09/2026.

As simulações são referências econômicas, não tarifa contratual confirmada. Este trabalho atualiza a especificação; não cria faturas nem altera assinaturas reais.

## 12. Estado da implementação (25/09/2026)

Implementado no código, sem publicação em produção:

- Registro de uso e tarifas congeladas (`models/consumo_flex.py`, `billing/flex.py`), com custo bruto, reserva interna de 15% e preço separados.
- Medição de texto, voz, transcrição, imagem, pesquisa e música pelo mesmo ponto (`billing/consumo_ia.py`), atribuída por request, WhatsApp, workers e tarefas em segundo plano.
- Seleção de modelos por programa e para o WhatsApp, catálogo, estimativa e amostra personalizada paga.
- WhatsApp sem franquia; oferta única Locufy Flex no checkout, painel e página de preços.
- Fechamento na fatura recorrente do Stripe, renovação, falha, nova tentativa, cancelamento e crédito vinculado.
- Combinações prontas de texto + voz: as 6 dos 3 modelos de texto com as 2 vozes (`billing/combinacoes.py`), escolhidas no passo do locutor do onboarding com exemplo em áudio, texto gerado e custos. Resultado da [validação](benchmarks/2026-09-25-combinacoes/README.md); as com Haiku exibem a limitação de fidelidade. O cliente escolhe uma ao gerar o locutor; a persona é gerada com o modelo de texto dela, o programa passa a usar texto e voz da combinação, e o painel mostra o preço estimado por hora, a estimativa mensal pelo horário do programa e o valor medido da geração. Só aparecem combinações com tarifas publicadas; `IA_COMBINACOES` remove as que não passaram pela validação de qualidade.

Verificação do fluxo com medição e bloqueio ligados (`tests/test_fluxo_flex_e2e.py`): adesão, uso real por rota, falha sem cobrança, cache sem cobrança, WhatsApp com reentrega, renovação com itens por modelo, cartão recusado bloqueando novas gerações, pagamento na mesma fatura, cancelamento sem mensalidade futura.

Correções feitas durante a verificação:

- Conta nova começava com limite financeiro zero e recebia recusa em toda geração. Agora recebe `IA_LIMITE_PADRAO_BRL` (R$ 300, provisório).
- Uma operação sem conclusão (processo reiniciado, thread perdida) mantinha a fatura em rascunho indefinidamente, sem cobrar nem a mensalidade. Após `IA_OPERACAO_ABANDONADA_MINUTOS` ela vira custo interno no fechamento.
- A classificação de tema em thread solta podia terminar depois da request e ficar pendente. Agora tem operação própria.
- O extrato e a fatura usavam o endereço da rota, com IDs, como funcionalidade, fragmentando linhas por programa. Agora usam nomes comerciais (`programa_ao_vivo`, `locucao`, `vinhetas` etc.).
- Rotas que convertem qualquer erro em 502 escondiam limite esgotado, inadimplência ou tarifa ausente. O motivo real chega ao painel.
- O assistente de suporte deixou de ser cobrado e bloqueado: conta inadimplente precisa perguntar como regularizar. Decisão reversível em `billing/contexto_ia.py`.

Pendências antes de habilitar a cobrança real:

1. Publicar as tarifas contratadas de todos os modelos em uso e conferir `GET /billing/admin/tarifas/pendentes` vazio. Com a medição ligada, modelo sem tarifa bloqueia a geração.
2. Criar o Price Locufy Flex (BRL 6990, mensal) e configurar `STRIPE_PRICE_ID_FLEX`.
3. Assinar no endpoint de webhook: `invoice.created`, `invoice.finalized`, `invoice.paid`, `invoice.payment_failed`, `invoice.payment_action_required`, `customer.subscription.updated`, `customer.subscription.deleted`.
4. Homologar um ciclo completo no modo de teste do Stripe (relógio de teste), incluindo renovação com consumo.
5. Confirmar o limite financeiro padrão. Hoje o cliente pode elevar o próprio limite até R$ 100.000; não há teto definido pela empresa para contas novas.
6. Ajustar manualmente as contas existentes.
