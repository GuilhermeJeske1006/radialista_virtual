---
name: seed-demo
description: Popula o banco local com a rádio de demonstração usada nos Reels da Locufy.
disable-model-invocation: true
allowed-tools: Bash Read Write Edit Glob Grep
---

Prepare o ambiente de gravação dos Reels.

1. Confira se o backend (http://localhost:8000) e o painel (http://localhost:3000) estão no ar.
   Se não estiverem, peça para o usuário rodar `./start-dev.sh` e pare.
2. Se `backend/scripts/seed_demo.py` não existir, crie-o com os modelos de `backend/app/models`.
   Ele deve poder rodar várias vezes sem duplicar nada e criar:
   - a conta "Rádio Cidade FM", frequência 98.7, login `demo@locufy.local` com uma senha forte
     gerada e impressa no terminal;
   - uma `wuzapi_hmac_key` de teste na conta (usada por /conversa-teste);
   - os radialistas "Zé do Rádio" (apresentador), "Lia" (co-apresentadora) e "Beto"
     (comentarista), cada um com uma voz do catálogo de `backend/app/tts/voices.py`;
   - o programa "Tarde da Cidade", com Zé, Lia e Beto, tom descontraído e os blocos
     abertura, musica, comentario, noticia, chamada_ouvinte e `patrocinador:<id>`;
   - o patrocinador "Mercado Bom Preço", tipo texto;
   - "política partidária" como tema proibido do programa.
3. Rode o script com o ambiente do backend e mostre o login de demonstração.

Nunca rode contra o banco de produção: aborte se a URL do banco não for local.
