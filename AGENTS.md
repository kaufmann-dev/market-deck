# AGENTS.md — Market Deck

Compact notes for AI agents working in this repo.

## Project shape
- Single-process FastAPI backend (`server.py`) + vanilla JS frontend (`index.html`, `static/`).
- No build step, no test suite, no linter/formatter configured.
- Designed for Coolify/Nixpacks deployment. `.python-version` = 3.12.

## Local development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_JWT_SECRET="$(openssl rand -hex 32)"
export MARKETDECK_ADMIN_EMAIL="admin@example.com"
export MARKETDECK_ADMIN_PASSWORD="change-me"

python server.py
# Open http://localhost:8000
```

## Environment variables
Required at startup: `DATABASE_URL`, `MARKETDECK_JWT_SECRET`, `MARKETDECK_ADMIN_EMAIL`, `MARKETDECK_ADMIN_PASSWORD`.
Missing any causes immediate `SystemExit(1)`.

## Database & seeding
- Schema is auto-created on startup (`CREATE TABLE IF NOT EXISTS`). No migration tool.
- `seed_data.py` is imported by `server.py` and seeded **only when `watchlists` is empty**.
  - Changing `seed_data.py` will **not** affect an existing database. To re-seed, truncate the `watchlists` table (or drop the DB).
- Admin users are inserted with `ON CONFLICT DO NOTHING`, so redeploys do not reset the admin password. Demo user seeding is also idempotent.
- The server retries PostgreSQL connection on startup (30 attempts by default) to tolerate slow DB spin-up.

## Frontend
- Plain CSS/JS. No bundler, no framework.
- `index.html` references `static/styles.css?v=2` and `static/app.js?v=2`. Bump the `v=` query param when deploying static asset changes to avoid stale browser caches.

## API / backend quirks
- In-memory rate limiting (`slowapi`) protects `/api/prices`.
- Price data is cached in PostgreSQL per account and ticker.
- Price fetching relies on `yfinance`. Calls can be slow or fail; the backend retries per-ticker on failure.

## Deployment
- `nixpacks.toml` sets start command: `python server.py`.
- Coolify settings: port 8000, health check path `/api/auth/demo-info`.
- Do not set `DATABASE_URL` to `localhost` inside Coolify containers; use the internal PostgreSQL service hostname.

## Verification
- There is no test suite. A quick sanity check is:
  ```bash
  python -m py_compile server.py seed_data.py
  ```
