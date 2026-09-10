# Análise da clonagem de voz — 10/09/2026

O maior ganho provável vem de melhorar a amostra e calibrar cada voz/modelo, antes de
acrescentar mais variação aleatória. Foram executados 123 testes automatizados e
12 sínteses reais. Não houve alteração do comportamento do aplicativo: os arquivos
novos são ferramentas de diagnóstico, resultados e esta proposta.

[Ouvir a comparação, com áudio incorporado](/tmp/locufy-clone-v3-2026-09-10/comparacao.html).
A página tem 24 players e funciona offline. Copie-a para guardar: `/tmp` é temporário.
Os 36 MP3s (12 originais e duas versões de cada um) estão na mesma pasta.
[Resultados das chamadas](comparacao-v3.json) e [diagnóstico de entrada](entrada-clone.json).

**O que o código faz hoje**

O upload chama `POST /v1/voices/add`, ou Instant Voice Cloning (IVC), em
[client.py:367](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py:367).
IVC não treina um modelo exclusivo do locutor; usa uma referência curta. Um corpus
de várias pessoas não melhora a identidade de um clone individual.
[Explicação oficial de IVC/PVC](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning).

O ambiente local está configurado para `eleven_v3`. Consultei os metadados da voz
padrão: categoria `professional`, 72 amostras e fine-tuning informado para modelos
v2/v2.5. O retorno não tinha estado de fine-tuning de v3. Isso não prova que a voz
seja incompatível: as 12 chamadas ao v3 funcionaram. Também não prova que esta seja
a voz escolhida em todos os radialistas ou a amostra que motivou a reclamação.

O projeto registra que o usuário preferiu v3 ao Flash na comparação de 09/09.
A recomendação é preservar essa preferência durante a avaliação.

**Melhorias propostas, em ordem de execução**

| Prioridade | Evidência no código/teste | Mudança proposta |
| --- | --- | --- |
| Alta | [router.py:128](/Users/guilhermejeske/projetos/locufy/backend/app/tts/router.py:128) só mede duração do arquivo. Silêncio e tom puro de 21 s passam. | Medir fala efetiva com detector de atividade vocal; rejeitar silêncio e arquivos sem fala. Mostrar alertas de clipping, nível baixo, ruído e reverberação. Um detector de volume sozinho não separa fala de música ou tons. |
| Alta | [router.py:31](/Users/guilhermejeske/projetos/locufy/backend/app/tts/router.py:31) aceita 20 s, e a UI recomenda aproximadamente 60 s. | Guiar a gravação para 60–120 s úteis, com um locutor e captura consistente. Aceitar múltiplos arquivos avaliando o total útil. O limiar de rejeição deve ser calibrado com gravações reais, sem exigir duração longa de material ruim. |
| Alta | [live/router.py:2460](/Users/guilhermejeske/projetos/locufy/backend/app/live/router.py:2460) infere clone por ausência no catálogo fixo. A voz profissional configurada recebe os deltas descritos como IVC. | Persistir categoria do provedor, origem, idioma/sotaque e perfil de síntese por voz. Separar IVC, PVC e biblioteca. Não aplicar desaceleração de IVC indiscriminadamente. |
| Alta | [client.py:200](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py:200) acumula tipo de bloco, tom, clone e jitter. | Calibrar primeiro um perfil estável por voz/modelo; testar `stability=0.5`, `style=0`, `speed=1.0` como referência experimental. Só manter variações que vencerem na escuta. |
| Alta | [client.py:107](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py:107) só reconhece tags ASCII sem espaços. `[muito feliz]` e `[áudio]` sobrevivem ao filtro. | Tratar todas as instruções entre colchetes no texto destinado à fala, preservando apenas tags aprovadas. Cobrir espaços, acentos e tags desconhecidas; cuidar de conteúdos legítimos entre colchetes. |
| Média | [client.py:380](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py:380) extrai apenas `voice_id` da resposta. | Persistir e apresentar `requires_verification`; evitar anunciar uma voz como pronta quando depende de verificação. |
| Média | [VozCloneModal.tsx:71](/Users/guilhermejeske/projetos/locufy/frontend-painel/components/VozCloneModal.tsx:71) deixa o navegador escolher o contêiner, mas marca sempre WebM. | Negociar MIME suportado, usar `recorder.mimeType` e extensão correspondente. Mostrar medidor de nível, duração útil e orientação de distância do microfone. A incompatibilidade por navegador foi identificada por leitura, sem teste em Safari nesta sessão. |
| Média | [client.py:242](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py:242) usa um único modelo global. | Permitir perfil/modelo por voz, preservando o v3 atual como padrão. PVC pode exigir outra combinação; comparar antes de migrar. |
| Média | [client.py:247](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py:247) normaliza valores monetários, mas depende do LLM para outros números. | Cobrir textos fixos: frequência, horário, telefone, abreviações, nomes de artistas e marcas. Usar aliases/dicionários quando suportados pelo modelo, com testes de pronúncia pt-BR. |
| Baixa | Saída TTS não especifica `output_format`; pós-produção decodifica MP3 e recodifica em 192 kbps. | Comparar saída de maior qualidade/PCM, quando habilitada no plano, para evitar perdas sucessivas. Aumentar o bitrate no final não recupera detalhes já perdidos. |

No perfil de clone, antes do jitter, música enérgica recebe estabilidade 0,45,
estilo 0,50 e velocidade 0,98; comentário calmo recebe 0,67 / 0,05 / 0,80;
notícia calma recebe 0,72 / 0 / 0,78. São valores enviados, não uma garantia de
que o v3 realize cada controle de forma proporcional. Nas chamadas reais, subir
`speed` para 1,0 no perfil neutro não reduziu a duração do comentário.

A API aceitou os valores contínuos de estabilidade do perfil atual. Não foi
comprovado erro de contrato por usar valores diferentes de 0, 0,5 e 1.
O guia descreve os modos Creative, Natural e Robust e recomenda escolher uma voz
compatível com a interpretação desejada. Ele também ainda contém uma ressalva de
otimização de PVC no v3 com linguagem de research preview; portanto, não trate
essa ressalva como prova de incompatibilidade atual.
[Guia oficial de direção vocal](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices).

O código remove `similarity_boost` e `use_speaker_boost` do payload v3. Aumentar
`_SIMILARITY_BOOST_CLONE` não muda as chamadas desse modelo. Também suprime
`previous_text` no v3, com teste de regressão para rejeição anterior do provedor.
Não recomendo reintroduzir esse campo sem verificar suporte na combinação real.

O tratamento `radio_fm`, pedido no ao vivo, já desliga pitch jitter, ruído de sala
e reverb. Os perfis antigos ainda usam esses efeitos, mas seria incorreto atribuir
a eles o som atual do Rádio FM. Se forem usados, comparar sem pitch shift em
janelas independentes de 400 ms: as emendas podem introduzir artefatos. Isso é
uma hipótese de processamento, não uma conclusão de escuta desta sessão.

A API aceita múltiplas amostras, informa verificação pendente e oferece remoção
opcional de ruído. O próprio provedor alerta que remover ruído de uma amostra já
limpa pode piorá-la; prefira regravar quando possível e compare antes/depois.
[Contrato de criação de IVC](https://elevenlabs.io/docs/api-reference/voices/ivc/create).
Formatos de saída e acesso dependem do plano.
[Contrato de síntese](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).

**Como preparar uma voz melhor**

Para a próxima IVC, grave 1–2 minutos de fala limpa, sem música, eco ou outra
pessoa; mantenha o microfone e o ambiente iguais. Para rádio, use o ritmo,
sotaque e intenção que devem aparecer no programa. Inclua frases declarativas,
perguntas, nomes e encerramentos; evite interpretar como anúncio gritado se o
objetivo for conversa. Guarde também um trecho humano separado para avaliação.
Não combine vozes diferentes na mesma identidade.

O provedor recomenda qualidade de captura acima do formato, sugere MP3 de
192 kbps ou mais e informa que WAV não costuma melhorar o clone por si só.
Também desaconselha acumular mais de 2–3 minutos esperando melhoria automática
na clonagem instantânea.
[Preparação IVC](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/instant-voice-cloning),
[formatos aceitos](https://elevenlabs.io/docs/help-center/product/voices/voice-cloning/what-files-do-you-accept-for-voice-cloning).

Se uma IVC bem gravada ainda não preservar a identidade, comparar PVC: pelo menos
30 minutos e, idealmente, 2–3 horas consistentes. Isso exige um fluxo diferente do
upload atual, com verificação e treinamento assíncrono.
[Preparação PVC](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/professional-voice-cloning).

**Onde obter vozes ou dados**

| Fonte | Uso indicado | Condição prática |
| --- | --- | --- |
| Gravação própria ou locutor contratado com autorização específica para voz sintética | Identidade exclusiva do Locufy; melhor aderência a sotaque e estilo | Obter a gravação seca e acordar uso comercial, clonagem e compartilhamento. Na PVC da ElevenLabs, o próprio titular cria/verifica na conta dele e compartilha a voz. [Regra oficial](https://help.elevenlabs.io/hc/en-us/articles/36842751624209-Can-I-create-a-Professional-Voice-Clone-of-someone-else-s-voice). |
| [ElevenLabs Voice Library](https://elevenlabs.io/pt/voice-library/professional) | Usar uma voz pronta em português brasileiro | Integrar o `voice_id` autorizado. O catálogo é fonte de vozes para síntese, não uma autorização para baixar demos e treinar outro clone. |
| [TTS-Portuguese Corpus](https://github.com/Edresson/TTS-Portuguese-Corpus) | Pesquisa/treinamento de TTS próprio em pt-BR | Cerca de 10 h 28 min de um locutor, 3.632 WAVs a 48 kHz, CC BY 4.0. O projeto relata gravação fora de estúdio e redução de ruído; avaliar artefatos. |
| [Multilingual LibriSpeech, português](https://openslr.org/94) | Pesquisa e avaliação de modelos próprios | CC BY 4.0, derivado de audiolivros; download português de 9,3 GB em FLAC ou 2,5 GB em Opus. O estilo é leitura, não necessariamente conversa de rádio. |

Os dois corpora são candidatos para outro projeto de treinamento; o Locufy atual
não tem pipeline de fine-tuning local para recebê-los. Licença do dataset não
substitui a verificação do direito de oferecer a identidade de um narrador como
voz comercial nem as condições do provedor. Não foram baixados corpora nem
clonadas pessoas novas neste teste. A busca pelo Stripe Directory não ficou
disponível no ambiente; a pesquisa acima usou fontes oficiais dos projetos.

**Resultados dos testes**

123 testes passaram no `backend/.venv`: 101 de TTS, rotas de clonagem, catálogo,
pós-produção e números; mais 22 do ao vivo relacionados a TTS, áudio e tom.
Os testes locais simulam serviços externos. `backend/.venv-test` estava sem
`sentry_sdk` e falhou durante a preparação; a execução válida usou `.venv`.

O diagnóstico adicional usou WAVs reais com banco e provedor simulados: silêncio
de 21 s e tom senoidal de 21 s avançaram até o provedor; silêncio de 5 s foi
rejeitado com 400. Isso comprova a lacuna local, sem afirmar que a ElevenLabs
aceitaria esses arquivos. A prova das tags confirmou que tags com espaços e
acentos sobrevivem ao filtro; não foi testado se elas seriam pronunciadas.

As 12 chamadas reais retornaram HTTP 200. Foram dois textos fictícios, três
variantes e duas repetições, com aproximadamente 3.126 caracteres de texto mais
tags e consumo normal de créditos. Nenhuma voz nova foi criada. Para cada
repetição, a seed da API foi igual entre variantes, com determinismo apenas
best-effort. A configuração atual também teve seu jitter registrado.

| Cenário | Variante | Síntese média (s) | Duração média (s) |
| --- | --- | ---: | ---: |
| Música | Atual | 6,49 | 13,00 |
| Música | Só estabilidade 0,5 | 6,03 | 12,88 |
| Música | Perfil neutro | 6,67 | 12,88 |
| Comentário | Atual | 8,13 | 16,32 |
| Comentário | Só estabilidade 0,5 | 9,57 | 16,56 |
| Comentário | Perfil neutro | 7,14 | 16,68 |

A variante de estabilidade altera apenas esse campo; conserva os outros ajustes
e texto da chamada original. A neutra altera estabilidade, estilo, velocidade e
remove a tag automática de calma; é uma alternativa completa, não um teste que
isola qual desses fatores causa uma eventual diferença.

Todos os 36 MP3s foram decodificados durante o processamento. As 24 versões para
escuta mediram −16,40 a −16,17 LUFS, com true peak de −2,26 a −2,22 dBTP. A maior
diferença de volume entre normalizado e Rádio FM da mesma síntese foi 0,13 LUFS.
A página foi conferida estruturalmente com 24 players; não houve teste visual em
navegador ou avaliação auditiva humana nesta execução.

Duas repetições por cenário não estabelecem p95, superioridade estatística ou
fidelidade vocal. Não há gravação humana de referência neste experimento, nem
pontuação de similaridade ou transcrição para medir erros de pronúncia. Não é
possível declarar um perfil vencedor em realismo com essas medidas.

Para escolher, ouvir sem revelar o perfil e avaliar naturalidade, pronúncia,
ritmo e finais de frase, de 1 a 5. Em uma segunda rodada, usar gravação humana
separada, mais textos (nomes, números e diferentes blocos), mais repetições e
avaliação do próprio locutor. Só então aplicar o perfil preferido por voz.

Comandos reproduzíveis, executados a partir de `backend`:

```sh
.venv/bin/python -m pytest tests/test_tts_client.py tests/test_tts_router.py tests/test_tts_voices.py tests/test_postprod_client.py tests/test_numeros.py -q
.venv/bin/python -m pytest tests/test_live_router.py -k 'tts or audio or tom' -q
PYTHONPATH=. .venv/bin/python scripts/auditar_entrada_clone.py
PYTHONPATH=. .venv/bin/python scripts/comparar_clone_v3.py --output /tmp/clone-nova-rodada
# A linha acima só descreve o teste. Para executar 12 sínteses e consumir créditos:
PYTHONPATH=. .venv/bin/python scripts/comparar_clone_v3.py --output /tmp/clone-nova-rodada --executar-api
```
