# Market Deck

Dashboard for displaying financial asset information — live prices, FX conversion, return tables, heatmaps, and multi-watchlist management — powered by a FastAPI + SQLAlchemy backend, a Svelte 5 frontend, PostgreSQL, and Yahoo Finance.

## Architecture

- **Backend** (`backend/`): packaged FastAPI app on SQLAlchemy 2 with Alembic migrations. Layered into API routers, services, and ORM models. Computes all FX conversion and return metrics server-side.
- **Frontend** (`frontend/`): Svelte 5 + Vite + TypeScript single-page app, built to `frontend/dist/` and served by the backend (with SPA fallback).
- **Deployment**: a single container built by Nixpacks (Python + Node), fronted by Coolify, backed by a separate Coolify PostgreSQL resource.

## Navigation

- [Features](#features)
- [Deploy on Coolify](#deploy-on-coolify)
- [Environment Variables](#environment-variables)
- [First Login](#first-login)
- [Operational Notes](#operational-notes)
- [Troubleshooting](#troubleshooting)
- [Local Development](#local-development)
- [API Summary](#api-summary)
- [References](#references)

## Features

- Admin account with full access to watchlists, tickers, per-list tags, settings, cache clearing, and password changes.
- Demo account with read-only access.
- Alembic-managed PostgreSQL schema, migrated automatically on startup; seed data on first startup.
- JWT login/session restore.
- Server-side authorization for all write endpoints.
- Server-side metrics: FX conversion, lookback returns, and monthly heatmap data computed on the backend.
- Single-stock dashboards with shareable `/stock/{symbol}` URLs, global Yahoo symbol search, native-currency charts, fundamentals, technicals, news, and analyst readouts.
- In-memory rate limits on Yahoo-backed read endpoints.
- Coolify/Nixpacks deployment files:
  - `.python-version`, `.nvmrc`
  - `requirements.txt`
  - `nixpacks.toml`

## Deploy on Coolify

This app is designed for a Coolify application resource plus a separate Coolify PostgreSQL resource.

1. Push this repository to the Git provider connected to Coolify.
2. Create and deploy a PostgreSQL resource in the same Coolify project/environment.
3. Copy the PostgreSQL internal connection URL.
4. Create a Coolify application from this repository.
5. Use the default Nixpacks build pack.
6. Keep **Is it a static site?** disabled.
7. Set:

```text
Base Directory: /
Port Exposes: 8000
Health Check Path: /api/auth/demo-info
```

`nixpacks.toml` defines the whole build and start:

- **Build**: installs `requirements.txt` (Python) and runs `cd frontend && npm ci && npm run build` (Node, pinned to 20 via `.nvmrc`).
- **Start**: `cd backend && python -m app.migrate && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` — runs pending Alembic migrations, then serves the API and the built `frontend/dist/`.

Leave the Coolify Start Command blank so it uses `nixpacks.toml`. Coolify normally provides `PORT` from `Port Exposes`; the server falls back to `8000` if `PORT` is absent.

If the Nixpacks polyglot detection ever fails to install the frontend (e.g. Node not provisioned), add an explicit install phase to `nixpacks.toml`:

```toml
[phases.install]
cmds = ["pip install -r requirements.txt", "cd frontend && npm ci"]
```

Use the PostgreSQL internal URL for `DATABASE_URL`, for example:

```env
DATABASE_URL=postgresql://postgres:password@postgresql-service:5432/postgres
```

Do not use `localhost` for `DATABASE_URL` in Coolify. Inside the app container, `localhost` means the app container itself, not the PostgreSQL container.

## Environment Variables

Required:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
MARKETDECK_JWT_SECRET=replace-with-a-long-random-secret
MARKETDECK_ADMIN_EMAIL=admin@example.com
MARKETDECK_ADMIN_PASSWORD=replace-with-a-strong-password
```

Optional:

```env
MARKETDECK_DB_CONNECT_RETRIES=30
MARKETDECK_DB_CONNECT_RETRY_DELAY=2
MARKETDECK_PRICE_CACHE_TTL_SECONDS=3600
MARKETDECK_STOCK_CHART_CACHE_TTL_SECONDS=900
MARKETDECK_FUNDAMENTALS_CACHE_TTL_SECONDS=21600
MARKETDECK_NEWS_CACHE_TTL_SECONDS=900
MARKETDECK_SEARCH_CACHE_TTL_SECONDS=3600
MARKETDECK_STATIC_DIR=frontend/dist
PORT=8000
```

Recommended Coolify settings:

| Setting | Value | Notes |
| --- | --- | --- |
| Build Variable | Yes | Coolify enables this by default. The app only needs these at runtime, so disabling buildtime is optional hardening. |
| Runtime Variable | Yes | Required. The server reads these when the container starts. |
| Literal | No | Use `Yes` only when the value contains `$...` text that must not be interpolated. |
| Multiline | No | None of these values should be multiline. |

Generate a JWT secret locally:

```bash
openssl rand -hex 32
```

## First Login

On first successful startup, the app applies migrations to create the schema, seeds default dashboard data, and inserts the demo and admin users.

Checklist:

1. Open the public app URL.
2. Click **Login as Demo** and confirm the dashboard loads.
3. Log out.
4. Log in with `MARKETDECK_ADMIN_EMAIL` and `MARKETDECK_ADMIN_PASSWORD`.
5. Confirm admin controls are visible.
6. Change the admin password in the app if desired.

Changing `MARKETDECK_ADMIN_PASSWORD` later does not overwrite an existing database user. Use the in-app password change flow after the first seed.

## Operational Notes

### Migrations

The schema is managed by Alembic. On startup, `app.migrate` runs before the server binds:

- An Alembic-managed database is upgraded to the latest revision.
- A **legacy database from before this refactor** (a `watchlists` table but no `alembic_version`) is stamped at the baseline revision `0001` — which matches that schema exactly — and then upgraded. Existing users, watchlists, and tickers are preserved.
- A fresh database has all migrations applied.

The `nixpacks.toml` start command also runs migrations, so they are applied automatically on every deploy.

### Database Seeding

Dashboard seed data is first-deploy only. If the `watchlists` table already has rows, the app skips watchlist/ticker/tag/settings seeding.

Admin and demo users are inserted with `ON CONFLICT DO NOTHING`, so redeploys do not reset the admin password.

### Startup Retries

The server retries the PostgreSQL connection during startup. This helps when Coolify starts the app while PostgreSQL is still becoming ready.

### Demo Account

The demo account is a real database user with role `demo`, but it does not use public credentials. The **Login as Demo** button calls `POST /api/auth/demo-login` and receives a read-only demo session.

Demo users can browse data and fetch prices, but write endpoints return `403`.

### Rate Limiting

Rate limiting is in memory and protects Yahoo-backed read endpoints:

- `GET /api/lists/{slug}/metrics`: `120/minute`
- `GET /api/search`: `120/minute`
- `GET /api/stocks/{symbol}`: `120/minute`
- `GET /api/stocks/{symbol}/chart`: `120/minute`
- `GET /api/stocks/{symbol}/news`: `120/minute`
- `GET /api/stocks/{symbol}/financials`: `120/minute`

The in-process rate limit and the price-fetch unresolved-symbol cooldown are per-process, so the app assumes a single instance. If you scale horizontally, move both to a shared backend such as Redis.

### Price Cache

Yahoo Finance chart responses are fetched in parallel and cached in PostgreSQL per account and ticker. This means the demo account shares cached prices across devices, while admin and demo sessions do not share price-cache entries with each other.

The default cache TTL is 1 hour. Override it with:

```env
MARKETDECK_PRICE_CACHE_TTL_SECONDS=3600
```

Tickers that Yahoo reports as unresolved are held in a short in-process cooldown so repeated list loads do not keep retrying known permanent failures immediately. Transient chart errors are not cooled down.

Admins can clear the server-side cache and failure cooldown through:

```text
DELETE /api/prices/cache
```

### Stock Data Cache

Single-stock pages use a separate global PostgreSQL `yahoo_cache` table for chart, search, news, summary, and financial statement JSON payloads. These payloads are account-agnostic and do not change when the watchlist base currency changes; stock pages display native Yahoo currency.

Yahoo fundamentals come from crumb-gated quoteSummary endpoints. If Yahoo rejects or fails the crumb flow, the app still returns chart, news, and technical data, with `fundamentalsAvailable: false`.

## Troubleshooting

### Restarting or Immediate Exit

Check Coolify logs for missing env vars, dependency installation errors, or PostgreSQL connection failures.

Required env vars:

```text
DATABASE_URL
MARKETDECK_JWT_SECRET
MARKETDECK_ADMIN_EMAIL
MARKETDECK_ADMIN_PASSWORD
```

### Cannot Connect to PostgreSQL

Check that:

- `DATABASE_URL` uses the Coolify internal PostgreSQL URL.
- The app and database are in the same Coolify project/network.
- The hostname is the PostgreSQL service hostname, not `localhost`.
- The PostgreSQL resource is running.

### Health Check Fails

Use:

```text
/api/auth/demo-info
```

This endpoint also checks database connectivity. If it fails, inspect app logs first.

### Login Fails

Check that the credentials match the database user. If the admin user already existed, changing `MARKETDECK_ADMIN_PASSWORD` in Coolify will not reset it.

## Local Development

Local development requires PostgreSQL and Node.js 20+.

**Backend** (serves the API, and `frontend/dist/` once built):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt   # runtime deps + pytest, ruff, respx, testcontainers

export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_JWT_SECRET="$(openssl rand -hex 32)"
export MARKETDECK_ADMIN_EMAIL="admin@example.com"
export MARKETDECK_ADMIN_PASSWORD="change-me"

cd backend
python -m app.migrate                 # optional; the server also migrates on startup
uvicorn app.main:app --reload
```

**Frontend** (Vite dev server on `http://localhost:5173`, proxying `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

During development, browse the Vite dev server for hot-reload. For a production-like run, `npm run build` and open the backend directly at `http://localhost:8000`.

### Checks

```bash
cd backend && ruff check app tests && pytest   # pytest uses a Postgres testcontainer, or set TEST_DATABASE_URL
cd frontend && npm run check && npm run build   # svelte-check + production build
```

## API Summary

Public:

- `GET /api/auth/demo-info`
- `POST /api/auth/login`
- `POST /api/auth/demo-login`

Authenticated admin or demo:

- `GET /api/auth/me`
- `GET /api/init`
- `GET /api/settings`
- `GET /api/lists/{slug}/metrics` — server-computed returns/heatmap; optional `?base=CUR` override
- `GET /api/search?q=QUERY` — Yahoo symbol/news search
- `GET /api/stocks/{symbol}` — stock overview and quoteSummary-backed fundamentals when available
- `GET /api/stocks/{symbol}/chart?range=1y&interval=1d` — OHLCV, meta, and server-computed technicals
- `GET /api/stocks/{symbol}/news`
- `GET /api/stocks/{symbol}/financials`

Admin only:

- `PUT /api/auth/password`
- `PUT /api/settings/{key}`
- `POST /api/lists`
- `PUT /api/lists/{slug}`
- `DELETE /api/lists/{slug}`
- `POST /api/lists/{slug}/tickers`
- `POST /api/lists/{slug}/tags`
- `PUT /api/lists/{slug}/tags/{tag}`
- `DELETE /api/lists/{slug}/tags/{tag}`
- `PUT /api/tickers/{id}`
- `DELETE /api/tickers/{id}`
- `DELETE /api/prices/cache`

Protected endpoints require:

```text
Authorization: Bearer <token>
```

## References

- [Coolify applications](https://coolify.io/docs/applications/)
- [Coolify environment variables](https://coolify.io/docs/knowledge-base/environment-variables)
- [Coolify health checks](https://coolify.io/docs/knowledge-base/health-checks)
