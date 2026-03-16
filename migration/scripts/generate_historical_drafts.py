"""Generate historical draft picks for ALL seasons (1-7) from MySQL data.

Season 8 already has drafts from generate_draft_economy_seed.py.
This script reconstructs preseason and winter drafts for seasons 1-7
using the same logic: player ownership in jornadas_temp.

Requires MySQL source container running (migration/docker-compose.yml).

Usage:
    cd migration && .venv/bin/python scripts/generate_historical_drafts.py
    cd migration && .venv/bin/python scripts/generate_historical_drafts.py --apply
    cd migration && .venv/bin/python scripts/generate_historical_drafts.py --season 5 --apply
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone

import mysql.connector
import psycopg

from config import get_mysql_config, get_pg_conninfo

POSITION_ORDER = {"POR": 1, "DEF": 2, "MED": 3, "DEL": 4}

# Approximate season start dates for realistic timestamps
SEASON_STARTS = {
    1: datetime(2018, 8, 15, 18, 0, tzinfo=timezone.utc),
    2: datetime(2019, 8, 15, 18, 0, tzinfo=timezone.utc),
    3: datetime(2020, 9, 10, 18, 0, tzinfo=timezone.utc),
    4: datetime(2021, 8, 13, 18, 0, tzinfo=timezone.utc),
    5: datetime(2022, 8, 12, 18, 0, tzinfo=timezone.utc),
    6: datetime(2023, 8, 11, 18, 0, tzinfo=timezone.utc),
    7: datetime(2024, 8, 15, 18, 0, tzinfo=timezone.utc),
}

WINTER_STARTS = {
    1: datetime(2019, 1, 10, 19, 0, tzinfo=timezone.utc),
    2: datetime(2020, 1, 10, 19, 0, tzinfo=timezone.utc),
    3: datetime(2021, 1, 10, 19, 0, tzinfo=timezone.utc),
    4: datetime(2022, 1, 10, 19, 0, tzinfo=timezone.utc),
    5: datetime(2022, 12, 15, 19, 0, tzinfo=timezone.utc),
    6: datetime(2024, 1, 10, 19, 0, tzinfo=timezone.utc),
    7: datetime(2025, 1, 10, 19, 0, tzinfo=timezone.utc),
}


def get_mysql_user_to_pg_participant(
    pg_cur: psycopg.Cursor,
    mysql_cur: mysql.connector.cursor.MySQLCursorDict,
    season_id: int,
    temporada: str,
) -> dict[int, int]:
    """Map MySQL usuario_temp.id -> PG season_participants.id by display_name."""
    pg_cur.execute(
        """
        SELECT sp.id, u.display_name
        FROM season_participants sp JOIN users u ON sp.user_id = u.id
        WHERE sp.season_id = %s
        """,
        (season_id,),
    )
    pg_name_to_pid = {row[1]: row[0] for row in pg_cur.fetchall()}

    mysql_cur.execute(
        "SELECT id, nombre FROM usuarios_temp WHERE temporada = %s",
        (temporada,),
    )
    mapping: dict[int, int] = {}
    for r in mysql_cur.fetchall():
        pg_pid = pg_name_to_pid.get(r["nombre"])
        if pg_pid:
            mapping[r["id"]] = pg_pid
    return mapping


def get_winter_changes(
    mysql_cur: mysql.connector.cursor.MySQLCursorDict,
    temporada: str,
    jornada_cambios: int,
) -> dict:
    """Get winter draft ownership changes from MySQL."""
    jornada_pre = jornada_cambios - 1

    # Players picked up in winter (new or transferred in)
    mysql_cur.execute(
        """
        SELECT post.id_user, post.nom_url FROM jornadas_temp post
        LEFT JOIN jornadas_temp pre
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND pre.jornada = %s
        WHERE post.temporada = %s AND post.jornada = %s AND post.id_user > 0
            AND (pre.nom_url IS NULL OR pre.id_user = 0 OR pre.id_user IS NULL)
        ORDER BY post.id_user
        """,
        (jornada_pre, temporada, jornada_cambios),
    )
    picks = [(r["id_user"], r["nom_url"]) for r in mysql_cur.fetchall()]

    # Players swapped between users
    mysql_cur.execute(
        """
        SELECT post.id_user, post.nom_url FROM jornadas_temp pre
        JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND post.id_user > 0 AND pre.id_user != post.id_user
        """,
        (jornada_cambios, temporada, jornada_pre),
    )
    picks.extend((r["id_user"], r["nom_url"]) for r in mysql_cur.fetchall())

    # Players dropped
    drops: dict[int, list[str]] = {}

    # Dropped to free pool
    mysql_cur.execute(
        """
        SELECT pre.id_user, pre.nom_url FROM jornadas_temp pre
        JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND (post.id_user = 0 OR post.id_user IS NULL)
        ORDER BY pre.id_user
        """,
        (jornada_cambios, temporada, jornada_pre),
    )
    for r in mysql_cur.fetchall():
        drops.setdefault(r["id_user"], []).append(r["nom_url"])

    # Dropped because player left league
    mysql_cur.execute(
        """
        SELECT pre.id_user, pre.nom_url FROM jornadas_temp pre
        LEFT JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND post.nom_url IS NULL
        ORDER BY pre.id_user
        """,
        (jornada_cambios, temporada, jornada_pre),
    )
    for r in mysql_cur.fetchall():
        drops.setdefault(r["id_user"], []).append(r["nom_url"])

    # Swapped out
    mysql_cur.execute(
        """
        SELECT pre.id_user, pre.nom_url FROM jornadas_temp pre
        JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND post.id_user > 0 AND pre.id_user != post.id_user
        """,
        (jornada_cambios, temporada, jornada_pre),
    )
    for r in mysql_cur.fetchall():
        drops.setdefault(r["id_user"], []).append(r["nom_url"])

    return {"picks": picks, "drops": drops}


def process_season(
    pg_conn: psycopg.Connection,
    mysql_conn: mysql.connector.MySQLConnection,
    season_id: int,
    temporada: str,
    jornada_cambios: int,
    apply: bool,
) -> None:
    """Generate draft data for a single season."""
    print(f"\n{'='*60}")
    print(f"Season {season_id}: {temporada} (jornada_cambios={jornada_cambios})")
    print(f"{'='*60}")

    pg_cur = pg_conn.cursor()
    mysql_cur = mysql_conn.cursor(dictionary=True)

    # Use consistent random seed per season
    random.seed(42 + season_id)

    # --- Map MySQL users to PG participants ---
    user_map = get_mysql_user_to_pg_participant(pg_cur, mysql_cur, season_id, temporada)
    if not user_map:
        print("  No participant mapping found, skipping.")
        return

    # --- Fetch participants ---
    pg_cur.execute(
        "SELECT id, user_id FROM season_participants WHERE season_id = %s ORDER BY id",
        (season_id,),
    )
    participants = pg_cur.fetchall()
    participant_ids = [p[0] for p in participants]
    n = len(participant_ids)
    print(f"  {n} participants")

    # --- Assign draft_order (stable random) ---
    draft_orders = list(range(1, n + 1))
    random.shuffle(draft_orders)
    pid_to_order = dict(zip(participant_ids, draft_orders))
    order_to_pid = {v: k for k, v in pid_to_order.items()}

    if apply:
        for pid, order in zip(participant_ids, draft_orders):
            pg_cur.execute(
                "UPDATE season_participants SET draft_order = %s WHERE id = %s",
                (order, pid),
            )

    # --- Build slug -> player maps ---
    pg_cur.execute(
        "SELECT id, slug, owner_id, position FROM players WHERE season_id = %s",
        (season_id,),
    )
    players_data = pg_cur.fetchall()
    slug_to_player = {row[1]: {"id": row[0], "owner_id": row[1], "position": row[3]} for row in players_data}
    player_id_to_info = {row[0]: {"position": row[3], "owner_id": row[2]} for row in players_data}
    slug_to_id = {row[1]: row[0] for row in players_data}

    # --- Get winter changes ---
    winter_changes = get_winter_changes(mysql_cur, temporada, jornada_cambios)
    winter_picks = winter_changes["picks"]
    winter_drops_original = get_winter_changes(mysql_cur, temporada, jornada_cambios)["drops"]

    # Build winter pick data
    winter_picked_ids: set[int] = set()
    winter_pick_data: list[tuple[int, int, int | None]] = []

    winter_drops_consumed: dict[int, list[str]] = {
        k: list(v) for k, v in winter_changes["drops"].items()
    }

    for mysql_user, picked_slug in winter_picks:
        pg_pid = user_map.get(mysql_user)
        if not pg_pid:
            continue
        player_id = slug_to_id.get(picked_slug)
        if not player_id:
            continue
        winter_picked_ids.add(player_id)

        dropped_player_id = None
        user_drops = winter_drops_consumed.get(mysql_user, [])
        if user_drops:
            dropped_slug = user_drops.pop(0)
            dropped_id = slug_to_id.get(dropped_slug)
            if dropped_id:
                dropped_player_id = dropped_id

        winter_pick_data.append((pg_pid, player_id, dropped_player_id))

    print(f"  Winter draft: {len(winter_pick_data)} picks")

    # --- Build preseason players from ownership ---
    pg_cur.execute(
        """
        SELECT id, owner_id, position
        FROM players
        WHERE season_id = %s AND owner_id IS NOT NULL
        ORDER BY owner_id, position, id
        """,
        (season_id,),
    )
    all_owned = pg_cur.fetchall()

    # owner_id in players table is participant_id
    preseason_players: dict[int, list[tuple[int, str]]] = {}
    for player_id, owner_id, position in all_owned:
        if player_id not in winter_picked_ids:
            preseason_players.setdefault(owner_id, []).append((player_id, position))

    # Add dropped players back to preseason
    for mysql_user, drop_slugs in winter_drops_original.items():
        pg_pid = user_map.get(mysql_user)
        if not pg_pid:
            continue
        for slug in drop_slugs:
            pid = slug_to_id.get(slug)
            if pid and pid not in winter_picked_ids:
                preseason_players.setdefault(pg_pid, []).append((pid, ""))

    # Sort by position
    for pid in preseason_players:
        preseason_players[pid].sort(
            key=lambda x: (POSITION_ORDER.get(x[1], 5), x[0])
        )

    pool_size = max((len(ps) for ps in preseason_players.values()), default=26)
    total_preseason = sum(len(ps) for ps in preseason_players.values())
    print(f"  Preseason: {total_preseason} players across {len(preseason_players)} participants (pool={pool_size})")

    if not apply:
        # Show what would happen
        for pid, ps in sorted(preseason_players.items()):
            print(f"    participant {pid}: {len(ps)} players")
        return

    # --- Create preseason draft ---
    draft_start = SEASON_STARTS.get(season_id, datetime(2020, 8, 15, 18, 0, tzinfo=timezone.utc))
    pg_cur.execute(
        """
        INSERT INTO drafts (season_id, draft_type, phase, status,
                           current_round, current_pick, started_at, completed_at)
        VALUES (%s, 'snake', 'preseason', 'completed', %s, %s, %s, %s)
        RETURNING id
        """,
        (season_id, pool_size, pool_size * n, draft_start, draft_start + timedelta(hours=4)),
    )
    preseason_draft_id = pg_cur.fetchone()[0]
    print(f"  Created preseason draft id={preseason_draft_id}")

    # --- Generate snake order picks ---
    pick_number = 0
    pick_index_by_pid: dict[int, int] = {pid: 0 for pid in participant_ids}
    pick_time = draft_start + timedelta(minutes=5)
    pick_rows = []

    for round_num in range(1, pool_size + 1):
        order_sequence = list(range(1, n + 1)) if round_num % 2 == 1 else list(range(n, 0, -1))

        for draft_pos in order_sequence:
            pid = order_to_pid[draft_pos]
            idx = pick_index_by_pid[pid]
            if idx >= len(preseason_players.get(pid, [])):
                continue
            player_id, _ = preseason_players[pid][idx]
            pick_index_by_pid[pid] = idx + 1
            pick_number += 1
            pick_rows.append(
                (preseason_draft_id, pid, player_id, round_num, pick_number, pick_time)
            )
            pick_time += timedelta(seconds=random.randint(15, 90))

    pg_cur.executemany(
        """
        INSERT INTO draft_picks (draft_id, participant_id, player_id,
                                round_number, pick_number, picked_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        pick_rows,
    )
    print(f"  Inserted {len(pick_rows)} preseason picks")

    # --- Create winter draft ---
    if winter_pick_data:
        winter_start = WINTER_STARTS.get(season_id, datetime(2021, 1, 10, 19, 0, tzinfo=timezone.utc))

        # Winter order: inverse standings at jornada_cambios - 1
        pg_cur.execute(
            """
            SELECT pms.participant_id, SUM(pms.total_points) AS season_pts
            FROM participant_matchday_scores pms
            JOIN matchdays md ON md.id = pms.matchday_id
            WHERE md.season_id = %s AND md.number <= %s AND md.counts = true
            GROUP BY pms.participant_id
            ORDER BY season_pts ASC
            """,
            (season_id, jornada_cambios - 1),
        )
        inverse_standings = [row[0] for row in pg_cur.fetchall()]
        winter_draft_order = {pid: idx for idx, pid in enumerate(inverse_standings)}
        winter_pick_data.sort(key=lambda x: winter_draft_order.get(x[0], 99))

        pg_cur.execute(
            """
            INSERT INTO drafts (season_id, draft_type, phase, status,
                               current_round, current_pick, started_at, completed_at)
            VALUES (%s, 'linear', 'winter', 'completed', 1, %s, %s, %s)
            RETURNING id
            """,
            (season_id, len(winter_pick_data), winter_start, winter_start + timedelta(hours=1)),
        )
        winter_draft_id = pg_cur.fetchone()[0]
        print(f"  Created winter draft id={winter_draft_id}")

        winter_pick_rows = []
        wtime = winter_start + timedelta(minutes=5)
        for wpick, (pg_pid, player_id, dropped_player_id) in enumerate(winter_pick_data, 1):
            winter_pick_rows.append(
                (winter_draft_id, pg_pid, player_id, dropped_player_id, 1, wpick, wtime)
            )
            wtime += timedelta(seconds=random.randint(30, 120))

        pg_cur.executemany(
            """
            INSERT INTO draft_picks (draft_id, participant_id, player_id,
                                    dropped_player_id, round_number, pick_number, picked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            winter_pick_rows,
        )
        print(f"  Inserted {len(winter_pick_rows)} winter picks")

    pg_conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate historical drafts for seasons 1-7")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--season", type=int, help="Only process this season_id")
    args = parser.parse_args()

    if not args.apply:
        print("DRY RUN — use --apply to save changes\n")

    mysql_conn = mysql.connector.connect(**get_mysql_config())
    pg_conn = psycopg.connect(get_pg_conninfo())

    try:
        # Get all seasons
        pg_cur = pg_conn.cursor()
        pg_cur.execute("SELECT id, name, matchday_winter FROM seasons ORDER BY id")
        seasons = pg_cur.fetchall()

        # Check which seasons already have drafts
        pg_cur.execute("SELECT DISTINCT season_id FROM drafts")
        existing = {row[0] for row in pg_cur.fetchall()}

        for season_id, name, matchday_winter in seasons:
            if args.season and season_id != args.season:
                continue
            if season_id in existing and not args.season:
                print(f"\nSeason {season_id} ({name}): already has drafts, skipping")
                continue

            # Clean existing drafts if re-running for specific season
            if season_id in existing and args.apply:
                pg_cur.execute(
                    "DELETE FROM draft_picks WHERE draft_id IN (SELECT id FROM drafts WHERE season_id = %s)",
                    (season_id,),
                )
                pg_cur.execute("DELETE FROM drafts WHERE season_id = %s", (season_id,))
                pg_conn.commit()
                print(f"\nCleaned existing drafts for season {season_id}")

            process_season(pg_conn, mysql_conn, season_id, name, matchday_winter, args.apply)

        if args.apply:
            # Reset sequences
            pg_cur.execute("SELECT setval('drafts_id_seq', (SELECT COALESCE(MAX(id),0) FROM drafts))")
            pg_cur.execute("SELECT setval('draft_picks_id_seq', (SELECT COALESCE(MAX(id),0) FROM draft_picks))")
            pg_conn.commit()
            print("\nSequences reset.")

        print("\nDone!")

    finally:
        pg_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    main()
