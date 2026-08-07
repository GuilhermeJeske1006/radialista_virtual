#!/bin/bash
# Sobe todos os serviços: wuzapi -> backend + frontend
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Subindo wuzapi (WhatsApp API)..."
docker compose -f "$ROOT_DIR/wuzapi/docker-compose.yml" up -d

echo "==> Aguardando wuzapi ficar saudável..."
until curl -sf -o /dev/null http://localhost:8080/status; do
  sleep 1
done

echo "==> Subindo backend + frontend..."
docker compose -f "$ROOT_DIR/backend/docker-compose.yml" up -d --build

echo "==> Tudo no ar:"
echo "    wuzapi:   http://localhost:8080"
echo "    backend:  http://localhost:8000"
echo "    frontend: http://localhost:3000"
