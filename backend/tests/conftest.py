"""Shared fixtures: a real PostgreSQL (testcontainers, or TEST_DATABASE_URL),
the app under TestClient with lifespan (migrations + seed), and auth tokens.

Environment must be configured before any `app.*` import, because Settings
is cached at first use.
"""
import os
from pathlib import Path

os.environ.setdefault("MARKETDECK_JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")
os.environ.setdefault("MARKETDECK_ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("MARKETDECK_ADMIN_PASSWORD", "admin-password")
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
from fastapi.testclient import TestClient
from sqlalchemy import text

ADMIN_EMAIL = os.environ["MARKETDECK_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["MARKETDECK_ADMIN_PASSWORD"]


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
    with TestClient(app) as test_client:
        yield test_client
    dispose_engine()


@pytest.fixture(autouse=True)
def clean_db(client):
    """Reset all tables to the freshly-seeded state before each test."""
    from app.db import session_factory
    from app.seed import run_seed
    from app.services import price_cache

    with session_factory()() as session:
        session.execute(
            text(
                "TRUNCATE users, settings, watchlists, tickers, watchlist_tags, price_cache "
                "RESTART IDENTITY CASCADE"
            )
        )
        session.commit()
        run_seed(session)
    with price_cache._failure_cache_lock:
        price_cache._failure_cache.clear()
    yield


@pytest.fixture
def admin_token(client) -> str:
    response = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


@pytest.fixture
def demo_token(client) -> str:
    response = client.post("/api/auth/demo-login")
    assert response.status_code == 200, response.text
    return response.json()["token"]


@pytest.fixture
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def demo_headers(demo_token) -> dict:
    return {"Authorization": f"Bearer {demo_token}"}
