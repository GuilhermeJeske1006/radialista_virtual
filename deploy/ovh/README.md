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

Automático a cada push na `master` (`.github/workflows/deploy.yml`):

1. roda os testes do backend e do painel (`backend-ci.yml` e `frontend-ci.yml`);
2. se passarem, publica as imagens no GHCR com a tag do commit;
3. entra no VPS por SSH e roda `deploy.sh`, que puxa as imagens, sobe e
   confere se backend e painel ficaram saudáveis. Se não ficarem, volta
   sozinho para a versão anterior e o job falha.

A chave usada pelo Actions (secret `OVH_SSH_KEY`) só consegue rodar o
`deploy.sh`: no `authorized_keys` ela tem `restrict,command="/opt/locufy/deploy.sh"`.
O login no GHCR usa o token temporário do próprio job, então nenhum token
fica salvo no VPS.

A versão no ar é o `IMAGE_TAG` do `.env`. Para voltar uma versão na mão:

```sh
cd /opt/locufy
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=<sha>/' .env
docker compose up -d
```

Mudanças no `docker-compose.yml`, no `Caddyfile` ou no `deploy.sh` não são
copiadas pelo deploy: copie para `/opt/locufy` e rode `docker compose up -d`.

## Acessar o banco do seu computador

O Postgres só escuta no `127.0.0.1` do VPS. Abra um túnel SSH:

```sh
ssh -N -L 5434:127.0.0.1:5432 ubuntu@40.160.150.84
```

e conecte em `localhost:5434`, banco `radialista`, usuário `radialista`
(ou banco/usuário `wuzapi`). As senhas estão no `.env` do VPS:

```sh
ssh ubuntu@40.160.150.84 'grep -E "^(APP|WUZAPI)_DB_PASSWORD=" /opt/locufy/.env'
```

## Backup do Postgres

```sh
docker compose exec -T postgres pg_dumpall -U radialista | gzip > backup-$(date +%F).sql.gz
```

## DNS (GoDaddy)

`locufybr.com`, `www`, `app` e `api` precisam ter registro A apontando para o IP do VPS.
O Caddy só consegue emitir o certificado depois que o DNS propagar.
