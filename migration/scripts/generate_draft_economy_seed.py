"""Generate realistic draft picks and transaction data for season 8.

Reads existing players (with owner_id) and queries MySQL for winter draft
changes to create:
- 2 drafts (preseason snake + winter linear)
- draft picks matching actual ownership (with dropped_player_id for winter)
- transactions (initial fees + weekly payments + winter draft fees)

Requires MySQL source container running (migration/docker-compose.yml).

Usage:
    cd migration && .venv/bin/python scripts/generate_draft_economy_seed.py
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import mysql.connector
import psycopg

SEASON_ID = 8
TEMPORADA = "2025-2026"
DB_DSN = "host=localhost port=5433 user=vpv password=vpv_secret dbname=ligavpv"
MYSQL_CONFIG = {
    "host": "franquiciadonpiso.com",
    "port": 3306,
    "user": "vpvadmin",
    "password": "Vpv1977",
    "database": "ligavpv",
}

POSITION_ORDER = {"POR": 1, "DEF": 2, "MED": 3, "DEL": 4}

# Payment rules for season 8
WEEKLY_PAYMENTS = {7: 3.00, 8: 5.00}  # ranking -> amount
INITIAL_FEE = 50.00
WINTER_DRAFT_FEE = 2.00


def get_winter_changes(mysql_conn: mysql.connector.MySQLConnection) -> dict:
    """Query MySQL for winter draft ownership changes.

    Returns dict with:
        - picks: list of (mysql_user_id, picked_slug) — players picked in winter draft
        - drops: dict[mysql_user_id, list[slug]] — players dropped per user
    """
    cur = mysql_conn.cursor(dictionary=True)

    # Get jornada_cambios for this season
    cur.execute(
        "SELECT jornada_cambios FROM temporadas WHERE temporada = %s",
        (TEMPORADA,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"picks": [], "drops": {}}
    jornada_cambios = row["jornada_cambios"]
    jornada_pre = jornada_cambios - 1

    # Players picked up in winter (unowned/absent pre-winter, owned post-winter)
    cur.execute(
        """
        SELECT post.id_user, post.nom_url FROM jornadas_temp post
        LEFT JOIN jornadas_temp pre
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND pre.jornada = %s
        WHERE post.temporada = %s AND post.jornada = %s AND post.id_user > 0
            AND (pre.nom_url IS NULL OR pre.id_user = 0 OR pre.id_user IS NULL)
        ORDER BY post.id_user
        """,
        (jornada_pre, TEMPORADA, jornada_cambios),
    )
    picks = [(r["id_user"], r["nom_url"]) for r in cur.fetchall()]

    # Players swapped between users
    cur.execute(
        """
        SELECT post.id_user, post.nom_url FROM jornadas_temp pre
        JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND post.id_user > 0 AND pre.id_user != post.id_user
        """,
        (jornada_cambios, TEMPORADA, jornada_pre),
    )
    picks.extend((r["id_user"], r["nom_url"]) for r in cur.fetchall())

    # Players dropped (owned pre-winter, unowned/absent post-winter)
    drops: dict[int, list[str]] = {}

    # Dropped to free pool
    cur.execute(
        """
        SELECT pre.id_user, pre.nom_url FROM jornadas_temp pre
        JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND (post.id_user = 0 OR post.id_user IS NULL)
        ORDER BY pre.id_user
        """,
        (jornada_cambios, TEMPORADA, jornada_pre),
    )
    for r in cur.fetchall():
        drops.setdefault(r["id_user"], []).append(r["nom_url"])

    # Dropped because player left league
    cur.execute(
        """
        SELECT pre.id_user, pre.nom_url FROM jornadas_temp pre
        LEFT JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND post.nom_url IS NULL
        ORDER BY pre.id_user
        """,
        (jornada_cambios, TEMPORADA, jornada_pre),
    )
    for r in cur.fetchall():
        drops.setdefault(r["id_user"], []).append(r["nom_url"])

    # Swapped out (owned by someone else post-winter)
    cur.execute(
        """
        SELECT pre.id_user, pre.nom_url FROM jornadas_temp pre
        JOIN jornadas_temp post
            ON pre.nom_url = post.nom_url AND pre.temporada = post.temporada AND post.jornada = %s
        WHERE pre.temporada = %s AND pre.jornada = %s
            AND pre.id_user > 0 AND post.id_user > 0 AND pre.id_user != post.id_user
        """,
        (jornada_cambios, TEMPORADA, jornada_pre),
    )
    for r in cur.fetchall():
        drops.setdefault(r["id_user"], []).append(r["nom_url"])

    cur.close()
    return {"picks": picks, "drops": drops}


def main() -> None:
    mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
    conn = psycopg.connect(DB_DSN)
    try:
        with conn:
            run(conn, mysql_conn)
        print("Done! Seed data generated successfully.")
    finally:
        conn.close()
        mysql_conn.close()


def run(conn: psycopg.Connection, mysql_conn: mysql.connector.MySQLConnection) -> None:
    cur = conn.cursor()

    # Clean existing data (in case of re-run)
    cur.execute("DELETE FROM draft_picks")
    cur.execute("DELETE FROM drafts")
    cur.execute("DELETE FROM transactions WHERE season_id = %s", (SEASON_ID,))
    print("Cleaned existing draft/transaction data.")

    # --- Fetch participants ---
    cur.execute(
        "SELECT id, user_id FROM season_participants WHERE season_id = %s ORDER BY id",
        (SEASON_ID,),
    )
    participants = cur.fetchall()  # [(participant_id, user_id), ...]
    participant_ids = [p[0] for p in participants]
    print(f"Found {len(participant_ids)} participants: {participant_ids}")

    # --- Assign draft_order (stable random) ---
    random.seed(42)
    draft_orders = list(range(1, len(participant_ids) + 1))
    random.shuffle(draft_orders)
    for pid, order in zip(participant_ids, draft_orders):
        cur.execute(
            "UPDATE season_participants SET draft_order = %s WHERE id = %s",
            (order, pid),
        )
    pid_to_order = dict(zip(participant_ids, draft_orders))
    order_to_pid = {v: k for k, v in pid_to_order.items()}
    print(f"Assigned draft_order: {pid_to_order}")

    # --- Build slug -> player_id map for this season ---
    cur.execute(
        "SELECT id, slug, owner_id FROM players WHERE season_id = %s",
        (SEASON_ID,),
    )
    slug_to_player = {row[1]: (row[0], row[2]) for row in cur.fetchall()}

    # --- Build mysql_user -> pg_participant_id map ---
    # Need to look up by display_name since IDs don't map directly
    cur.execute(
        """
        SELECT sp.id, u.display_name
        FROM season_participants sp JOIN users u ON sp.user_id = u.id
        WHERE sp.season_id = %s
        """,
        (SEASON_ID,),
    )
    pg_name_to_pid = {row[1]: row[0] for row in cur.fetchall()}

    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(
        "SELECT id, nombre FROM usuarios_temp WHERE temporada = %s",
        (TEMPORADA,),
    )
    mysql_user_to_pg_pid = {}
    for r in mysql_cur.fetchall():
        pg_pid = pg_name_to_pid.get(r["nombre"])
        if pg_pid:
            mysql_user_to_pg_pid[r["id"]] = pg_pid
    mysql_cur.close()
    print(f"MySQL user -> PG participant mapping: {mysql_user_to_pg_pid}")

    # --- Get winter draft changes from MySQL ---
    winter_changes = get_winter_changes(mysql_conn)
    winter_picks = winter_changes["picks"]  # [(mysql_user, slug)]
    winter_drops = winter_changes["drops"]  # {mysql_user: [slugs]}

    # Build set of winter-picked player IDs and dropped player IDs per participant
    winter_picked_ids: set[int] = set()
    winter_pick_data: list[tuple[int, int, int | None]] = []  # (participant_id, player_id, dropped_player_id)

    for mysql_user, picked_slug in winter_picks:
        pg_pid = mysql_user_to_pg_pid.get(mysql_user)
        if not pg_pid:
            continue
        player_info = slug_to_player.get(picked_slug)
        if not player_info:
            print(f"  WARNING: picked slug '{picked_slug}' not found in PG players")
            continue
        player_id = player_info[0]
        winter_picked_ids.add(player_id)

        # Find a dropped player for this participant
        user_drops = winter_drops.get(mysql_user, [])
        dropped_player_id = None
        if user_drops:
            dropped_slug = user_drops.pop(0)
            dropped_info = slug_to_player.get(dropped_slug)
            if dropped_info:
                dropped_player_id = dropped_info[0]

        winter_pick_data.append((pg_pid, player_id, dropped_player_id))

    print(f"Winter draft: {len(winter_pick_data)} picks with dropped_player_id")

    # --- Fetch owned players (these are the preseason-drafted ones) ---
    cur.execute(
        """
        SELECT id, owner_id, position
        FROM players
        WHERE season_id = %s AND owner_id IS NOT NULL
        ORDER BY owner_id, position, id
        """,
        (SEASON_ID,),
    )
    all_owned = cur.fetchall()

    # Group by participant — exclude winter picks (they were drafted in winter, not preseason)
    preseason_players: dict[int, list[tuple[int, str]]] = {}
    for player_id, owner_id, position in all_owned:
        if player_id not in winter_picked_ids:
            preseason_players.setdefault(owner_id, []).append((player_id, position))

    # Also add dropped players to preseason (they were originally drafted in preseason)
    for mysql_user, drop_slugs_original in winter_changes["drops"].items():
        pg_pid = mysql_user_to_pg_pid.get(mysql_user)
        if not pg_pid:
            continue
        # We already popped from winter_drops above, so re-query original
    # Re-get drops since we consumed them above
    winter_changes2 = get_winter_changes(mysql_conn)
    for mysql_user, drop_slugs in winter_changes2["drops"].items():
        pg_pid = mysql_user_to_pg_pid.get(mysql_user)
        if not pg_pid:
            continue
        for slug in drop_slugs:
            player_info = slug_to_player.get(slug)
            if player_info:
                preseason_players.setdefault(pg_pid, []).append(
                    (player_info[0], "")  # position doesn't matter for ordering
                )

    # Sort each participant's players by position priority
    for pid in preseason_players:
        preseason_players[pid].sort(
            key=lambda x: (POSITION_ORDER.get(x[1], 5), x[0])
        )

    preseason_pool = 26
    counts = {pid: len(ps) for pid, ps in preseason_players.items()}
    print(f"Preseason players per participant: {counts}")

    # --- Create preseason draft ---
    draft_start = datetime(2025, 7, 15, 18, 0, tzinfo=timezone.utc)
    cur.execute(
        """
        INSERT INTO drafts (season_id, draft_type, phase, status,
                           current_round, current_pick, started_at, completed_at)
        VALUES (%s, 'snake', 'preseason', 'completed', %s, %s, %s, %s)
        RETURNING id
        """,
        (
            SEASON_ID,
            preseason_pool,
            preseason_pool * len(participant_ids),
            draft_start,
            draft_start + timedelta(hours=4),
        ),
    )
    preseason_draft_id = cur.fetchone()[0]
    print(f"Created preseason draft id={preseason_draft_id}")

    # --- Generate snake order picks ---
    n = len(participant_ids)
    pick_number = 0
    pick_index_by_pid: dict[int, int] = {pid: 0 for pid in participant_ids}
    pick_time = draft_start + timedelta(minutes=5)

    pick_rows = []
    for round_num in range(1, preseason_pool + 1):
        if round_num % 2 == 1:
            order_sequence = list(range(1, n + 1))
        else:
            order_sequence = list(range(n, 0, -1))

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

    cur.executemany(
        """
        INSERT INTO draft_picks (draft_id, participant_id, player_id,
                                round_number, pick_number, picked_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        pick_rows,
    )
    print(f"Inserted {len(pick_rows)} preseason draft picks.")

    # --- Create winter draft ---
    if winter_pick_data:
        winter_start = datetime(2026, 1, 10, 19, 0, tzinfo=timezone.utc)
        cur.execute(
            """
            INSERT INTO drafts (season_id, draft_type, phase, status,
                               current_round, current_pick, started_at, completed_at)
            VALUES (%s, 'linear', 'winter', 'completed', 1, %s, %s, %s)
            RETURNING id
            """,
            (
                SEASON_ID,
                len(winter_pick_data),
                winter_start,
                winter_start + timedelta(hours=1),
            ),
        )
        winter_draft_id = cur.fetchone()[0]
        print(f"Created winter draft id={winter_draft_id}")

        # Winter draft order: inverse of accumulated standings at jornada_cambios - 1
        # Worst-ranked participant picks first
        cur.execute(
            """
            SELECT pms.participant_id, SUM(pms.total_points) AS season_pts
            FROM participant_matchday_scores pms
            JOIN matchdays md ON md.id = pms.matchday_id
            WHERE md.season_id = %s AND md.number <= %s AND md.counts = true
            GROUP BY pms.participant_id
            ORDER BY season_pts ASC
            """,
            (SEASON_ID, 22),  # jornada_cambios - 1
        )
        inverse_standings = [row[0] for row in cur.fetchall()]
        winter_draft_order = {pid: idx for idx, pid in enumerate(inverse_standings)}
        print(f"Winter draft order (inverse standings): {[pid for pid in inverse_standings]}")

        winter_pick_data.sort(key=lambda x: winter_draft_order.get(x[0], 99))

        winter_pick_rows = []
        wtime = winter_start + timedelta(minutes=5)
        for wpick, (pg_pid, player_id, dropped_player_id) in enumerate(
            winter_pick_data, 1
        ):
            winter_pick_rows.append(
                (
                    winter_draft_id,
                    pg_pid,
                    player_id,
                    dropped_player_id,
                    1,
                    wpick,
                    wtime,
                )
            )
            wtime += timedelta(seconds=random.randint(30, 120))

        cur.executemany(
            """
            INSERT INTO draft_picks (draft_id, participant_id, player_id,
                                    dropped_player_id, round_number, pick_number, picked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            winter_pick_rows,
        )
        print(f"Inserted {len(winter_pick_rows)} winter draft picks (with dropped_player_id).")

    winter_participant_ids = {d[0] for d in winter_pick_data}

    # === TRANSACTIONS ===

    tx_rows: list[tuple] = []
    season_start = datetime(2025, 8, 1, 12, 0, tzinfo=timezone.utc)

    # 1. Initial fees
    for pid in participant_ids:
        tx_rows.append((
            SEASON_ID, pid, None, "initial_fee", INITIAL_FEE,
            "Cuota inicial temporada", season_start,
        ))
    print(f"Generated {len(participant_ids)} initial_fee transactions.")

    # 2. Weekly payments based on actual rankings
    cur.execute(
        """
        SELECT pms.participant_id, pms.matchday_id, pms.ranking, md.number
        FROM participant_matchday_scores pms
        JOIN matchdays md ON md.id = pms.matchday_id
        WHERE md.season_id = %s AND md.counts = true
        ORDER BY md.number, pms.ranking
        """,
        (SEASON_ID,),
    )
    scores = cur.fetchall()

    # Get matchday dates for realistic timestamps
    cur.execute(
        "SELECT id, number, first_match_at FROM matchdays WHERE season_id = %s",
        (SEASON_ID,),
    )
    md_dates = {row[0]: row[2] for row in cur.fetchall()}

    weekly_count = 0
    for participant_id, matchday_id, ranking, md_number in scores:
        if ranking in WEEKLY_PAYMENTS:
            amount = WEEKLY_PAYMENTS[ranking]
            md_date = md_dates.get(matchday_id) or season_start
            tx_rows.append((
                SEASON_ID, participant_id, matchday_id, "weekly_payment", amount,
                f"Jornada {md_number} - puesto {ranking}",
                md_date + timedelta(days=1) if md_date else season_start,
            ))
            weekly_count += 1
    print(f"Generated {weekly_count} weekly_payment transactions.")

    # 3. Winter draft fees
    winter_fee_count = 0
    # Count picks per participant from winter_pick_data
    winter_picks_per_pid: dict[int, int] = {}
    for pg_pid, _, _ in winter_pick_data:
        winter_picks_per_pid[pg_pid] = winter_picks_per_pid.get(pg_pid, 0) + 1
    for pid, n_changes in winter_picks_per_pid.items():
        tx_rows.append((
            SEASON_ID, pid, None, "winter_draft_fee",
            WINTER_DRAFT_FEE * n_changes,
            f"Draft invierno - {n_changes} cambio(s)",
            datetime(2026, 1, 11, 12, 0, tzinfo=timezone.utc),
        ))
        winter_fee_count += 1
    print(f"Generated {winter_fee_count} winter_draft_fee transactions.")

    # Bulk insert transactions
    cur.executemany(
        """
        INSERT INTO transactions (season_id, participant_id, matchday_id,
                                 type, amount, description, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        tx_rows,
    )
    print(f"Inserted {len(tx_rows)} total transactions.")

    # Reset sequences
    cur.execute("SELECT setval('drafts_id_seq', (SELECT COALESCE(MAX(id),0) FROM drafts))")
    cur.execute("SELECT setval('draft_picks_id_seq', (SELECT COALESCE(MAX(id),0) FROM draft_picks))")
    cur.execute("SELECT setval('transactions_id_seq', (SELECT COALESCE(MAX(id),0) FROM transactions))")

    conn.commit()


if __name__ == "__main__":
    main()
