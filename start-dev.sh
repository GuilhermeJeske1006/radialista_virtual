#!/bin/bash
# Sobe todos os serviços em modo dev: código local montado por volume,
# uvicorn --reload e next dev -- edições no front/back refletem nas portas
# 3000/8000 sem precisar de rebuild (só reconstrói a imagem se mudar deps).
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Subindo wuzapi (WhatsApp API)..."
docker compose -f "$ROOT_DIR/wuzapi/docker-compose.yml" up -d

echo "==> Subindo backend + frontend (modo dev, hot reload)..."
docker compose \
  -f "$ROOT_DIR/backend/docker-compose.yml" \
  -f "$ROOT_DIR/backend/docker-compose.dev.yml" \
  up -d --build

echo "==> Tudo no ar (dev):"
echo "    wuzapi:   http://localhost:8080"
echo "    backend:  http://localhost:8000  (uvicorn --reload)"
echo "    frontend: http://localhost:3000  (next dev)"
