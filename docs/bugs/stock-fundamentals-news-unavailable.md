# Stock fundamentals and news unavailable

## Fix timestamp

2026-07-04 22:34:29 CEST (+0200)

## Current commit

f6f76275e6cb1b092a50be6938f73fc66f6e78c6

## Symptom

The single-stock dashboard chart loaded for `META`, but the page showed fundamentals unavailable, empty overview values, no news, and empty analyst data.

## Confirmed root cause

The stock dashboard reused the full browser-style Yahoo headers for search, news, crumb, and quoteSummary calls. Live checks showed those exact requests returned rate-limit responses with the full headers, while the minimal `{"User-Agent": "Mozilla/5.0"}` header returned valid data:

- `GET /v1/finance/search?q=META` returned quotes and news.
- `GET /v1/test/getcrumb` returned a crumb.
- `GET /v10/finance/quoteSummary/META` returned profile, statistics, financial data, calendar, recommendation, earnings, and earnings trend modules.

The stock routes also cached empty search/news fallback payloads. Once the bad header path wrote `{"news": []}` or empty search results into `yahoo_cache`, the UI could remain empty until the cache TTL expired even after Yahoo became reachable again.

## Changes made

- Restored the Yahoo service headers to the minimal `{"User-Agent": "Mozilla/5.0"}` header for search, news, crumb, quoteSummary, and chart calls.
- Changed `search_symbols()` and `fetch_news()` to return `None` on upstream failure so API routes can degrade gracefully without caching failure fallbacks.
- Updated `/api/search` and `/api/stocks/{symbol}/news` to bypass empty cached payloads and refetch, which clears already-stale empty cache entries naturally on the next request.
- Added stock API regression tests for upstream search/news failures and stale empty search/news responses.

## Verification

- `cd backend && ../.venv/bin/ruff check app tests`
- `cd backend && ../.venv/bin/python -m pytest tests/test_stocks_api.py`
- `cd backend && ../.venv/bin/python -m pytest`
- Live service probe for `META` returned 7 search quotes, 4 search news items, 10 stock news items, and quoteSummary modules including `summaryProfile`, `defaultKeyStatistics`, `financialData`, and `recommendationTrend`.
