"""Idempotent migration runner.

Handles three database states:
1. Alembic-managed (alembic_version exists)  -> upgrade to head.
2. Legacy pre-Alembic schema (watchlists exists, no alembic_version)
   -> stamp 0001 (the baseline matching that schema), then upgrade.
3. Fresh/empty database -> run all migrations.
"""
import logging

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command

from .config import BACKEND_DIR
from .db import get_engine, wait_for_db
from .log import setup_logging

logger = logging.getLogger(__name__)

BASELINE_REVISION = "0001"


def _alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def run_migrations() -> None:
    wait_for_db()
    inspector = inspect(get_engine())
    has_version_table = inspector.has_table("alembic_version")
    has_legacy_schema = inspector.has_table("watchlists")

    cfg = _alembic_config()
    if not has_version_table and has_legacy_schema:
        logger.info("adopting legacy schema: stamping baseline revision %s", BASELINE_REVISION)
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
    logger.info("database schema is up to date")


if __name__ == "__main__":
    setup_logging()
    run_migrations()
