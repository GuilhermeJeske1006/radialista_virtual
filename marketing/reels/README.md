# Reels da Locufy

Nove Reels (V1 a V9) que mostram o sistema funcionando, produzidos de ponta a ponta por um comando.

## Rodar

Com o ambiente local no ar (`./start-dev.sh`), no Claude Code:

```
/criar-reels            # todos
/criar-reels V5 V8      # só alguns
/criar-reels V5 --refazer
```

Sem o Claude Code, o mesmo pipeline (sem a revisão de marca):

```bash
cd marketing/tools && node criar-reels.mjs
```

Os MP4 saem em `marketing/reels/<id>/out/<id>.mp4`, com `capa.jpg` e `legendas.srt` ao lado.

## O que cada etapa faz

| Etapa | Script | Resultado |
| --- | --- | --- |
| Rádio de demonstração | `backend/scripts/seed_demo.py` | Rádio Cidade FM, Zé do Rádio, Lia, Beto, programa Tarde da Cidade, patrocinador Mercado Bom Preço; login em `.demo.json` |
| Conversa de teste | `backend/scripts/conversa_teste.py` | `conversa.json` com as respostas reais do locutor; pedidos entram na fila do ao vivo; nada sai pelo WuzAPI |
| Gravação de tela | `marketing/tools/gravar.mjs` | `tela/cena-NN.webm` em 1080x1920 e os áudios reais do ao vivo |
| Locução | `backend/scripts/locucao_reel.py` | `audio/cena-NN.mp3` com a narradora (voz Scheila) via ElevenLabs |
| Legendas e montagem | `marketing/tools/preparar.mjs` | `legendas.srt` e `montagem.json` |
| Render | `marketing/reels-remotion/render.mjs` | `out/<id>.mp4` e `out/capa.jpg` |
| Revisão | agente `revisor-marca` | `revisao.md` com APROVADO ou REPROVADO |

## Requisitos

- Backend com `.venv` e o `.env` com `ANTHROPIC_API_KEY` e `ELEVENLABS_API_KEY` (consome créditos).
- Node 18 ou mais novo. A primeira execução instala Playwright (Chromium) e Remotion.
- `ffprobe` (do ffmpeg) é opcional: sem ele, a duração dos áudios é estimada.

## Editar um vídeo

O roteiro de cada vídeo está em `<id>/roteiro.md` (texto) e `<id>/roteiro.json` (o que os scripts
executam). Para mudar falas, telas ou ações, edite o `roteiro.json` e rode de novo com `--refazer`.
O agente `roteirista-reels` gera o `roteiro.json` de um vídeo novo a partir do `roteiro.md`.
