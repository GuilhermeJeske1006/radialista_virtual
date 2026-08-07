#!/bin/bash
# Uso: ./gerar_qr.sh <user_token>
set -e
TOKEN="${1:?informe o token do usuario WuzAPI}"
curl -s -X POST http://localhost:8080/session/connect -H "token: $TOKEN" -H "Content-Type: application/json" -d '{"Subscribe":["Message"],"Immediate":true}' > /dev/null
sleep 2
curl -s http://localhost:8080/session/qr -H "token: $TOKEN" | python3 -c "
import json, sys, base64
d = json.load(sys.stdin)
qr = d['data']['QRCode']
if not qr:
    print('Ja conectado ou QR vazio:', d)
else:
    b64 = qr.split(',',1)[1]
    with open('qr.png','wb') as f:
        f.write(base64.b64decode(b64))
    print('QR salvo em wuzapi/qr.png -- escaneie AGORA (expira rapido)')
"
