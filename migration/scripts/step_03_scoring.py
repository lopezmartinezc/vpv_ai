"""
step_03_scoring.py - Insert default scoring_rules and season_payments for all seasons.

Both tables are fully driven by the constants defined below.  The same set of
rules and payment bands is inserted once per season_id found in ctx.season_map.

PostgreSQL target tables:

    scoring_rules (season_id, rule_key, position, value, description)
    season_payments (season_id, payment_type, position_rank, amount, description)

After this step both tables are populated for every season.
"""

import logging
from decimal import Decimal

import mysql.connector
import psycopg

from context import MigrationContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring rules
# (rule_key, position | None, value, description)
# ---------------------------------------------------------------------------

# position=None means the rule applies to all positions.
# For rules that depend on position (ptos_gol, ptos_imbatibilidad_*) a separate
# row exists per applicable position.

SCORING_RULES: list[tuple[str, str | None, int | float, str]] = [
    # --- Participacion ---
    ("ptos_jugar",                  None,  1,   "Jugar el partido"),
    ("ptos_titular",                None,  1,   "Ser titular"),
    # --- Resultado ---
    ("ptos_resultado_win",          None,  2,   "Victoria del equipo"),
    ("ptos_resultado_draw",         None,  1,   "Empate del equipo"),
    ("ptos_resultado_loss",         None,  0,   "Derrota del equipo"),
    # --- Goles por posicion ---
    ("ptos_gol",                    "POR", 10,  "Gol de portero"),
    ("ptos_gol",                    "DEF", 8,   "Gol de defensa"),
    ("ptos_gol",                    "MED", 7,   "Gol de mediocampista"),
    ("ptos_gol",                    "DEL", 5,   "Gol de delantero"),
    # --- Imbatibilidad: bonus ---
    ("ptos_imbatibilidad_clean",    "POR", 4,   "Porteria a 0 (POR, >=65 min)"),
    ("ptos_imbatibilidad_clean",    "DEF", 3,   "Porteria a 0 (DEF, >=45 min)"),
    # --- Imbatibilidad: minutos minimos ---
    ("ptos_imbatibilidad_min",      "POR", 65,  "Minutos minimos imbatibilidad POR"),
    ("ptos_imbatibilidad_min",      "DEF", 45,  "Minutos minimos imbatibilidad DEF"),
    # --- Imbatibilidad: penalizacion portero ---
    ("ptos_imbatibilidad_1gol",     "POR", 0,   "POR con 1 gol encajado"),
    ("ptos_imbatibilidad_per_gol",  "POR", -1,  "POR penalizacion por gol (>1 gol)"),
    # --- Acciones positivas ---
    ("ptos_gol_p",                  None,  5,   "Gol de penalti"),
    ("ptos_asis",                   None,  2,   "Asistencia"),
    ("ptos_pen_par",                None,  5,   "Penalti parado"),
    ("ptos_tiro_palo",              None,  1,   "Tiro al palo"),
    ("ptos_pen_for",                None,  1,   "Penalti forzado"),
    # --- Acciones negativas ---
    ("ptos_pen_fall",               None,  -3,  "Penalti fallado"),
    ("ptos_gol_pp",                 None,  -2,  "Gol en propia puerta"),
    ("ptos_ama",                    None,  -1,  "Tarjeta amarilla"),
    ("ptos_roja",                   None,  -3,  "Roja directa o doble amarilla"),
    ("ptos_pen_com",                None,  -1,  "Penalti cometido"),
    # --- Valoracion Marca ---
    ("ptos_marca_1",                None,  1,   "Marca 1 estrella"),
    ("ptos_marca_2",                None,  2,   "Marca 2 estrellas"),
    ("ptos_marca_3",                None,  3,   "Marca 3 estrellas"),
    ("ptos_marca_4",                None,  4,   "Marca 4 estrellas"),
    ("ptos_marca_no_jugo",          None,  -1,  "Marca \"-\" (no jugo)"),
    ("ptos_marca_sc",               None,  0,   "Marca \"SC\" (sin calificar)"),
    # --- Valoracion AS ---
    ("ptos_as_per_pica",            None,  1,   "AS por cada pica"),
    ("ptos_as_no_jugo",             None,  -1,  "AS \"-\" (no jugo)"),
    ("ptos_as_sc",                  None,  0,   "AS \"SC\" (sin calificar)"),
]


# ---------------------------------------------------------------------------
# Season payment bands
# (payment_type, position_rank | None, amount, description)
# ---------------------------------------------------------------------------

SEASON_PAYMENTS: list[tuple[str, int | None, float, str]] = [
    # --- Cuota inicial ---
    ("initial_fee",         None, 50.00, "Cuota inicial"),
    # --- Pago semanal por puesto (1 = mejor, 8 = peor) ---
    ("weekly_position",     1,    0.00,  "1o no paga"),
    ("weekly_position",     2,    0.00,  "2o no paga"),
    ("weekly_position",     3,    0.00,  "3o no paga"),
    ("weekly_position",     4,    0.00,  "4o no paga"),
    ("weekly_position",     5,    0.00,  "5o no paga"),
    ("weekly_position",     6,    0.00,  "6o no paga"),
    ("weekly_position",     7,    3.00,  "7o paga 3 EUR"),
    ("weekly_position",     8,    5.00,  "8o (ultimo) paga 5 EUR"),
    # --- Draft invierno ---
    ("winter_draft_change", None, 2.00,  "2 EUR por cada cambio"),
    # --- Premios fin de temporada ---
    ("prize",               1,    200.00, "Premio al 1o"),
    ("prize",               2,    100.00, "Premio al 2o"),
    ("prize",               3,    50.00,  "Premio al 3o"),
]


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

def run(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: psycopg.Connection,
    ctx: MigrationContext,
) -> None:
    """Insert scoring_rules and season_payments for every season in ctx.season_map."""

    if not ctx.season_map:
        raise ValueError(
            "ctx.season_map is empty. "
            "Ensure step_01_seasons ran successfully before this step."
        )

    insert_rule_sql = """
        INSERT INTO scoring_rules (season_id, rule_key, position, value, description)
        VALUES (%(season_id)s, %(rule_key)s, %(position)s, %(value)s, %(description)s)
    """

    insert_payment_sql = """
        INSERT INTO season_payments (season_id, payment_type, position_rank, amount, description)
        VALUES (%(season_id)s, %(payment_type)s, %(position_rank)s, %(amount)s, %(description)s)
    """

    total_rules = 0
    total_payments = 0

    seasons_sorted = sorted(ctx.season_map.items())  # [(name, season_id), ...]

    with pg_conn.cursor() as pg_cur:
        for season_name, season_id in seasons_sorted:

            # --- scoring_rules ---
            rules_for_season = 0
            for rule_key, position, value, description in SCORING_RULES:
                pg_cur.execute(
                    insert_rule_sql,
                    {
                        "season_id": season_id,
                        "rule_key": rule_key,
                        "position": position,
                        "value": Decimal(str(value)),
                        "description": description,
                    },
                )
                rules_for_season += 1

            total_rules += rules_for_season

            # --- season_payments ---
            payments_for_season = 0
            for payment_type, position_rank, amount, description in SEASON_PAYMENTS:
                pg_cur.execute(
                    insert_payment_sql,
                    {
                        "season_id": season_id,
                        "payment_type": payment_type,
                        "position_rank": position_rank,
                        "amount": Decimal(str(amount)),
                        "description": description,
                    },
                )
                payments_for_season += 1

            total_payments += payments_for_season

            log.info(
                "  Season %-12s (id=%d): %d scoring_rules, %d season_payments",
                season_name,
                season_id,
                rules_for_season,
                payments_for_season,
            )

    log.info(
        "Total scoring_rules inserted: %d (%d rules x %d seasons)",
        total_rules,
        len(SCORING_RULES),
        len(ctx.season_map),
    )
    log.info(
        "Total season_payments inserted: %d (%d bands x %d seasons)",
        total_payments,
        len(SEASON_PAYMENTS),
        len(ctx.season_map),
    )
