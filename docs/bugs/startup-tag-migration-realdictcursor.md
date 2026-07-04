# Startup Tag Migration RealDictCursor Crash

1. Fix timestamp: 2026-07-04 12:21:33 CEST (+0200)
2. Current commit before fix: 8443227d11e888dcda091930e3eb75ccb2597f21
3. Symptom: Application startup failed during `sync_watchlist_tags()` with `KeyError: 0` at `_table_exists(cur, "tag_colors")`.
4. Confirmed root cause: `_table_exists()` indexed `cur.fetchone()[0]`, but `sync_watchlist_tags()` passes a `RealDictCursor`, where rows are dictionaries instead of tuples.
5. Exact changes made: Updated `_table_exists()` and `_column_exists()` to read the first returned value from either tuple-shaped or dict-shaped cursor rows.
6. Verification: `python -m py_compile server.py seed_data.py` passed. A direct import-based helper check could not run locally because `psycopg2` is not installed in the shell environment.
