"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

APP_SESSION_COOKIE = "marketdeck_session"
OIDC_FLOW_COOKIE = "marketdeck_oidc_flow"
SESSION_IDLE_SECONDS = 24 * 60 * 60
SESSION_ABSOLUTE_SECONDS = 7 * 24 * 60 * 60

PRICE_FETCH_MAX_WORKERS = 32
PRICE_FETCH_TIMEOUT_SECONDS = 5
PRICE_FETCH_TOTAL_TIMEOUT_SECONDS = 5
PRICE_FAILURE_COOLDOWN_SECONDS = 300
PRICE_HISTORY_DAYS = 430
YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
YAHOO_QUOTE_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"
YAHOO_FUNDAMENTALS_TIMESERIES_URL = (
    "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries"
)
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_COOKIE_URL = "https://fc.yahoo.com/"

LOCAL_HTTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _normalize_http_url(name: str, value: str, *, origin_only: bool) -> str:
    normalized = value.rstrip("/")
    try:
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
        _ = parsed.port  # Validate a present port while preserving it in the normalized value.
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid absolute HTTP(S) URL") from exc

    if parsed.scheme not in ("http", "https") or not parsed.netloc or not hostname:
        raise ValueError(f"{name} must be a valid absolute HTTP(S) URL")
    if (
        parsed.username
        or parsed.password
        or "@" in parsed.netloc
        or "?" in normalized
        or "#" in normalized
        or "\\" in normalized
    ):
        raise ValueError(f"{name} must not contain credentials, a query, or a fragment")
    if parsed.scheme == "http" and hostname not in LOCAL_HTTP_HOSTS:
        raise ValueError(
            f"{name} must use HTTPS unless its host is localhost, 127.0.0.1, or ::1"
        )
    if origin_only and parsed.path:
        raise ValueError(f"{name} must be an origin without a path")
    return parsed.geturl()


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    public_url: str = Field(validation_alias="MARKETDECK_PUBLIC_URL")
    oidc_issuer_url: str = Field(validation_alias="MARKETDECK_OIDC_ISSUER_URL")
    oidc_client_id: str = Field(min_length=1, validation_alias="MARKETDECK_OIDC_CLIENT_ID")
    oidc_client_secret: SecretStr = Field(
        min_length=1, validation_alias="MARKETDECK_OIDC_CLIENT_SECRET"
    )
    oidc_state_secret: SecretStr = Field(
        min_length=32, validation_alias="MARKETDECK_OIDC_STATE_SECRET"
    )

    db_connect_retries: int = Field(default=30, validation_alias="MARKETDECK_DB_CONNECT_RETRIES")
    db_connect_retry_delay: float = Field(default=2.0, validation_alias="MARKETDECK_DB_CONNECT_RETRY_DELAY")
    price_cache_ttl_seconds: int = Field(default=3600, validation_alias="MARKETDECK_PRICE_CACHE_TTL_SECONDS")
    stock_chart_cache_ttl_seconds: int = Field(
        default=900, validation_alias="MARKETDECK_STOCK_CHART_CACHE_TTL_SECONDS"
    )
    fundamentals_cache_ttl_seconds: int = Field(
        default=21600, validation_alias="MARKETDECK_FUNDAMENTALS_CACHE_TTL_SECONDS"
    )
    news_cache_ttl_seconds: int = Field(default=900, validation_alias="MARKETDECK_NEWS_CACHE_TTL_SECONDS")
    search_cache_ttl_seconds: int = Field(
        default=3600, validation_alias="MARKETDECK_SEARCH_CACHE_TTL_SECONDS"
    )
    static_dir: Path = Field(
        default=REPO_ROOT / "frontend" / "dist", validation_alias="MARKETDECK_STATIC_DIR"
    )
    port: int = Field(default=8000, validation_alias="PORT")

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Coolify hands out postgres:// / postgresql:// URLs; SQLAlchemy needs the driver suffix.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg2://" + value[len(prefix):]
        return value

    @field_validator("public_url")
    @classmethod
    def _normalize_public_url(cls, value: str) -> str:
        return _normalize_http_url("MARKETDECK_PUBLIC_URL", value, origin_only=True)

    @field_validator("oidc_issuer_url")
    @classmethod
    def _normalize_oidc_issuer_url(cls, value: str) -> str:
        return _normalize_http_url("MARKETDECK_OIDC_ISSUER_URL", value, origin_only=False)

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
