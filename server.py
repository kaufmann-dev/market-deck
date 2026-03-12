"""
server.py – FastAPI backend serving static files + REST API for watchlist CRUD
Run:  python server.py
"""
import sqlite3, os
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import yfinance as yf
import pandas as pd

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "data.db"

app = FastAPI()

# ── DB helper ──
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

# ══════════════════════════════════════
#  PYDANTIC MODELS
# ══════════════════════════════════════
class TickerCreate(BaseModel):
    symbol: str
    name: str
    tag: str = ""
    currency: str = "USD"

class TickerUpdate(BaseModel):
    symbol: Optional[str] = None
    name: Optional[str] = None
    tag: Optional[str] = None
    currency: Optional[str] = None

class WatchlistCreate(BaseModel):
    slug: str
    name: str
    short_name: str
    category: str = "Other"
    description: str = ""
    tag: str = ""
    currency: str = "USD"
    show_type: bool = True

class WatchlistUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    tag: Optional[str] = None
    currency: Optional[str] = None
    show_type: Optional[bool] = None

class SettingUpdate(BaseModel):
    value: str

class PricesRequest(BaseModel):
    tickers: List[str]

class TagColorUpdate(BaseModel):
    bg: str
    text: str
    border: str

def _normalize_category(category: Optional[str]) -> str:
    cleaned = " ".join((category or "").split())
    return (cleaned or "Other").upper()

def _normalize_tag(tag: str) -> str:
    cleaned = " ".join(str(tag or "").split())
    return cleaned.upper()

# ══════════════════════════════════════
#  API: INIT (single call to bootstrap frontend)
# ══════════════════════════════════════
@app.get("/api/init")
def api_init():
    with get_db() as conn:
        # settings
        settings = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM settings")
        }

        # tag colors
        tag_colors = {
            row["tag"]: {"bg": row["bg"], "text": row["text"], "border": row["border"]}
            for row in conn.execute("SELECT * FROM tag_colors")
        }

        watchlists = list(conn.execute("SELECT * FROM watchlists ORDER BY id"))
        lists = {
            wl["slug"]: {
                "id": wl["id"],
                "name": wl["name"],
                "shortName": wl["short_name"],
                "category": wl["category"],
                "description": wl["description"],
                "tag": wl["tag"],
                "currency": wl["currency"],
                "showType": bool(wl["show_type"]),
                "items": [],
            }
            for wl in watchlists
        }
        watchlist_slugs = {wl["id"]: wl["slug"] for wl in watchlists}

        # watchlists + tickers (same shape as the old lists.json)
        for t in conn.execute("SELECT * FROM tickers ORDER BY watchlist_id, sort_order"):
            slug = watchlist_slugs.get(t["watchlist_id"])
            if slug is None:
                continue
            lists[slug]["items"].append({
                "id": t["id"],
                "ticker": t["symbol"],
                "name": t["name"],
                "tag": t["tag"],
                "currency": t["currency"],
            })

    return {"settings": settings, "tagColors": tag_colors, "lists": lists}

# ══════════════════════════════════════
#  API: SETTINGS
# ══════════════════════════════════════
@app.get("/api/settings")
def get_settings():
    with get_db() as conn:
        return {row["key"]: row["value"] for row in conn.execute("SELECT * FROM settings")}

@app.put("/api/settings/{key}")
def update_setting(key: str, body: SettingUpdate):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, body.value))
        conn.commit()
    return {"key": key, "value": body.value}

# ══════════════════════════════════════
#  API: WATCHLISTS
# ══════════════════════════════════════
@app.post("/api/lists")
def create_list(body: WatchlistCreate):
    with get_db() as conn:
        try:
            category = _normalize_category(body.category)
            cur = conn.execute("""
                INSERT INTO watchlists (slug, name, short_name, category, description, tag, currency, show_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (body.slug, body.name, body.short_name, category, body.description, body.tag, body.currency, int(body.show_type)))
            conn.commit()
            return {"id": cur.lastrowid, "slug": body.slug}
        except sqlite3.IntegrityError:
            raise HTTPException(400, f"Slug '{body.slug}' already exists")

@app.put("/api/lists/{slug}")
def update_list(slug: str, body: WatchlistUpdate):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM watchlists WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, "List not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        if "category" in updates:
            updates["category"] = _normalize_category(updates["category"])
        # map short_name -> short_name column
        col_map = {"short_name": "short_name", "show_type": "show_type"}
        
        # Format boolean mappings to 1/0 for sqlite
        def _map_val(k, v):
            if k == "show_type": return int(v)
            return v
            
        set_clause = ", ".join(f"{col_map.get(k,k)}=?" for k in updates)
        vals = [_map_val(k, v) for k, v in updates.items()] + [slug]
        conn.execute(f"UPDATE watchlists SET {set_clause} WHERE slug=?", vals)
        conn.commit()
    return {"ok": True}

@app.delete("/api/lists/{slug}")
def delete_list(slug: str):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM watchlists WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, "List not found")
        conn.execute("DELETE FROM tickers WHERE watchlist_id=?", (row["id"],))
        conn.execute("DELETE FROM watchlists WHERE id=?", (row["id"],))
        conn.commit()
    return {"ok": True}

# ══════════════════════════════════════
#  API: TICKERS
# ══════════════════════════════════════
@app.post("/api/lists/{slug}/tickers")
def add_ticker(slug: str, body: TickerCreate):
    with get_db() as conn:
        wl = conn.execute("SELECT id FROM watchlists WHERE slug=?", (slug,)).fetchone()
        if not wl:
            raise HTTPException(404, "List not found")
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1) FROM tickers WHERE watchlist_id=?", (wl["id"],)).fetchone()[0]
        cur = conn.execute("""
            INSERT INTO tickers (watchlist_id, symbol, name, tag, currency, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (wl["id"], body.symbol, body.name, body.tag, body.currency, max_order + 1))
        conn.commit()
        return {"id": cur.lastrowid}

@app.put("/api/tickers/{ticker_id}")
def update_ticker(ticker_id: int, body: TickerUpdate):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM tickers WHERE id=?", (ticker_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Ticker not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        col_map = {"symbol": "symbol"}
        set_clause = ", ".join(f"{col_map.get(k,k)}=?" for k in updates)
        vals = list(updates.values()) + [ticker_id]
        conn.execute(f"UPDATE tickers SET {set_clause} WHERE id=?", vals)
        conn.commit()
    return {"ok": True}

@app.delete("/api/tickers/{ticker_id}")
def delete_ticker(ticker_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM tickers WHERE id=?", (ticker_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Ticker not found")
        conn.execute("DELETE FROM tickers WHERE id=?", (ticker_id,))
        conn.commit()
    return {"ok": True}

# ══════════════════════════════════════
#  API: TAG COLORS
# ══════════════════════════════════════
@app.put("/api/tag-colors/{tag}")
def update_tag_color(tag: str, body: TagColorUpdate):
    normalized_tag = _normalize_tag(tag)
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO tag_colors (tag, bg, text, border) VALUES (?, ?, ?, ?)",
                     (normalized_tag, body.bg, body.text, body.border))
        conn.commit()
    return {"ok": True}

@app.delete("/api/tag-colors/{tag}")
def delete_tag_color(tag: str):
    normalized_tag = _normalize_tag(tag)
    with get_db() as conn:
        conn.execute("DELETE FROM tag_colors WHERE tag=?", (normalized_tag,))
        conn.commit()
    return {"ok": True}

# ══════════════════════════════════════
#  API: PRICES (server-side yfinance fetch)
#  In-memory per-ticker cache with TTL
# ══════════════════════════════════════
import time as _time

CACHE_TTL = 300  # 5 minutes

# In-memory per-ticker result cache
_price_cache = {}  # { "AAPL": { "data": [...], "ts": 1234567890 } }

def _is_cacheable_series(data):
    return isinstance(data, list) and len(data) >= 2

def _is_cached(ticker):
    entry = _price_cache.get(ticker)
    if entry and not _is_cacheable_series(entry["data"]):
        _price_cache.pop(ticker, None)
        return False
    if entry and (_time.time() - entry["ts"]) < CACHE_TTL:
        return True
    return False

def _get_cached(ticker):
    return _price_cache[ticker]["data"]

def _set_cached(ticker, data):
    if not _is_cacheable_series(data):
        _price_cache.pop(ticker, None)
        return
    _price_cache[ticker] = {"data": data, "ts": _time.time()}

def _download_prices(tickers):
    if not tickers:
        return {}

    df = yf.download(
        tickers,
        period="14mo",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    return _parse_df(df, tickers)

def _extract_close_series(df, ticker):
    if isinstance(df, pd.Series):
        return df.dropna()

    if isinstance(df, pd.DataFrame):
        if isinstance(df.columns, pd.MultiIndex):
            for candidate in (("Close", ticker), (ticker, "Close")):
                if candidate in df.columns:
                    return df[candidate].dropna()

            for level in (0, -1):
                try:
                    closes = df.xs("Close", axis=1, level=level)
                except (KeyError, ValueError):
                    continue

                if isinstance(closes, pd.Series):
                    return closes.dropna()
                if ticker in closes.columns:
                    return closes[ticker].dropna()
                if closes.shape[1] == 1:
                    return closes.iloc[:, 0].dropna()

        if "Close" in df.columns:
            closes = df["Close"]
            if isinstance(closes, pd.DataFrame):
                if ticker in closes.columns:
                    return closes[ticker].dropna()
                if closes.shape[1] == 1:
                    return closes.iloc[:, 0].dropna()
            return closes.dropna()

    if hasattr(df, "Close"):
        closes = df.Close
        if isinstance(closes, pd.DataFrame):
            if ticker in closes.columns:
                return closes[ticker].dropna()
            if closes.shape[1] == 1:
                return closes.iloc[:, 0].dropna()
        return closes.dropna()

    return None

def _parse_df(df, tickers):
    """Parse a yfinance DataFrame into {ticker: [{date, close}, ...]}"""
    result = {}
    if df.empty:
        return {t: None for t in tickers}

    if len(tickers) == 1:
        ticker = tickers[0]
        try:
            closes = _extract_close_series(df, ticker)
            points = []
            if closes is not None and hasattr(closes, 'items'):
                for date, close in closes.items():
                    if pd.notna(close):
                        points.append({"date": date.strftime("%Y-%m-%d"), "close": round(float(close), 4)})
            
            result[ticker] = points if points else None
        except Exception as e:
            print(f"Error parsing single ticker {ticker}: {e}")
            result[ticker] = None
    else:
        for ticker in tickers:
            try:
                closes = _extract_close_series(df, ticker)
                if closes is None:
                    result[ticker] = None
                    continue
                points = []
                for date, close in closes.items():
                    if pd.notna(close):
                        points.append({"date": date.strftime("%Y-%m-%d"), "close": round(float(close), 4)})
                result[ticker] = points if points else None
            except Exception:
                result[ticker] = None
    return result

@app.post("/api/prices")
def fetch_prices(body: PricesRequest):
    tickers = body.tickers
    if not tickers:
        return {}

    result = {}

    # Check in-memory cache first — serve cached tickers instantly
    need_fetch = []
    for t in tickers:
        if _is_cached(t):
            result[t] = _get_cached(t)
        else:
            need_fetch.append(t)

    # Only download tickers not in cache
    if need_fetch:
        try:
            fresh = _download_prices(need_fetch)

            missing = [ticker for ticker, data in fresh.items() if data is None]
            for ticker in missing:
                try:
                    fresh[ticker] = _download_prices([ticker]).get(ticker)
                except Exception as retry_error:
                    print(f"yfinance retry error for {ticker}: {retry_error}")
                    fresh[ticker] = None

            for t, data in fresh.items():
                result[t] = data
                _set_cached(t, data)
        except Exception as e:
            print(f"yfinance download error: {e}")
            for t in need_fetch:
                try:
                    data = _download_prices([t]).get(t)
                except Exception as retry_error:
                    print(f"yfinance fallback error for {t}: {retry_error}")
                    data = None
                result[t] = data
                _set_cached(t, data)

    for t in tickers:
        if t not in result:
            result[t] = None

    return result

@app.delete("/api/prices/cache")
def clear_price_cache():
    global _price_cache
    _price_cache.clear()
    return {"ok": True}

# ══════════════════════════════════════
#  STATIC FILES (serve index.html + assets)
#  Using a catch-all route so API routes above take priority
# ══════════════════════════════════════
@app.get("/{path:path}")
def serve_static(path: str):
    if not path or path == "/":
        return FileResponse(APP_DIR / "index.html")

    try:
        file_path = (APP_DIR / path).resolve(strict=False)
        file_path.relative_to(APP_DIR)
    except ValueError:
        raise HTTPException(404, "Not found")

    if file_path.is_file():
        return FileResponse(file_path)
    # fallback to index.html for SPA-like behavior
    return FileResponse(APP_DIR / "index.html")

# ══════════════════════════════════════
#  RUN
# ══════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print(f"Starting server at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
