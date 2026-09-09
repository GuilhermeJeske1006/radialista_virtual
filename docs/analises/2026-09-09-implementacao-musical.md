# Implementação do formato musical de companhia

Implementação baseada na [análise da referência Manhã Play](2026-09-09-referencia-talkplay.md). O programa agora pode alternar sequências musicais, identificações curtas e retomadas com o apresentador principal, com uma única abertura na largada.

## Como usar

No editor do programa, selecionar **Formato do programa → Musical de companhia**. Usar **Usar sequência musical sugerida** para preencher o roteiro e salvar. O botão substitui a sequência em edição; selecionar apenas o formato mantém o roteiro personalizado.

Quando não há roteiro personalizado, o ciclo é:

1. Duas músicas sem locução obrigatória.
2. Identificação curta.
3. Mais duas músicas.
4. Retomada breve.

A abertura acontece antes do primeiro ciclo. O encerramento segue a proximidade do horário final do programa. As músicas são buscadas pelo repertório e critérios já cadastrados; pedidos reais continuam sendo anunciados e seguem seu fluxo de atendimento. Vinhetas e patrocinadores cadastrados podem ser colocados no roteiro pelos blocos existentes.

O perfil não insere comentários extras aleatórios. Programas existentes recebem `padrao` na migração, executada na inicialização do backend, e só adotam o novo formato quando configurados. A migração foi feita pelo mecanismo já usado pelo projeto, sem novo serviço ou dependência.

## Mudanças

- Perfil persistido no modelo, API e formulário; geração de configuração por IA também conhece a opção.
- Roteiro musical com abertura única, preservação dos blocos personalizados e apresentador principal. A prévia dos próximos blocos acompanha o mesmo ciclo.
- Música sem pedido: seleção normal da faixa e histórico preservados; nenhuma chamada de geração de locução ou TTS para anunciar essa faixa.
- Metas editoriais: abertura 20–30 s, identificação 3–7 s, retomada 6–12 s, anúncio de pedido musical 4–8 s e encerramento 10–18 s.
- Orçamento de palavras por função e uma única tentativa de reescrita quando excedido, compartilhada com a revisão de repetição já existente. Se a segunda resposta ainda exceder o orçamento, registra aviso e preserva a fala inteira; não corta nomes ou frases. Os tempos são metas, não uma garantia sobre a duração sintetizada.
- Direção de linguagem coloquial e energia moderada. O perfil dispensa inserções aleatórias de hesitações, mudanças de ideia, hora certa e marcos de tempo.
- Contrato `pausa_antes_ms`: aplicado uma vez antes do conteúdo preparado, com cancelamento ao pausar ou pular. Valores iniciais: 0 ms na largada e entre duas músicas; 150 ms em transições com música/vinheta; 800 ms envolvendo notícia; 350 ms nas demais. Os valores não são uma medição das transições da referência.
- Removida a segunda espera após o bloco no player atual. `intervalo_ms` continua na API para painéis antigos, mas o player atualizado o ignora.
- Cama musical permanece baixa durante o diálogo inteiro. A execução substituída não restaura o volume sobre a nova execução.
- Falas canceladas antes da reprodução não entram na gravação exportada; uma participação cancelada durante a transição é confirmada como interrompida.
- Contingência local do formato musical usa uma identificação curta, sem prometer uma música ainda indisponível.

## Validação

Resultado: **716 testes do backend e 125 do frontend passaram; TypeScript passou sem erros**. Depois do último ajuste de normalização dos rótulos e direção do prompt, os cinco testes específicos do perfil musical foram executados novamente e passaram. A suíte do frontend emite avisos de `act` nos testes da prévia e de navegação no jsdom, sem falhas.

Os testes adicionados exercitam o endpoint real com banco de teste e serviços externos substituídos, o formulário e a prévia com React Testing Library, e o hook do player com timers controlados. Cobrem sequência sem anúncios, orçamento de retomada, pedido real, encerramento por horário, persistência e rejeição de perfil inválido, migração de programa existente, pausas canceláveis e estabilidade da cama entre interlocutores.

As suítes completas incluem os testes existentes de áudio com FFmpeg: MP3 válido, preservação de duração/canais, controle de loudness e picos e ausência de ruído adicionado ao silêncio. Não houve chamadas reais aos fornecedores de IA, envio do áudio de referência, alteração de voz, mudança de masterização ou publicação em produção nesta implementação.

Comandos, nos respectivos diretórios:

```sh
# backend
STORAGE_BACKEND=local AWS_EC2_METADATA_DISABLED=true .venv/bin/python -m pytest -q --tb=short

# frontend-painel
npm test -- --reporter=dot
./node_modules/.bin/tsc --noEmit
```

## Limites e próxima avaliação

O ciclo é baseado em quantidade de faixas e na grade existente. Ainda não monta automaticamente um bloco fechado de 34 minutos a partir das durações de todas as músicas. O transporte do YouTube pode introduzir espera de carregamento; remover pausas programadas não garante reprodução sem intervalos.

Não foi produzido nem ouvido um programa completo com os serviços reais nesta etapa. A avaliação perceptiva de voz e da mistura completa continua sendo um piloto de escuta, em volume equivalente à referência. Esse piloto deve orientar ajustes finos de voz, relação voz/música e emendas. Locução sobre introdução musical, alinhamento das vinhetas aos pontos musicais e masterização da mistura completa exigem trabalho específico no transporte/mixer.
