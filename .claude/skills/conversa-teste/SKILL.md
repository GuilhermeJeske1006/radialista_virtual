---
name: conversa-teste
description: Simula as mensagens de ouvinte de um Reel no webhook do WhatsApp, sem enviar nada pelo WuzAPI, e salva as respostas reais do locutor.
argument-hint: [id-do-video]
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob Grep
---

Gere a conversa de WhatsApp do vídeo $ARGUMENTS com o comportamento real do sistema.

1. Leia `backend/app/whatsapp/webhook.py`: o formato do corpo que o WuzAPI envia
   (`_extrair_mensagem`) e a assinatura HMAC (`_verificar_assinatura`).
2. Se `backend/scripts/conversa_teste.py` não existir, crie-o. Ele deve:
   - rodar dentro do backend, com o banco local (aborte se o banco não for local);
   - trocar `app.whatsapp.webhook.enviar_mensagem` por uma função que só guarda o texto
     (assim nada sai pelo WuzAPI);
   - enviar cada mensagem com `fastapi.testclient.TestClient` para `/webhook/whatsapp`,
     com o corpo no formato do WuzAPI, o telefone de teste `5500000000000` e o header
     `x-hmac-signature` calculado com a chave da conta de demonstração;
   - aguardar o tempo de agrupamento de mensagens do webhook entre um envio e outro.
3. Rode o script com os itens de `mensagens_ouvinte` de `marketing/reels/$ARGUMENTS/roteiro.json`.
4. Salve `marketing/reels/$ARGUMENTS/conversa.json` como lista de
   `{"de": "ouvinte" | "locutor", "texto": "...", "hora": "14:02"}`, na ordem da conversa.
5. Mostre a conversa. Pedidos de música e abraço devem aparecer na fila do programa
   (confira no banco) para o /gravar-tela do ao vivo.
