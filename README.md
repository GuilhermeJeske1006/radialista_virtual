# Radialista Virtual

"Locutor virtual" com IA, integrado ao WhatsApp. Responde ouvintes, ajusta tom (formal/informal), roda dentro de travas de segurança (conteúdo, horário, volume) — vendido como SaaS pra rádios/emissoras.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python + FastAPI |
| LLM | Claude (Anthropic) |
| WhatsApp | [WuzAPI](https://github.com/asternic/wuzapi) (self-hosted, Go/whatsmeow) |
| Banco | PostgreSQL |
| Cache/rate limit | Redis |
| TTS | ElevenLabs |
| Pagamentos | Stripe |
| Painel | Next.js 16 + React 19 + Tailwind |
| Deploy | Docker Compose |

## Estrutura

```
backend/            FastAPI — auth, billing, config, live, llm, guardrails, onboarding, patrocinadores, tts, whatsapp
frontend-painel/     Painel Next.js (config do locutor pela rádio)
wuzapi/              WuzAPI self-hosted (ponte com WhatsApp)
docs/                Plano técnico
start.sh             Sobe tudo em modo produção (build)
start-dev.sh         Sobe tudo em modo dev (hot reload)
```

## Rodando local

1. Copiar env de exemplo e preencher:
   ```
   cp backend/.env.example backend/.env
   cp wuzapi/.env.example wuzapi/.env
   cp frontend-painel/.env.local.example frontend-painel/.env.local
   ```
   Preencher em `backend/.env`: `ANTHROPIC_API_KEY`, `WUZAPI_ADMIN_TOKEN` (mesmo valor do `wuzapi/.env`), `JWT_SECRET`, `APP_DB_PASSWORD`, chaves Stripe/YouTube/ElevenLabs conforme necessidade.

2. Subir tudo:
   ```
   ./start-dev.sh   # dev, hot reload (uvicorn --reload + next dev)
   ./start.sh       # produção, build das imagens
   ```

3. Serviços:
   - wuzapi: http://localhost:8080
   - backend: http://localhost:8000
   - frontend: http://localhost:3000

Pareamento do WhatsApp via QR Code — ver `wuzapi/gerar_qr.sh`.

## Testes

```
# backend (pytest + coverage)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                              # roda a suite
ruff check app tests                # lint
pytest --cov=app --cov-report=term-missing   # com cobertura

# frontend (vitest + testing-library)
cd frontend-painel
npm install
npm test                # roda a suite
npm run test:coverage   # com cobertura
npx tsc --noEmit        # typecheck
```

Banco e Redis dos testes de backend são simulados (SQLite em memória via fixture `db_session`
em `backend/tests/conftest.py`, e `fakeredis` no lugar do Redis real) — não precisa subir
Postgres/Redis pra rodar a suite local.

## CI/CD

GitHub Actions roda lint + testes automaticamente em push/PR pra `master`:

- `.github/workflows/backend-ci.yml` — ruff + pytest (dispara em mudanças em `backend/`)
- `.github/workflows/frontend-ci.yml` — tsc + vitest + `next build` (dispara em mudanças em `frontend-painel/`)

Só CI por enquanto (sem deploy automático) — deploy continua manual via `start.sh`.

## Docs

Plano técnico completo em [docs/plano.md](docs/plano.md).
