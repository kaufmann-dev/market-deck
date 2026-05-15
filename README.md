# MarketDeck

MarketDeck is a FastAPI and vanilla JavaScript financial dashboard with two login tiers:

- **Admin:** full dashboard access, including watchlists, tickers, tag colors, settings, cache clearing, and password changes.
- **Demo:** read-only dashboard access. Demo users can browse, filter, switch periods, switch views, and temporarily change base currency, but their changes are not persisted.

The app uses PostgreSQL for persistent data, JWT authentication, bcrypt password hashes, and endpoint-specific rate limiting for expensive Yahoo Finance price requests.

## Deployment Readiness

This repository is ready for a Coolify deployment with PostgreSQL as a separate Coolify resource.

What is already included:

- `requirements.txt` for Nixpacks/Python dependency detection.
- `.python-version` to keep production on Python 3.12.
- `nixpacks.toml` with an explicit production start command.
- PostgreSQL schema creation on app startup.
- PostgreSQL startup retries to handle Coolify database/app boot timing.
- First-start seed data from `seed_data.py`.
- Seeded admin and demo users.
- JWT login, session restore, logout, and role-aware UI.
- Admin-only server authorization for all write endpoints.
- Demo read-only behavior in the frontend and backend.
- Rate limiting on:
  - `POST /api/auth/login`: `5/minute`
  - `POST /api/prices`: `30/minute` and `1/second`
- Coolify-compatible health endpoint: `GET /api/auth/demo-info`.

Important deployment notes:

- There is no Dockerfile and no Docker Compose file. Deploy the app with Coolify's default Nixpacks build pack.
- PostgreSQL must be created as a separate Coolify database resource.
- `DATABASE_URL`, `MARKETDECK_JWT_SECRET`, `MARKETDECK_ADMIN_EMAIL`, and `MARKETDECK_ADMIN_PASSWORD` are required before the app can start.
- The app intentionally uses PostgreSQL only.

## Project Structure

```text
.
|-- server.py
|-- seed_data.py
|-- .python-version
|-- requirements.txt
|-- nixpacks.toml
|-- index.html
`-- static/
    |-- app.js
    `-- styles.css
```

Seed data is maintained directly in `seed_data.py`.

## Environment Variables

Configure these in the Coolify application resource under **Environment Variables**.

Use these Coolify settings for every environment variable listed below:

- Available at Buildtime: **No**
- Available at Runtime: **Yes**
- Is Literal: **Yes**
- Is Multiline: **No**

Required variables:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
MARKETDECK_JWT_SECRET=replace-with-a-long-random-secret
MARKETDECK_ADMIN_EMAIL=admin@example.com
MARKETDECK_ADMIN_PASSWORD=replace-with-a-strong-password
```

Optional variables:

```env
MARKETDECK_DEMO_EMAIL=demo@marketdeck.app
MARKETDECK_DEMO_PASSWORD=marketdeck
MARKETDECK_DB_CONNECT_RETRIES=30
MARKETDECK_DB_CONNECT_RETRY_DELAY=2
PORT=8000
```

`PORT` is usually provided by Coolify from the exposed port. If it is not set, the server falls back to `8000`.

Generate a strong JWT secret locally:

```bash
openssl rand -hex 32
```

## Coolify Deployment Guide

### 1. Push This Repository

Push the project to GitHub or another Git provider connected to Coolify.

The deployment expects these files to be present in the repository root:

- `server.py`
- `.python-version`
- `requirements.txt`
- `nixpacks.toml`
- `seed_data.py`
- `index.html`
- `static/app.js`
- `static/styles.css`

### 2. Create the PostgreSQL Resource

In Coolify:

1. Open your project and environment.
2. Click **New Resource**.
3. Select **PostgreSQL**.
4. Deploy the database.
5. Copy the database **internal connection URL**.

Use the internal URL for `DATABASE_URL` when the app and database are in the same Coolify project/network. It will look similar to:

```env
DATABASE_URL=postgresql://postgres:password@postgresql-service:5432/postgres
```

Do not use `localhost` in `DATABASE_URL` from the app container. `localhost` would point to the app container itself, not the PostgreSQL container.

### 3. Create the Application Resource

In Coolify:

1. Click **New Resource**.
2. Choose your Git repository.
3. Select the branch to deploy.
4. Use the default **Nixpacks** build pack.
5. Keep **Is it a static site?** disabled. This is a FastAPI app that also serves static files.

### 4. Configure Build and Start Settings

Set:

```text
Base Directory: /
Port Exposes: 8000
```

Set the start command to:

```bash
python server.py
```

The repository also includes `nixpacks.toml`, so Coolify/Nixpacks can pick this up automatically. The server uses `PORT` when Coolify provides it and falls back to `8000`.

### 5. Add Application Environment Variables

In the application resource, open **Environment Variables** and add the variables from the Environment Variables section above.

Use these settings for each variable:

- Available at Buildtime: **No**
- Available at Runtime: **Yes**
- Is Literal: **Yes**
- Is Multiline: **No**

Recommended:

- Keep `MARKETDECK_JWT_SECRET`, `MARKETDECK_ADMIN_PASSWORD`, and the database password private.
- Change the admin password from the in-app admin menu after first login if you do not want the env var password to remain your long-term password.

### 6. Configure Health Check

Use this health check path:

```text
/api/auth/demo-info
```

Expected response code:

```text
200
```

This endpoint is intentionally public because the demo credentials are public. It also touches the database, so a passing health check confirms both the app and PostgreSQL connection are available.

If Coolify reports `No available server`, check the application logs first. Failed health checks can prevent routing.

### 7. Deploy

Click **Deploy**.

On first startup the app will:

1. Validate required environment variables.
2. Connect to PostgreSQL, retrying briefly if the database is still starting.
3. Create tables if they do not exist.
4. Seed the demo user.
5. Seed the admin user.
6. Insert default settings, watchlists, tickers, and tag colors if the `watchlists` table is empty.

On later deploys:

- Existing users are not overwritten.
- Existing dashboard data is not reseeded if watchlists already exist.
- Admin UI edits remain in PostgreSQL.

## First Login Checklist

After deployment:

1. Open the public app URL.
2. Confirm the login screen appears.
3. Click **Login as Demo**.
4. Confirm demo users can browse lists, rankings, heatmap, filters, and temporary base currency changes.
5. Log out.
6. Log in with `MARKETDECK_ADMIN_EMAIL` and `MARKETDECK_ADMIN_PASSWORD`.
7. Confirm admin-only controls are visible:
   - Edit list
   - Create list
   - Tag color editor
   - Edit tickers
   - Change password
8. Change the admin password from the dashboard if desired.

## Operational Notes

### Database Seeding

Seeding is intentionally first-deploy only for dashboard data. The app checks whether `watchlists` is empty:

- Empty: insert seed settings, watchlists, tickers, and tag colors.
- Not empty: skip dashboard data seeding.

Admin and demo users are inserted with `ON CONFLICT DO NOTHING`, so repeated deployments do not reset passwords.

### Demo Account

The demo account is a real database user with role `demo`.

Demo users:

- Can call read endpoints.
- Can fetch prices.
- Cannot persist settings.
- Cannot create, edit, or delete watchlists, tickers, tag colors, or cache data.
- Receive `403` if they manually call write endpoints.

### Rate Limiting

Rate limiting is in memory and per app process.

Protected endpoints:

- `POST /api/auth/login`: `5/minute` per IP.
- `POST /api/prices`: `30/minute` and `1/second` per IP.

This is appropriate for the MVP single-process Coolify deployment. If you scale horizontally later, move rate-limit storage to a shared backend such as Redis.

### Price Cache

Yahoo Finance responses are cached in memory for 5 minutes per ticker. The cache is lost on app restart. Admin users can clear it through the API/UI path that calls:

```text
DELETE /api/prices/cache
```

## Troubleshooting

### App Fails Immediately on Startup

Check Coolify logs for:

```text
ERROR: MARKETDECK_ADMIN_EMAIL and MARKETDECK_ADMIN_PASSWORD are required.
```

or:

```text
ERROR: DATABASE_URL and MARKETDECK_JWT_SECRET are required.
```

Fix the missing environment variables and redeploy.

### Cannot Connect to PostgreSQL

Check:

- `DATABASE_URL` uses the Coolify internal PostgreSQL URL.
- The app and database resources are in the same Coolify project/network.
- The hostname is the PostgreSQL service hostname, not `localhost`.
- The database resource is running.

### Health Check Fails

Use:

```text
/api/auth/demo-info
```

If it fails, inspect application logs. This endpoint checks database connectivity, so failures usually mean missing env vars, invalid `DATABASE_URL`, or PostgreSQL not ready.

### Login Fails

Check:

- The admin email/password match the env vars used on the first successful startup.
- If the admin user already existed, changing `MARKETDECK_ADMIN_PASSWORD` later will not overwrite that database user's password.
- Use the in-app **Change Password** action after logging in as admin.

### Demo Credentials Are Wrong

The login screen reads demo credentials from:

```text
GET /api/auth/demo-info
```

If you set `MARKETDECK_DEMO_EMAIL` or `MARKETDECK_DEMO_PASSWORD`, those values are displayed publicly by design.

## Local Development

Local development also requires PostgreSQL.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:password@localhost:5432/marketdeck"
export MARKETDECK_JWT_SECRET="$(openssl rand -hex 32)"
export MARKETDECK_ADMIN_EMAIL="admin@example.com"
export MARKETDECK_ADMIN_PASSWORD="change-me"

uvicorn server:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

## API Summary

Public:

- `GET /api/auth/demo-info`
- `POST /api/auth/login`

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
- `PUT /api/tickers/{id}`
- `DELETE /api/tickers/{id}`
- `PUT /api/tag-colors/{tag}`
- `DELETE /api/tag-colors/{tag}`
- `DELETE /api/prices/cache`

All protected endpoints require:

```text
Authorization: Bearer <token>
```

## References

- Coolify application deployment docs: https://coolify.io/docs/applications/
- Coolify database docs: https://coolify.io/docs/databases/
- Coolify environment variable docs: https://coolify.io/docs/knowledge-base/environment-variables
- Coolify health check docs: https://coolify.io/docs/knowledge-base/health-checks
