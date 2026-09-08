# Atendimento de ouvintes: operação e validação

O fluxo novo é ativado por rádio no painel **Ao Vivo → Atendimento aos ouvintes** (administradores). Por padrão fica desativado, permitindo um piloto sem alterar as outras contas. A opção **resposta automática no WhatsApp** do radialista continua controlando o envio de respostas. Desativar o fluxo novo retoma o caminho legado; os pedidos novos permanecem registrados para revisão e não são consumidos pela fila legada.

## Fluxo implementado

1. Webhook identifica e autentica a rádio; IDs do fluxo novo recebem um namespace por conta, compatível com a restrição de unicidade existente.
2. Inbox persistente registra cada bolha. Depois de seis segundos de silêncio, as bolhas pendentes do mesmo ouvinte/programa são processadas juntas. Reentregas das bolhas anteriores também são reconhecidas.
3. Uma trava por rádio/ouvinte impede processamento concorrente. O pedido e o processamento das bolhas são confirmados no banco antes do envio da resposta.
4. Conversa recente contém até dez mensagens de usuário/assistente. Somente respostas enviadas entram como falas da rádio. Contexto expira após 24 horas de inatividade e reinicia na mudança de ocorrência do programa; o nome preferido e a opção de atendimento humano são independentes desse histórico. A limpeza é feita no acesso à conversa; os logs operacionais existentes continuam seguindo sua política anterior.
5. O agente pede informações faltantes, interpreta correções/cancelamentos e registra solicitações completas para revisão. Alterações só afetam um pedido pendente identificado sem ambiguidade.
6. A equipe confere a autorização, escolhe o nome e escreve o texto que pode ir ao ar. A aprovação verifica o horário, os temas, as restrições musicais e o perfil do programa. O texto privado original fica separado.
7. Cada pedido pertence a um programa e à sua ocorrência na grade (ID + data local do início, inclusive quando atravessa a meia-noite). Uma transferência exige escolha explícita de outro programa no horário de exibição e uma nova revisão. Não há transferência automática.
8. O player recebe ID e token de seleção. Fim natural de fala, fim da faixa ou corte configurado da faixa podem confirmar execução. Erro, timeout, falta de áudio ou interrupção não confirmam execução. A geração antecipada de roteiro não marca o pedido como atendido.

O novo roteiro recebe somente o texto aprovado, a identidade do radialista e o contexto da rádio/programa. Pede reação breve e específica, sem deduzir profissão, sentimentos ou intimidade. A recorrência usa o identificador do ouvinte em vez do nome. A fila favorece outro ouvinte quando a seleção anterior foi da mesma pessoa.

## Controles da equipe

- Aprovar conteúdo para o ar, editar nome, cancelar ou recusar com motivo.
- Transferir para revisão em outro programa em exibição.
- Revisar seleção sem confirmação: antes, interromper o bloco no player e conferir se a participação tocou. Um token antigo não pode confirmar uma nova seleção.
- Assumir a conversa e devolver ao agente. O atendimento humano continua no WhatsApp conectado. Mensagens manuais recebidas via `FromMe` pausam o agente; ecos reconhecidos de respostas automáticas não pausam.
- Conferir envios incertos no WhatsApp antes de tentar novamente. Falha ao estabelecer conexão permite duas tentativas automáticas; timeout após envio exige conferência para evitar duplicidade. Uma resposta antiga não é reenviada se a conversa avançou.
- Consultar contagens dos estados dos pedidos nos últimos 30 dias e o histórico das alterações de cada participação.

## Estados

`aguardando_revisao` → `em_fila` → `selecionado` → `executado`.

Alternativas: `cancelado`, `nao_atendido`, `expirado`. Correções e transferências retornam à revisão. Pedidos de transmissões encerradas expiram na seleção/consulta da fila. Seleções sem callback continuam visíveis para conferência humana; não são reenfileiradas automaticamente.

Histórico anterior marcado como atendido recebe `historico_legado`: não é tratado como evidência de reprodução confirmada pelo novo player. Um pedido de sorteio é uma solicitação; não confirma inscrição ou elegibilidade.

## Banco e compatibilidade

As rotinas idempotentes de startup acrescentam colunas à fila, à conta e aos logs, além do índice de consulta por programa/transmissão/estado. As tabelas de conversa e inbox são criadas pelo metadata existente. O conteúdo anterior é preservado. Teste de migração verifica duas execuções sobre a mesma tabela legada.

A exclusão mútua depende do Redis já usado pela aplicação; seleção concorrente usa bloqueio de linha em PostgreSQL. Os testes usam SQLite/FakeRedis. Sem ID do provedor, não há como reconhecer com certeza uma reentrega como sendo a mesma mensagem.

## Validação e piloto

Testes automatizados cobrem isolamento de rádios/programas, mensagens fragmentadas, reentrega, falhas de envio, correção, cancelamento, autorização, perfil musical, expiração, seleção, callbacks, histórico privado e migração. A interface foi exercitada com Playwright em desktop e celular, com APIs simuladas. O teste de navegador também reproduz fim de áudio e erro de áudio simulados, verificando os callbacks `executado` e `falhou`.

Para o piloto, ativar uma rádio de teste e a resposta automática de um radialista, enviar pedidos de texto/áudio pelo WhatsApp, aprovar o conteúdo e acompanhar o player. Conferir a resposta entregue, o texto falado e o estado final da fila. Incluir uma interrupção deliberada e uma música indisponível. A qualidade das falas geradas pelos provedores e a entrega real do WhatsApp precisam dessa validação operacional; os testes locais não são prova de transmissão real.

Não foi ativada nenhuma conta de produção nem enviado conteúdo a ouvintes durante esta implementação.
