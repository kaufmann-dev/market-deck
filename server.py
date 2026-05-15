"""
FastAPI backend serving MarketDeck static files and REST APIs.
"""
import os
import sys
import time as _time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd
import psycopg2
import psycopg2.errors
import psycopg2.pool
import yfinance as yf
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from seed_data import SEED_SETTINGS, SEED_TAG_COLORS, SEED_TICKERS, SEED_WATCHLISTS

APP_DIR = Path(__file__).resolve().parent
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 86400
DEMO_EMAIL_DEFAULT = "demo@marketdeck.app"
DEMO_PASSWORD_DEFAULT = "marketdeck"
REQUIRED_ENV = [
    "DATABASE_URL",
    "MARKETDECK_JWT_SECRET",
    "MARKETDECK_ADMIN_EMAIL",
    "MARKETDECK_ADMIN_PASSWORD",
]


def _validate_required_env():
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if not missing:
        return

    if "MARKETDECK_ADMIN_EMAIL" in missing or "MARKETDECK_ADMIN_PASSWORD" in missing:
        print(
            "ERROR: MARKETDECK_ADMIN_EMAIL and MARKETDECK_ADMIN_PASSWORD are required.\n"
            "Set these environment variables before starting the server.",
            file=sys.stderr,
        )
    else:
        print(
            "ERROR: DATABASE_URL and MARKETDECK_JWT_SECRET are required.\n"
            "Set these environment variables before starting the server.",
            file=sys.stderr,
        )
    raise SystemExit(1)


_validate_required_env()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=os.environ["DATABASE_URL"],
)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    print(f"rate limit exceeded: ip={get_remote_address(request)} endpoint={request.url.path}")
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Try again later."},
        headers={"Retry-After": "60"},
    )


@contextmanager
def get_db():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def dict_rows(cursor):
    return [dict(row) for row in cursor.fetchall()]


def dict_row(cursor):
    row = cursor.fetchone()
    return dict(row) if row else None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, os.environ["MARKETDECK_JWT_SECRET"], algorithm=JWT_ALGORITHM)


class CurrentUser(BaseModel):
    email: str
    role: str


def get_current_user(request: Request) -> CurrentUser:
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Not authenticated")

    try:
        payload = jwt.decode(token, os.environ["MARKETDECK_JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Token expired")

    email = payload.get("sub")
    role = payload.get("role")
    if not email or role not in ("admin", "demo"):
        raise HTTPException(401, "Token expired")
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT email, role FROM users WHERE email = %s", (email,))
        user = dict_row(cur)
    if not user or user["role"] != role:
        raise HTTPException(401, "Token expired")
    return CurrentUser(email=user["email"], role=user["role"])


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(403, "Read-only account. Write operations require admin privileges.")
    return current_user


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


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def _normalize_category(category: Optional[str]) -> str:
    cleaned = " ".join((category or "").split())
    return (cleaned or "Other").upper()


def _normalize_tag(tag: str) -> str:
    cleaned = " ".join(str(tag or "").split())
    return cleaned.upper()


def init_database():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'demo')),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlists (
                    id SERIAL PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    short_name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Other',
                    description TEXT NOT NULL DEFAULT '',
                    tag TEXT NOT NULL DEFAULT '',
                    currency TEXT NOT NULL DEFAULT 'USD',
                    show_type BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tickers (
                    id SERIAL PRIMARY KEY,
                    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    tag TEXT NOT NULL DEFAULT '',
                    currency TEXT NOT NULL DEFAULT 'USD',
                    sort_order INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_colors (
                    tag TEXT PRIMARY KEY,
                    bg TEXT NOT NULL,
                    text TEXT NOT NULL,
                    border TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickers_watchlist_id ON tickers(watchlist_id)"
            )
            conn.commit()

        seed_users(conn)
        seed_initial_data(conn)


def seed_users(conn):
    demo_email = os.environ.get("MARKETDECK_DEMO_EMAIL", DEMO_EMAIL_DEFAULT)
    demo_password = os.environ.get("MARKETDECK_DEMO_PASSWORD", DEMO_PASSWORD_DEFAULT)
    admin_email = os.environ["MARKETDECK_ADMIN_EMAIL"]
    admin_password = os.environ["MARKETDECK_ADMIN_PASSWORD"]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, 'demo')
            ON CONFLICT (email) DO NOTHING
            """,
            (demo_email, hash_password(demo_password)),
        )
        cur.execute(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, 'admin')
            ON CONFLICT (email) DO NOTHING
            """,
            (admin_email, hash_password(admin_password)),
        )
    conn.commit()


def seed_initial_data(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) AS count FROM watchlists")
        if cur.fetchone()["count"] > 0:
            return

        for key, value in SEED_SETTINGS.items():
            cur.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING
                """,
                (key, value),
            )

        watchlist_ids = {}
        for watchlist in SEED_WATCHLISTS:
            cur.execute(
                """
                INSERT INTO watchlists (slug, name, short_name, category, description, tag, currency, show_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO NOTHING
                RETURNING id
                """,
                (
                    watchlist["slug"],
                    watchlist["name"],
                    watchlist["short_name"],
                    _normalize_category(watchlist.get("category")),
                    watchlist.get("description", ""),
                    watchlist.get("tag", ""),
                    watchlist.get("currency", "USD"),
                    watchlist.get("show_type", True),
                ),
            )
            row = cur.fetchone()
            if row:
                watchlist_ids[watchlist["slug"]] = row["id"]

        sort_orders = {}
        for ticker in SEED_TICKERS:
            watchlist_id = watchlist_ids.get(ticker["watchlist_slug"])
            if watchlist_id is None:
                continue
            sort_order = sort_orders.get(ticker["watchlist_slug"], 0)
            sort_orders[ticker["watchlist_slug"]] = sort_order + 1
            cur.execute(
                """
                INSERT INTO tickers (watchlist_id, symbol, name, tag, currency, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    watchlist_id,
                    ticker["symbol"],
                    ticker["name"],
                    ticker.get("tag", ""),
                    ticker.get("currency", "USD"),
                    sort_order,
                ),
            )

        for tag, colors in SEED_TAG_COLORS.items():
            cur.execute(
                """
                INSERT INTO tag_colors (tag, bg, text, border)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tag) DO NOTHING
                """,
                (_normalize_tag(tag), colors["bg"], colors["text"], colors["border"]),
            )
    conn.commit()
    print("seed complete: initial MarketDeck data inserted")


init_database()


@app.get("/api/auth/demo-info")
def demo_info():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
    return {
        "email": os.environ.get("MARKETDECK_DEMO_EMAIL", DEMO_EMAIL_DEFAULT),
        "password": os.environ.get("MARKETDECK_DEMO_PASSWORD", DEMO_PASSWORD_DEFAULT),
    }


@app.post("/api/auth/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT email, password_hash, role FROM users WHERE email = %s", (body.email,))
        user = dict_row(cur)

    if not user or not verify_password(body.password, user["password_hash"]):
        print(f"failed login: email={body.email} ip={get_remote_address(request)}")
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token(user["email"], user["role"])
    return {"token": token, "email": user["email"], "role": user["role"]}


@app.get("/api/auth/me")
def me(current_user: CurrentUser = Depends(get_current_user)):
    return {"email": current_user.email, "role": current_user.role}


@app.put("/api/auth/password")
def change_password(
    body: PasswordChangeRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT password_hash FROM users WHERE email = %s", (current_user.email,))
        user = dict_row(cur)
        if not user or not verify_password(body.current_password, user["password_hash"]):
            raise HTTPException(400, "Current password is incorrect")
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE email = %s",
            (hash_password(body.new_password), current_user.email),
        )
        conn.commit()
    return {"ok": True}


@app.get("/api/init")
def api_init(current_user: CurrentUser = Depends(get_current_user)):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT key, value FROM settings")
        settings = {row["key"]: row["value"] for row in cur.fetchall()}

        cur.execute("SELECT tag, bg, text, border FROM tag_colors")
        tag_colors = {
            row["tag"]: {"bg": row["bg"], "text": row["text"], "border": row["border"]}
            for row in cur.fetchall()
        }

        cur.execute("SELECT * FROM watchlists ORDER BY id")
        watchlists = dict_rows(cur)
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

        cur.execute("SELECT * FROM tickers ORDER BY watchlist_id, sort_order")
        for ticker in cur.fetchall():
            slug = watchlist_slugs.get(ticker["watchlist_id"])
            if slug is None:
                continue
            lists[slug]["items"].append(
                {
                    "id": ticker["id"],
                    "ticker": ticker["symbol"],
                    "name": ticker["name"],
                    "tag": ticker["tag"],
                    "currency": ticker["currency"],
                }
            )

    return {"settings": settings, "tagColors": tag_colors, "lists": lists}


@app.get("/api/settings")
def get_settings(current_user: CurrentUser = Depends(get_current_user)):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in cur.fetchall()}


@app.put("/api/settings/{key}")
def update_setting(
    key: str,
    body: SettingUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, body.value),
        )
        conn.commit()
    return {"key": key, "value": body.value}


@app.post("/api/lists")
def create_list(
    body: WatchlistCreate,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            category = _normalize_category(body.category)
            cur.execute(
                """
                INSERT INTO watchlists (slug, name, short_name, category, description, tag, currency, show_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    body.slug,
                    body.name,
                    body.short_name,
                    category,
                    body.description,
                    body.tag,
                    body.currency,
                    body.show_type,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {"id": row["id"], "slug": body.slug}
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(400, f"Slug '{body.slug}' already exists")


@app.put("/api/lists/{slug}")
def update_list(
    slug: str,
    body: WatchlistUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM watchlists WHERE slug = %s", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "List not found")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        if "category" in updates:
            updates["category"] = _normalize_category(updates["category"])

        allowed_columns = {
            "name": "name",
            "short_name": "short_name",
            "category": "category",
            "description": "description",
            "tag": "tag",
            "currency": "currency",
            "show_type": "show_type",
        }
        set_clause = ", ".join(f"{allowed_columns[key]} = %s" for key in updates)
        vals = list(updates.values()) + [slug]
        cur.execute(f"UPDATE watchlists SET {set_clause} WHERE slug = %s", vals)
        conn.commit()
    return {"ok": True}


@app.delete("/api/lists/{slug}")
def delete_list(
    slug: str,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM watchlists WHERE slug = %s", (slug,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "List not found")
        cur.execute("DELETE FROM watchlists WHERE id = %s", (row["id"],))
        conn.commit()
    return {"ok": True}


@app.post("/api/lists/{slug}/tickers")
def add_ticker(
    slug: str,
    body: TickerCreate,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM watchlists WHERE slug = %s", (slug,))
        wl = cur.fetchone()
        if not wl:
            raise HTTPException(404, "List not found")
        cur.execute("SELECT COALESCE(MAX(sort_order), -1) AS max_order FROM tickers WHERE watchlist_id = %s", (wl["id"],))
        max_order = cur.fetchone()["max_order"]
        cur.execute(
            """
            INSERT INTO tickers (watchlist_id, symbol, name, tag, currency, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (wl["id"], body.symbol, body.name, body.tag, body.currency, max_order + 1),
        )
        row = cur.fetchone()
        conn.commit()
        return {"id": row["id"]}


@app.put("/api/tickers/{ticker_id}")
def update_ticker(
    ticker_id: int,
    body: TickerUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM tickers WHERE id = %s", (ticker_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Ticker not found")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")

        allowed_columns = {
            "symbol": "symbol",
            "name": "name",
            "tag": "tag",
            "currency": "currency",
        }
        set_clause = ", ".join(f"{allowed_columns[key]} = %s" for key in updates)
        vals = list(updates.values()) + [ticker_id]
        cur.execute(f"UPDATE tickers SET {set_clause} WHERE id = %s", vals)
        conn.commit()
    return {"ok": True}


@app.delete("/api/tickers/{ticker_id}")
def delete_ticker(
    ticker_id: int,
    current_user: CurrentUser = Depends(require_admin),
):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM tickers WHERE id = %s", (ticker_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Ticker not found")
        cur.execute("DELETE FROM tickers WHERE id = %s", (ticker_id,))
        conn.commit()
    return {"ok": True}


@app.put("/api/tag-colors/{tag}")
def update_tag_color(
    tag: str,
    body: TagColorUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    normalized_tag = _normalize_tag(tag)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tag_colors (tag, bg, text, border)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tag) DO UPDATE SET
                bg = EXCLUDED.bg,
                text = EXCLUDED.text,
                border = EXCLUDED.border
            """,
            (normalized_tag, body.bg, body.text, body.border),
        )
        conn.commit()
    return {"ok": True}


@app.delete("/api/tag-colors/{tag}")
def delete_tag_color(
    tag: str,
    current_user: CurrentUser = Depends(require_admin),
):
    normalized_tag = _normalize_tag(tag)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tag_colors WHERE tag = %s", (normalized_tag,))
        conn.commit()
    return {"ok": True}


CACHE_TTL = 300
_price_cache = {}


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
    result = {}
    if df.empty:
        return {t: None for t in tickers}

    if len(tickers) == 1:
        ticker = tickers[0]
        try:
            closes = _extract_close_series(df, ticker)
            points = []
            if closes is not None and hasattr(closes, "items"):
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
@limiter.limit("30/minute")
@limiter.limit("1/second")
def fetch_prices(
    request: Request,
    body: PricesRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    tickers = body.tickers
    if not tickers:
        return {}

    result = {}
    need_fetch = []
    for ticker in tickers:
        if _is_cached(ticker):
            result[ticker] = _get_cached(ticker)
        else:
            need_fetch.append(ticker)

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

            for ticker, data in fresh.items():
                result[ticker] = data
                _set_cached(ticker, data)
        except Exception as e:
            print(f"yfinance download error: {e}")
            for ticker in need_fetch:
                try:
                    data = _download_prices([ticker]).get(ticker)
                except Exception as retry_error:
                    print(f"yfinance fallback error for {ticker}: {retry_error}")
                    data = None
                result[ticker] = data
                _set_cached(ticker, data)

    for ticker in tickers:
        if ticker not in result:
            result[ticker] = None

    return result


@app.delete("/api/prices/cache")
def clear_price_cache(current_user: CurrentUser = Depends(require_admin)):
    _price_cache.clear()
    return {"ok": True}


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
    return FileResponse(APP_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting server at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
