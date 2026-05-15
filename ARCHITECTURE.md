# Architecture Summary

**Concept:** Rebuild MarketDeck with JWT-based authentication (admin + demo roles), rate-limited price fetching, and Coolify deployment, while preserving the existing vanilla HTML/JS frontend and migrating from SQLite to PostgreSQL.

**Stack:**

| Choice | Justification |
| :--- | :--- |
| Python 3.11+ with FastAPI + Uvicorn | Existing backend. No reason to change. Mature, stable. |
| python-jose + passlib[bcrypt] | JWT creation/verification and password hashing. Minimal, standard libraries for FastAPI. |
| slowapi | Rate limiting middleware built for FastAPI. Uses `limits` under the hood. Off-the-shelf, removes build work. |
| PostgreSQL + psycopg2-binary | Requested over SQLite. Handles concurrent reads/writes better. psycopg2 is the standard synchronous PostgreSQL driver for Python. Connected via `DATABASE_URL` environment variable. |
| Vanilla HTML/CSS/JS (existing) | No frontend framework needed. Single HTML file with view toggles (login / home / list). Consistent with existing conventions. |
| Coolify GitHub clone deploy | No Dockerfile. Coolify auto-detects Python from `requirements.txt` and runs `uvicorn server:app`. |

---

## System Design

### Components

| Component | Responsibility | Technology |
| :--- | :--- | :--- |
| **Login view** | Unauthenticated landing page. Displays demo credentials. Accepts email/password form. | Static HTML in `index.html`, toggled by `app.js` |
| **Dashboard views** | Homepage (watchlist grid, tag editor) and list view (rankings, heatmap). Unchanged structure. | Existing `index.html` + `app.js` |
| **Auth router** | `POST /api/auth/login` — validates credentials, returns JWT. `GET /api/auth/me` — validates token, returns user info. `GET /api/auth/demo-info` — returns public demo credentials for display. | FastAPI route handlers in `server.py` |
| **Auth middleware** | FastAPI dependency that extracts and validates JWT from `Authorization: Bearer` header. Injects `current_user` (email, role) into request context. | `Depends(get_current_user)` |
| **Authorization guard** | Checks `current_user.role`. Returns 403 if demo user attempts a write operation. Applied per-endpoint. | Inline check inside route handler or second dependency |
| **Rate limiter** | Counts requests per IP. Returns 429 with `Retry-After` when threshold exceeded. Applied only to `POST /api/prices`. | slowapi (`@limiter.limit("30/minute;1/second")`) |
| **Users table + seeder** | Stores admin and demo accounts. Seeds demo user on startup. Seeds admin from environment variables. | PostgreSQL `users` table, startup migration in `server.py` |
| **Password change** | Admin-only form to change their own password. | `PUT /api/auth/password` endpoint, modal form in dashboard |
| **Logout** | Clears JWT from localStorage, redirects to login view. Available to both roles. | Button in top bar, `app.js` handler |
| **Price cache** | In-memory per-ticker cache with 5-min TTL. Unchanged from current implementation. | Existing `_price_cache` dict in `server.py` |
| **Static file server** | Catch-all route serves `index.html` and static assets. Unchanged. | Existing `@app.get("/{path:path}")` |

### Data Flow

**Login flow:**
```
Browser                    Server                    Database
  │                          │                          │
  │  1. GET /                │                          │
  │─────────────────────────►│                          │
  │  2. index.html + app.js  │                          │
  │◄─────────────────────────│                          │
  │                          │                          │
  │  3. GET /api/auth/demo-info (no auth)               │
  │─────────────────────────►│                          │
  │  4. { email, password }  │                          │
  │◄─────────────────────────│                          │
  │                          │                          │
  │  5. User submits email+password                     │
  │     POST /api/auth/login │                          │
  │─────────────────────────►│                          │
  │                          │  6. SELECT FROM users    │
  │                          │─────────────────────────►│
  │                          │  7. user row             │
  │                          │◄─────────────────────────│
  │                          │                          │
  │                          │  8. bcrypt.verify(pw)    │
  │                          │  9. Sign JWT{email,role} │
  │                          │                          │
  │  10. { token, role }     │                          │
  │◄─────────────────────────│                          │
  │                          │                          │
  │  11. Store JWT in localStorage                     │
  │  12. Show dashboard view                            │
```

**Authenticated request flow:**
```
Browser                    Server                    Database
  │                          │                          │
  │  GET /api/init            │                          │
  │  Authorization: Bearer X  │                          │
  │─────────────────────────►│                          │
  │                          │  1. Decode & verify JWT  │
  │                          │  2. Extract role         │
  │                          │  3. GET allowed (all)    │
  │                          │─────────────────────────►│
  │  4. data                  │                          │
  │◄─────────────────────────│                          │
```

**Demo user attempts write:**
```
Browser                    Server
  │                          │
  │  PUT /api/settings/X     │
  │  Authorization: Bearer X  │
  │─────────────────────────►│
  │                          │  1. Decode JWT
  │                          │  2. role == "demo"
  │                          │  3. Method is PUT → 403
  │  403 Forbidden            │
  │◄─────────────────────────│
```

**Rate-limited price request:**
```
Browser                    Server                    Yahoo Finance
  │                          │                          │
  │  POST /api/prices         │                          │
  │─────────────────────────►│                          │
  │                          │  1. slowapi checks IP    │
  │                          │     counter              │
  │                          │     If >30/min → 429     │
  │                          │     If OK → proceed      │
  │                          │  2. Check in-memory      │
  │                          │     cache                │
  │                          │  3. For uncached:        │
  │                          │─────────────────────────►│
  │                          │  4. price data           │
  │                          │◄─────────────────────────│
  │  5. prices               │                          │
  │◄─────────────────────────│                          │
```

### Trust Boundaries

```
                        ┌──────────────────────────┐
                        │       Browser             │
                        │  localStorage: JWT        │
                        │  state: role, settings     │
                        │                            │
                        │  ┌──────────────────────┐ │
                        │  │  DEMO USER           │ │
                        │  │  Edit buttons hidden  │ │
                        │  │  Write API calls      │ │
                        │  │  skipped entirely     │ │
                        │  └──────────────────────┘ │
                        │                            │
                        │  ┌──────────────────────┐ │
                        │  │  ADMIN USER          │ │
                        │  │  Full UI shown       │ │
                        │  │  Write API calls      │ │
                        │  │  sent to server       │ │
                        │  └──────────────────────┘ │
                        └────────────┬─────────────┘
                                     │ HTTPS
                                     │ Authorization: Bearer <JWT>
                        ┌────────────▼─────────────┐
                        │       Server              │
                        │                            │
                        │  ┌──────────────────────┐ │
                        │  │  Auth Middleware      │ │
                        │  │  Verify JWT signature │ │
                        │  │  Extract role         │ │
                        │  └──────────┬───────────┘ │
                        │             │              │
                        │  ┌──────────▼───────────┐ │
                        │  │  Authz Guard         │ │
                        │  │  role=demo + PUT/POST │ │
                        │  │  /DELETE → 403       │ │
                        │  └──────────┬───────────┘ │
                        │             │              │
                        │  ┌──────────▼───────────┐ │
                        │  │  Rate Limiter        │ │
                        │  │  Only on /api/prices │ │
                        │  │  30/min + 1/sec      │ │
                        │  └──────────┬───────────┘ │
                        │             │              │
                        │  ┌──────────▼───────────┐ │
                        │  │  Route Handler        │ │
                        │  └──────────┬───────────┘ │
                        │             │              │
                        │  ┌──────────▼───────────┐ │
                        │  │  PostgreSQL            │ │
                        │  │  (parametrized SQL)   │ │
                        │  └──────────────────────┘ │
                        └────────────────────────────┘
```

**Key security points:**
- The JWT signature is the only trust anchor. The browser cannot forge a valid signature without the server secret.
- Frontend hiding of buttons is a UX convenience, not a security control. The server's authorization guard is the real enforcement.
- The demo credentials endpoint (`GET /api/auth/demo-info`) is unauthenticated — these are public by design.
- The login endpoint is rate-limited to prevent brute force (5 attempts/IP/minute).

### Synchronous vs. Asynchronous

All interactions are synchronous HTTP request/response. There are no async handoffs (no queues, no background workers, no WebSockets). This is appropriate for the scale and complexity:

- **Auth**: Synchronous. Login returns a token immediately.
- **Price fetching**: Synchronous. The server blocks while waiting for Yahoo Finance, but this is acceptable — one request serves all tickers for a watchlist. The frontend shows a spinner during the 2–10 second wait.
- **Rate limiting**: Synchronous. The check happens before the handler runs.

### Failure Modes

| Failure | Response | Recovery |
| :--- | :--- | :--- |
| Missing JWT | 401 `{"detail": "Not authenticated"}` | Frontend redirects to login view |
| Expired/invalid JWT | 401 `{"detail": "Token expired"}` | Frontend clears localStorage, shows login |
| Demo user tries write | 403 `{"detail": "Read-only account"}` | Frontend catches 403, shows toast (shouldn't happen since buttons are hidden) |
| Rate limit exceeded | 429 `{"detail": "Too many requests"}` + `Retry-After` header | Frontend shows error, user waits. Cached data still served. |
| Yahoo Finance fails | 200 with `null` for failed tickers | Existing retry logic in `_download_prices`. Frontend shows "N failed" in status bar. |
| DB connection fails | 500 | Coolify health check catches this, triggers restart |
| yfinance import fails at startup | Server fails to start | Coolify shows deployment failure. Fix `requirements.txt`. |

---

## Data Model

### Entities

| Entity | Table | Key Fields | Relationships |
| :--- | :--- | :--- | :--- |
| **User** | `users` | `id INTEGER PK`, `email TEXT UNIQUE NOT NULL`, `password_hash TEXT NOT NULL`, `role TEXT NOT NULL CHECK(role IN ('admin','demo'))`, `created_at TEXT DEFAULT datetime('now')` | None |
| **Setting** | `settings` (existing) | `key TEXT PK`, `value TEXT` | None |
| **Watchlist** | `watchlists` (existing) | `id INTEGER PK`, `slug TEXT UNIQUE`, `name`, `short_name`, `category`, `description`, `tag`, `currency`, `show_type` | Has many `tickers` (FK: `tickers.watchlist_id`) |
| **Ticker** | `tickers` (existing) | `id INTEGER PK`, `watchlist_id INTEGER FK`, `symbol`, `name`, `tag`, `currency`, `sort_order` | Belongs to `watchlists` (CASCADE delete) |
| **Tag color** | `tag_colors` (existing) | `tag TEXT PK`, `bg TEXT`, `text TEXT`, `border TEXT` | None |

### Schema Notes

**New migration — auto-applied on startup:**

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'demo')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Existing tables — converted to PostgreSQL:**

The current SQLite schema (4 tables: `settings`, `watchlists`, `tickers`, `tag_colors`) must be migrated. Key PostgreSQL equivalents:

| SQLite | PostgreSQL |
| :--- | :--- |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `INSERT OR REPLACE` | `INSERT ... ON CONFLICT ... DO UPDATE` (upsert) |
| `INSERT OR IGNORE` | `INSERT ... ON CONFLICT DO NOTHING` |
| `?` placeholders | `%s` placeholders (psycopg2) |
| `COALESCE(MAX(sort_order),-1)` | same syntax, works in PostgreSQL |
| `datetime('now')` | `NOW()` |
| `PRAGMA foreign_keys = ON` | Not needed (enforced by default) |
| `lastrowid` | `RETURNING id` clause |

**Connection management:**

Replace the current `sqlite3` context manager with `psycopg2` connection pooling:

```python
import psycopg2
import psycopg2.pool
from contextlib import contextmanager

# Created once at startup
_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=os.environ["DATABASE_URL"]
)

@contextmanager
def get_db():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)
```

**Seed data — applied on startup after migration:**

```python
# Demo user: always seeded. Credentials from env vars (with defaults).
# Using INSERT ... ON CONFLICT DO NOTHING (idempotent).
cursor.execute("""
    INSERT INTO users (email, password_hash, role)
    VALUES (%s, %s, 'demo')
    ON CONFLICT (email) DO NOTHING
""", (demo_email, bcrypt_hash(demo_password)))

# Admin user: seeded only if env vars are set.
if admin_email and admin_password:
    cursor.execute("""
        INSERT INTO users (email, password_hash, role)
        VALUES (%s, %s, 'admin')
        ON CONFLICT (email) DO NOTHING
    """, (admin_email, bcrypt_hash(admin_password)))
```

**Indexes:**
- `users.email` — unique index (from UNIQUE constraint). Used on every login lookup.
- Equivalent indexes on existing tables (migrated from SQLite schema).

**State location:**
- **User credentials**: PostgreSQL `users` table (persistent)
- **JWT**: Browser `localStorage` (cleared on logout or expiry). Expires after **24 hours** for both admin and demo roles.
- **Demo user's temporary settings**: `app.js` state object in memory (lost on page refresh or logout)
- **Price cache**: Server-side `_price_cache` dict in memory (5-min TTL, lost on server restart)
- **Watchlist data**: PostgreSQL (persistent, shared across all users)

**JWT expiry — design decision:**

Both admin and demo tokens expire after **24 hours**. This balances security and UX:

- **No refresh token infrastructure**: Adding refresh tokens would require a token store, rotation logic, and additional client complexity — disproportionate for a single-admin personal tool with a public demo.
- **Demo tokens**: Carry zero privileges (view-only). Even if stolen, the attacker can only see public financial data. 24h prevents a leaked token from persisting indefinitely.
- **Admin tokens**: 24h limits the exposure window to one day. The admin is a single person who will notice unusual activity quickly. For a banking or multi-user app, shorter expiry + refresh would be required, but this is a personal dashboard.

**Migration strategy:**

A one-time migration script (`scripts/migrate_to_pg.py`) converts the existing `data.db` SQLite database to PostgreSQL:
1. Read all rows from each SQLite table
2. Insert into equivalent PostgreSQL tables
3. Reset sequences (e.g., `SELECT setval('tickers_id_seq', MAX(id))`)

Existing seed scripts (`scripts/migrate.py`) should be updated to target PostgreSQL directly. The legacy `data/lists.json` and `data/colors.json` files remain as seed data sources.

---

## API & Interfaces

### Endpoints

All endpoints except `/api/auth/login` and `/api/auth/demo-info` require `Authorization: Bearer <JWT>` header.

#### New endpoints

| Method | Path | Auth | Role | Rate Limit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | None | — | 5/min/IP | Accepts `{"email": "...", "password": "..."}`. Returns `{"token": "...", "email": "...", "role": "admin\|demo"}` or 401. |
| `GET` | `/api/auth/me` | Bearer | any | — | Validates token. Returns `{"email": "...", "role": "admin\|demo"}`. Used on page reload to restore session. |
| `GET` | `/api/auth/demo-info` | None | — | — | Returns `{"email": "...", "password": "..."}`. Public — used by the login page to display demo credentials. |
| `PUT` | `/api/auth/password` | Bearer | admin | — | Admin changes their own password. Body: `{"current_password": "...", "new_password": "..."}`. Returns `{"ok": true}` or 400/403. |

**POST /api/auth/login request:**
```json
{
    "email": "user@example.com",
    "password": "secret123"
}
```

**POST /api/auth/login response (200):**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "email": "user@example.com",
    "role": "admin"
}
```

**POST /api/auth/login response (401):**
```json
{
    "detail": "Invalid email or password"
}
```

**GET /api/auth/me response (200):**
```json
{
    "email": "user@example.com",
    "role": "admin"
}
```

**GET /api/auth/demo-info response (200):**
```json
{
    "email": "demo@marketdeck.app",
    "password": "marketdeck"
}
```

**PUT /api/auth/password request:**
```json
{
    "current_password": "old-secret",
    "new_password": "new-secret-123"
}
```

**PUT /api/auth/password response (200):**
```json
{
    "ok": true
}
```

**PUT /api/auth/password response (400 — wrong current password):**
```json
{
    "detail": "Current password is incorrect"
}
```

#### Existing endpoints — updated authorization

| Method | Path | Role | Change |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/init` | any | No change. Returns all data for the dashboard bootstrap. |
| `GET` | `/api/settings` | any | No change. |
| `PUT` | `/api/settings/{key}` | admin | **New: requires admin role.** 403 for demo. |
| `POST` | `/api/lists` | admin | **New: requires admin role.** 403 for demo. |
| `PUT` | `/api/lists/{slug}` | admin | **New: requires admin role.** 403 for demo. |
| `DELETE` | `/api/lists/{slug}` | admin | **New: requires admin role.** 403 for demo. |
| `POST` | `/api/lists/{slug}/tickers` | admin | **New: requires admin role.** 403 for demo. |
| `PUT` | `/api/tickers/{id}` | admin | **New: requires admin role.** 403 for demo. |
| `DELETE` | `/api/tickers/{id}` | admin | **New: requires admin role.** 403 for demo. |
| `PUT` | `/api/tag-colors/{tag}` | admin | **New: requires admin role.** 403 for demo. |
| `DELETE` | `/api/tag-colors/{tag}` | admin | **New: requires admin role.** 403 for demo. |
| `POST` | `/api/prices` | any | **New: rate limited** at 30/min + 1/sec per IP. No role restrictions (both admin and demo can fetch prices). |
| `DELETE` | `/api/prices/cache` | admin | **New: requires admin role.** 403 for demo. This is an admin-only operation because it affects the shared cache. |
| `GET` | `/{path:path}` | None | No change. Serves static files and `index.html`. |

**403 error shape (all write endpoints for demo):**
```json
{
    "detail": "Read-only account. Write operations require admin privileges."
}
```

**429 error shape (rate limit):**
```json
{
    "detail": "Too many requests. Try again later."
}
```
With `Retry-After: 60` header (or remaining seconds).

**JWT payload shape:**
```json
{
    "sub": "user@example.com",
    "role": "admin",
    "exp": 1740000000,
    "iat": 1739913600
}
```
Both admin and demo tokens expire 24 hours after issuance (`exp = iat + 86400`).

**Pagination:** Not required for any endpoint. The most data returned is `/api/init` with ~155 tickers across 5 watchlists, well within single-response limits. The prices endpoint already batches all tickers in one request.

### Events / Queues

None. This system has no event-driven or asynchronous communication. All interactions are synchronous HTTP requests.

---

## Non-Functional Requirements

| Concern | Target | Approach |
| :--- | :--- | :--- |
| **Latency** | Login <200ms, token validation <10ms, price fetch 2–10s, cached price <5ms, dashboard render <100ms | Login: single bcrypt verify + JWT sign. Token: symmetric HS256 decode. Prices: dominated by Yahoo Finance round-trip. Cached: in-memory dict lookup. Render: all client-side JS computation. |
| **Scalability** | 50 concurrent demo users, 1 admin | Single server process. PostgreSQL handles concurrent reads efficiently. yfinance downloads batch all tickers in one call — no per-ticker fan-out. Bottleneck is Yahoo Finance network latency, not local compute. Rate limiting caps at 30 price requests/min/IP — with 5-min cache, most hits are cache serves. |
| **Security** | No data exposure, no privilege escalation, no brute-force credential attacks | JWT signed with HS256 (secret from `MARKETDECK_JWT_SECRET` env var). Passwords hashed with bcrypt (passlib). All SQL parametrized via psycopg2 `%s` placeholders. Login rate-limited at 5 attempts/min/IP. JWT expires after 24h for both roles. Secrets never in source code — only env vars. The demo password is public by design, so its exposure is not a vulnerability. Static file server rejects path traversal (existing `resolve(strict=False)` + `relative_to` guard). |
| **Observability** | Login attempts, rate limit hits, yfinance failures must be loggable | `print()` calls for: failed login attempts (email + IP), rate limit 429s (IP + endpoint), yfinance download errors (existing). For production, these are picked up by stdout and visible in Coolify's deployment logs. No structured logging framework needed at this scale. |
| **Operability** | Deploy via Coolify GitHub clone. Config via env vars. PostgreSQL as external service. | **No Dockerfile.** Coolify auto-detects Python from `requirements.txt` and runs `uvicorn server:app --host 0.0.0.0 --port $PORT`. Health check: `GET /api/auth/demo-info` (returns 200 if server is up and DB is reachable). Rollback: redeploy previous commit from git history. Database is external — use Coolify's PostgreSQL service or a separate managed PostgreSQL instance. |

### Environment Variables

| Variable | Required | Default | Purpose |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | — | PostgreSQL connection string. Format: `postgresql://user:password@host:5432/dbname`. |
| `MARKETDECK_JWT_SECRET` | **Yes** | — | HS256 signing key. Generate with `openssl rand -hex 32`. |
| `MARKETDECK_ADMIN_EMAIL` | **Yes** (on first deploy) | — | Seeds the admin user on first startup. |
| `MARKETDECK_ADMIN_PASSWORD` | **Yes** (on first deploy) | — | Seeds the admin user on first startup. |
| `MARKETDECK_DEMO_EMAIL` | No | `demo@marketdeck.app` | Demo account email (public). |
| `MARKETDECK_DEMO_PASSWORD` | No | `marketdeck` | Demo account password (public). |
| `PORT` | No | `8000` | Server port. Coolify sets this automatically. |

**Coolify deployment notes:**
- Create a PostgreSQL database in Coolify (or use an existing one). Set the `DATABASE_URL` env var to its connection string.
- Clone the GitHub repo into Coolify. It auto-detects Python from `requirements.txt`.
- Set all environment variables in the Coolify service config.
- The first deploy seeds the `users` table (admin from env vars, demo with defaults).
- Database schema migrations run on startup (`CREATE TABLE IF NOT EXISTS`).

---

## Risks & Tradeoffs

- **JWT in localStorage vs httpOnly cookie** — **Stored in localStorage.** Tradeoff: localStorage is readable by JavaScript, so an XSS vulnerability could leak the token. However, httpOnly cookies require CSRF protection and complicate the vanilla JS frontend. For a public demo app with no PII and no financial transactions, the localStorage approach is the pragmatically correct choice. If this were a banking app, cookies + CSRF tokens would be required.
- **PostgreSQL vs SQLite** — **PostgreSQL.** Tradeoff: PostgreSQL requires an external service (or Coolify's managed PostgreSQL), adding a deployment dependency. In return, it handles concurrent reads and writes more robustly, uses standard SQL, and is the explicitly requested database. The existing SQLite data must be migrated once via `scripts/migrate_to_pg.py`.
- **Single index.html with view toggles vs separate login page** — **Single HTML with view toggles.** Tradeoff: the login screen HTML is sent to every visitor, including authenticated ones (though hidden by JS). This is consistent with how the app already toggles between home and list views. A separate login page would require server-side HTML serving or a second HTML file, adding complexity without meaningful benefit.
- **slowapi vs manual rate limiter** — **slowapi.** Tradeoff: slowapi adds one dependency (`slowapi` + `limits`). A manual rate limiter using a dict of `{ip: [timestamps]}` would be ~20 lines of code. slowapi is chosen because it handles edge cases (clock skew, memory cleanup of expired entries, `Retry-After` headers) that a manual implementation would eventually need. Cost of the dependency is low.
- **Admin seeding via env vars vs management CLI** — **Env vars.** Tradeoff: environment variables are the standard way to configure deployed services. A management CLI (`python scripts/create-admin.py`) would be more secure (password not in env) but requires shell access to the server. For a Coolify deployment, env vars are the path of least friction. After seeding, the admin can change their password via the in-app form — the env var is only used once at initial deploy.
- **In-app password change vs CLI-only** — **In-app form.** The admin can change their password via a modal in the dashboard (`PUT /api/auth/password`). This is a simple endpoint that verifies the current password and updates the hash. Demo users cannot change the shared demo password (would lock out other demo users).

---

## Resolved Decisions

All open questions from the concept are resolved:

- **Logout UX** — **Yes, there is a logout button.** It appears in the top bar for both admin and demo users. Clears `localStorage` (removes JWT), resets all in-memory state, and shows the login view. Implemented as a `logout()` function in `app.js`.
- **JWT expiry duration** — **24 hours for both admin and demo.** This balances security and UX. Demo tokens have zero privileges (view-only), so even if stolen, there is no damage — but 24h prevents indefinite persistence. Admin tokens carry write access, so a 24h window limits exposure without forcing daily re-logins. A refresh token infrastructure was considered but rejected as disproportionate overhead for a single-admin personal tool.
- **Admin password changes** — **In-app form, admin only.** A "Change Password" modal accessible from the dashboard (admin role only). Endpoint: `PUT /api/auth/password`. Accepts current password + new password. Verifies current password against bcrypt hash, updates if correct, returns 400 if wrong. Demo users cannot access this — the demo password is shared and configured via env vars only.
- **Deployment strategy** — **Coolify GitHub clone, no Dockerfile.** Coolify auto-detects Python from `requirements.txt`. PostgreSQL is provisioned separately (Coolify service or external). Env vars configured in Coolify's service settings.
- **Database** — **PostgreSQL.** Migration from the existing SQLite `data.db` is a one-time operation via `scripts/migrate_to_pg.py`.
