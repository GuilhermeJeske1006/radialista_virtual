# WhatsApp: implementação, operação e validação

Implementação local de 12/11/2026 do [plano de evolução](plano-whatsapp-conversas-contexto.md). Não foi feito deploy nem ativada uma rádio de produção. Os testes de navegador usam APIs simuladas; os testes de concorrência usam PostgreSQL temporário, separado do banco do projeto.

## Fluxo entregue

1. No atendimento novo, o webhook autenticado persiste entrada, identidade da conversa e evento antes de confirmar o recebimento. STT, visão, agrupamento e interpretação podem executar no worker separado.
2. O worker retoma entradas pendentes após reinício. A exclusão por conversa usa advisory lock em PostgreSQL, numa conexão dedicada que sobrevive aos commits. SQLite/FakeRedis são usados nos testes unitários; a garantia entre processos é validada em PostgreSQL.
3. Texto de mídia é salvo antes de interpretar a conversa. Uma falha posterior não exige transcrever novamente uma mídia cujo checkpoint foi confirmado. Bolhas são agrupadas após silêncio configurável, com espera máxima, limite por grupo e separação de ocorrências na meia-noite.
4. Pedido, histórico, resposta pretendida e evento são confirmados na mesma transação. A outbox envia depois; timeout ambíguo fica `incerto`. IDs retornados pelo provedor identificam ecos sem comparar textos históricos.
5. A central reúne histórico paginado, respostas sem depender do eco, busca por contato, não lidas por operador, envio manual idempotente, responsável pelo atendimento, notas internas, pedidos e contribuições para pauta.
6. SSE distribui invalidações por conta, com cursor sequencial e replay. A atribuição do cursor e o commit são serializados por conta. O stream valida a sessão durante a conexão, limita conexões com leases e não mantém conexão SQL durante a espera. A aplicação compartilha um EventSource e mantém atualização periódica quando o stream falha.
7. Todo bloco preparado recebe identidade e token. O player precisa assumir a reprodução; outro player com lease ativo é recusado. Somente um bloco concluído publica o texto no contexto público. Uma pergunta preparada, interrompida ou sem áudio confirmado não vira pergunta feita.
8. O agente recebe o contexto público recente, referências de respostas citadas e um resumo privado com IDs de origem e validade. Histórico privado e notas internas não são entradas do roteiro.
9. Uma resposta claramente relacionada à discussão pode virar candidata automaticamente, limitada a uma candidata por ouvinte/discussão. A equipe também pode propor uma mensagem manualmente. Apenas a revisão com texto autorizado cria a pauta do programa. A confirmação do bloco que utiliza essa pauta marca a contribuição como utilizada e atualiza a conversa.
10. Fixar uma pauta é idempotente; descartar deixa uma decisão persistente que impede o matcher de recriar a associação. Excluir um programa encerra e desvincula o estado do canal, preservando as evidências. Radialistas com histórico do novo atendimento devem ser desativados para preservar esse histórico.
11. O resultado de um pedido aparece na conversa. A rádio pode habilitar o aviso ao ouvinte após reprodução confirmada. O aviso usa a mesma outbox e fica desligado por padrão.

## Ativação e serviços

O atendimento continua habilitado por conta em **Ao Vivo → Atendimento aos ouvintes**. A opção de resposta automática de cada radialista continua controlando as respostas do agente. Não é necessário ligar automaticamente contas existentes.

Os arquivos Compose locais e de produção incluem `whatsapp-worker` com o mesmo banco e Redis do backend. Eles definem `WHATSAPP_WORKER_ATIVO=true` tanto no servidor HTTP quanto no worker. O worker de produção aguarda a saúde do backend, que executa a migração aditiva de tabelas e índices.

Para execução fora do Compose:

```sh
# No ambiente do backend, depois de criar/migrar as tabelas.
WHATSAPP_WORKER_ATIVO=true .venv/bin/python -m app.whatsapp.worker
```

O processo HTTP também precisa receber `WHATSAPP_WORKER_ATIVO=true`. Com `false`, permanece disponível o caminho síncrono de compatibilidade; não há recuperação autônoma de entradas desse caminho sem o worker. O controle humano da central também pausa respostas do caminho legado.

Configuração documentada em `backend/.env.example`:

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `WHATSAPP_WORKER_ATIVO` | `false` fora dos Compose | Confirma a entrada e delega o atendimento novo ao worker. |
| `WHATSAPP_DEBOUNCE_S` | `6` | Silêncio antes de agrupar mensagens. |
| `WHATSAPP_AGRUPAMENTO_MAX_S` | `60` | Evita espera infinita quando o ouvinte continua digitando. |
| `WHATSAPP_TENTATIVAS_MAX` | `5` | Encaminha entradas com falha persistente para conferência operacional. |
| `WHATSAPP_MIDIA_RETENCAO_HORAS` | `24` | Limpa mídia bruta da inbox. Transcrição e registros operacionais têm ciclo próprio. |

A imagem WuzAPI não foi trocada nem fixada numa versão sem verificar compatibilidade. A instância do outro sistema presente no Compose de produção foi preservada.

## Conferência de falhas

- **Mensagem com falha:** o painel mostra a pendência e permite retomar o processamento. Mídia já expirada precisa ser reenviada pelo ouvinte.
- **Envio incerto:** conferir no WhatsApp antes de tentar novamente. A ação exige confirmação explícita e recusa contexto antigo quando a conversa já avançou.
- **Atendimento humano:** uma pessoa assume a conversa; outra pessoa não pode enviar por ela. A API permite transferência explícita de responsável na mesma conta. Envios manuais pendentes/incertos precisam ser resolvidos antes de devolver ao agente.
- **Callback ausente:** o preparo não é tratado como fala concluída. A fila mantém os controles existentes de revisão de seleções sem confirmação.
- **Sessão do WhatsApp:** conexão continua sendo consultada no provedor; token provisionado não é tratado como prova de conexão no dashboard/checklist. Mudanças observadas também geram eventos de estado.

Não alternar o modo de processamento com jobs e envios em execução. Para rollback operacional, pausar a entrada/atendimento da conta, drenar ou conferir pendências e então trocar os processos. As tabelas novas são aditivas; o histórico anterior continua disponível.

## Contratos adicionados

- `GET /ouvintes/central`: lista operacional com busca, modo de atendimento, não lidas e paginação.
- `GET|POST /ouvintes/conversas/{id}/mensagens`: histórico por cursor e envio manual com chave idempotente.
- `GET /ouvintes/conversas/{id}/contexto`: pedidos, memória privada, notas e contribuições.
- `POST /ouvintes/conversas/{id}/leitura` e `/notas`: marcador por operador e anotação interna.
- `POST /ouvintes/conversas/{id}/contribuicoes`, `PATCH /ouvintes/contribuicoes/{id}`: proposta e revisão editorial.
- `GET /ouvintes/eventos`: SSE com `Last-Event-ID`.
- `POST /ouvintes/transmissao/blocos/{id}/eventos`: reprodução/heartbeat/resultado autenticados com token e player.
- `GET /ouvintes/transmissao/programas/{id}/contexto`: contexto confirmado e estado observado do player.
- `GET /ouvintes/operacao`, `POST /ouvintes/entradas/{id}/reprocessar`, `POST /ouvintes/envios/{id}/reenviar`: acompanhamento e recuperação.

Os endpoints existentes de pedidos, assumir/devolver atendimento, métricas e exportação continuam disponíveis.

## Testes reproduzíveis

```sh
cd backend
.venv/bin/ruff check app tests
.venv/bin/pytest -q

# Exclusivamente contra um PostgreSQL de teste. Cada teste cria e remove seu próprio schema.
WHATSAPP_TEST_DATABASE_URL=postgresql://usuario:senha@localhost:porta/banco_teste \
  .venv/bin/pytest -q tests/test_whatsapp_canal.py -k postgres
```

```sh
cd frontend-painel
npx tsc --noEmit
npm test
npm run build
```

O ambiente host inspecionado tem Next instalado em versão diferente da declarada no lockfile. O build padrão foi validado em container isolado com **Next 16.3.0 e Node 20**, sem alterar as dependências locais ou o container de desenvolvimento. O build com Webpack também passou no host; o Turbopack do Next 16.3.5 instalado no host falhou na resolução das fontes.

Resultados desta execução: **1.489 testes passaram na suíte completa do backend**, com três testes PostgreSQL pulados nessa rodada e executados separadamente (**3 passaram**). A rodada direcionada final de canal, atendimento e integração de pautas passou com **54 testes**. O frontend passou com **350 testes em 63 arquivos**, além de typecheck, build de produção e validação em Chromium desktop/celular. Ruff e validação dos Compose também passaram. Resumo estruturado em [validacao.json](benchmarks/2026-11-12-whatsapp/validacao.json).

As evidências visuais com dados simulados ficam em [desktop](benchmarks/2026-11-12-whatsapp/desktop.png) e [celular](benchmarks/2026-11-12-whatsapp/celular.png), acompanhadas do [script de validação](benchmarks/2026-11-12-whatsapp/playwright.cjs). Os testes cobrem reentrega, agrupamento, checkpoint de mídia, outbox, timeout de envio, disputa entre operadores, isolamento de contas, memória privada, resposta citada, replay do stream, reprodução, revisão de pauta, migração e arquivamento de programa.

## Validação externa ainda necessária

Antes do rollout, executar o piloto numa rádio de teste: texto/áudio/imagem reais, QR, queda de sessão, ID de envio, eco, interrupção de reprodução e participação revisada. Nenhuma mensagem real foi enviada durante esta execução.

Recibos de entrega/leitura, histórico sincronizado e aliases PN/LID dependem dos contratos da versão WuzAPI implantada. O estado implementado de envio aceito pelo provedor não é apresentado como entrega ou leitura. A confirmação do navegador demonstra o resultado do player, não a recepção do sinal externo da emissora.

Ficam para a aferição em piloto: SLOs de latência/capacidade com volume real, qualidade das respostas dos modelos, agrupamento editorial mais elaborado por ouvintes distintos e a política definitiva de retenção/exclusão dos registros e derivados. A limpeza da mídia bruta e a expiração do contexto já têm tratamento próprio; não equivalem à exclusão de todo o histórico.
