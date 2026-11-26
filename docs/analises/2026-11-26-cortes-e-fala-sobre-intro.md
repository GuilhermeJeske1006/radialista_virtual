# Cortes de música (início/fim) e fala sobre a introdução — 26/11/2026

## Como a rádio faz

- **Corte de silêncio no início/fim (cue-in / cue-out):** automações (Autocue/Liquidsoap, PlayIt Live, Airtime/Silan) medem o
  silêncio **relativo ao volume da própria faixa**, não por dBFS fixo. O ponto de saída ("mix point"/segue) é o que dispara a
  próxima faixa; a cauda depois dele é descartada com fade.
- **Ramp / "bater o poste":** o locutor fala sobre a introdução instrumental e termina antes do vocal. A automação mostra a
  contagem regressiva da intro, mas a **marca de intro é manual** (PlayIt Live admite que não detecta o início do vocal).
  Música com "cold intro" (vocal no começo) não comporta fala. A prática é controversa; o consenso técnico é: música abaixada
  sob a voz, nunca fala sobre o vocal.
- Fontes: moonbase59.github.io/autocue, playitsoftware.com/FAQs, radioking (mix points), MusicMaster (talk-over),
  radioinsight.com ("talking about talking over music").

## O que já existia

`obter_inicio_seguro`/`obter_fim_seguro` (ffmpeg `silencedetect`, **-35 dBFS fixo**, 1,2 s) e fade de saída no painel.
Limites: limiar absoluto confundia introdução baixinha de balada com silêncio; não cortava **cauda longa** (reverb/acorde que
nunca vira silêncio); cada função rodava yt-dlp separado; falha era cacheada por 30 dias como "sem corte".

## O que mudou

### Backend — `app/live/audio_analysis.py`
- Envelope RMS (50 ms) em numpy; silêncio = quadro **32 dB abaixo do percentil 90 da faixa** (piso -75 dBFS).
- **Início:** primeiro fim de silêncio ≥1,2 s dentro da janela inicial (≤20 s), a partir de 2 s; folga de 0,15 s.
- **Fim:** (1) início de silêncio longo na janela final; (2) **cauda longa**: depois do último trecho forte (18 dB abaixo do
  nível da faixa) a música ainda soa por >8 s → corta 4 s após ele. Corte colado no fim do vídeo (<2 s) é descartado.
- Uma extração (yt-dlp) e uma decodificação por faixa; mix longo (música de fundo) decodifica só cabeça (90 s) e final (180 s).
- Falha de rede/ffmpeg: "sem corte" com cache de 10 min (antes: 30 dias).
- **Início do vocal:** primeira palavra de Scribe (`scribe_v2`, timestamp de palavra) sobre os 70 s a partir do início tocado;
  cache 30 dias por faixa+início. `RAMP_MUSICA_HABILITADO=false` desliga. Custo ≈ US$ 0,008 por música nova (70 s × tarifa
  `ia_stt_usd_hora`), só na 1ª vez; passa pela admissão `executar("stt", ...)`.
- `MusicaBlocoItem.inicio_vocal_segundos` (novo campo, opcional).

### Painel — `lib/falaSobreIntro.ts` + `hooks/useLiveEngine.ts`
- Regras: introdução ≥8 s; voz entra 2 s depois do início da música; fala termina ≥1,5 s antes do vocal; fala ≤15 s; música
  a 30 % sob a voz (fade 0,6 s), volta a 100 % em 0,9 s.
- A duração real da fala é medida no navegador; se não cabe → fala **antes** da música, como sempre.
- Guardas: nunca fala por cima do vocal (corta em vocal − 0,4 s); música pulada/terminada para a fala; música que falha antes
  de ficar audível → fala toca inteira antes da substituta (não se perde); página sem interação → fluxo normal.
- Só a 1ª música do bloco, só fala de uma voz, nunca o encerramento. A fala sobreposta não soma na duração do bloco.

## Validação

- Áudio real (yt-dlp → ffmpeg → numpy), 3 faixas (Rick Astley, Evidências, Garota de Ipanema): análise de cortes 1,5–2,8 s;
  início do vocal medido 18,9 s / 24,4 s / 41,1 s (Rick: 18,8 s confere com a faixa).
- Cenários fabricados sobre as faixas reais: +12 s de silêncio inicial → início 11–12; +1 s → ignorado; +25 s de cauda → corta
  ~4 s após o último trecho forte; +10 s de silêncio final → corta no fim da música; cauda curta natural → preserva.
- Testes: `backend/tests/test_live_audio_analysis.py` (41), propagação em `test_live_music.py`/`test_song_service.py`;
  painel: `lib/__tests__/falaSobreIntro.test.ts` (11) e `hooks/__tests__/useLiveEngine.falaSobreIntro.test.ts` (8).
  Backend 2765 passed; painel 445 passed; `tsc` e `ruff` limpos.

## Limites conhecidos (não resolvidos)

- **Escuta humana não feita.** O ramp foi validado por tempo (posições), não por ouvido: confirmar numa rádio real se
  30 % de volume e a margem de 1,5 s soam bem.
- Scribe pode **não transcrever vocalise** ("ooh/aah" baixinho) → vocal medido tarde demais → fala invade o vocal. A margem
  de 1,5 s e o corte em vocal − 0,4 s mitigam, não eliminam. Se aparecer em produção, subir `MARGEM_VOCAL_S`.
- Intro/outro com **fala de videoclipe por cima de música** ou aplauso alto não é detectado por volume (só silêncio e cauda).
- O relógio do backend (`relogio.py`) continua estimando o bloco como fala + música; com ramp o bloco real é menor (estimativa
  conservadora, o painel mede o tempo real).
- Intervalos dos YouTube IFrame: `startSeconds`/posição têm granularidade de ~0,25 s.
