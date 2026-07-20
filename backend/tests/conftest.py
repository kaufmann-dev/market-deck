"""Shared fixtures: a real PostgreSQL (testcontainers, or TEST_DATABASE_URL),
the app under TestClient with lifespan (migrations + seed), and local sessions.

Environment must be configured before any `app.*` import, because Settings
is cached at first use.
"""
import os
from pathlib import Path

os.environ.setdefault("MARKETDECK_PUBLIC_URL", "https://testserver")
os.environ.setdefault("MARKETDECK_OIDC_ISSUER_URL", "https://idp.test/application/o/marketdeck")
os.environ.setdefault("MARKETDECK_OIDC_CLIENT_ID", "marketdeck-test")
os.environ.setdefault("MARKETDECK_OIDC_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault(
    "MARKETDECK_OIDC_STATE_SECRET",
    "test-state-secret-0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("MARKETDECK_DB_CONNECT_RETRIES", "3")
os.environ.setdefault("MARKETDECK_DB_CONNECT_RETRY_DELAY", "0.2")

# Let testcontainers talk to podman when no docker daemon is configured.
_PODMAN_SOCK = Path(f"/run/user/{os.getuid()}/podman/podman.sock")
if (
    "TEST_DATABASE_URL" not in os.environ
    and "DOCKER_HOST" not in os.environ
    and _PODMAN_SOCK.exists()
):
    os.environ["DOCKER_HOST"] = f"unix://{_PODMAN_SOCK}"
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

PUBLIC_URL = os.environ["MARKETDECK_PUBLIC_URL"]


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def client(database_url):
    os.environ["DATABASE_URL"] = database_url

    from app.config import get_settings

    get_settings.cache_clear()

    from app.db import dispose_engine
    from app.main import app

    dispose_engine()
    with TestClient(app, base_url=PUBLIC_URL) as test_client:
        yield test_client
    dispose_engine()


@pytest.fixture(autouse=True)
def clean_db(client):
    """Reset all tables to the freshly-seeded state before each test."""
    from app.db import session_factory
    from app.oidc import get_oidc_client
    from app.seed import run_seed
    from app.services import price_cache, yahoo_auth

    with session_factory()() as session:
        session.execute(
            text(
                "TRUNCATE auth_sessions, settings, watchlists, tickers, watchlist_tags, "
                "price_cache, yahoo_cache "
                "RESTART IDENTITY CASCADE"
            )
        )
        session.commit()
        run_seed(session)
    with price_cache._failure_cache_lock:
        price_cache._failure_cache.clear()
    yahoo_auth.invalidate()
    get_oidc_client.cache_clear()
    client.cookies.clear()
    yield


@pytest.fixture
def admin_headers(client) -> dict:
    from app.config import APP_SESSION_COOKIE
    from app.db import session_factory
    from app.security import create_auth_session

    with session_factory()() as session:
        raw_token = create_auth_session(
            session,
            role="admin",
            subject="oidc-admin-subject",
            display_name="admin@test.local",
            id_token="test-id-token",
        )
    return {
        "Cookie": f"{APP_SESSION_COOKIE}={raw_token}",
        "Origin": PUBLIC_URL,
    }


@pytest.fixture
def demo_headers(client) -> dict:
    from app.config import APP_SESSION_COOKIE
    from app.db import session_factory
    from app.security import create_auth_session

    with session_factory()() as session:
        raw_token = create_auth_session(session, role="demo")
    return {
        "Cookie": f"{APP_SESSION_COOKIE}={raw_token}",
        "Origin": PUBLIC_URL,
    }
