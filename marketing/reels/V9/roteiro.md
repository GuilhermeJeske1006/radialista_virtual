# V9 · O que a IA não leva ao ar

Etapa: meio · 20 s · CTA: link na bio

| Tempo | Imagem | Texto na tela / fala |
| --- | --- | --- |
| 0–8 s | Celular: ouvinte manda "E aí, em quem você vai votar na eleição?" | "E se o ouvinte tentar puxar polêmica?" |
| 8–15 s | Conversas (/conversas): a mensagem aparece como "Bloqueada — conteúdo não permitido" | "Tema proibido não vai ao ar." |
| 15–20 s | Logo | "Você decide do que a rádio fala. Link na bio." |

No sistema atual, mensagem com tópico proibido é bloqueada e registrada, sem resposta automática
(`backend/app/whatsapp/webhook.py`, status `bloqueado_conteudo`). O vídeo mostra exatamente isso.
