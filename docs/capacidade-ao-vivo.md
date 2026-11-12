# Capacidade e continuidade do ao vivo

O controle compartilhado em `backend/app/guardrails/provedores.py` limita as chamadas
de todas as rádios, workers e servidores que usam o mesmo Redis e credenciais. Fila
limitada, prioridade do ao vivo e leases com expiração evitam que um pico ou um worker
encerrado deixe a conta sem controle. Todos os modelos TTS compartilham um teto
conservador. Claude Opus 4.x e Sonnet 4.x compartilham seus respectivos pools; os
demais modelos têm pools próprios. Solicitações de teste de consumo também passam
pelo controle. O cache de áudio existente continua antes da admissão.

## Configuração

`backend/.env.example` documenta as variáveis. Os defaults são tetos operacionais
conservadores, não limites garantidos pelos fornecedores. Confirmar o plano/modelo
na ElevenLabs e os limites da organização Anthropic antes de dimensionar a frota.
Não usar novas chaves para contornar as cotas da mesma organização.

`IA_LIMITES_PROVEDORES` define concorrência por serviço e RPM, tokens de entrada e
saída por minuto do LLM. Informar o objeto completo ao substituir a variável. Um
override em `IA_LIMITES_POR_POOL` altera somente os campos indicados, por exemplo:

```dotenv
IA_LIMITES_POR_POOL={"llm:claude-opus-5":{"rpm":100,"entrada":200000,"saida":40000}}
```

Esse exemplo não é uma recomendação de cota. Reservar capacidade para a variabilidade
de latência e para outras aplicações que usam a mesma organização. Aumentar servidores
não aumenta limites do fornecedor. Ambientes independentes devem usar Redis e
credenciais próprios; todos os processos da mesma instalação precisam da mesma
configuração. Alterações nas variáveis exigem reiniciar esses processos.

Os buckets repõem capacidade continuamente. A entrada conhecida é reservada por
bytes UTF-8 (conservador) e a saída pelo `max_tokens`; ao receber `usage`, ambos são
reconciliados com o uso real. Tokens lidos do cache não consomem o bucket de entrada.
Busca web reserva contexto adicional (`IA_BUSCA_RESERVA_TOKENS`); uso maior cria
dívida que impede novas admissões até a reposição. Uma chamada maior que o bucket
configurado é recusada imediatamente. Conferir esses tetos também para geração de
configuração e pesquisa, que usam mais tokens que uma locução curta.
Imagens usam a margem configurável `IA_IMAGEM_RESERVA_TOKENS` por imagem, reconciliada
com o uso real; o base64 do arquivo não é contado como texto no bucket.

`IA_FILA_MAX` limita pendências por pool e `IA_FILA_ESPERA_S` limita a espera de cada
admissão. O timeout da operação inclui espera e retries; requests do ao vivo têm
um orçamento compartilhado de 65 segundos. Redis indisponível recusa novas chamadas
pagas e preserva a reprodução já preparada. Não há queda para chamadas ilimitadas.

## Recuperação

Rejeições explícitas 429/503/529 permitem retry com jitter e cooldown compartilhado.
`Retry-After` em segundos/data e `retry-after-ms` são respeitados sem encurtamento.
Se a espera não cabe no prazo, a operação termina e o cooldown continua protegendo
outras rádios. Limite financeiro mensal não é retentado. Timeout e conexão interrompida
não repetem POST: o fornecedor pode já ter cobrado. Streaming retém sua vaga até o
último byte/close e nunca reinicia depois de começar a entregar áudio.

O player mantém os dois blocos de antecedência existentes. Falhas de texto espaçam
as próximas tentativas em 5, 10, 20 e até 30 segundos, com jitter; falhas de voz
também suspendem novas sínteses brevemente. Música e arquivos já preparados continuam
disponíveis. Se o texto falhar, a rota autenticada `/live/{radio}/programas/{programa}/reserva`
serve somente uma vinheta de passagem automática, ativa, pronta e pertencente ao
programa/conta. Não chama IA nem serve notícias antigas. Sem essa gravação, permanece
o comportamento de música de fundo e texto local. A transmissão ainda depende de
uma fonte de música disponível, navegador ativo e permissão de reprodução.

O preparo da abertura usa um pool pequeno com backlog limitado, sessões de banco
próprias por tarefa e ordem de início mais próximo. O tick do scheduler retorna
sem aguardar as gerações. Somente preparos concluídos deduplicam a ocorrência por
horas; falhas podem ser tentadas na próxima rodada. `GETDEL` consome o preparo uma
vez mesmo com dois clientes simultâneos (Redis 6.2+).

## Monitoramento e dimensionamento

`GET /admin/ia/capacidade`, com autenticação de superadministrador, mostra limites
configurados, fila, chamadas em andamento, cooldown, buckets disponíveis e totais
dos últimos 15 intervalos de minuto: solicitações, sucessos, erros, 429, retries,
recusas, tempos de fila/execução e tokens. Headers de limites/uso publicados pelo
fornecedor aparecem quando disponíveis. O SDK Anthropic não expõe todos os headers
nas respostas de sucesso. Não são retornadas chaves nem textos das rádios.

O endpoint sinaliza ocupação instantânea de 70%, rate limits e recusas. Os logs
registram filas vencidas e retries para o monitoramento já instalado. O consumo e
os limites financeiros por conta continuam no sistema de billing existente; saldo
externo dos fornecedores deve ser acompanhado também nos respectivos consoles.

Uma estimativa inicial é:

```
rádios ≈ concorrência × 60 × utilização desejada
         / (segundos de geração × chamadas TTS por rádio por minuto)
```

Calcular separadamente os tetos de RPM/entrada/saída do Claude e adotar o menor
resultado, incluindo chamadas auxiliares. Usar latências medidas sob carga e
programação real. Diálogos geram uma chamada de voz por linha, não por bloco.

Para testar o mecanismo sem APIs ou créditos:

```sh
cd backend
.venv/bin/python scripts/simular_capacidade.py --radios 1 5 10 25 50 --concorrencia 3
```

A simulação usa fakeredis e latência artificial, com duas gerações por rádio.
Valida que o teto é respeitado, a fila escoa e leases são liberados. Não prova
capacidade de produção. Antes de ampliar o limite comercial, medir uma carga gradual
com latências reais, horários coincidentes e falhas de Redis/provedores, acompanhando
CPU, memória, banco, pós-produção e tamanho da reserva de áudio. Ajustar o plano dos
fornecedores quando a demanda sustentada ultrapassar a margem disponível.
