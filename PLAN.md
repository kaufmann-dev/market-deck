# Implementation Plan

## Overview
This plan implements MarketDeck's public demo and authenticated admin deployment, based on `CONCEPT.md`, `ARCHITECTURE.md`, and `DESIGN.md`. The work converts the existing local FastAPI and vanilla JS dashboard to a PostgreSQL-backed, JWT-authenticated app with admin/demo roles, demo read-only isolation, rate-limited price fetching, and Coolify-compatible startup. The plan contains 14 sequential tasks.

---

## Tasks

### Task 1: Runtime Setup and Project Scaffolding
**Description:** Add the Python runtime dependency manifest and startup conventions required by the architecture: FastAPI/Uvicorn, PostgreSQL, JWT/password hashing, slowapi, yfinance, pandas, and any existing runtime dependencies. This implements the architecture stack and Coolify GitHub clone deployment requirement.
**Files:** `requirements.txt`, `README.md`
**Dependencies:** None
**Acceptance Criteria:**
- `requirements.txt` exists and includes `fastapi`, `uvicorn`, `psycopg2-binary`, `python-jose`, `passlib[bcrypt]`, `slowapi`, `yfinance`, and `pandas`.
- `README.md` documents local startup with required environment variables: `DATABASE_URL`, `MARKETDECK_JWT_SECRET`, `MARKETDECK_ADMIN_EMAIL`, and `MARKETDECK_ADMIN_PASSWORD`.
- The documented production command matches the architecture: `uvicorn server:app --host 0.0.0.0 --port $PORT`.

---

### Task 2: Seed Data Module
**Description:** Replace runtime JSON bootstrapping with a `seed_data.py` module containing the initial watchlists, tickers, tag colors, and settings as structured Python data. This implements the architecture's auto-seed strategy while preserving the existing data currently stored in `data/lists.json` and `data/colors.json`.
**Files:** `seed_data.py`, `data/lists.json`, `data/colors.json`
**Dependencies:** Task 1
**Acceptance Criteria:**
- `seed_data.py` exports `SEED_WATCHLISTS`, `SEED_TICKERS`, `SEED_TAG_COLORS`, and `SEED_SETTINGS`.
- The seed data preserves every watchlist, ticker, tag color, and default setting needed by the current dashboard.
- Tickers reference watchlists by slug using `watchlist_slug`, as specified in `ARCHITECTURE.md`.
- The module can be imported without reading JSON files at runtime.

---

### Task 3: PostgreSQL Connection and Environment Validation
**Description:** Replace the SQLite connection helper with a psycopg2 threaded connection pool and fail-fast environment validation. This implements the architecture's PostgreSQL data layer and startup failure modes.
**Files:** `server.py`
**Dependencies:** Task 2
**Acceptance Criteria:**
- `server.py` validates `DATABASE_URL`, `MARKETDECK_JWT_SECRET`, `MARKETDECK_ADMIN_EMAIL`, and `MARKETDECK_ADMIN_PASSWORD` before serving requests.
- Missing required env vars print the exact clear startup error described in `ARCHITECTURE.md` and stop the process.
- `get_db()` uses a `psycopg2.pool.ThreadedConnectionPool` and returns connections to the pool after each request.
- SQLite-specific imports, `DB_PATH`, `sqlite3.Row`, and `PRAGMA foreign_keys` are removed from the active server path.

---

### Task 4: Startup Schema Creation and Idempotent Seeding
**Description:** Add startup initialization that creates all PostgreSQL tables and seeds users, settings, watchlists, tickers, and tag colors. This implements the architecture's users table, data model, and first-deploy seed strategy.
**Files:** `server.py`, `seed_data.py`
**Dependencies:** Task 3
**Acceptance Criteria:**
- Startup creates `users`, `settings`, `watchlists`, `tickers`, and `tag_colors` using `CREATE TABLE IF NOT EXISTS`.
- Startup always seeds the demo account from `MARKETDECK_DEMO_EMAIL` / `MARKETDECK_DEMO_PASSWORD` defaults and the admin account from required env vars using bcrypt hashes.
- Watchlist seed data is inserted only when `watchlists` is empty.
- Re-running startup does not duplicate users, watchlists, tickers, settings, or tag colors.
- PostgreSQL SQL syntax is used throughout: `%s` placeholders, `ON CONFLICT`, and `RETURNING id` where needed.

---

### Task 5: SQL Port of Existing Data APIs
**Description:** Convert existing settings, watchlist, ticker, tag-color, and init endpoints from SQLite SQL to PostgreSQL SQL while preserving response shapes used by the frontend. This implements the architecture's PostgreSQL migration for existing dashboard APIs.
**Files:** `server.py`
**Dependencies:** Task 4
**Acceptance Criteria:**
- `GET /api/init` returns the same JSON shape as before: `settings`, `tagColors`, and `lists`.
- Existing CRUD endpoint behavior is preserved for valid admin-style requests.
- SQLite-specific statements such as `INSERT OR REPLACE`, `INSERT OR IGNORE`, `?` placeholders, and `lastrowid` are no longer used.
- Boolean fields such as `show_type` are stored and returned correctly with PostgreSQL booleans.

---

### Task 6: Authentication API and JWT Helpers
**Description:** Add password verification, JWT creation/validation, current-user dependency, and auth endpoints. This implements the concept's single login screen and the architecture's auth router, auth middleware, JWT payload, and 24-hour expiry.
**Files:** `server.py`
**Dependencies:** Task 5
**Acceptance Criteria:**
- `POST /api/auth/login` accepts email/password, verifies bcrypt hash, and returns `token`, `email`, and `role`.
- `GET /api/auth/me` validates `Authorization: Bearer <JWT>` and returns the current email and role.
- `GET /api/auth/demo-info` returns the public demo credentials from environment/defaults.
- JWT payload includes `sub`, `role`, `iat`, and `exp`, with a 24-hour expiry.
- Invalid credentials return `401 {"detail": "Invalid email or password"}`.
- Missing, invalid, or expired tokens return 401 responses that the frontend can use to redirect to login.

---

### Task 7: Server-Side Authorization Guards
**Description:** Require authentication for all API endpoints except login and demo-info, and restrict write operations to admins. This implements the concept's two account tiers and the architecture's authorization guard.
**Files:** `server.py`
**Dependencies:** Task 6
**Acceptance Criteria:**
- `GET /api/init`, `GET /api/settings`, and `POST /api/prices` accept both admin and demo JWTs.
- Settings, watchlist, ticker, tag-color, price-cache clear, and password-change write operations require admin role.
- Demo writes return `403 {"detail": "Read-only account. Write operations require admin privileges."}`.
- The static catch-all route remains unauthenticated so the login page can load.
- Authorization is enforced server-side and does not rely on hidden frontend controls.

---

### Task 8: Rate Limiting
**Description:** Add slowapi middleware and endpoint-specific rate limits for login and price fetching. This implements the concept's Yahoo Finance abuse protection and the architecture's rate limiter.
**Files:** `server.py`, `requirements.txt`
**Dependencies:** Task 7
**Acceptance Criteria:**
- `POST /api/prices` is limited per IP to both `30/minute` and `1/second`.
- `POST /api/auth/login` is limited per IP to `5/minute`.
- A throttled price request returns 429 before `_download_prices()` or Yahoo Finance is reached.
- Rate-limit responses include a useful JSON detail and `Retry-After` behavior from slowapi.
- Other CRUD endpoints are not globally rate limited.

---

### Task 9: Login, Logout, and Session UI
**Description:** Add the unauthenticated login view, demo credential display, login-as-demo flow, logout control, and session restoration. This implements the concept's public showcase flow and the architecture's single `index.html` view-toggle approach.
**Files:** `index.html`, `static/app.js`, `static/styles.css`
**Dependencies:** Task 8
**Acceptance Criteria:**
- Visitors initially see a login screen with demo email and password displayed.
- Entering credentials or clicking "Login as Demo" stores the JWT in `localStorage` and shows the dashboard.
- On page load, an existing JWT is validated with `GET /api/auth/me`; valid sessions restore the dashboard and invalid sessions clear local storage and show login.
- Logout is available to both roles, clears the JWT and in-memory state, and returns to the login view.
- Login and logout styling follows `DESIGN.md`: dark terminal layout, rectangular controls, uppercase labels, no decorative imagery.

---

### Task 10: Authenticated Frontend API Client
**Description:** Update the frontend request helpers so API calls include the Bearer token, handle 401/403/429 errors consistently, and preserve existing data rendering. This implements the architecture's authenticated request flow and failure modes.
**Files:** `static/app.js`
**Dependencies:** Task 9
**Acceptance Criteria:**
- Every protected API call sends `Authorization: Bearer <token>`.
- A 401 response clears the saved token and returns the user to the login view.
- A 403 response displays a read-only/account permission message without corrupting local state.
- A 429 response displays a rate-limit message for price fetches.
- Existing dashboard navigation, rankings, heatmap, type filter, and price loading continue to work after login.

---

### Task 11: Demo Read-Only Frontend Behavior
**Description:** Add role-aware UI behavior so demo users can browse and change temporary view settings but cannot trigger persistent writes. This implements the concept's demo session isolation and the architecture's browser-side demo state decision.
**Files:** `static/app.js`, `index.html`, `static/styles.css`
**Dependencies:** Task 10
**Acceptance Criteria:**
- Demo users do not see or cannot use create/edit/delete controls for watchlists, tickers, tag colors, settings persistence, password changes, or cache clearing.
- Demo changes to base currency, lookback period, top-N, view mode, and type filter remain in `app.js` state only and are not sent as persistent writes.
- Refreshing or logging out of a demo session discards temporary demo changes.
- Admin users retain the familiar full-access editing experience.
- Server-side 403 protection still blocks direct demo write attempts even if a request is manually crafted.

---

### Task 12: Admin Password Change
**Description:** Add the admin-only password change endpoint and dashboard modal. This implements the architecture's resolved in-app password change decision.
**Files:** `server.py`, `index.html`, `static/app.js`, `static/styles.css`
**Dependencies:** Task 11
**Acceptance Criteria:**
- `PUT /api/auth/password` requires admin authentication.
- The endpoint verifies `current_password`, hashes `new_password`, updates the current admin user, and returns `{"ok": true}`.
- Wrong current password returns `400 {"detail": "Current password is incorrect"}`.
- Demo users cannot access the UI and receive 403 if they call the endpoint directly.
- After changing the password, the admin can log out and log back in with the new password.

---

### Task 13: Deployment and Health Documentation
**Description:** Align project documentation with the architecture's Coolify deployment model and remove conflicting deployment assumptions. This implements the concept's Coolify packaging requirement and the architecture's no-Dockerfile deployment decision.
**Files:** `README.md`
**Dependencies:** Task 12
**Acceptance Criteria:**
- Documentation states that deployment uses Coolify GitHub clone auto-detection, not Dockerfile or Docker Compose.
- Required Coolify environment variables and demo defaults are listed.
- Health check guidance uses `GET /api/auth/demo-info`.
- PostgreSQL is documented as a separate Coolify service connected through `DATABASE_URL`.
- The concept/architecture SQLite vs PostgreSQL conflict is called out as resolved in favor of `ARCHITECTURE.md`.

---

### Task 14: Integration Verification
**Description:** Verify the complete system end to end: startup, seeding, auth flows, role permissions, demo isolation, price rate limiting, and frontend rendering. This is the final task required by the planning rules and implements the success criteria from `CONCEPT.md`.
**Files:** `server.py`, `seed_data.py`, `index.html`, `static/app.js`, `static/styles.css`, `README.md`
**Dependencies:** Task 13
**Acceptance Criteria:**
- A fresh PostgreSQL database starts successfully, creates tables, and seeds admin, demo, watchlists, tickers, tag colors, and settings.
- `GET /api/auth/demo-info`, `POST /api/auth/login`, `GET /api/auth/me`, `GET /api/init`, and `POST /api/prices` work with expected auth behavior.
- Demo users can browse watchlists, rankings, heatmaps, filters, lookback periods, and temporary currency changes without persisting writes.
- Demo users receive 403 for direct write attempts to every admin-only endpoint.
- Admin users can create, edit, and delete watchlists, tickers, tag colors, settings, clear the price cache, and change their password.
- More than 30 `POST /api/prices` requests in 60 seconds from one IP returns 429, and more than 1 request per second also returns 429.
- The app renders correctly on desktop and mobile according to `DESIGN.md`, including login, dashboard, list, modal, and mobile navigation states.

---

## Future Work
- Admin account creation CLI or management command for adding additional admins after the seeded account.
- Password reset and email verification flows.
- httpOnly cookie auth with CSRF protection if the app grows beyond a personal dashboard.
- Structured logging and metrics beyond stdout/stderr.
- Persistent distributed rate-limit storage if the app is scaled beyond a single process.
- SQLite-to-PostgreSQL migration tooling, if preserving an existing production SQLite database becomes necessary.

## Risks
- **Concept and architecture database mismatch:** `CONCEPT.md` mentions SQLite backward compatibility, while `ARCHITECTURE.md` explicitly resolves the system to a clean PostgreSQL setup with no SQLite migration. Mitigation: implement PostgreSQL as the source of truth and document the decision in `README.md`.
- **JWT in localStorage:** XSS could expose tokens. Mitigation: keep token lifetime at 24 hours, avoid injecting unescaped HTML, and continue using the existing escaping helpers for user-controlled content.
- **slowapi in-memory limits:** Default in-memory rate limiting is per process and resets on restart. Mitigation: acceptable for MVP single-process Coolify deployment; move to shared storage only if scaling horizontally.
- **Yahoo Finance availability:** Price fetching can fail or slow down independently of MarketDeck. Mitigation: keep existing cache and failure behavior that returns `null` for failed tickers.
- **Seed data drift:** After first deploy, admin edits live in PostgreSQL and no longer track `seed_data.py`. Mitigation: treat `seed_data.py` as first-deploy defaults only and avoid reseeding populated tables.
