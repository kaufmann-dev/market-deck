# Yahoo chart header failure cooldown

## Fix timestamp

2026-07-04 22:24:52 CEST (+0200)

## Current commit

e6f2268cd84fcc083aed584acd92b9916a62b729

## Symptom

The sector ETF watchlist loaded as `0/11 tickers loaded` with all 11 symbols failing: `XLY`, `XLP`, `XLE`, `XLF`, `XLV`, `XLI`, `XLB`, `XLK`, `XLU`, `XLRE`, and `XLC`.

## Confirmed root cause

The Yahoo chart path used the newer full browser-style `_HEADERS` that were added for broader stock data work. In the exact `download_prices(["XLY"])` service path, those headers caused the chart request to fail, while the old minimal chart header `{"User-Agent": "Mozilla/5.0"}` returned a valid 501-point series.

The metrics failure cooldown also treated every unsuccessful chart fetch as a known-bad ticker. That meant transient chart failures could suppress retries for valid symbols during the cooldown window, making a temporary request failure look like every ticker in a watchlist was invalid.

## Changes made

- Split chart requests onto `_CHART_HEADERS = {"User-Agent": "Mozilla/5.0"}`. A later stock-dashboard availability fix extended the same minimal header back to search, news, crumb, and quoteSummary requests after the fuller headers also proved incompatible with those Yahoo surfaces.
- Changed `download_prices` chart URLs from wall-clock `period1`/`period2` timestamps to Yahoo's relative `range=2y` query to avoid future-dated local clocks producing brittle requests.
- Added `PriceDownloadResult.permanent_failures` so `price_cache.record_fetch_results` only places unresolved 404 symbols into the cooldown when the Yahoo downloader can distinguish permanent failures from transient ones.
- Added a regression test asserting metrics chart requests use `range=2y` and do not send `period1` or `period2`.

## Verification

- `cd backend && ../.venv/bin/ruff check app tests`
- `cd backend && ../.venv/bin/python -m pytest tests/test_metrics_api.py`
- `cd backend && ../.venv/bin/python -m pytest`
- Live service probe through `app.services.yahoo.download_prices` returned `11/11` valid series for `XLY`, `XLP`, `XLE`, `XLF`, `XLV`, `XLI`, `XLB`, `XLK`, `XLU`, `XLRE`, and `XLC`.
