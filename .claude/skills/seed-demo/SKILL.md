---
name: seed-demo
description: Cria ou atualiza a rádio de demonstração (Rádio Cidade FM) usada nos Reels da Locufy.
disable-model-invocation: true
allowed-tools: Bash Read
---

1. Confira se o Postgres e o Redis locais estão no ar (`./start-dev.sh`).
2. Rode, em `backend`:

   ```bash
   PYTHONPATH=. .venv/bin/python scripts/seed_demo.py
   ```

3. Mostre o login e a senha que o script imprimiu. Eles ficam também em
   `marketing/reels/.demo.json` (fora do git), lido pelos outros scripts.

O script recusa banco que não seja local e pode rodar várias vezes sem duplicar nada.
Ele cria Zé do Rádio, Lia e Beto no programa "Tarde da Cidade", o patrocinador
"Mercado Bom Preço" e os tópicos proibidos (política partidária, eleições, religião).
