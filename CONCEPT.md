# Concept: MarketDeck (Multi-User Auth + Demo)

## Problem Statement
MarketDeck is currently a local-only, single-user financial dashboard. It has no access controls, runs on localhost, and cannot be shared publicly without exposing full admin capabilities. Additionally, its Yahoo Finance price-fetching has no rate limiting, making it vulnerable to abuse if exposed to the open internet.

## Target Audience
Two distinct user groups:
- **Admin (you)**: Full access to all features — manage watchlists, tickers, tag colors, base currency, and all configuration.
- **Demo users (anyone on the internet)**: View-only access to the dashboard. They can browse watchlists, rankings, and heatmaps, and change temporary settings (like lookback period or base currency), but none of their changes are persisted. Their session modifications are ephemeral.

## Core Value Proposition
- **Public showcase**: Anyone can immediately explore the dashboard with a single click using credentials displayed right on the login screen — no sign-up friction.
- **Zero risk exposure**: Demo users cannot modify configurations, corrupt data, or affect the admin experience.
- **Admin control**: You retain full administrative power with the ability to add more admin accounts in the future.
- **Throttled by design**: Rate limiting protects the most expensive operation (Yahoo Finance API calls) from accidental or intentional abuse.

## Scope Boundaries

### In Scope (MVP)
- **Login screen** with demo credentials displayed prominently
- **Two account tiers**: admin (full access) and demo (view-only)
- **Single seeded admin account** with ability to add more later
- **Session-based authentication** (JWT or simple token approach)
- **Demo session isolation**: all changes (currency, lookback, filters) are ephemeral and not persisted to the database
- **Rate limiting** on price-fetching endpoints to protect Yahoo Finance API
- **Coolify deployment** packaging (Dockerfile or Compose config)
- **Backward compatibility**: existing SQLite schema and data survive the transition

### Out of Scope
- User registration UI (admin accounts are created via CLI or seed script only)
- OAuth / social login providers
- User roles beyond admin and demo (no "editor" or "viewer" tiers)
- Audit logging of demo user activity
- Multi-tenancy or per-user databases
- Password reset flows
- Email verification

## Success Criteria
1. A visitor can navigate to the deployed URL and see a login screen with demo credentials.
2. Clicking "Login as Demo" (or entering the displayed credentials) grants immediate access to the full read-only dashboard.
3. Demo users can switch watchlists, change periods, toggle rankings/heatmap, and filter by type — but cannot save, edit, delete, or create anything. Any "edit" buttons are hidden or disabled.
4. The admin can log in with their own credentials and see the familiar full-access experience (edit watchlists, tickers, tag colors, settings).
5. A single IP making more than 30 requests to `POST /api/prices` within 60 seconds receives a 429 Too Many Requests response. A burst of more than 1 request per second to the same endpoint also triggers a 429. Throttled requests never reach Yahoo Finance.
6. The app starts in a Coolify container with environment variables for the admin credentials.

## Key Decisions
- **Single login screen, two paths**: No separate registration flow. The demo credentials are always visible on the login screen, making the demo path frictionless.
- **Session-only for demo**: Demo user changes live entirely in-memory on the client (or in a server-side session). They never touch SQLite.
- **Rate limiting is endpoint-specific**: Only the price-fetching pipeline gets throttled, not general CRUD operations.
- **Admin accounts are additive**: The first admin is seeded, and more can be added via the database or a management command without requiring a UI for it.
- **Coolify packaging**: A Dockerfile wraps the existing Python/FastAPI app, with environment variables for configuration.

## Resolved Decisions

- **Session strategy**: Browser-side. Demo user changes live in `app.js` state only. The frontend simply skips all PATCH/PUT/DELETE API calls for demo sessions. No backend session store needed.
- **Demo user identifier**: A real "demo" user row in the database. This makes auth middleware simple — check the user's role on every request. The demo account is seeded with `role = "demo"`.
- **Rate limit thresholds**: Two-tier rate limiting on `POST /api/prices` only:
  - **30 requests per minute per IP** — covers even rapid browsing through all 5 watchlists multiple times within 60 seconds.
  - **1 request per second burst** — prevents rapid-fire hammering.
  
  These are based on the fact that each watchlist visit triggers exactly one batched `yf.download()` call (up to 99 tickers at once). Normal usage is 5–15 calls/minute; 30/min is generous headroom. Yahoo Finance has no published rate limit, but batch requests reduce external API pressure significantly.
