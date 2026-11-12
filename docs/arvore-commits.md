# Árvore de commits e integração com o Claude Code

Atualizada em 12/11/2026. Este registro separa o plano de rádio executado pelo Claude Code das frentes adicionais que estavam na árvore local.

## Base do Claude Code

No início da organização, o worktree `locufy-radio` estava limpo na branch `melhoria/f4-promessas`, em `04bff64`. A F4 já inclui o encerramento independente da F3 (`24cdd13`), posterior ao antigo ponteiro local da F3 (`c382859`). Na conferência final, o Claude já havia criado `melhoria/f5-fontes` a partir da nossa integração em `6ca7049`; seu worktree estava limpo em `356575d`.

A referência `melhoria/f3-contexto-emissao` foi avançada **somente por fast-forward**, de `c382859` para `24cdd13`. O histórico e a branch da F4 foram preservados, assim como o worktree do Claude. As avaliações e os estados das frentes continuam sendo os registrados em [melhoria-radio/RELATORIO.md](melhoria-radio/RELATORIO.md).

```text
melhoria/f0-bancada              ce44667
  └─ melhoria/f1-relogio         0f8831a
      └─ melhoria/f2-duracao-fala 930c796
          └─ melhoria/f3-contexto-emissao 24cdd13
              └─ melhoria/f4-promessas   04bff64
                  └─ integração do WhatsApp e frentes adicionais
                      ff58d48 → 8cc7573 → a62849f → b013a9b → ae98042
                      → 9f0aea2 → 575fca3 → 1666752 → 7aeac02 → 6ca7049
                          ├─ f1efbba  documentação da integração pós-F4
                          └─ F5: 14 commits → 356575d
                              └─ HEAD: união dos dois históricos
                                 melhoria/f5-fontes [worktree do Claude Code]
                                 integracao/whatsapp-pos-f4 [worktree principal]
```

Os commits novos foram criados por assunto e reaplicados sobre a F4. Somente esses commits locais novos foram reescritos durante o rebase; nenhum commit do Claude foi reescrito. `master` e as referências remotas não foram alteradas. Os commits permanecem locais.

## Separação das frentes

| Commit | Escopo |
| --- | --- |
| `ff58d48` | Controle compartilhado de capacidade, filas, recuperação do Ao Vivo, preparo antecipado, reserva e testes. |
| `8cc7573` | Descoberta contextual de fontes, edição dos links e paginação da pauta. |
| `a62849f` | API e painel do piloto esportivo, revisão factual, áudio e migração de fontes. |
| `b013a9b` | Inbox/worker/outbox, eventos, memória privada, discussão, contexto confirmado e testes de backend. |
| `ae98042` | Central de conversas, autoria, envio manual, notas, recuperação e integração do player. |
| `9f0aea2` | Plano, operação e capturas/testes do WhatsApp. |
| `575fca3` | Documento de estado dos Reels que já estava na árvore, sem alteração ou publicação de vídeos. |
| `1666752` | Aviso de reprodução de pedido legado usa o programa validado pela F4; callback repetido não duplica envio. |
| `7aeac02` | Relato atribuído de data futura, sem chamada da emissora, não é cortado como promessa. Chamadas reais continuam sujeitas à agenda. |
| `6ca7049` | Testes de retentativa usam sessões independentes, evitando reciclagem de IDs do SQLite no mesmo mapa de identidades. |

As mudanças já existentes de capacidade, descoberta e esportes foram preservadas em commits próprios. Arquivos compartilhados foram separados no index, sem substituir a versão de trabalho durante essa organização.

## Compatibilidade com a F4

O rebase não exigiu resolução de conflitos textuais. A revisão semântica encontrou duas diferenças relevantes:

- Desde a F4, o player também confirma pedidos legados, cujo `programa_id` na fila é nulo. A notificação do WhatsApp passou a usar o programa validado pelo callback, com teste de idempotência para duas confirmações iguais.
- O marcador “amanhã” fazia o detector cortar a notícia esportiva “Segundo a federação, o próximo jogo será amanhã”. O detector agora distingue relatos atribuídos de tipo genérico e sem referência à emissora das chamadas do locutor. O recorte é conservador; não comprova a veracidade de uma notícia nem substitui a F5. Testes cobrem as datas factuais e garantem que a atribuição não libere promessas de conteúdo da emissora.

A suíte completa também revelou uma fragilidade no dublê do worker: ele reutilizava uma sessão após rollback, enquanto o processo real abre uma sessão por tarefa. O teste foi alinhado ao ciclo real, eliminando a reciclagem de identidades do SQLite entre tentativas.

Foram mantidos os tokens e a confirmação de seleção da F4, o controle de promessas, as obrigações do relógio, os detectores de participação e os relatórios independentes do Claude. A integração não declara concluídas as fases seguintes pelo simples acréscimo do piloto esportivo ou do WhatsApp. A F5 avançou independentemente no worktree do Claude após essa integração.

As simulações dos três perfis foram repetidas em modo `fake`, sem rede e sem cobrança. Os resumos ficam em [integracao-f4/simulacao](integracao-f4/simulacao/).

| Perfil | Hard times perdidos | Anúncios sem confirmação | Promessas vencidas | Pedidos indevidos | Ouvintes inexistentes | Atraso máximo |
| --- | --- | --- | --- | --- | --- | --- |
| Musical adulto | 0 | 0 | 0 | 0 | 0 | 0 s |
| Popular/sertanejo | 0 | 0 | 0 | 0 | 0 | 0,36 s |
| Variedades leves | 0 | 0 | 0 | 0 | 0 | 0 s |

Essas simulações validam a mecânica com dublês; não substituem avaliação de locução com provedores reais ou piloto com uma rádio. Nenhum custo de geração real foi autorizado ou executado nesta organização do histórico.

## Validação final

O código em `6ca7049`, já integrado à F4, passou na suíte completa do backend: **1.633 testes aprovados e 3 ignorados**, em 446,50 segundos. Ruff, TypeScript, os **350 testes do frontend em 63 arquivos**, os **3 testes de concorrência com PostgreSQL** e o build de produção em Docker com Next 16.3.0 e Node 20.20.2 também passaram. O banco temporário foi removido após a validação.

As três simulações acima foram executadas sobre esse mesmo commit. O commit `f1efbba` registra somente documentação e evidências dessa validação.

## Integração na fase mais recente

A pedido do usuário, todo o histórico foi reunido na versão mais recente do plano: **F5, branch `melhoria/f5-fontes`**. A F5 em `356575d` já descendia de `6ca7049` e continha todo o código do WhatsApp, da central de conversas, do contexto confirmado, da capacidade dos provedores e do piloto esportivo. Faltava somente `f1efbba`, com a árvore e as evidências da integração pós-F4.

Os dois históricos foram unidos por merge, sem conflitos e sem reescrever commits. O backend e o frontend resultantes são idênticos aos da F5 em `356575d`; as diferenças adicionais são a documentação da integração. A branch `melhoria/f5-fontes` é avançada por fast-forward para esse merge, mantendo o worktree do Claude na mesma branch. A branch `integracao/whatsapp-pos-f4` também passa a conter a F5, apesar do nome histórico.

O relatório do Claude registra a F5 como implementada, com portão local verde e portão independente/juiz pendentes. Os 1.901 testes de backend e 354 de frontend do portão local estão em [melhoria-radio/f5/testes.md](melhoria-radio/f5/testes.md). O estado dessas revisões pendentes permanece o registrado no relatório.

Conferência após a união: **359 testes de backend aprovados e 3 ignorados** (WhatsApp, atendimento, dados verificáveis, promessas e notícias), em 45,11 segundos; **354 testes do frontend aprovados em 65 arquivos**, em 14,66 segundos; Ruff e TypeScript aprovados. A comparação com `356575d` confirmou ausência de diferenças no código de backend e frontend. A suíte completa de backend não foi repetida nesta união documental; os 1.901 testes acima são o resultado já registrado pelo Claude para esse mesmo código.

Operação e limites do canal: [whatsapp-operacao.md](whatsapp-operacao.md). O registro anterior de testes do WhatsApp continua preservado; a validação pós-F4 é registrada separadamente em [integracao-f4/validacao.json](integracao-f4/validacao.json).
