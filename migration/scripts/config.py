import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from migration/ directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def get_mysql_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3307")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "migration"),
        "database": os.getenv("MYSQL_DATABASE", "ligavpv"),
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def get_pg_conninfo() -> str:
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    user = os.getenv("PG_USER", "vpv")
    password = os.getenv("PG_PASSWORD", "vpv")
    database = os.getenv("PG_DATABASE", "ligavpv")
    return f"host={host} port={port} user={user} password={password} dbname={database}"
