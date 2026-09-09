# Comparação de geração de falas — 09/09/2026

O maior ganho medido veio de trocar a síntese de voz por Eleven Flash v2.5. O caminho recomendado é um piloto de Flash com a voz já configurada e o tratamento Rádio FM, mantendo Opus 5 inicialmente para escrever. A escolha definitiva da voz depende de escuta: transcrição e métricas de áudio não demonstram equivalência de expressividade ou identidade vocal.

Nenhum modelo de produção foi alterado. As chamadas foram feitas diretamente às APIs já utilizadas pelo projeto, com dados fictícios, sem publicar áudio ou atender ouvintes reais.

## Suíte do projeto

| Verificação | Resultado |
|---|---|
| Backend completo — pytest | 709 passaram em 165,40 s |
| Frontend completo — Vitest | 115 passaram, em 19 arquivos |
| TypeScript — `tsc --noEmit` | Passou |
| Sintaxe do script — `py_compile` | Passou |

A primeira execução do backend teve 699 sucessos e 10 falhas porque herdou `STORAGE_BACKEND=s3` do ambiente local, sem credenciais AWS. Ao executar a suíte completa com `STORAGE_BACKEND=local AWS_EC2_METADATA_DISABLED=true`, os 709 testes passaram. Não foi necessário alterar o código de produção. A suíte do projeto usa mocks para fornecedores; a comparação de desempenho foi feita separadamente nas APIs reais.

Comandos de verificação, nos respectivos diretórios:

```sh
# backend
STORAGE_BACKEND=local AWS_EC2_METADATA_DISABLED=true .venv/bin/python -m pytest -q --tb=short
# frontend-painel
npm test -- --reporter=dot
./node_modules/.bin/tsc --noEmit
```

## Método

- Texto: 3 modelos × 5 cenários × 2 rodadas = 30 chamadas reais. Mesmo prompt base de `montar_system_prompt`, mesma mensagem por cenário, até 512 tokens, sem retentativas. Opus/Sonnet com thinking desabilitado e esforço baixo; Haiku sem parâmetro de esforço. Ordem dos modelos alternada entre rodadas.
- Cenários: anúncio musical, evento sem autorização, evento sem data confirmada, evento encerrado e diálogo de dois apresentadores.
- Voz: 2 modelos × 3 tamanhos de texto × 2 rodadas = 12 sínteses reais, mesma voz configurada no ambiente, mesma direção de energia, uma tentativa, timeout de leitura de 35 s e pós-produção `radio_fm` do projeto. As configurações específicas de cada modelo foram montadas pelo cliente existente.
- Áudio: decodificação e análise das 12 amostras; transcrição de 4 amostras médias/longas com Scribe v1, seguida de comparação textual.
- Cada etapa executou suas chamadas sequencialmente. As etapas de texto e voz rodaram simultaneamente em processos separados, junto da suíte local; os tempos incluem rede e as condições dessa execução.

O benchmark de texto usa o prompt base real, com cenários sintéticos. Não reproduz todos os acréscimos da rota `/proxima`, busca musical, histórico longo, clima, banco, concorrência em produção ou falas regeneradas. No diálogo foi usada uma instrução sintética com o mesmo formato de saída, não o caminho completo de roster. O teto uniforme de 512 tokens difere do teto de 4096 usado atualmente por `gerar_configuracao` em diálogos. Nenhuma resposta atingiu o teto neste ensaio.

## Latência de texto

| Modelo solicitado | Chamadas bem-sucedidas | Mediana | Maior tempo observado |
|---|---:|---:|---:|
| Claude Opus 5 | 10/10 | 4,06 s | 6,19 s |
| Claude Sonnet 5 | 10/10 | 3,39 s | 4,56 s |
| Claude Haiku 4.5 | 10/10 | 2,37 s | 3,20 s |

Sonnet reduziu a mediana em aproximadamente 16% (0,67 s) e Haiku em 42% (1,70 s), em relação ao Opus. As respostas têm comprimentos diferentes: totais de saída foram 1.730 tokens para Opus, 1.694 para Sonnet e 1.440 para Haiku. Não interpretar essa comparação como taxa pura de geração de tokens.

## Latência de voz, incluindo Rádio FM

| Texto | Eleven v3: média das 2 rodadas | Flash v2.5: média das 2 rodadas | Redução |
|---|---:|---:|---:|
| Curto — 118 caracteres | 4,14 s | 1,30 s | 69% |
| Médio — 372 caracteres | 10,44 s | 2,74 s | 74% |
| Longo — 692 caracteres | 19,31 s | 3,94 s | 80% |

Mediana geral: 10,44 s no v3 e 2,74 s no Flash, redução de 74%. Ambos concluíram as 6 sínteses sem erro. A redução é do tempo de espera para gerar/processar o arquivo; não é uma aceleração de quatro vezes na reprodução da fala.

O pós-processamento Rádio FM ficou incluído nos tempos e foi preservado. Não é necessário removê-lo para obter o ganho observado. O timeout maior e a ausência de retentativas do ensaio diferem da política atual de produção: zero falhas em 12 chamadas não prova que os timeouts desaparecerão sob carga.

## Qualidade e aderência às instruções

- Todos os modelos recusaram os convites explícitos para o evento sem autorização e para a edição encerrada; nenhum inventou uma data para o evento de data desconhecida nesses cenários.
- Há uma falha editorial comum aos três: no cenário de data desconhecida, prometeram divulgar posteriormente quando a informação chegasse, sem condicionar isso à autorização da rádio. Exemplo do Opus: “Assim que tiver informação certinha, a gente comenta.” A regra de eventos ainda precisa de refinamento e nova avaliação, independentemente da troca de modelo.
- Sonnet confundiu o nome fictício “Tarde Musical” com o horário atual em algumas respostas. O contexto real era de manhã, mas uma saída abriu com “Boa tarde, Curitiba!”. Em outra, começou a mencionar “quarta-feira de sol” sem clima informado e se corrigiu na própria fala.
- Haiku retornou os dois diálogos com cercas Markdown, apesar do pedido de JSON puro. O parser atual `extrair_json` tolera isso, portanto não equivale a quebra do endpoint. Também gerou emojis e expressões menos adequadas à locução; o teste não justifica adotá-lo como redator padrão somente pela velocidade.
- Opus também não foi perfeito: acrescentou familiaridade local não fornecida, como “o pessoal aqui de Curitiba conhece bem”, e fez promessas de divulgação futura. Não há aprovação editorial integral de nenhum dos três modelos.
- As 12 amostras de voz decodificaram corretamente, tiveram valores finitos e nenhuma amostra digital atingiu o limiar de saturação adotado (amplitude absoluta ≥ 0,999 após decodificação). Isso não exclui artefatos perceptivos.
- As quatro transcrições preservaram os pedidos, nomes e frases principais. Houve pequenas variações, como “deixa”/“deixe” e “para a sua”/“pra sua”, que também podem vir do reconhecimento de voz. Não houve omissão de frase inteira observada. Transcrição não avalia emoção, sotaque, naturalidade ou fidelidade de uma voz clonada.

## Caminho recomendado

1. Fazer piloto do `eleven_flash_v2_5` com a voz configurada e Rádio FM. Ouvir as amostras abaixo para decidir se a entrega vocal atende à rádio. Manter v3 disponível para a locução que exija sua expressividade.
2. Manter Opus 5 inicialmente. O ganho do Sonnet neste ensaio foi pequeno diante do ganho de voz; trocar ambos juntos dificultaria atribuir mudanças de qualidade. Sonnet continua candidato a um segundo piloto com prompts completos de produção e maior cobertura editorial.
3. Corrigir promessas de divulgação futura sem autorização e testar as respostas do agente novamente. Isso é um problema observado inclusive no modelo atual.
4. Após o piloto, medir separadamente texto, síntese, pós-produção e retentativas no fluxo real. Revisar a espera acumulada quando a síntese integrada falha e o navegador tenta `/tts` novamente. Já existe preparo antecipado de blocos; este teste não indica necessidade de aumentar o número de blocos preparados.

Não somar as medianas de texto e voz como se fossem medição completa de `/proxima`: as entradas de TTS foram fixas e independentes das respostas dos modelos. A amostra de duas rodadas por cenário é exploratória; não mede p95, SLA, estabilidade prolongada, carga simultânea ou todas as vozes cadastradas.

## Evidências e reprodução

- [Resultados completos de texto](texto.json)
- [Resultados completos de síntese](voz.json)
- [Métricas e transcrições de áudio](qualidade_audio.json)
- [Textos fixos usados na síntese](entradas_voz.json)
- [Script de reprodução](../../../backend/scripts/benchmark_falas.py)

As amostras estão no diretório temporário `/tmp/locufy-benchmark-2026-09-09`:

- [V3 — texto médio](/tmp/locufy-benchmark-2026-09-09/eleven_v3-media-1.mp3)
- [Flash — texto médio](/tmp/locufy-benchmark-2026-09-09/eleven_flash_v2_5-media-1.mp3)
- [V3 — texto longo](/tmp/locufy-benchmark-2026-09-09/eleven_v3-longa-1.mp3)
- [Flash — texto longo](/tmp/locufy-benchmark-2026-09-09/eleven_flash_v2_5-longa-1.mp3)

Execute a partir de `backend`; as etapas de benchmark consomem créditos dos fornecedores configurados:

```sh
PYTHONPATH=. .venv/bin/python scripts/benchmark_falas.py texto --output /tmp/locufy-benchmark --repeticoes 2
PYTHONPATH=. .venv/bin/python scripts/benchmark_falas.py voz --output /tmp/locufy-benchmark --repeticoes 2
PYTHONPATH=. .venv/bin/python scripts/benchmark_falas.py verificar_audio --output /tmp/locufy-benchmark
```

O script passou a guardar as entradas e o modelo retornado para próximas execuções após a coleta inicial; esses campos adicionais não constam nos resultados de texto desta execução. Os nomes solicitados foram `claude-opus-5`, `claude-sonnet-5` e `claude-haiku-4-5`.
