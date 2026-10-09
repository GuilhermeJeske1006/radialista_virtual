# Eleven v4 e v4 Turbo contra v3 e Flash 2.5

Executado em 08/10/2026 com a API real, pelo mesmo caminho de síntese do ao vivo
(`app.tts.client.sintetizar_audio_stream`: normalização de números, tags, perfil da voz). Uma
geração por caso: resultado indicativo, não estatístico. Não usou banco.

**Resultado:** v4 e v4 Turbo leem as mesmas tags do v3, sem falar nenhuma em voz alta, e
começam a responder em menos de 1 s em todas as gerações, sem os picos do v3. O v4 **ignora o
`speed`**: o ritmo por bloco e por voz de `app.tts.client` não vale nele. Oferecidos nas
combinações Premium v4, Equilibrada v4 e Voz Premium v4 (ver `../2026-09-25-combinacoes`).

## Como foi medido

Script: `backend/scripts/comparar_v4.py` (reproduzível, consome créditos; retoma uma execução
interrompida). 3 vozes (padrão, Paulo, Yasmin) × 4 modelos × 5 falas no formato que o LLM
entrega (abertura, notícia, comentário, patrocinador, chamada de ouvinte), com tags da
whitelist, `......` de troca de assunto e números. Mede primeiro byte e tempo total via
streaming, duração, palavras por minuto, header `character-cost` e fidelidade pela transcrição
do Scribe (palavras faltando/sobrando, tag lida em voz alta).

## Resultado por modelo (15 gerações cada)

| Modelo | 1º byte mediana (faixa) | Total mediana (faixa) | Palavras/min | `character-cost` (~220 caracteres) | Tag falada |
|---|---:|---:|---:|---:|---:|
| v3 | 0,88 s (0,65–8,73) | 6,4 s (4,4–13,7) | 162 | 98 | 0 |
| v4 | 0,81 s (0,71–0,95) | 5,0 s (4,4–6,4) | 158 | 27 | 0 |
| v4 Turbo | 0,45 s (0,42–0,84) | 4,4 s (4,1–5,1) | 158 | 13 | 0 |
| Flash 2.5 | 0,43 s (0,40–0,70) | 2,4 s (1,8–5,3) | 171 | 47 | 0 |

- **Latência:** os picos do v3 (2,6 s, 3,9 s e 8,7 s no primeiro byte) foram todos na voz
  padrão; com Paulo e Yasmin o v3 ficou entre 0,65 e 0,93 s.
- **Custo:** o `character-cost` do v4 reflete o desconto de lançamento de 72% (98 × 0,28 ≈ 27),
  válido até 12/10/2026. Sem ele, v4 cobra o mesmo por caractere que o v3 e o Turbo, metade.
- **Direção vocal:** `[sighs]` virou suspiro detectado pelo Scribe nas 6 gerações v4/Turbo e em
  nenhuma do v3. `[laughs]` só foi detectado uma vez (Turbo, Yasmin).
- **Ritmo:** sem `speed`, o v4 ficou entre 139 e 195 palavras/min. Yasmin é mais lenta em todos
  os modelos (≈ 147).
- **Faltando/sobrando** são inflados pelo Scribe escrever "15h30" e "R$ 12,90" em dígitos contra
  o texto enviado por extenso. Lendo as transcrições, o único erro de conteúdo é o bug abaixo.

## Testes diretos na API (mesmo dia)

- `speed` 0,7 e 1,2 deram a mesma duração (12,8 s); `stability` e `style` quase não mudam o
  áudio. No v4 o ritmo se controla por tags (`[slowly]`, `[rushed]`).
- `previous_text` é aceito no v4/Turbo (no v3 dá 400): volta a continuidade de entonação entre
  falas. `[pause]` rende ≈ 1,2 s de silêncio, como no v3.

## Pendências

- **"R$ 4,5 milhões"** vira "quatro reais,5 milhões" em `app/numeros.py`, em todos os modelos; o
  v4 lê "quatro reais, cinco milhões" (valor errado).
- **"Ela diz" → "Ela disse"** em 4 das 6 gerações v4/Turbo da chamada de ouvinte, logo após o
  suspiro. Pode ser o modelo ou o transcritor: confirmar ouvindo `*-chamada_ouvinte-eleven_v4*.mp3`.
- Expressividade e preferência humana não são medidas aqui: escutar os áudios.

## Arquivos

- `resultados.json`: texto enviado, métricas e transcrição de cada geração.
- `<voz>-<caso>-<modelo>.mp3`: áudios gerados.
