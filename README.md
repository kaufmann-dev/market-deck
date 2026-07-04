# Market Deck

Dashboard for ranking financial assets by price momentum — live prices, FX conversion, return heatmaps, and multi-watchlist management — powered by FastAPI, PostgreSQL, and Yahoo Finance.

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
- PostgreSQL schema creation and seed data on first startup.
- JWT login/session restore.
- Server-side authorization for all write endpoints.
- Rate limits on login and price-fetching endpoints.
- Coolify/Nixpacks deployment files:
  - `.python-version`
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
Start Command: python server.py
Health Check Path: /api/auth/demo-info
```

`nixpacks.toml` already defines the start command, but setting it in Coolify is also fine. Coolify normally provides `PORT` from `Port Exposes`; the server falls back to `8000` if `PORT` is absent.

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

On first successful startup, the app creates tables, seeds default dashboard data, inserts the demo user, and inserts the admin user.

Checklist:

1. Open the public app URL.
2. Click **Login as Demo** and confirm the dashboard loads.
3. Log out.
4. Log in with `MARKETDECK_ADMIN_EMAIL` and `MARKETDECK_ADMIN_PASSWORD`.
5. Confirm admin controls are visible.
6. Change the admin password in the app if desired.

Changing `MARKETDECK_ADMIN_PASSWORD` later does not overwrite an existing database user. Use the in-app password change flow after the first seed.

## Operational Notes

### Database Seeding

Dashboard seed data is first-deploy only. If the `watchlists` table already has rows, the app skips watchlist/ticker/settings seeding. Startup migrations still normalize existing ticker tags and create per-list tag catalogs when needed.

Admin users are inserted with `ON CONFLICT DO NOTHING`, so redeploys do not reset the admin password. Demo user seeding is also idempotent.

### Startup Retries

The server retries the PostgreSQL connection during startup. This helps when Coolify starts the app while PostgreSQL is still becoming ready.

### Demo Account

The demo account is a real database user with role `demo`, but it does not use public credentials. The **Login as Demo** button calls `POST /api/auth/demo-login` and receives a read-only demo session.

Demo users can browse data and fetch prices, but write endpoints return `403`.

### Rate Limiting

Rate limiting is in memory and only protects the Yahoo Finance proxy endpoint:

- `POST /api/prices`: `120/minute`

If you scale horizontally, move rate-limit storage to a shared backend such as Redis.

### Price Cache

Yahoo Finance chart responses are fetched in parallel and cached in PostgreSQL per account and ticker. This means the demo account shares cached prices across devices, while admin and demo sessions do not share price-cache entries with each other.

The default cache TTL is 1 hour. Override it with:

```env
MARKETDECK_PRICE_CACHE_TTL_SECONDS=3600
```

Tickers that Yahoo cannot resolve are held in a short in-process failure cooldown so repeated list loads do not keep retrying known failures immediately.

Admins can clear the server-side cache and failure cooldown through:

```text
DELETE /api/prices/cache
```

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

Local development requires PostgreSQL.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_JWT_SECRET="$(openssl rand -hex 32)"
export MARKETDECK_ADMIN_EMAIL="admin@example.com"
export MARKETDECK_ADMIN_PASSWORD="change-me"

python server.py
```

Open:

```text
http://localhost:8000
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
- `POST /api/prices`

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
