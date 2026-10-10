---
name: conversa-teste
description: Simula as mensagens de ouvinte de um Reel no webhook real do WhatsApp, sem enviar nada pelo WuzAPI, e salva as respostas do locutor.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read
---

1. Rode `/seed-demo` antes, se ainda não rodou.
2. Rode, em `backend`:

   ```bash
   PYTHONPATH=. .venv/bin/python scripts/conversa_teste.py $ARGUMENTS
   ```

3. Mostre a conversa salva em `marketing/reels/$ARGUMENTS/conversa.json`.

O script roda o webhook dentro do próprio processo, com a assinatura HMAC da conta de
demonstração, e troca o envio pelo WuzAPI por uma função que só guarda o texto. Pedidos de
música e abraço entram na fila do ao vivo de verdade. Mensagem com tópico proibido fica
bloqueada, sem resposta, como no sistema real.
