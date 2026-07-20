# AGENTS.md — Market Deck

Compact notes for AI agents working in this repo.

## Project shape
- **Backend** (`backend/`): packaged FastAPI app (`app/`) on SQLAlchemy 2 + Alembic, PostgreSQL. Layered into `api/` routers, `services/`, `models.py`, `schemas.py`, `security.py`, `config.py` (pydantic-settings), `db.py`, `seed.py`, `migrate.py`.
- **Frontend** (`frontend/`): Svelte 5 + Vite + TypeScript SPA. Reactive stores in `src/lib/stores/*.svelte.ts` (runes), typed API client in `src/lib/api/`, lightweight history routing in `src/lib/stores/router.svelte.ts`, components in `src/lib/components/`. Built to `frontend/dist/`, which the backend serves (SPA fallback + path-traversal guard in `app/main.py`).
- Deployed as a single container via Coolify/Nixpacks. `.python-version` = 3.12, `.nvmrc` = 20.

## Local development
Two terminals. Backend (needs PostgreSQL running):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime + pytest/ruff/respx/testcontainers
export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_PUBLIC_URL="http://localhost:5173"
export MARKETDECK_OIDC_ISSUER_URL="https://identity.example.com/application/o/market-deck"
export MARKETDECK_OIDC_CLIENT_ID="market-deck-local"
export MARKETDECK_OIDC_CLIENT_SECRET="set-locally"
export MARKETDECK_OIDC_STATE_SECRET="$(openssl rand -hex 32)"
cd backend && python -m app.migrate && uvicorn app.main:app --reload
```
Frontend (Vite dev server proxies `/api` → `localhost:8000`):
```bash
cd frontend && npm install && npm run dev
```
For a production-like run, `npm run build` then open the uvicorn port (8000) directly.

## Agent tooling
- Project-local skills installed under `.agents/skills/`: `svelte-code-writer`, `svelte-core-bestpractices`, and `postgresql-table-design`.
- Project-local MCP configs provide `svelte`, `context7`, and `playwright`. Codex/OpenCode also include a disabled optional `postgres` MCP entry that uses `DATABASE_URL`.
- For Svelte component/module work, use the Svelte MCP server before writing, reviewing, or refactoring Svelte code: call `list-sections`, fetch relevant sections with `get-documentation`, then run `svelte-autofixer` after edits until it has no issues or suggestions.
- For library/framework/API usage, use `context7` for version-specific docs. Prefer official docs and existing repo patterns over generic examples.
- For browser interaction and UI testing, use the Playwright MCP server when explicitly requested or genuinely necessary. Do not use the Playwright CLI as a substitute.

## Environment variables
Required: `DATABASE_URL`, `MARKETDECK_PUBLIC_URL`, `MARKETDECK_OIDC_ISSUER_URL`, `MARKETDECK_OIDC_CLIENT_ID`, `MARKETDECK_OIDC_CLIENT_SECRET`, `MARKETDECK_OIDC_STATE_SECRET` (pydantic-settings raises on startup if missing).
Optional: `MARKETDECK_DB_CONNECT_RETRIES` (30), `MARKETDECK_DB_CONNECT_RETRY_DELAY` (2), `MARKETDECK_PRICE_CACHE_TTL_SECONDS` (3600), `MARKETDECK_STOCK_CHART_CACHE_TTL_SECONDS` (900), `MARKETDECK_FUNDAMENTALS_CACHE_TTL_SECONDS` (21600), `MARKETDECK_NEWS_CACHE_TTL_SECONDS` (900), `MARKETDECK_SEARCH_CACHE_TTL_SECONDS` (3600), `MARKETDECK_STATIC_DIR` (defaults to `frontend/dist`), `PORT` (8000).
`DATABASE_URL` accepts `postgres://` / `postgresql://` and is normalized to `postgresql+psycopg2://` in `config.py`.

## Database & migrations
- **Alembic** owns the schema (`backend/alembic/versions/`). `app/migrate.py` runs on startup: upgrades if already Alembic-managed; **stamps `0001` then upgrades** a legacy pre-Alembic DB (detected by an existing `watchlists` table with no `alembic_version`); runs all migrations on a fresh DB.
- New schema change: edit `app/models.py`, then `cd backend && alembic revision --autogenerate -m "..."`, review the generated file, commit it.
- Seeding (`app/seed.py`, runs after migrations in the lifespan): watchlist/ticker/tag data seeds **only when `watchlists` is empty**. Authentication records are never seeded; OIDC identities stay provider-owned and demo sessions are created on demand. Editing `seed_data.py` does not re-seed an existing DB.

## Metrics / business logic
- All FX conversion and return math lives server-side in `app/services/metrics.py` (pure functions, injectable `today`). It is a faithful port of the old client math — see the module docstring for the two preserved quirks (JS-style month rollover, USX cents). `GET /api/lists/{slug}/metrics?base=CUR` returns computed lookbacks/monthly/currentPrice; the frontend only ranks (`src/lib/scoring.ts`) and renders.
- Price fetching (`app/services/yahoo.py`) uses parallel Yahoo chart-JSON requests; results cache in PostgreSQL per account+ticker, and permanently unresolved tickers enter a short in-process cooldown (`app/services/price_cache.py`). Both caches are per-process (single-instance). `slowapi` rate-limits the metrics endpoint (`120/minute`).
- Single-stock data uses `GET /api/search`, `GET /api/stocks/{symbol}`, `/chart`, `/news`, and `/financials`. Chart/search/news are auth-free Yahoo surfaces; the overview's fundamentals (profile/keyStats/financialData) come from crumb/cookie-gated quoteSummary and degrade to `fundamentalsAvailable:false` when crumb auth fails. `/financials` builds full income/balance/cash-flow statements from the crumb-gated `fundamentals-timeseries` endpoint (`yahoo.fetch_fundamentals_timeseries`) — the quoteSummary `*History` modules no longer return detailed line items — and degrades to `financialsAvailable:false`. Both paths authenticate via `app/services/yahoo_auth.py`.
- `app/services/technicals.py` is pure indicator math over OHLCV. Global stock/search/news/fundamental JSON payloads cache in `yahoo_cache` via `app/services/stock_cache.py`; this cache is account-agnostic and separate from `price_cache`.

## Frontend notes
- No manual cache-busting; Vite emits hashed asset filenames.
- Icons are bundled via `@lucide/svelte` (no CDN). Charts are bundled via `lightweight-charts` (no CDN). Google Fonts stay linked in `frontend/index.html`.
- Router state is authoritative for views: `/`, `/list/{slug}`, and `/stock/{symbol}`. The app store holds loaded data and bridges route changes to `loadMetrics` / `loadStock`.
- Design system ("Terminal Dark") lives in `frontend/src/app.css`, ported from the original stylesheet. Keep DESIGN.md as the source of truth for visual rules.

## Svelte implementation patterns
- Treat this as a Svelte 5 project. Use runes, snippets, and fine-grained reactivity.
- Use `$props()` for component inputs and treat props as changeable.
- Use `$state` only for values that must update the template, a derived value, or an effect. Use `$state.raw` for large objects, API responses, or arrays that are reassigned whole rather than deeply mutated.
- Use `$derived` for computed state. Use `$derived.by` only when the computation needs a multi-line function.
- Avoid `$effect` unless syncing with an external non-Svelte API such as chart/canvas libraries. Prefer event-boundary updates, function bindings, `$derived`, `<svelte:window>`, `<svelte:document>`, or `createSubscriber` where appropriate.
- Use modern Svelte syntax in new code: `onclick={...}`, snippets with `{@render ...}`, `<DynamicComponent>`, `{@attach ...}`, classes with `$state` fields for shared reactive logic, and keyed `{#each}` blocks with stable object identifiers.
- Avoid legacy Svelte syntax in new/refactored code: `export let`, `$$props`, `$$restProps`, `$:` reactive blocks, `<slot>`, `$$slots`, `<svelte:component>`, `<svelte:self>`, `use:action`, `class:` directives, and `on:` event attributes.
- Use CSS custom properties for parent-to-child styling boundaries and preserve the existing Terminal Dark CSS/token style before adding new visual patterns.

## Verification
```bash
cd backend && ruff check app tests && pytest      # pytest uses a Postgres testcontainer (podman/docker socket) or TEST_DATABASE_URL
cd frontend && npm run check && npm run build      # svelte-check + production build
```
Tests need a container runtime for testcontainers; set `TEST_DATABASE_URL` to point at an existing Postgres if none is available.

## Deployment
- `nixpacks.toml`: Python + Node providers; build phase runs the frontend build; start runs `app.migrate` then uvicorn.
- Coolify: port 8000, health check `/api/auth/demo-info`. Migrations run automatically on start. Do not point `DATABASE_URL` at `localhost` inside Coolify — use the internal PostgreSQL service hostname.
