# AGENTS.md — Market Deck

Compact notes for AI agents working in this repo.

## Project shape
- **Backend** (`backend/`): packaged FastAPI app (`app/`) on SQLAlchemy 2 + Alembic, PostgreSQL. Layered into `api/` routers, `services/`, `models.py`, `schemas.py`, `security.py`, `config.py` (pydantic-settings), `db.py`, `seed.py`, `migrate.py`.
- **Frontend** (`frontend/`): Svelte 5 + Vite + TypeScript SPA. Reactive stores in `src/lib/stores/*.svelte.ts` (runes), typed API client in `src/lib/api/`, components in `src/lib/components/`. Built to `frontend/dist/`, which the backend serves (SPA fallback + path-traversal guard in `app/main.py`).
- Deployed as a single container via Coolify/Nixpacks. `.python-version` = 3.12, `.nvmrc` = 20.

## Local development
Two terminals. Backend (needs PostgreSQL running):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime + pytest/ruff/respx/testcontainers
export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_JWT_SECRET="$(openssl rand -hex 32)"
export MARKETDECK_ADMIN_EMAIL="admin@example.com"
export MARKETDECK_ADMIN_PASSWORD="change-me"
cd backend && python -m app.migrate && uvicorn app.main:app --reload
```
Frontend (Vite dev server proxies `/api` → `localhost:8000`):
```bash
cd frontend && npm install && npm run dev
```
For a production-like run, `npm run build` then open the uvicorn port (8000) directly.

## Environment variables
Required: `DATABASE_URL`, `MARKETDECK_JWT_SECRET`, `MARKETDECK_ADMIN_EMAIL`, `MARKETDECK_ADMIN_PASSWORD` (pydantic-settings raises on startup if missing).
Optional: `MARKETDECK_DB_CONNECT_RETRIES` (30), `MARKETDECK_DB_CONNECT_RETRY_DELAY` (2), `MARKETDECK_PRICE_CACHE_TTL_SECONDS` (3600), `MARKETDECK_STATIC_DIR` (defaults to `frontend/dist`), `PORT` (8000).
`DATABASE_URL` accepts `postgres://` / `postgresql://` and is normalized to `postgresql+psycopg2://` in `config.py`.

## Database & migrations
- **Alembic** owns the schema (`backend/alembic/versions/`). `app/migrate.py` runs on startup: upgrades if already Alembic-managed; **stamps `0001` then upgrades** a legacy pre-Alembic DB (detected by an existing `watchlists` table with no `alembic_version`); runs all migrations on a fresh DB.
- New schema change: edit `app/models.py`, then `cd backend && alembic revision --autogenerate -m "..."`, review the generated file, commit it.
- Seeding (`app/seed.py`, runs after migrations in the lifespan): admin + demo users are idempotent (`ON CONFLICT DO NOTHING`); watchlist/ticker/tag data seeds **only when `watchlists` is empty**. Editing `seed_data.py` does not re-seed an existing DB.

## Metrics / business logic
- All FX conversion and return math lives server-side in `app/services/metrics.py` (pure functions, injectable `today`). It is a faithful port of the old client math — see the module docstring for the two preserved quirks (JS-style month rollover, USX cents). `GET /api/lists/{slug}/metrics?base=CUR` returns computed lookbacks/monthly/currentPrice; the frontend only ranks (`src/lib/scoring.ts`) and renders.
- Price fetching (`app/services/yahoo.py`) uses parallel Yahoo chart-JSON requests; results cache in PostgreSQL per account+ticker, failed tickers in a short in-process cooldown (`app/services/price_cache.py`). Both caches are per-process (single-instance). `slowapi` rate-limits the metrics endpoint (`120/minute`).

## Frontend notes
- No manual cache-busting; Vite emits hashed asset filenames.
- Icons are bundled via `@lucide/svelte` (no CDN). Google Fonts stay linked in `frontend/index.html`.
- Design system ("Terminal Dark") lives in `frontend/src/app.css`, ported from the original stylesheet. Keep DESIGN.md as the source of truth for visual rules.

## Verification
```bash
cd backend && ruff check app tests && pytest      # pytest uses a Postgres testcontainer (podman/docker socket) or TEST_DATABASE_URL
cd frontend && npm run check && npm run build      # svelte-check + production build
```
Tests need a container runtime for testcontainers; set `TEST_DATABASE_URL` to point at an existing Postgres if none is available.

## Deployment
- `nixpacks.toml`: Python + Node providers; build phase runs the frontend build; start runs `app.migrate` then uvicorn.
- Coolify: port 8000, health check `/api/auth/demo-info`. Migrations run automatically on start. Do not point `DATABASE_URL` at `localhost` inside Coolify — use the internal PostgreSQL service hostname.
