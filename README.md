# MarketDeck

MarketDeck is a public-demo-ready financial dashboard for ranking assets by momentum and viewing trailing monthly returns in a heatmap. It supports admin and demo logins, PostgreSQL persistence, server-side Yahoo Finance price loading, historical FX conversion into a shared base currency, and rate-limited price fetching.

## Stack

- Frontend: vanilla HTML, CSS, and JavaScript
- Backend: FastAPI + Uvicorn
- Database: PostgreSQL
- Auth: JWT with bcrypt password hashes
- Rate limiting: slowapi
- Market data: Yahoo Finance via `yfinance`

## Setup

Install Python 3.11+ and PostgreSQL, then install dependencies:

```bash
pip install -r requirements.txt
```

Set the required environment variables:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_JWT_SECRET="replace-with-a-long-random-secret"
export MARKETDECK_ADMIN_EMAIL="admin@example.com"
export MARKETDECK_ADMIN_PASSWORD="change-me"
```

Optional demo credentials can also be configured:

```bash
export MARKETDECK_DEMO_EMAIL="demo@marketdeck.app"
export MARKETDECK_DEMO_PASSWORD="marketdeck"
```

Start the app locally:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Production

Coolify should deploy this repository as a GitHub clone Python app. No Dockerfile or Docker Compose file is required. Coolify auto-detects Python from `requirements.txt` and runs:

```bash
uvicorn server:app --host 0.0.0.0 --port $PORT
```

Create PostgreSQL as a separate Coolify service and set `DATABASE_URL` to that database connection string. Required production variables are:

- `DATABASE_URL`
- `MARKETDECK_JWT_SECRET`
- `MARKETDECK_ADMIN_EMAIL`
- `MARKETDECK_ADMIN_PASSWORD`

The server creates tables and seeds the admin, demo user, settings, watchlists, tickers, and tag colors on first startup. Health checks can use:

```text
GET /api/auth/demo-info
```

The project concept originally referenced SQLite backward compatibility, but the validated architecture resolves deployment to a clean PostgreSQL setup with no SQLite migration. PostgreSQL and `seed_data.py` are the implementation source of truth for this build.

## API

- `POST /api/auth/login` logs in and returns a JWT
- `GET /api/auth/me` validates a JWT and returns the current user
- `GET /api/auth/demo-info` returns public demo credentials
- `PUT /api/auth/password` changes the current admin password
- `GET /api/init` returns settings, tag colors, watchlists, and tickers
- `GET /api/settings` returns all settings
- `PUT /api/settings/{key}` updates a setting such as `GLOBAL_BASE_CURRENCY`
- `POST /api/lists` creates a watchlist
- `PUT /api/lists/{slug}` updates watchlist metadata
- `DELETE /api/lists/{slug}` deletes a watchlist and its tickers
- `POST /api/lists/{slug}/tickers` adds a ticker to a watchlist
- `PUT /api/tickers/{id}` updates a ticker
- `DELETE /api/tickers/{id}` deletes a ticker
- `PUT /api/tag-colors/{tag}` upserts a tag color
- `DELETE /api/tag-colors/{tag}` deletes a tag color
- `POST /api/prices` fetches historical price data
- `DELETE /api/prices/cache` clears the server-side price cache

All API endpoints except `/api/auth/login` and `/api/auth/demo-info` require `Authorization: Bearer <token>`.
