# Pós-produção Rádio FM

O painel solicita `radio_fm` tanto em `/proxima` quanto em `/tts`, incluindo diálogos. Arquivos de patrocinadores e vinhetas continuam sendo reproduzidos diretamente. Clientes que omitem o perfil preservam a síntese original.

O perfil usa corte em 80 Hz, redução de 1,5 dB em 275 Hz, presença de 2 dB em 3 kHz, compressão 3:1 (10/120 ms), saturação leve e de-esser. Reverb, ruído artificial e variação aleatória de afinação ficam desligados. O compressor tem limiar inicial de -18 dB; a redução efetiva depende do áudio.

A masterização acontece depois dos efeitos, em duas passagens do FFmpeg, com meta de -16 LUFS e teto de -2 dBTP antes da codificação, deixando margem para MP3. Não é um padrão de transmissão FM: é um ponto inicial para a saída web. A mistura com música no player é separada; estas medições são da voz.

A música desce em 150 ms durante a fala e volta em 900 ms. Pós-produção exige o áudio completo: os pedidos de fala aguardam até 60 segundos e o próximo bloco até 45 segundos. Cada passagem de FFmpeg tem limite de 30 segundos; falhas no processamento são informadas como erro, sem devolver áudio cru como se estivesse tratado.

## Validação com amostras públicas em 2026-09-08

| Voz | Original | Rádio FM | Pico final | Processamento local |
| --- | --- | --- | --- | --- |
| Paulo | -20,48 LUFS | -16,40 LUFS | -2,25 dBTP | 0,65 s |
| Will | -22,05 LUFS | -16,67 LUFS | -2,24 dBTP | 0,70 s |

Fonte das amostras: https://elevenlabs.io/text-to-speech/portuguese. Não houve clonagem nem chamada paga de síntese. Medições feitas sobre o MP3 final decodificado pelo FFmpeg. Elas verificam nível e picos, não substituem escuta comparativa. Para comparar timbre, igualar o volume percebido entre original e tratado.

Testes de áudio cobrem mono, estéreo, duração, silêncio e loudness. O teste de integração passa áudio pela pós-produção real tanto na resposta embutida quanto em `/tts`, substituindo apenas o provedor TTS e a geração de texto.
