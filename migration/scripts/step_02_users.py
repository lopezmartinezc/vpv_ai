"""
step_02_users.py - Migrate usuarios_temp -> users + season_participants.

MySQL source table: usuarios_temp
    id        SMALLINT     AUTO_INCREMENT  (SLOT number, NOT a person ID)
    temporada VARCHAR(15)
    nombre    VARCHAR(100)
    pass      VARCHAR(150) NULLABLE

CRITICAL: The `id` column is a slot number that was reassigned between seasons
(notably in 2022-2023). Deduplication is done by `nombre` (display name), which
is unique within this small friend group across all seasons.

Algorithm:
1. Query all rows ordered by temporada DESC, id (most recent season first, so
   the first password encountered for each person is the most recent one).
2. Deduplicate by nombre.strip() into a dict of PersonInfo objects.
3. For each unique person:
   - Derive username: lowercase, spaces/dots -> hyphens, strip trailing hyphens.
   - Hash the username as the initial password with bcrypt.
   - INSERT INTO users RETURNING id.
4. For each (temporada, slot_id) of that person:
   - Resolve season_id from ctx.season_map.
   - INSERT INTO season_participants RETURNING id.
   - Store ctx.participant_map[(temporada, slot_id)] = participant_id.
5. Print a verification summary table.

After this step ctx.participant_map is fully populated.
"""

import logging
import re
from dataclasses import dataclass, field

import bcrypt
import mysql.connector
import psycopg

from context import MigrationContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@dataclass
class _PersonInfo:
    display_name: str
    password_hash: str | None  # raw hash from MySQL (kept for reference only)
    seasons: list[tuple[str, int]] = field(default_factory=list)
    # list of (temporada, slot_id) — in the order we encountered them


def _derive_username(display_name: str) -> str:
    """
    Build a URL-safe username from a display name.

    Rules:
    - Lowercase
    - Spaces and dots replaced with hyphens
    - Collapse consecutive hyphens into one
    - Strip leading/trailing hyphens

    Examples:
      'Daniel H.'  -> 'daniel-h'
      'Carlos'     -> 'carlos'
      'Juan A.'    -> 'juan-a'
      'Jose M. R.' -> 'jose-m-r'
    """
    name = display_name.strip().lower()
    name = re.sub(r"[ .]+", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name


def _hash_username_as_password(username: str) -> str:
    """Return a bcrypt hash of the username (used as the initial password)."""
    return bcrypt.hashpw(username.encode(), bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# Main step
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Migrate all rows from usuarios_temp into users + season_participants."""

    # ------------------------------------------------------------------
    # 1. Read source data from MySQL
    # ------------------------------------------------------------------
    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(
        """
        SELECT id, temporada, nombre, pass
        FROM usuarios_temp
        ORDER BY temporada DESC, id
        """
    )
    rows = mysql_cur.fetchall()
    mysql_cur.close()

    log.info("Found %d row(s) in MySQL usuarios_temp.", len(rows))

    if not rows:
        log.warning("No rows in usuarios_temp — nothing to migrate.")
        return

    # ------------------------------------------------------------------
    # 2. Deduplicate by nombre into PersonInfo objects
    # ------------------------------------------------------------------
    # Because we ORDER BY temporada DESC (most recent first), the first
    # password encountered per person is the most recent one.
    persons: dict[str, _PersonInfo] = {}

    for row in rows:
        nombre = row["nombre"].strip()
        slot_id: int = row["id"]
        temporada: str = row["temporada"]
        raw_pass: str | None = row["pass"]

        if nombre not in persons:
            persons[nombre] = _PersonInfo(
                display_name=nombre,
                password_hash=raw_pass,  # stored for reference; we use bcrypt below
            )

        persons[nombre].seasons.append((temporada, slot_id))

    log.info("Unique persons found: %d", len(persons))

    # ------------------------------------------------------------------
    # 3 & 4. Insert users and season_participants
    # ------------------------------------------------------------------
    insert_user_sql = """
        INSERT INTO users (username, password_hash, display_name, is_admin)
        VALUES (%(username)s, %(password_hash)s, %(display_name)s, %(is_admin)s)
        RETURNING id
    """

    insert_participant_sql = """
        INSERT INTO season_participants (season_id, user_id, is_active)
        VALUES (%(season_id)s, %(user_id)s, %(is_active)s)
        RETURNING id
    """

    users_inserted = 0
    participants_inserted = 0
    summary_rows: list[tuple[int, str, str, int]] = []  # (user_id, username, display_name, n_seasons)

    with pg_conn.cursor() as pg_cur:
        for display_name, person in persons.items():
            # --- derive username and initial password hash ---
            username = _derive_username(display_name)
            password_hash = _hash_username_as_password(username)

            # --- insert user ---
            pg_cur.execute(
                insert_user_sql,
                {
                    "username": username,
                    "password_hash": password_hash,
                    "display_name": person.display_name,
                    "is_admin": False,
                },
            )
            (user_id,) = pg_cur.fetchone()
            users_inserted += 1

            # --- insert season_participants for each (temporada, slot) ---
            for temporada, slot_id in person.seasons:
                season_id = ctx.season_map.get(temporada)
                if season_id is None:
                    raise ValueError(
                        f"Season '{temporada}' not found in ctx.season_map. "
                        "Ensure step_01_seasons ran successfully before this step."
                    )

                pg_cur.execute(
                    insert_participant_sql,
                    {
                        "season_id": season_id,
                        "user_id": user_id,
                        "is_active": True,
                    },
                )
                (participant_id,) = pg_cur.fetchone()
                participants_inserted += 1

                ctx.participant_map[(temporada, slot_id)] = participant_id

            summary_rows.append(
                (user_id, username, person.display_name, len(person.seasons))
            )

    # ------------------------------------------------------------------
    # 5. Verification summary table
    # ------------------------------------------------------------------
    log.info("Users inserted: %d", users_inserted)
    log.info("season_participants inserted: %d", participants_inserted)

    col_w_id = 6
    col_w_user = 24
    col_w_name = 28
    col_w_seas = 9

    header = (
        f"{'ID':>{col_w_id}}  "
        f"{'Username':<{col_w_user}}  "
        f"{'Display Name':<{col_w_name}}  "
        f"{'Seasons':>{col_w_seas}}"
    )
    separator = "-" * len(header)

    log.info("User summary (for verification):")
    log.info(separator)
    log.info(header)
    log.info(separator)

    for user_id, username, display_name, n_seasons in sorted(summary_rows, key=lambda r: r[0]):
        log.info(
            "%*d  %-*s  %-*s  %*d",
            col_w_id, user_id,
            col_w_user, username,
            col_w_name, display_name,
            col_w_seas, n_seasons,
        )

    log.info(separator)
    log.info(
        "ctx.participant_map populated with %d entries.",
        len(ctx.participant_map),
    )
