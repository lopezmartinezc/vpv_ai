"""Shared database configuration for migration and backend scripts.

Loads credentials from migration/.env (default) or migration/.env.sync.
All scripts that need MySQL + PostgreSQL should import from here.

Usage:
    from config import get_mysql_config, get_pg_conninfo

    # For incremental_sync (prefers .env.sync):
    from config import load_sync_env
    load_sync_env()  # call before get_mysql_config / get_pg_conninfo
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_MIGRATION_DIR = Path(__file__).resolve().parent.parent


def load_sync_env() -> None:
    """Load .env.sync if it exists, otherwise fall back to .env.

    Call this before get_mysql_config / get_pg_conninfo when running
    incremental sync (which may use different MySQL credentials).
    """
    sync_env = _MIGRATION_DIR / ".env.sync"
    default_env = _MIGRATION_DIR / ".env"
    load_dotenv(sync_env if sync_env.exists() else default_env, override=True)


# Default: load migration/.env on import
load_dotenv(_MIGRATION_DIR / ".env")


def get_mysql_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", ""),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "ligavpv"),
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def get_pg_conninfo() -> str:
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    user = os.getenv("PG_USER", "vpv")
    password = os.getenv("PG_PASSWORD", "")
    database = os.getenv("PG_DATABASE", "ligavpv")
    return f"host={host} port={port} user={user} password={password} dbname={database}"
