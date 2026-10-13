#!/bin/sh
# Deploy chamado pelo GitHub Actions (.github/workflows/deploy.yml).
#
# A chave de deploy fica presa a este script no authorized_keys do VPS:
#   restrict,command="/opt/locufy/deploy.sh" ssh-ed25519 AAAA... github-actions-deploy
# O sha do commit chega como comando do ssh (SSH_ORIGINAL_COMMAND) e o
# usuario + token temporario do GHCR chegam pela entrada padrao.
set -eu
cd /opt/locufy

TAG="${SSH_ORIGINAL_COMMAND:-}"
if ! printf '%s' "$TAG" | grep -Eq '^[0-9a-f]{40}$'; then
	echo "sha invalido: '$TAG'" >&2
	exit 2
fi
read -r GHCR_USER
read -r GHCR_TOKEN

# Credencial do GHCR so durante o pull, fora do ~/.docker do servidor.
DOCKER_CONFIG=$(mktemp -d)
export DOCKER_CONFIG
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
IMAGE_TAG="$TAG" docker compose pull --quiet backend frontend landing

ANTERIOR=$(sed -n 's/^IMAGE_TAG=//p' .env)
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$TAG/" .env
docker compose up -d

saudavel() {
	for _ in $(seq 1 30); do
		status=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q backend)")
		if [ "$status" = healthy ] &&
			docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://frontend:3000/login', timeout=5)" 2>/dev/null; then
			return 0
		fi
		sleep 5
	done
	return 1
}

if ! saudavel; then
	echo "backend/painel nao ficaram saudaveis com $TAG; voltando para $ANTERIOR" >&2
	sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$ANTERIOR/" .env
	docker compose up -d
	exit 1
fi

# Imagens sem uso ha mais de 7 dias (mantem as recentes para rollback).
docker image prune -af --filter until=168h >/dev/null
echo "deploy ok: $TAG"
