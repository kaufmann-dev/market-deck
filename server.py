"""
FastAPI backend serving Market Deck static files and REST APIs.
"""
import json
import math
import os
import sys
import time as _time
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import List, Optional
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg2
import psycopg2.errors
import psycopg2.pool
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from psycopg2.extras import Json, RealDictCursor
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from seed_data import SEED_SETTINGS, SEED_TAG_COLORS, SEED_TICKERS, SEED_WATCHLISTS

APP_DIR = Path(__file__).resolve().parent
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 86400
DEMO_USER_ID = "__marketdeck_demo_user__"
DEMO_AUTH_DISABLED = "disabled"
REQUIRED_ENV = [
    "DATABASE_URL",
    "MARKETDECK_JWT_SECRET",
    "MARKETDECK_ADMIN_EMAIL",
    "MARKETDECK_ADMIN_PASSWORD",
]


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


DB_CONNECT_RETRIES = _int_env("MARKETDECK_DB_CONNECT_RETRIES", 30)
DB_CONNECT_RETRY_DELAY = _float_env("MARKETDECK_DB_CONNECT_RETRY_DELAY", 2)
PRICE_CACHE_TTL_SECONDS = _int_env("MARKETDECK_PRICE_CACHE_TTL_SECONDS", 3600)
PRICE_FETCH_MAX_WORKERS = 32
PRICE_FETCH_TIMEOUT_SECONDS = 5
PRICE_FETCH_TOTAL_TIMEOUT_SECONDS = 5
PRICE_FAILURE_COOLDOWN_SECONDS = 300
PRICE_HISTORY_DAYS = 430
YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_CHART_HEADERS = {"User-Agent": "Mozilla/5.0"}
_price_failure_cache = {}
_price_failure_cache_lock = Lock()


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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_pool = None

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
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def connect_database_pool():
    global _pool
    if _pool is not None:
        return

    _validate_required_env()
    last_error = None
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=os.environ["DATABASE_URL"],
            )
            print("database connection pool ready")
            return
        except psycopg2.OperationalError as exc:
            last_error = exc
            print(
                f"database connection attempt {attempt}/{DB_CONNECT_RETRIES} failed: {exc}",
                file=sys.stderr,
            )
            if attempt < DB_CONNECT_RETRIES:
                _time.sleep(DB_CONNECT_RETRY_DELAY)

    raise RuntimeError("Could not connect to PostgreSQL") from last_error


def close_database_pool():
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def dict_rows(cursor):
    return [dict(row) for row in cursor.fetchall()]


def dict_row(cursor):
    row = cursor.fetchone()
    return dict(row) if row else None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
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

    subject = payload.get("sub")
    role = payload.get("role")
    if not subject or role not in ("admin", "demo"):
        raise HTTPException(401, "Token expired")

    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if role == "demo":
            cur.execute("SELECT email, role FROM users WHERE role = 'demo' ORDER BY id LIMIT 1")
        else:
            cur.execute("SELECT email, role FROM users WHERE email = %s", (subject,))
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
    tag: str
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
    currency: str = "USD"
    show_tag: bool = True


class WatchlistUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    currency: Optional[str] = None
    show_tag: Optional[bool] = None


class SettingUpdate(BaseModel):
    value: str


class PricesRequest(BaseModel):
    tickers: List[str]


class TagUpdate(BaseModel):
    tag: Optional[str] = None
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


def _tag_color_defaults(tag: str) -> dict:
    normalized_tag = _normalize_tag(tag)
    seeded = {_normalize_tag(name): colors for name, colors in SEED_TAG_COLORS.items()}
    if normalized_tag == "GLOBAL":
        return {
            "bg": "rgba(99, 102, 241, .1)",
            "text": "#818cf8",
            "border": "rgba(99, 102, 241, .3)",
        }
    return seeded.get(normalized_tag, seeded["OTHER"])


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
        )
        """,
        (table, column),
    )
    row = cur.fetchone()
    return row[0] if not isinstance(row, dict) else next(iter(row.values()))


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (table,))
    row = cur.fetchone()
    value = row[0] if not isinstance(row, dict) else next(iter(row.values()))
    return value is not None


def _require_watchlist_tag(cur, watchlist_id: int, tag: str) -> str:
    normalized_tag = _normalize_tag(tag)
    if not normalized_tag:
        raise HTTPException(400, "Tag is required")
    cur.execute(
        "SELECT 1 FROM watchlist_tags WHERE watchlist_id = %s AND tag = %s",
        (watchlist_id, normalized_tag),
    )
    if not cur.fetchone():
        raise HTTPException(400, f"Tag '{normalized_tag}' is not defined for this list")
    return normalized_tag


def _get_watchlist_id(cur, slug: str) -> int:
    cur.execute("SELECT id FROM watchlists WHERE slug = %s", (slug,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "List not found")
    return row["id"]


def init_database():
    connect_database_pool()
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
                    currency TEXT NOT NULL DEFAULT 'USD',
                    show_tag BOOLEAN NOT NULL DEFAULT TRUE
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
                CREATE TABLE IF NOT EXISTS watchlist_tags (
                    id SERIAL PRIMARY KEY,
                    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
                    tag TEXT NOT NULL,
                    bg TEXT NOT NULL,
                    text TEXT NOT NULL,
                    border TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (watchlist_id, tag)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_cache (
                    account_email TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    data JSONB NOT NULL,
                    cached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (account_email, ticker)
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickers_watchlist_id ON tickers(watchlist_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_watchlist_tags_watchlist_id ON watchlist_tags(watchlist_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_cache_cached_at ON price_cache(cached_at)"
            )
            if _column_exists(cur, "watchlists", "show_type") and not _column_exists(cur, "watchlists", "show_tag"):
                cur.execute("ALTER TABLE watchlists RENAME COLUMN show_type TO show_tag")
            elif not _column_exists(cur, "watchlists", "show_tag"):
                cur.execute("ALTER TABLE watchlists ADD COLUMN show_tag BOOLEAN NOT NULL DEFAULT TRUE")
            if _column_exists(cur, "watchlists", "tag"):
                cur.execute("ALTER TABLE watchlists DROP COLUMN tag")
            conn.commit()

        seed_users(conn)
        seed_initial_data(conn)
        sync_watchlist_tags(conn)


def seed_users(conn):
    admin_email = os.environ["MARKETDECK_ADMIN_EMAIL"]
    admin_password = os.environ["MARKETDECK_ADMIN_PASSWORD"]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, 'demo')
            ON CONFLICT (email) DO NOTHING
            """,
            (DEMO_USER_ID, DEMO_AUTH_DISABLED),
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
                INSERT INTO watchlists (slug, name, short_name, category, description, currency, show_tag)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO NOTHING
                RETURNING id
                """,
                (
                    watchlist["slug"],
                    watchlist["name"],
                    watchlist["short_name"],
                    _normalize_category(watchlist.get("category")),
                    watchlist.get("description", ""),
                    watchlist.get("currency", "USD"),
                    watchlist.get("show_tag", True),
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
                    _normalize_tag(ticker.get("tag", "")),
                    ticker.get("currency", "USD"),
                    sort_order,
                ),
            )
    conn.commit()
    print("seed complete: initial Market Deck data inserted")


def sync_watchlist_tags(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        legacy_colors = {}
        if _table_exists(cur, "tag_colors"):
            cur.execute("SELECT tag, bg, text, border FROM tag_colors")
            legacy_colors = {
                _normalize_tag(row["tag"]): {
                    "bg": row["bg"],
                    "text": row["text"],
                    "border": row["border"],
                }
                for row in cur.fetchall()
            }

        cur.execute(
            """
            UPDATE tickers
            SET tag = UPPER(REGEXP_REPLACE(BTRIM(tag), '\\s+', ' ', 'g'))
            """
        )
        cur.execute("SELECT id FROM watchlists ORDER BY id")
        for watchlist in cur.fetchall():
            cur.execute(
                """
                SELECT tag, MIN(sort_order) AS first_sort, MIN(id) AS first_id
                FROM tickers
                WHERE watchlist_id = %s AND BTRIM(tag) <> ''
                GROUP BY tag
                ORDER BY first_sort, first_id
                """,
                (watchlist["id"],),
            )
            for sort_order, row in enumerate(cur.fetchall()):
                tag = _normalize_tag(row["tag"])
                colors = legacy_colors.get(tag) or _tag_color_defaults(tag)
                cur.execute(
                    """
                    INSERT INTO watchlist_tags (watchlist_id, tag, bg, text, border, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (watchlist_id, tag) DO NOTHING
                    """,
                    (
                        watchlist["id"],
                        tag,
                        colors["bg"],
                        colors["text"],
                        colors["border"],
                        sort_order,
                    ),
                )

        if _table_exists(cur, "tag_colors"):
            cur.execute("DROP TABLE tag_colors")
    conn.commit()


@app.on_event("startup")
def startup():
    init_database()


@app.on_event("shutdown")
def shutdown():
    close_database_pool()


@app.get("/api/auth/demo-info")
def demo_info():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
    return {"demoLogin": True}


@app.post("/api/auth/login")
def login(request: Request, body: LoginRequest):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT email, password_hash, role FROM users WHERE email = %s", (body.email,))
        user = dict_row(cur)

    if not user or user["role"] == "demo":
        print(f"failed login: email={body.email} ip={get_remote_address(request)}")
        raise HTTPException(401, "Invalid email or password")

    if not verify_password(body.password, user["password_hash"]):
        print(f"failed login: email={body.email} ip={get_remote_address(request)}")
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token(user["email"], user["role"])
    return {"token": token, "email": user["email"], "role": user["role"]}


@app.post("/api/auth/demo-login")
def demo_login(request: Request):
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT role FROM users WHERE role = 'demo' ORDER BY id LIMIT 1")
        user = dict_row(cur)

    if not user:
        print(f"failed demo login: demo user missing ip={get_remote_address(request)}")
        raise HTTPException(503, "Demo login is temporarily unavailable")

    token = create_access_token("demo", user["role"])
    return {"token": token, "role": user["role"]}


@app.get("/api/auth/me")
def me(current_user: CurrentUser = Depends(get_current_user)):
    if current_user.role == "demo":
        return {"role": current_user.role}
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

        cur.execute("SELECT * FROM watchlists ORDER BY id")
        watchlists = dict_rows(cur)
        lists = {
            wl["slug"]: {
                "id": wl["id"],
                "name": wl["name"],
                "shortName": wl["short_name"],
                "category": wl["category"],
                "description": wl["description"],
                "currency": wl["currency"],
                "showTag": bool(wl["show_tag"]),
                "tags": [],
                "items": [],
            }
            for wl in watchlists
        }
        watchlist_slugs = {wl["id"]: wl["slug"] for wl in watchlists}

        cur.execute(
            """
            SELECT watchlist_id, tag, bg, text, border, sort_order
            FROM watchlist_tags
            ORDER BY watchlist_id, sort_order, tag
            """
        )
        for tag in cur.fetchall():
            slug = watchlist_slugs.get(tag["watchlist_id"])
            if slug is None:
                continue
            lists[slug]["tags"].append(
                {
                    "tag": tag["tag"],
                    "bg": tag["bg"],
                    "text": tag["text"],
                    "border": tag["border"],
                    "sortOrder": tag["sort_order"],
                }
            )

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

    return {"settings": settings, "lists": lists}


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
                INSERT INTO watchlists (slug, name, short_name, category, description, currency, show_tag)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    body.slug,
                    body.name,
                    body.short_name,
                    category,
                    body.description,
                    body.currency,
                    body.show_tag,
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
            "currency": "currency",
            "show_tag": "show_tag",
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
        watchlist_id = _get_watchlist_id(cur, slug)
        tag = _require_watchlist_tag(cur, watchlist_id, body.tag)
        cur.execute("SELECT COALESCE(MAX(sort_order), -1) AS max_order FROM tickers WHERE watchlist_id = %s", (watchlist_id,))
        max_order = cur.fetchone()["max_order"]
        cur.execute(
            """
            INSERT INTO tickers (watchlist_id, symbol, name, tag, currency, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (watchlist_id, body.symbol, body.name, tag, body.currency, max_order + 1),
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
        cur.execute("SELECT id, watchlist_id FROM tickers WHERE id = %s", (ticker_id,))
        ticker = cur.fetchone()
        if not ticker:
            raise HTTPException(404, "Ticker not found")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        if "tag" in updates:
            updates["tag"] = _require_watchlist_tag(cur, ticker["watchlist_id"], updates["tag"])

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


@app.post("/api/lists/{slug}/tags")
def create_list_tag(
    slug: str,
    body: TagUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    normalized_tag = _normalize_tag(body.tag or "")
    if not normalized_tag:
        raise HTTPException(400, "Tag is required")
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        watchlist_id = _get_watchlist_id(cur, slug)
        try:
            cur.execute("SELECT COALESCE(MAX(sort_order), -1) AS max_order FROM watchlist_tags WHERE watchlist_id = %s", (watchlist_id,))
            sort_order = cur.fetchone()["max_order"] + 1
            cur.execute(
                """
                INSERT INTO watchlist_tags (watchlist_id, tag, bg, text, border, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (watchlist_id, normalized_tag, body.bg, body.text, body.border, sort_order),
            )
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(400, f"Tag '{normalized_tag}' already exists for this list")
    return {"tag": normalized_tag}


@app.put("/api/lists/{slug}/tags/{tag}")
def update_list_tag(
    slug: str,
    tag: str,
    body: TagUpdate,
    current_user: CurrentUser = Depends(require_admin),
):
    normalized_tag = _normalize_tag(tag)
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        watchlist_id = _get_watchlist_id(cur, slug)
        cur.execute(
            """
            UPDATE watchlist_tags
            SET bg = %s, text = %s, border = %s
            WHERE watchlist_id = %s AND tag = %s
            """,
            (body.bg, body.text, body.border, watchlist_id, normalized_tag),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Tag not found")
        conn.commit()
    return {"ok": True}


@app.delete("/api/lists/{slug}/tags/{tag}")
def delete_list_tag(
    slug: str,
    tag: str,
    current_user: CurrentUser = Depends(require_admin),
):
    normalized_tag = _normalize_tag(tag)
    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        watchlist_id = _get_watchlist_id(cur, slug)
        cur.execute(
            "SELECT COUNT(*) AS count FROM tickers WHERE watchlist_id = %s AND tag = %s",
            (watchlist_id, normalized_tag),
        )
        if cur.fetchone()["count"] > 0:
            raise HTTPException(400, "Cannot delete a tag while tickers use it")
        cur.execute(
            "DELETE FROM watchlist_tags WHERE watchlist_id = %s AND tag = %s",
            (watchlist_id, normalized_tag),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Tag not found")
        conn.commit()
    return {"ok": True}


def _is_cacheable_series(data):
    return isinstance(data, list) and len(data) >= 2


def _account_cache_key(current_user: CurrentUser) -> str:
    if current_user.role == "demo":
        return "demo"
    return current_user.email.strip().lower()


def _unique_tickers(tickers: List[str]) -> List[str]:
    seen = set()
    unique = []
    for ticker in tickers:
        cleaned = " ".join(str(ticker or "").split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def _get_cached_prices(account_email: str, tickers: List[str]):
    if not tickers:
        return {}

    with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            DELETE FROM price_cache
            WHERE cached_at < NOW() - (%s * INTERVAL '1 second')
            """,
            (PRICE_CACHE_TTL_SECONDS,),
        )
        cur.execute(
            """
            SELECT ticker, data
            FROM price_cache
            WHERE account_email = %s
              AND ticker = ANY(%s)
              AND cached_at >= NOW() - (%s * INTERVAL '1 second')
            """,
            (account_email, tickers, PRICE_CACHE_TTL_SECONDS),
        )
        rows = cur.fetchall()
        conn.commit()

    cached = {}
    for row in rows:
        data = row["data"]
        if _is_cacheable_series(data):
            cached[row["ticker"]] = data
    return cached


def _set_cached_prices(account_email: str, price_data):
    cacheable = {
        ticker: data
        for ticker, data in price_data.items()
        if _is_cacheable_series(data)
    }
    if not cacheable:
        return

    with get_db() as conn, conn.cursor() as cur:
        for ticker, data in cacheable.items():
            cur.execute(
                """
                INSERT INTO price_cache (account_email, ticker, data, cached_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (account_email, ticker) DO UPDATE SET
                    data = EXCLUDED.data,
                    cached_at = EXCLUDED.cached_at
                """,
                (account_email, ticker, Json(data)),
            )
        conn.commit()


def _recent_failed_tickers(tickers):
    now = _time.monotonic()
    recent = []
    with _price_failure_cache_lock:
        for ticker in tickers:
            failed_at = _price_failure_cache.get(ticker)
            if failed_at is None:
                continue
            if now - failed_at < PRICE_FAILURE_COOLDOWN_SECONDS:
                recent.append(ticker)
            else:
                _price_failure_cache.pop(ticker, None)
    return recent


def _record_price_fetch_results(price_data):
    now = _time.monotonic()
    with _price_failure_cache_lock:
        for ticker, data in price_data.items():
            if _is_cacheable_series(data):
                _price_failure_cache.pop(ticker, None)
            else:
                _price_failure_cache[ticker] = now


def _chart_timezone(meta):
    timezone_name = (meta or {}).get("exchangeTimezoneName") or (meta or {}).get("timezone")
    if not timezone_name:
        return timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _chart_closes(indicators):
    if not isinstance(indicators, dict):
        return []

    adjclose = indicators.get("adjclose") or []
    if adjclose:
        closes = adjclose[0].get("adjclose") if isinstance(adjclose[0], dict) else None
        if closes and any(close is not None for close in closes):
            return closes

    quote_data = indicators.get("quote") or []
    if quote_data:
        closes = quote_data[0].get("close") if isinstance(quote_data[0], dict) else None
        if closes and any(close is not None for close in closes):
            return closes
    return []


def _parse_chart_payload(payload):
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict) or chart.get("error"):
        return None

    results = chart.get("result") or []
    if not results or not isinstance(results[0], dict):
        return None

    result = results[0]
    timestamps = result.get("timestamp") or []
    closes = _chart_closes(result.get("indicators"))
    if not timestamps or not closes:
        return None

    tz = _chart_timezone(result.get("meta"))
    points = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        try:
            close_value = float(close)
            timestamp_value = int(timestamp)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close_value):
            continue
        date = datetime.fromtimestamp(timestamp_value, tz).date().isoformat()
        points.append({"date": date, "close": round(close_value, 4)})
    return points if len(points) >= 2 else None


def _chart_url(ticker, period1, period2):
    encoded_ticker = quote(ticker, safe="")
    return (
        f"{YAHOO_CHART_BASE_URL}/{encoded_ticker}"
        f"?period1={period1}&period2={period2}"
        "&interval=1d&events=history&includeAdjustedClose=true"
    )


def _fetch_chart_prices(ticker, period1, period2):
    request = UrlRequest(_chart_url(ticker, period1, period2), headers=YAHOO_CHART_HEADERS)
    with urlopen(request, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read())
    return _parse_chart_payload(payload)


def _download_prices(tickers):
    if not tickers:
        return {}

    now = datetime.now(timezone.utc)
    period1 = int((now - timedelta(days=PRICE_HISTORY_DAYS)).timestamp())
    period2 = int(now.timestamp())
    result = {ticker: None for ticker in tickers}
    executor = ThreadPoolExecutor(max_workers=min(PRICE_FETCH_MAX_WORKERS, len(tickers)))
    futures = {
        executor.submit(_fetch_chart_prices, ticker, period1, period2): ticker
        for ticker in tickers
    }

    try:
        done, not_done = wait(futures, timeout=PRICE_FETCH_TOTAL_TIMEOUT_SECONDS)
        for future in not_done:
            future.cancel()

        failures = []
        for future in done:
            ticker = futures[future]
            try:
                result[ticker] = future.result()
            except Exception as exc:
                failures.append(f"{ticker}: {type(exc).__name__}")
                result[ticker] = None
        if failures:
            print(f"Yahoo chart failures ({len(failures)}): {', '.join(failures[:8])}")
        if not_done:
            print(f"Yahoo chart timed out for {len(not_done)} tickers")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return result


@app.post("/api/prices")
@limiter.limit("120/minute")
def fetch_prices(
    request: Request,
    body: PricesRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    started_at = _time.monotonic()
    tickers = _unique_tickers(body.tickers)
    if not tickers:
        return {}

    account_email = _account_cache_key(current_user)
    result = _get_cached_prices(account_email, tickers)
    cache_hits = len(result)
    uncached = [ticker for ticker in tickers if ticker not in result]
    recent_failures = set(_recent_failed_tickers(uncached))
    for ticker in recent_failures:
        result[ticker] = None
    need_fetch = [ticker for ticker in uncached if ticker not in recent_failures]

    if need_fetch:
        fresh = _download_prices(need_fetch)
        _record_price_fetch_results(fresh)
        for ticker, data in fresh.items():
            result[ticker] = data
        _set_cached_prices(account_email, fresh)

    for ticker in tickers:
        if ticker not in result:
            result[ticker] = None

    elapsed = _time.monotonic() - started_at
    print(
        "price fetch "
        f"requested={len(tickers)} cache_hits={cache_hits} "
        f"recent_failures={len(recent_failures)} yahoo_chart_fetch={len(need_fetch)} "
        f"elapsed={elapsed:.2f}s"
    )
    return result


@app.delete("/api/prices/cache")
def clear_price_cache(current_user: CurrentUser = Depends(require_admin)):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM price_cache")
        deleted = cur.rowcount
        conn.commit()
    with _price_failure_cache_lock:
        _price_failure_cache.clear()
    return {"ok": True, "deleted": deleted}


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

    port = _int_env("PORT", 8000)
    print(f"Starting server at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
