# Produção no VPS da OVH

Tudo roda via `docker compose` em `/opt/locufy`:

| Serviço    | Imagem                                         | Exposto                         |
|------------|------------------------------------------------|---------------------------------|
| caddy      | `caddy:2-alpine`                               | 80/443, HTTPS automático        |
| frontend   | `ghcr.io/guilhermejeske1006/locufy-frontend`   | `app.locufybr.com`              |
| backend    | `ghcr.io/guilhermejeske1006/locufy-backend`    | `api.locufybr.com`              |
| landing    | `ghcr.io/guilhermejeske1006/locufy-landing`    | `locufybr.com` (www redireciona)|
| wuzapi     | `asternic/wuzapi:latest`                       | só rede interna                 |
| postgres   | `postgres:16-alpine` (bancos `radialista` e `wuzapi`) | só rede interna          |
| redis      | `redis:7-alpine`                               | só rede interna                 |

## Arquivos no VPS

- `docker-compose.yml`, `Caddyfile`, `postgres-init/` (deste diretório)
- `.env`: senhas dos bancos e chaves do WuzAPI (modelo em `.env.example`)
- `.env.backend`: variáveis do backend (modelo em `.env.backend.example`)

Os dois `.env` ficam só no servidor, com `chmod 600`.

## Deploy de nova versão

O push na `master` publica as imagens no GHCR (`.github/workflows/docker-publish.yml`).
No VPS:

```sh
cd /opt/locufy
docker compose pull
docker compose up -d
```

Para fixar uma versão, use `IMAGE_TAG=<sha do commit>` no `.env`.

## Backup do Postgres

```sh
docker compose exec -T postgres pg_dumpall -U radialista | gzip > backup-$(date +%F).sql.gz
```

## DNS (GoDaddy)

`locufybr.com`, `www`, `app` e `api` precisam ter registro A apontando para o IP do VPS.
O Caddy só consegue emitir o certificado depois que o DNS propagar.
