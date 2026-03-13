"""
migrate.py - Main migration orchestrator.

Usage:
    python migrate.py               # run all steps, commit each one
    python migrate.py --step 3      # start from step index 3 (0-based)
    python migrate.py --dry-run     # rollback every step instead of committing
    python migrate.py --step 2 --dry-run

=== PRODUCTION DEPLOYMENT (FULL LOAD) ===

Prerequisites:
  - PostgreSQL 16 running, user 'vpv' created with CREATEDB
  - MySQL accessible (remote or local)
  - migration/.env configured with MYSQL_* and PG_* credentials
  - backend/.env configured with PG_* vars + JWT + Telegram
  - migration/.venv installed (pip install -r requirements.txt)
  - backend/.venv installed (pip install -r requirements.txt)

Step 1: Create database
  sudo -u postgres psql -c "CREATE DATABASE ligavpv OWNER vpv;"

Step 2: Full migration (migration/.venv)
  cd migration/scripts && source ../.venv/bin/activate
  python migrate.py
  deactivate

Step 3: Post-migration scripts (migration/.venv — needs MySQL)
  cd ../../backend
  source ../migration/.venv/bin/activate
  python -m scripts.populate_ownership_log
  python -m scripts.fix_winter_draft_drops --apply
  cd ../migration/scripts
  python generate_draft_economy_seed.py --apply
  deactivate

Step 4: Backend scripts (backend/.venv — no MySQL needed)
  cd ../../backend && source .venv/bin/activate
  python -m scripts.backfill_weekly_payments

Step 5: Scraping for current season
  python -m src.features.scraping.cli update-calendar 8
  python -m src.features.scraping.cli download-photos 8
  deactivate

Step 6: Start services
  sudo systemctl start vpv-backend

Re-migration: drop database first, then repeat from Step 1
  sudo -u postgres psql -c "DROP DATABASE IF EXISTS ligavpv;"
"""

import argparse
import logging
import sys
import time
import warnings
from pathlib import Path
from types import ModuleType
from typing import Callable

import mysql.connector
import psycopg

from config import get_mysql_config, get_pg_conninfo
from context import MigrationContext

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema helpers (steps 00 and 01)
# ---------------------------------------------------------------------------

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


def _exec_sql_file(pg_conn: psycopg.Connection, sql_path: Path) -> None:
    """Read a .sql file and execute it against the PostgreSQL connection."""
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    log.info("Reading SQL file: %s", sql_path)
    sql = sql_path.read_text(encoding="utf-8")

    with pg_conn.cursor() as cur:
        cur.execute(sql)


def run_schema(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Step 00 - Execute 00_create_schema.sql against PostgreSQL."""
    _exec_sql_file(pg_conn, _SCHEMA_DIR / "00_create_schema.sql")


def run_seed(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Step 01 - Execute 01_seed_data.sql against PostgreSQL."""
    _exec_sql_file(pg_conn, _SCHEMA_DIR / "01_seed_data.sql")


def run_fix_stats_ok(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Post-scores - Recalculate stats_ok from actual player_stats data.

    MySQL est_ok may be unreliable.  This step sets matches.stats_ok = TRUE
    when a match has player_stats with played=TRUE, then propagates to
    matchdays when all counting matches are stats_ok.
    """
    logger = logging.getLogger(__name__)
    with pg_conn.cursor() as cur:
        # 1. matches.stats_ok based on real player_stats
        cur.execute("""
            UPDATE matches m
            SET stats_ok = TRUE
            WHERE m.stats_ok = FALSE
              AND EXISTS (
                  SELECT 1 FROM player_stats ps
                  WHERE ps.match_id = m.id AND ps.played = TRUE
              )
        """)
        logger.info("Marked %d match(es) as stats_ok from player_stats", cur.rowcount)

        # 2. matchdays.stats_ok when all counting matches are stats_ok
        cur.execute("""
            UPDATE matchdays md
            SET stats_ok = TRUE
            WHERE md.stats_ok = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM matches m
                  WHERE m.matchday_id = md.id
                    AND m.counts = TRUE
                    AND m.stats_ok = FALSE
              )
              AND EXISTS (
                  SELECT 1 FROM matches m
                  WHERE m.matchday_id = md.id
                    AND m.counts = TRUE
                    AND m.stats_ok = TRUE
              )
        """)
        logger.info("Marked %d matchday(s) as stats_ok", cur.rowcount)


def run_indexes(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Post-migration - Execute 03_add_indexes.sql for performance indexes."""
    _exec_sql_file(pg_conn, _SCHEMA_DIR / "03_add_indexes.sql")


def run_set_admin(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Post-migration - Set default admin user."""
    logger = logging.getLogger(__name__)
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET is_admin = TRUE WHERE username = 'carlos'"
        )
        logger.info("Set is_admin=TRUE for %d user(s)", cur.rowcount)


# ---------------------------------------------------------------------------
# Optional step module loader
# ---------------------------------------------------------------------------

def _try_import(module_name: str) -> ModuleType | None:
    """Import a step module by name, returning None if it is missing."""
    try:
        import importlib
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        warnings.warn(
            f"Step module '{module_name}' not found — step will be skipped.",
            stacklevel=2,
        )
        return None


# Attempt to import all step modules at startup so that missing ones are
# reported up-front rather than halfway through the migration.
_step_01_seasons    = _try_import("step_01_seasons")
_step_02_users      = _try_import("step_02_users")
_step_03_scoring    = _try_import("step_03_scoring")
_step_04_teams      = _try_import("step_04_teams")
_step_05_matchdays  = _try_import("step_05_matchdays")
_step_06_players    = _try_import("step_06_players")
_step_07_player_stats = _try_import("step_07_player_stats")
_step_08_lineups    = _try_import("step_08_lineups")
_step_09_scores     = _try_import("step_09_scores")
_step_10_validate   = _try_import("step_10_validate")


def _get_run(module: ModuleType | None) -> Callable | None:
    """Return the `run` callable from a module, or None if the module is absent."""
    if module is None:
        return None
    return getattr(module, "run", None)


# ---------------------------------------------------------------------------
# Step registry
# ---------------------------------------------------------------------------

# Each entry: (label, callable_or_None)
# None callables are produced when the module failed to import; they are
# skipped at runtime with a clear warning.
_ALL_STEPS: list[tuple[str, Callable | None]] = [
    ("00. Create schema",        run_schema),
    ("01. Seed data",            run_seed),
    ("02. Seasons",              _get_run(_step_01_seasons)),
    ("03. Users + Participants", _get_run(_step_02_users)),
    ("04. Scoring + Payments",   _get_run(_step_03_scoring)),
    ("05. Teams",                _get_run(_step_04_teams)),
    ("06. Matchdays + Matches",  _get_run(_step_05_matchdays)),
    ("07. Players",              _get_run(_step_06_players)),
    ("08. Player Stats",         _get_run(_step_07_player_stats)),
    ("09. Lineups",              _get_run(_step_08_lineups)),
    ("10. Scores",               _get_run(_step_09_scores)),
    ("11. Fix stats_ok",         run_fix_stats_ok),
    ("12. Validate",             _get_run(_step_10_validate)),
    ("13. Add indexes",          run_indexes),
    ("14. Set admin user",       run_set_admin),
]

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MySQL → PostgreSQL migration orchestrator."
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        metavar="N",
        help="Start from step index N (0-based, default: 0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Rollback each step instead of committing (nothing is persisted).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _row_counts(pg_conn: psycopg.Connection) -> dict[str, int]:
    """Return approximate row counts for every user table in the public schema."""
    query = """
        SELECT relname, n_live_tup
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY relname;
    """
    with pg_conn.cursor() as cur:
        cur.execute(query)
        return {row[0]: row[1] for row in cur.fetchall()}


def _log_counts(label: str, before: dict[str, int], after: dict[str, int]) -> None:
    """Log tables whose row count changed between before and after."""
    deltas = {
        tbl: after[tbl] - before.get(tbl, 0)
        for tbl in after
        if after[tbl] != before.get(tbl, 0)
    }
    if deltas:
        for tbl, delta in sorted(deltas.items()):
            log.info("  %-40s  +%d rows", tbl, delta)
    else:
        log.info("  (no row-count changes detected)")


def main() -> None:
    args = _parse_args()
    dry_run: bool = args.dry_run
    start_from: int = args.step

    if dry_run:
        log.info("DRY-RUN mode — all steps will be rolled back.")

    if start_from > 0:
        log.info("Starting from step index %d.", start_from)

    # ------------------------------------------------------------------
    # Connect to MySQL
    # ------------------------------------------------------------------
    log.info("Connecting to MySQL...")
    try:
        mysql_conn = mysql.connector.connect(**get_mysql_config())
    except mysql.connector.Error as exc:
        log.error("Could not connect to MySQL: %s", exc)
        sys.exit(1)

    mysql_conn.autocommit = False  # explicit transaction control

    # ------------------------------------------------------------------
    # Connect to PostgreSQL
    # ------------------------------------------------------------------
    log.info("Connecting to PostgreSQL...")
    try:
        pg_conn = psycopg.connect(get_pg_conninfo(), autocommit=False)
    except psycopg.Error as exc:
        log.error("Could not connect to PostgreSQL: %s", exc)
        mysql_conn.close()
        sys.exit(1)

    # ------------------------------------------------------------------
    # Run steps
    # ------------------------------------------------------------------
    ctx = MigrationContext()
    steps = _ALL_STEPS[start_from:]
    wall_start = time.perf_counter()

    try:
        for idx, (label, fn) in enumerate(steps, start=start_from):
            separator = "-" * 60
            log.info(separator)
            log.info("STEP %d: %s", idx, label)
            log.info(separator)

            if fn is None:
                log.warning("Step %d ('%s') has no implementation — skipping.", idx, label)
                continue

            counts_before = _row_counts(pg_conn)
            step_start = time.perf_counter()

            try:
                fn(mysql_conn, pg_conn, ctx)
            except Exception as exc:
                log.error("Step %d ('%s') FAILED: %s", idx, label, exc)
                log.info("Rolling back PostgreSQL transaction...")
                pg_conn.rollback()
                raise

            step_elapsed = time.perf_counter() - step_start
            # ANALYZE so pg_stat_user_tables reflects the inserts we just made
            with pg_conn.cursor() as _c:
                _c.execute("ANALYZE")
            counts_after = _row_counts(pg_conn)
            _log_counts(label, counts_before, counts_after)

            if dry_run:
                pg_conn.rollback()
                log.info("Step %d rolled back (dry-run). [%.2fs]", idx, step_elapsed)
            else:
                pg_conn.commit()
                log.info("Step %d committed. [%.2fs]", idx, step_elapsed)

    except Exception:
        # Error already logged inside the loop; just exit cleanly.
        sys.exit(1)
    finally:
        pg_conn.close()
        mysql_conn.close()
        log.info("Database connections closed.")

    total_elapsed = time.perf_counter() - wall_start
    log.info("=" * 60)
    if dry_run:
        log.info("DRY-RUN complete in %.2f seconds. No data was persisted.", total_elapsed)
    else:
        log.info("Migration complete in %.2f seconds.", total_elapsed)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
