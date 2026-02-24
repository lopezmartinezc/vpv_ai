"""Generate realistic draft picks and transaction data for season 8.

Reads existing players (with owner_id) and matchday scores to create:
- 2 drafts (preseason snake + winter linear)
- ~286+ draft picks matching existing ownership
- ~56 transactions (initial fees + weekly payments + winter draft fees)

Usage:
    cd migration && .venv/bin/python scripts/generate_draft_economy_seed.py
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import psycopg

SEASON_ID = 8
DB_DSN = "host=localhost port=5433 user=vpv password=vpv_secret dbname=ligavpv"

POSITION_ORDER = {"POR": 1, "DEF": 2, "MED": 3, "DEL": 4}

# Payment rules for season 8
WEEKLY_PAYMENTS = {7: 3.00, 8: 5.00}  # ranking -> amount
INITIAL_FEE = 50.00
WINTER_DRAFT_FEE = 2.00


def main() -> None:
    conn = psycopg.connect(DB_DSN)
    try:
        with conn:
            run(conn)
        print("Done! Seed data generated successfully.")
    finally:
        conn.close()


def run(conn: psycopg.Connection) -> None:
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

    # --- Fetch owned players grouped by participant ---
    cur.execute(
        """
        SELECT id, owner_id, position
        FROM players
        WHERE season_id = %s AND owner_id IS NOT NULL
        ORDER BY owner_id, position, id
        """,
        (SEASON_ID,),
    )
    all_owned = cur.fetchall()  # [(player_id, owner_id, position), ...]

    # Group by participant
    players_by_participant: dict[int, list[tuple[int, str]]] = {}
    for player_id, owner_id, position in all_owned:
        players_by_participant.setdefault(owner_id, []).append((player_id, position))

    # Sort each participant's players by position priority
    for pid in players_by_participant:
        players_by_participant[pid].sort(
            key=lambda x: (POSITION_ORDER.get(x[1], 5), x[0])
        )

    counts = {pid: len(ps) for pid, ps in players_by_participant.items()}
    print(f"Players per participant: {counts}")

    # --- Determine preseason (26) vs winter picks ---
    preseason_pool = 26
    preseason_players: dict[int, list[tuple[int, str]]] = {}
    winter_players: dict[int, list[tuple[int, str]]] = {}

    for pid, player_list in players_by_participant.items():
        preseason_players[pid] = player_list[:preseason_pool]
        if len(player_list) > preseason_pool:
            winter_players[pid] = player_list[preseason_pool:]

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
        # Snake: odd rounds forward, even rounds reverse
        if round_num % 2 == 1:
            order_sequence = list(range(1, n + 1))
        else:
            order_sequence = list(range(n, 0, -1))

        for draft_pos in order_sequence:
            pid = order_to_pid[draft_pos]
            idx = pick_index_by_pid[pid]
            if idx >= len(preseason_players.get(pid, [])):
                continue  # safety
            player_id, _ = preseason_players[pid][idx]
            pick_index_by_pid[pid] = idx + 1
            pick_number += 1
            pick_rows.append(
                (preseason_draft_id, pid, player_id, round_num, pick_number, pick_time)
            )
            pick_time += timedelta(seconds=random.randint(15, 90))

    # Bulk insert preseason picks
    cur.executemany(
        """
        INSERT INTO draft_picks (draft_id, participant_id, player_id,
                                round_number, pick_number, picked_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        pick_rows,
    )
    print(f"Inserted {len(pick_rows)} preseason draft picks.")

    # --- Create winter draft (if any extra players) ---
    if winter_players:
        winter_start = datetime(2026, 1, 10, 19, 0, tzinfo=timezone.utc)
        total_winter_picks = sum(len(ps) for ps in winter_players.values())
        cur.execute(
            """
            INSERT INTO drafts (season_id, draft_type, phase, status,
                               current_round, current_pick, started_at, completed_at)
            VALUES (%s, 'linear', 'winter', 'completed', 1, %s, %s, %s)
            RETURNING id
            """,
            (
                SEASON_ID,
                total_winter_picks,
                winter_start,
                winter_start + timedelta(hours=1),
            ),
        )
        winter_draft_id = cur.fetchone()[0]
        print(f"Created winter draft id={winter_draft_id}")

        # Linear order: by draft_order
        winter_pick_rows = []
        wpick = 0
        wtime = winter_start + timedelta(minutes=5)
        # Sort participants by draft_order for linear draft
        sorted_winter = sorted(winter_players.keys(), key=lambda p: pid_to_order[p])
        for pid in sorted_winter:
            for player_id, _ in winter_players[pid]:
                wpick += 1
                winter_pick_rows.append(
                    (winter_draft_id, pid, player_id, 1, wpick, wtime)
                )
                wtime += timedelta(seconds=random.randint(30, 120))

        cur.executemany(
            """
            INSERT INTO draft_picks (draft_id, participant_id, player_id,
                                    round_number, pick_number, picked_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            winter_pick_rows,
        )
        print(f"Inserted {len(winter_pick_rows)} winter draft picks.")
    else:
        winter_players_set: set[int] = set()

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
    winter_participant_ids = set(winter_players.keys()) if winter_players else set()
    for pid in winter_participant_ids:
        n_changes = len(winter_players[pid])
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
