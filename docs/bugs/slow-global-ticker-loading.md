# Slow Global Ticker Loading

1. Fix timestamp: 2026-07-04 11:53:46 CEST (+0200)
2. Current commit before fix: 8d3c66363337f3e04686bb7488d5d6acc398dd7f
3. Symptom: Opening the global watchlist still showed `Loading 99 tickers + 12 FX rates...` for several seconds after the first threaded `yfinance` optimization.
4. Confirmed root cause: The backend still fetched all 111 symbols through `yfinance.download`, which builds a large OHLC dataframe and can hit yfinance cache contention. A local benchmark for the exact 111-symbol request took about 5.3s through `yfinance`; direct Yahoo chart JSON requests completed much faster.
5. Exact changes made: Replaced the `yfinance` dataframe fetch path with parallel Yahoo chart JSON requests, parsed adjusted close data directly, kept the PostgreSQL price cache and failure cooldown, removed unused `yfinance`/`pandas` dependencies, and updated project docs.
6. Verification: The implemented direct chart loader fetched the exact global list in 0.86s with 110/111 successful symbols. `ROG.SW` returned a Yahoo HTTP 404 and remains a failed ticker.
