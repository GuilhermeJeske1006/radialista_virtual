# Deploy no Render

Stack completa rodando no Render (workspace "Locufy's workspace", projeto **Locufy**), tier free em tudo. Este documento descreve a topologia, como reproduzir/atualizar o deploy e as limitações conhecidas do free tier. Nenhum segredo real aparece aqui — só nomes de variável (os valores ficam nas Environment Variables de cada serviço no dashboard do Render, e localmente em `backend/.env`, que é gitignored).

## Topologia

| Recurso | Nome no Render | Tipo | URL / notas |
|---|---|---|---|
| Backend | `radialista-backend` | Web Service, Docker (`backend/`) | https://radialista-backend.onrender.com |
| Frontend | `radialista-frontend` | Web Service, Docker (`frontend-painel/`) | https://radialista-frontend.onrender.com |
| Frontend (domínio próprio) | — | CNAME | https://app.locufybr.com → `radialista-frontend.onrender.com` |
| WuzAPI | `radialista-wuzapi` | Web Service, imagem `asternic/wuzapi:latest` | https://radialista-wuzapi.onrender.com |
| Postgres | `radialista-db` | Render Postgres (free) | compartilhado entre backend e wuzapi (ver abaixo) |
| Redis | `radialista-redis` | Render Key Value (free) | usado só pelo backend |

Backend e frontend buildam a partir do mesmo repo GitHub (`GuilhermeJeske1006/radialista_virtual`, branch `master`), cada um com `--root-directory` apontando pra sua pasta. Auto-deploy ligado: todo push em `master` redeploya quem tiver arquivo mudado dentro do seu `rootDir`.

### Por que Postgres compartilhado

Render free tier permite só 1 Postgres free por workspace. Criar uma 2ª instância pro wuzapi falhou (`cannot have more than one active free tier database`). Em vez de upgrade pago, backend e wuzapi apontam pro mesmo banco `radialista_db` — risco baixo porque as tabelas de cada um não colidem em nome. Se algum dia migrar pra plano pago, vale separar de novo.

## Variáveis de ambiente

### `radialista-backend`

Nomes obrigatórios/usados (ver `backend/app/config/settings.py` pra lista completa e defaults):

```
DATABASE_URL, REDIS_URL
WUZAPI_BASE_URL, WUZAPI_ADMIN_TOKEN, WUZAPI_USER_TOKEN, WUZAPI_WEBHOOK_URL
JWT_SECRET, FRONTEND_URL, CORS_EXTRA_ORIGINS
ANTHROPIC_API_KEY
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID_STARTER, STRIPE_PRICE_ID_GROWTH, STRIPE_PRICE_ID_PROFESSIONAL
YOUTUBE_API_KEY, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
STORAGE_BACKEND, AWS_S3_BUCKET, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, UPLOAD_DIR
SENTRY_DSN, SENTRY_ENVIRONMENT
LOCUTOR_NOME
```

`ANTHROPIC_API_KEY` e `WUZAPI_USER_TOKEN` não têm default no `Settings` — sem eles o processo crasha no boot (`pydantic_core.ValidationError`). Os demais têm fallback vazio/local e só desativam a feature correspondente (Stripe, ElevenLabs, YouTube/Spotify, Sentry, SMTP).

`WUZAPI_USER_TOKEN` na prática só é lido por `app/db/seed.py` (bootstrap de conta de teste local) — em produção o token real de cada conta fica em `accounts.wuzapi_token`, criado via `POST /onboarding/wuzapi-user` (ver seção "Conta de teste").

`STORAGE_BACKEND=s3` está configurado (bucket AWS real) em vez de `local` — Render free não tem disco persistente, então upload local se perderia a cada deploy/restart.

### `radialista-frontend`

```
NEXT_PUBLIC_API_URL=/api          # build-time (bakeado no bundle client-side)
INTERNAL_API_URL=<url do backend>  # build-time (ver "Gotcha do Next.js" abaixo)
```

### `radialista-wuzapi`

```
WUZAPI_ADMIN_TOKEN, DB_URI, WEBHOOK_FORMAT
WUZAPI_GLOBAL_ENCRYPTION_KEY, WUZAPI_GLOBAL_HMAC_KEY, WUZAPI_GLOBAL_WEBHOOK
```

`WUZAPI_ADMIN_TOKEN` aqui precisa ser o mesmo valor do `WUZAPI_ADMIN_TOKEN` no backend — é o que autentica a criação de usuário via `/admin/users` no onboarding.

## Gotcha do Next.js: rewrites rodam em build time

`frontend-painel/next.config.js` faz proxy de `/api/*` pro backend via `rewrites()`, lendo `process.env.INTERNAL_API_URL`. O Next gera o `routes-manifest.json` durante `next build`, não relê essa env var em runtime — então o valor precisa estar disponível **no momento do build**, não só no container rodando.

Corrigido em `frontend-painel/Dockerfile` (estágio de build declara `ARG INTERNAL_API_URL` + `ARG NEXT_PUBLIC_*`, seguido de `ENV` com o mesmo nome) e em `backend/docker-compose.yml` (`build.args`). O Render repassa automaticamente env vars do serviço como build args quando o Dockerfile declara `ARG` com nome igual — por isso basta configurar a env var normalmente no dashboard, sem flag especial.

Sem esse `ARG`, o proxy sempre cai no fallback `http://localhost:8000` e quebra fora de uma máquina onde frontend e backend dividem a mesma rede — isso afetava `./start.sh` local também, não só o Render.

## Domínio próprio

`app.locufybr.com` (GoDaddy) aponta via CNAME pro `radialista-frontend.onrender.com`. Adicionado em Settings → Custom Domains do serviço no dashboard (CLI do Render não tem comando de custom domain). TLS via Let's Encrypt, emitido automático pelo Render depois que o CNAME propaga.

A URL antiga (`radialista-frontend.onrender.com`) continua liberada via `CORS_EXTRA_ORIGINS` no backend, como fallback.

## Conta de teste (Radio Guabiruba)

Criada via fluxo real da aplicação, não via `app/db/seed.py` (Render Jobs de one-off exigem plano pago, bloqueado no free tier usado aqui):

1. `POST /auth/register` — cria `Account` + `Usuario` + `RadioConfig` + `Programa`.
2. `PUT /config/radio` — seta `nome_radio="Radio Guabiruba"`, `cidade="Guabiruba"`, `tipo_radio="popular_mix"`.
3. `POST /onboarding/wuzapi-user` — cria usuário no WuzAPI, grava `account.wuzapi_token`/`wuzapi_user_id`/`wuzapi_hmac_key` no Postgres.
4. Pareamento do WhatsApp: `POST /onboarding/connect` + `GET /onboarding/qrcode`, escanear com o celular (expira rápido, gerar de novo se passar do tempo).

Credenciais da conta de teste não estão neste documento (repo público) — combine por outro canal ou recrie uma conta nova pelo mesmo fluxo se precisar.

## Como atualizar env vars / redeployar

O Render CLI (`v2.22.0` no momento deste deploy) **não tem comando pra editar env vars de um serviço existente** (`render services update` não aceita `--env-var`). Único jeito via CLI: `render services delete <id>` seguido de `render services create` com o set completo de novo (a URL pública se mantém, já que é baseada no `--name`).

Script usado pra isso neste projeto: `recreate_backend.py` no scratchpad da sessão que fez o deploy (não commitado — lê `backend/.env` + um arquivo de secrets gerados na sessão, monta os `--env-var` e chama `render services create`). Se for repetir, recriar esse script a partir dos nomes de variável listados acima, valores vindo de `backend/.env` (local) e do dashboard do Render (rotacionados/gerados: `JWT_SECRET`, `WUZAPI_ADMIN_TOKEN`, `WUZAPI_GLOBAL_ENCRYPTION_KEY`, `WUZAPI_GLOBAL_HMAC_KEY`).

Alternativa sem downtime de recriação: editar direto pelo dashboard (Environment tab do serviço) — dispara redeploy automático, sem trocar o ID/URL do serviço.

## Limitações do free tier

- **Postgres expira em 30 dias** desde a criação — precisa upgrade de plano antes disso ou os dados somem.
- **Web services free hibernam** por inatividade — primeiro acesso depois de um tempo parado leva ~30-50s (cold start).
- **WuzAPI sem disco persistente** — sessão do WhatsApp pareada é perdida a cada restart/redeploy/sleep do serviço; precisa re-parear o QR Code (`wuzapi/gerar_qr.sh` localmente, ou via `POST /onboarding/connect` + `GET /onboarding/qrcode` em produção).
- **Um Postgres free só** por workspace — motivo do banco compartilhado entre backend e wuzapi (ver acima).

## Referência rápida de comandos

```bash
# workspace ativo
render workspace set tea-dagurqijnfac73fh5qtg

# status dos serviços
render services -o json

# logs
render logs -r <service-id> --limit 100 -o text

# status do último deploy
render deploys list <service-id> -o json

# conectar num Postgres do Render
render psql <postgres-id>
```
