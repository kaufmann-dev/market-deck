# Market Deck

Market Deck is a local dashboard for ranking financial assets by momentum and viewing trailing monthly returns in a heatmap. It supports multiple watchlists, server-side Yahoo Finance price loading, historical FX conversion into a shared base currency, and inline editing backed by SQLite.

## Features

- Momentum rankings for 1M, 3M, 6M, and 12M lookbacks
- Monthly heatmap with a trailing 12M return column
- Multiple editable watchlists with per-ticker tags and currencies
- Global base currency conversion using historical FX series from Yahoo Finance
- Built-in CRUD UI for watchlists, tickers, and tag colors
- Server-side price fetching with caching and safer request handling
- Watchlist categories are grouped case-insensitively in the sidebar

## Stack

- Frontend: vanilla HTML, CSS, and JavaScript
- Backend: FastAPI + Uvicorn
- Database: SQLite (`data.db`)
- Market data: Yahoo Finance via `yfinance`

## Project Structure

```text
.
|-- index.html
|-- server.py
|-- static/
|   |-- app.js
|   `-- styles.css
|-- scripts/
|   |-- get_volumes.py
|   `-- migrate.py
`-- data/
    |-- colors.json
    |-- lists.json
    `-- volumes.json
```

`data.db` is generated locally and is ignored by git.

## Setup

1. Install Python 3.10+.
2. Install dependencies:

```bash
pip install fastapi uvicorn pydantic yfinance pandas
```

3. If you do not already have `data.db`, create it from the legacy JSON files:

```bash
python scripts/migrate.py
```

4. Start the server:

```bash
python server.py
```

5. Open [http://localhost:8000](http://localhost:8000).

## Utilities

### Rebuild the database

```bash
python scripts/migrate.py
```

This recreates `data.db` from `data/lists.json` and `data/colors.json`.

Warning: running it again destroys existing UI edits stored in the database.

### Refresh cached volume data

```bash
python scripts/get_volumes.py
```

This reads `data/lists.json` and writes `data/volumes.json`.

## API

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

## Notes

- The app serves local files through a guarded catch-all route and rejects path traversal attempts.
- The frontend now keeps list loads alive in the background when you switch views quickly, so returning to a still-loading list reuses the existing request instead of restarting it.
- The server retries tickers that come back missing from a batch Yahoo Finance response, which helps reduce partial list loads.
- Price and CRUD requests now surface HTTP errors instead of silently acting like they succeeded.
