"""Step 10: Validate migrated data with count checks and integrity queries."""

import logging

from context import MigrationContext

logger = logging.getLogger(__name__)


def run(mysql_conn, pg_conn, ctx: MigrationContext) -> None:
    pg_cur = pg_conn.cursor()
    my_cur = mysql_conn.cursor()

    errors = []

    def check(label: str, query: str, expected=None, is_range=False):
        pg_cur.execute(query)
        actual = pg_cur.fetchone()[0]
        if expected is None:
            logger.info("  %-45s = %s", label, actual)
        elif is_range:
            lo, hi = expected
            if lo <= actual <= hi:
                logger.info("  %-45s = %s  (expected %d-%d)", label, actual, lo, hi)
            else:
                msg = f"{label}: got {actual}, expected {lo}-{hi}"
                logger.error("  FAIL: %s", msg)
                errors.append(msg)
        else:
            if actual == expected:
                logger.info("  %-45s = %s  OK", label, actual)
            else:
                msg = f"{label}: got {actual}, expected {expected}"
                logger.error("  FAIL: %s", msg)
                errors.append(msg)

    logger.info("=" * 60)
    logger.info("VALIDATION RESULTS")
    logger.info("=" * 60)

    # --- Row counts ---
    logger.info("--- Row counts ---")
    check("seasons", "SELECT COUNT(*) FROM seasons", 8)
    check("users", "SELECT COUNT(*) FROM users", is_range=True, expected=(10, 20))
    check("season_participants", "SELECT COUNT(*) FROM season_participants", is_range=True, expected=(70, 110))
    check("scoring_rules", "SELECT COUNT(*) FROM scoring_rules", is_range=True, expected=(200, 300))
    check("season_payments", "SELECT COUNT(*) FROM season_payments", is_range=True, expected=(80, 120))
    check("teams", "SELECT COUNT(*) FROM teams", is_range=True, expected=(100, 200))
    check("matchdays", "SELECT COUNT(*) FROM matchdays", is_range=True, expected=(250, 320))
    check("matches", "SELECT COUNT(*) FROM matches", is_range=True, expected=(2500, 3200))
    check("players", "SELECT COUNT(*) FROM players", is_range=True, expected=(4000, 8000))
    check("player_stats", "SELECT COUNT(*) FROM player_stats", is_range=True, expected=(150000, 250000))
    check("lineups", "SELECT COUNT(*) FROM lineups")
    check("lineup_players", "SELECT COUNT(*) FROM lineup_players")
    check("participant_matchday_scores", "SELECT COUNT(*) FROM participant_matchday_scores")
    check("valid_formations", "SELECT COUNT(*) FROM valid_formations", 6)

    # --- Empty tables (by design) ---
    logger.info("--- Empty tables (by design) ---")
    check("drafts (empty)", "SELECT COUNT(*) FROM drafts", 0)
    check("draft_picks (empty)", "SELECT COUNT(*) FROM draft_picks", 0)
    check("transactions (empty)", "SELECT COUNT(*) FROM transactions", 0)
    check("competitions (empty)", "SELECT COUNT(*) FROM competitions", 0)

    # --- Integrity checks ---
    logger.info("--- Integrity checks ---")
    check(
        "Orphan player_stats (no player)",
        "SELECT COUNT(*) FROM player_stats ps LEFT JOIN players p ON ps.player_id = p.id WHERE p.id IS NULL",
        0,
    )
    check(
        "Orphan player_stats (no matchday)",
        "SELECT COUNT(*) FROM player_stats ps LEFT JOIN matchdays md ON ps.matchday_id = md.id WHERE md.id IS NULL",
        0,
    )
    check(
        "Orphan lineup_players (no player)",
        "SELECT COUNT(*) FROM lineup_players lp LEFT JOIN players p ON lp.player_id = p.id WHERE p.id IS NULL",
        0,
    )
    check(
        "Orphan lineup_players (no lineup)",
        "SELECT COUNT(*) FROM lineup_players lp LEFT JOIN lineups l ON lp.lineup_id = l.id WHERE l.id IS NULL",
        0,
    )

    # --- Cross-check with MySQL ---
    logger.info("--- Cross-check with MySQL source ---")

    my_cur.execute("SELECT COUNT(*) FROM temporadas")
    mysql_seasons = my_cur.fetchone()[0]
    pg_cur.execute("SELECT COUNT(*) FROM seasons")
    pg_seasons = pg_cur.fetchone()[0]
    if mysql_seasons == pg_seasons:
        logger.info("  Seasons match: MySQL=%d, PG=%d  OK", mysql_seasons, pg_seasons)
    else:
        msg = f"Seasons mismatch: MySQL={mysql_seasons}, PG={pg_seasons}"
        logger.error("  FAIL: %s", msg)
        errors.append(msg)

    my_cur.execute("SELECT COUNT(*) FROM list_jornadas_temp")
    mysql_matches = my_cur.fetchone()[0]
    pg_cur.execute("SELECT COUNT(*) FROM matches")
    pg_matches = pg_cur.fetchone()[0]
    logger.info("  Matches: MySQL=%d, PG=%d", mysql_matches, pg_matches)

    my_cur.execute("SELECT COUNT(DISTINCT nom_url, temporada) FROM jornadas_temp")
    mysql_player_seasons = my_cur.fetchone()[0]
    pg_cur.execute("SELECT COUNT(*) FROM players")
    pg_players = pg_cur.fetchone()[0]
    logger.info("  Player-seasons: MySQL=%d, PG=%d (diff=skipped foreign teams)",
                mysql_player_seasons, pg_players)

    my_cur.execute("SELECT COUNT(*) FROM jornadas_temp")
    mysql_stats = my_cur.fetchone()[0]
    pg_cur.execute("SELECT COUNT(*) FROM player_stats")
    pg_stats = pg_cur.fetchone()[0]
    logger.info("  Player stats: MySQL=%d, PG=%d (diff=skipped foreign teams)",
                mysql_stats, pg_stats)

    # --- Season breakdown ---
    logger.info("--- Stats per season ---")
    pg_cur.execute("""
        SELECT s.name,
               COUNT(DISTINCT ps.player_id) AS players,
               COUNT(ps.id) AS stats,
               COALESCE(SUM(ps.pts_total), 0) AS total_pts
        FROM seasons s
        LEFT JOIN matchdays md ON md.season_id = s.id
        LEFT JOIN player_stats ps ON ps.matchday_id = md.id
        GROUP BY s.name
        ORDER BY s.name
    """)
    for row in pg_cur.fetchall():
        logger.info("  %-12s  players=%-5d  stats=%-7d  total_pts=%d",
                     row[0], row[1], row[2], row[3])

    # --- Formation validity ---
    logger.info("--- Formation validity ---")
    pg_cur.execute("""
        SELECT l.formation, COUNT(*) AS cnt
        FROM lineups l
        LEFT JOIN valid_formations vf ON vf.formation = l.formation
        WHERE vf.id IS NULL
        GROUP BY l.formation
        ORDER BY cnt DESC
    """)
    invalid_formations = pg_cur.fetchall()
    if not invalid_formations:
        logger.info("  All lineup formations are valid  OK")
    else:
        for row in invalid_formations:
            logger.warning("  Invalid formation: %s (count=%d)", row[0], row[1])

    pg_cur.close()
    my_cur.close()

    # --- Summary ---
    logger.info("=" * 60)
    if errors:
        logger.error("VALIDATION FAILED: %d error(s)", len(errors))
        for e in errors:
            logger.error("  - %s", e)
    else:
        logger.info("VALIDATION PASSED: all checks OK")
    logger.info("=" * 60)
