# Teste de naturalidade e velocidade — 09/09/2026

## Resultado da escuta e configuração atual

O usuário continuou percebendo a locução como quadrada e sem expressão com o
Flash ajustado. Por isso, o padrão voltou para `eleven_v3`, recuperando o caminho
anterior de prosódia e direção vocal. O Flash ajustado permanece disponível por
`ELEVENLABS_MODEL=eleven_flash_v2_5` para comparações futuras. O preparo antecipado
existente continua ativo; a primeira fala e respostas imediatas podem demorar mais.
Áudios já preparados precisam ser descartados pelo encerramento e reinício do ao
vivo para uma nova escuta do v3. Abaixo está o registro do teste anterior.

## Configuração avaliada no teste

O Flash v2.5 passou a usar um perfil independente: estabilidade 0,50, similaridade
0,75, estilo 0, velocidade 1,0 e speaker boost ligado. Os ajustes anteriores de
tipo de bloco, tom e clone não se acumulam nesse perfil. O v3 e o Multilingual v2
mantêm os ajustes anteriores. O modelo padrão era Flash durante este teste;
não há seleção automática de modelo por bloco.

Essa é uma configuração inicial para escuta, não uma conclusão de que o Flash
alcançou a naturalidade do v3. A velocidade 1,0 controla a reprodução da fala;
o tempo abaixo mede a geração do arquivo, incluindo rede.

## Comparação pronta para ouvir

[Abrir a comparação com áudio incorporado](/tmp/locufy-equilibrio-voz-2026-09-09-escuta/comparacao.html).
A página funciona offline e pode ser copiada sozinha. O diretório temporário pode
ser removido pelo sistema; salve a página para preservar a comparação.

Foram feitas seis chamadas à ElevenLabs com a voz padrão do ambiente: dois
cenários, três variantes, uma síntese por combinação. O Flash anterior foi
reproduzido com os mesmos presets que recebia antes desta alteração. O texto é
igual entre as variantes de cada cenário. Não foram usados ouvintes reais.

Cada síntese foi salva em três versões: original do provedor, sem efeitos com
volume normalizado e com o tratamento Rádio FM existente. A página apresenta as
duas últimas, ambas com alvo de −16 LUFS e teto de −2 dBTP. As versões de cada par
derivam do mesmo áudio original, sem uma nova chamada ao provedor.

| Cenário | Flash anterior | Flash ajustado | Eleven v3 |
| --- | ---: | ---: | ---: |
| Anúncio musical | 1,55 s | 1,31 s | 8,55 s |
| Comentário calmo | 1,34 s | 1,31 s | 7,99 s |

Tempos de síntese completa, sem pós-produção. Uma medição por combinação não
estabelece latência típica, p95 ou ganho percentual confiável. Esta execução usa
timeout de 35 s e não repete chamadas, diferindo dos limites do ao vivo.

As 12 versões da página foram decodificadas pelo FFmpeg. O loudness medido após
codificação ficou entre −16,58 e −16,17 LUFS e o true peak entre −2,25 e −2,20 dBTP.
A diferença máxima entre a versão sem efeitos e a Rádio FM da mesma síntese foi
0,20 LUFS. Essas medidas ajudam na comparação de volume, mas não avaliam emoção,
identidade vocal ou artefatos perceptivos.

## Como testar

1. Compare primeiro as versões sem efeitos: timbre, entonação, finais de frase e
   fidelidade à voz original.
2. Compare cada uma com o tratamento Rádio FM. Observe se o caráter metálico
   aparece ou se acentua nessa etapa.
3. Teste novas falas no programa local. O backend em desenvolvimento usa recarga
   automática e o perfil novo foi conferido no contêiner. Áudios já preparados
   continuam com a configuração usada quando foram gerados.

Se o Flash ajustado continuar artificial, o v3 permanece selecionável por
`ELEVENLABS_MODEL=eleven_v3` no ambiente do backend. Recrie o contêiner após mudar
variáveis de ambiente. O programa já prepara dois blocos à frente; não houve
alteração nessa fila. A primeira fala e respostas que não puderem ser antecipadas
continuam sujeitas à latência maior do v3.

Para comparar outra voz ou repetir o teste, execute a partir de `backend`, usando
uma pasta nova (seis sínteses por execução, com consumo de créditos):

```sh
PYTHONPATH=. .venv/bin/python scripts/comparar_vozes.py --output /tmp/locufy-vozes-nova-escuta
# Opcional: acrescente --voice-id ID_DA_VOZ para usar outro locutor.
```

O script gera `resultados.json`, arquivos MP3 e `comparacao.html`, sem publicar
áudio ou modificar configurações persistidas. Os resultados não contêm a chave
da API. Nesta sessão, a tentativa inicial sem acesso à rede falhou antes de gerar
áudio; a execução com acesso à ElevenLabs completou as seis sínteses.

## Validação

74 testes passaram: cliente TTS, rotas de voz, catálogo e pós-produção. Os novos
casos verificam o payload efetivo do Flash com voz clonada e de catálogo, em tom
calmo e enérgico, tanto em streaming quanto com resposta completa. A página foi
conferida com 12 players e os arquivos de áudio foram analisados pelo FFmpeg.

Referência para os valores iniciais: [guia de Text to Speech da ElevenLabs](https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech).
