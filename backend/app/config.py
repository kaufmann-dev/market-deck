"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 86400
DEMO_USER_ID = "__marketdeck_demo_user__"
DEMO_AUTH_DISABLED = "disabled"

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


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: str = Field(validation_alias="MARKETDECK_JWT_SECRET")
    admin_email: str = Field(validation_alias="MARKETDECK_ADMIN_EMAIL")
    admin_password: str = Field(validation_alias="MARKETDECK_ADMIN_PASSWORD")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
