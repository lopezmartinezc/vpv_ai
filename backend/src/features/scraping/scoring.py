from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from src.features.scraping.parsers import PlayerMatchdayStats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PointsBreakdown:
    """Calculated fantasy points for a player in a single matchday.

    Every field is an integer number of points (positive or negative).
    ``pts_total`` is the authoritative sum; individual fields are kept for
    transparency / audit purposes.
    """

    pts_play: int
    pts_starter: int
    pts_result: int
    pts_clean_sheet: int
    pts_goals: int
    pts_penalty_goals: int
    pts_assists: int
    pts_penalties_saved: int
    pts_woodwork: int
    pts_penalties_won: int
    pts_penalties_missed: int
    pts_own_goals: int
    pts_yellow: int
    pts_red: int
    pts_pen_committed: int
    pts_marca: int
    pts_as: int
    pts_marca_as: int
    pts_total: int


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------


class ScoringEngine:
    """Calculates fantasy points from raw scraped stats and DB scoring rules.

    This class NEVER hardcodes scoring values.  All point values are read
    from the ``scoring_rules`` table via the *rules* dict passed at
    construction.

    Rules dict format
    -----------------
    The dict is keyed by ``rule_key`` (matches ``scoring_rules.rule_key``).
    Each value is itself a dict mapping ``position | None`` → ``Decimal``.

    Example::

        {
            "ptos_gol": {
                None: None,      # no global default — position is required
                "POR": Decimal("10"),
                "DEF": Decimal("8"),
                "MED": Decimal("7"),
                "DEL": Decimal("5"),
            },
            "ptos_jugar": {None: Decimal("1")},
        }

    A ``None`` key (position=None) represents a *global* rule that applies
    regardless of position.  When a position-specific value exists it takes
    precedence over the global one.
    """

    def __init__(self, rules: dict[str, dict[str | None, Decimal | None]]) -> None:
        self._rules = rules

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, key: str, position: str | None = None) -> int:
        """Return the integer rule value for *key*, position-aware.

        Lookup order:
        1. Position-specific value (``position`` key in the inner dict).
        2. Global value (``None`` key in the inner dict).
        3. 0 — safe default so missing rules don't crash.
        """
        rule = self._rules.get(key, {})
        if position is not None and position in rule:
            val = rule[position]
            if val is not None:
                return int(val)
        global_val = rule.get(None)
        if global_val is not None:
            return int(global_val)
        return 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, stats: PlayerMatchdayStats, position: str) -> PointsBreakdown:
        """Calculate points breakdown for *stats* at *position*.

        IMPORTANT: *position* must be ``player_stats.position`` (the position
        in which the player actually featured that matchday), NOT
        ``players.position`` (their registered position).

        Parameters
        ----------
        stats:
            Raw scraped stats for one matchday.
        position:
            Matchday position: "POR" | "DEF" | "MED" | "DEL".

        Returns
        -------
        PointsBreakdown with all sub-totals filled in and ``pts_total``
        equal to their sum.
        """
        if not stats.played:
            # Player did not participate — all scoring components are zero
            # except possibly the media ratings which can carry a "no jugó"
            # penalty.
            pts_marca = self._calc_marca(stats.marca_rating)
            pts_as = self._calc_as(stats.as_picas)
            pts_marca_as = pts_marca + pts_as
            return PointsBreakdown(
                pts_play=0,
                pts_starter=0,
                pts_result=0,
                pts_clean_sheet=0,
                pts_goals=0,
                pts_penalty_goals=0,
                pts_assists=0,
                pts_penalties_saved=0,
                pts_woodwork=0,
                pts_penalties_won=0,
                pts_penalties_missed=0,
                pts_own_goals=0,
                pts_yellow=0,
                pts_red=0,
                pts_pen_committed=0,
                pts_marca=pts_marca,
                pts_as=pts_as,
                pts_marca_as=pts_marca_as,
                pts_total=pts_marca_as,
            )

        # ------------------------------------------------------------------
        # 1. Playing bonus
        # ------------------------------------------------------------------
        pts_play = self._get("ptos_jugar")

        # ------------------------------------------------------------------
        # 2. Starter bonus
        #    A player is a starter when: event == "Salida" (came off the bench)
        #    means they STARTED and were substituted out, OR they played 90 mins
        #    with no substitution event.
        # ------------------------------------------------------------------
        is_starter = stats.event == "Salida" or stats.event is None
        pts_starter = self._get("ptos_titular") if is_starter else 0

        # ------------------------------------------------------------------
        # 3. Match result
        # ------------------------------------------------------------------
        if stats.result == 2:
            pts_result = self._get("ptos_resultado_win")
        elif stats.result == 1:
            pts_result = self._get("ptos_resultado_draw")
        else:
            pts_result = self._get("ptos_resultado_loss")

        # ------------------------------------------------------------------
        # 4. Clean sheet / goals conceded
        # ------------------------------------------------------------------
        pts_clean_sheet = self._calc_clean_sheet(
            position=position,
            goals_against=stats.goals_against,
            minutes_played=stats.minutes_played,
        )

        # ------------------------------------------------------------------
        # 5. Goals (regular) — position-specific
        # ------------------------------------------------------------------
        pts_goals = stats.goals * self._get("ptos_gol", position)

        # ------------------------------------------------------------------
        # 6. Penalty goals (global)
        # ------------------------------------------------------------------
        pts_penalty_goals = stats.penalty_goals * self._get("ptos_gol_p")

        # ------------------------------------------------------------------
        # 7. Assists (global)
        # ------------------------------------------------------------------
        pts_assists = stats.assists * self._get("ptos_asis")

        # ------------------------------------------------------------------
        # 8. Penalties saved (global rule; legacy code applied only to POR
        #    but the DB rule is global — follow DB)
        # ------------------------------------------------------------------
        pts_penalties_saved = stats.penalties_saved * self._get("ptos_pen_par")

        # ------------------------------------------------------------------
        # 9. Woodwork (global)
        # ------------------------------------------------------------------
        pts_woodwork = stats.woodwork * self._get("ptos_tiro_palo")

        # ------------------------------------------------------------------
        # 10. Penalties won / committed (global)
        # ------------------------------------------------------------------
        pts_penalties_won = stats.penalties_won * self._get("ptos_pen_for")
        pts_pen_committed = stats.penalties_committed * self._get("ptos_pen_com")

        # ------------------------------------------------------------------
        # 11. Missed penalties (global, negative value in DB)
        # ------------------------------------------------------------------
        pts_penalties_missed = stats.penalties_missed * self._get("ptos_pen_fall")

        # ------------------------------------------------------------------
        # 12. Own goals (global, negative value in DB)
        # ------------------------------------------------------------------
        pts_own_goals = stats.own_goals * self._get("ptos_gol_pp")

        # ------------------------------------------------------------------
        # 13. Yellow card (global, negative value in DB)
        # ------------------------------------------------------------------
        pts_yellow = int(stats.yellow_card) * self._get("ptos_ama")

        # ------------------------------------------------------------------
        # 14. Red card / double yellow (global, negative value in DB)
        # ------------------------------------------------------------------
        pts_red = self._get("ptos_roja") if (stats.double_yellow or stats.red_card) else 0

        # ------------------------------------------------------------------
        # 15-17. Media ratings
        # ------------------------------------------------------------------
        pts_marca = self._calc_marca(stats.marca_rating)
        pts_as = self._calc_as(stats.as_picas)
        pts_marca_as = pts_marca + pts_as

        # ------------------------------------------------------------------
        # 18. Total
        # ------------------------------------------------------------------
        pts_total = (
            pts_play
            + pts_starter
            + pts_result
            + pts_clean_sheet
            + pts_goals
            + pts_penalty_goals
            + pts_assists
            + pts_penalties_saved
            + pts_woodwork
            + pts_penalties_won
            + pts_penalties_missed
            + pts_own_goals
            + pts_yellow
            + pts_red
            + pts_pen_committed
            + pts_marca_as
        )

        breakdown = PointsBreakdown(
            pts_play=pts_play,
            pts_starter=pts_starter,
            pts_result=pts_result,
            pts_clean_sheet=pts_clean_sheet,
            pts_goals=pts_goals,
            pts_penalty_goals=pts_penalty_goals,
            pts_assists=pts_assists,
            pts_penalties_saved=pts_penalties_saved,
            pts_woodwork=pts_woodwork,
            pts_penalties_won=pts_penalties_won,
            pts_penalties_missed=pts_penalties_missed,
            pts_own_goals=pts_own_goals,
            pts_yellow=pts_yellow,
            pts_red=pts_red,
            pts_pen_committed=pts_pen_committed,
            pts_marca=pts_marca,
            pts_as=pts_as,
            pts_marca_as=pts_marca_as,
            pts_total=pts_total,
        )

        logger.debug(
            "ScoringEngine.calculate: pos=%s played=%s minutes=%d → pts_total=%d",
            position,
            stats.played,
            stats.minutes_played,
            pts_total,
        )
        return breakdown

    # ------------------------------------------------------------------
    # Private calculators
    # ------------------------------------------------------------------

    def _calc_clean_sheet(self, position: str, goals_against: int, minutes_played: int) -> int:
        """Calculate clean-sheet / goals-conceded bonus/penalty.

        Rules (all values read from DB):
        - POR:
            - 0 goals & minutes >= ptos_imbatibilidad_min(POR) → ptos_imbatibilidad_clean(POR)
            - 1 goal → ptos_imbatibilidad_1gol(POR)  [usually 0]
            - >1 goal → goals_against * ptos_imbatibilidad_per_gol(POR)  [usually -1/goal]
        - DEF:
            - 0 goals & minutes >= ptos_imbatibilidad_min(DEF) → ptos_imbatibilidad_clean(DEF)
            - otherwise → 0
        - MED / DEL: no clean-sheet rule → 0
        """
        if position == "POR":
            min_minutes = self._get("ptos_imbatibilidad_min", "POR")
            if goals_against == 0 and minutes_played >= min_minutes:
                return self._get("ptos_imbatibilidad_clean", "POR")
            elif goals_against == 1:
                return self._get("ptos_imbatibilidad_1gol", "POR")
            elif goals_against > 1:
                return goals_against * self._get("ptos_imbatibilidad_per_gol", "POR")
            return 0

        elif position == "DEF":
            min_minutes = self._get("ptos_imbatibilidad_min", "DEF")
            if goals_against == 0 and minutes_played >= min_minutes:
                return self._get("ptos_imbatibilidad_clean", "DEF")
            return 0

        # MED / DEL — no clean-sheet rule
        return 0

    def _calc_marca(self, marca_rating: str | None) -> int:
        """Convert raw Marca rating string to integer points.

        Mapping (all values from DB):
        - "★"    → ptos_marca_1
        - "★★"   → ptos_marca_2
        - "★★★"  → ptos_marca_3
        - "★★★★" → ptos_marca_4
        - "-"    → ptos_marca_no_jugo
        - "SC"   → ptos_marca_sc
        - None   → 0
        """
        if marca_rating is None:
            return 0
        star_map = {
            "\u2605": "ptos_marca_1",
            "\u2605\u2605": "ptos_marca_2",
            "\u2605\u2605\u2605": "ptos_marca_3",
            "\u2605\u2605\u2605\u2605": "ptos_marca_4",
        }
        if marca_rating in star_map:
            return self._get(star_map[marca_rating])
        if marca_rating == "-":
            return self._get("ptos_marca_no_jugo")
        if marca_rating == "SC":
            return self._get("ptos_marca_sc")
        return 0

    def _calc_as(self, as_picas: str | None) -> int:
        """Convert raw AS picas string to integer points.

        When ``as_picas`` is a numeric string the player received that many
        picas; each is worth ``ptos_as_per_pica`` points.
        Special strings "-" (no jugó) and "SC" are handled via separate rules.
        """
        if as_picas is None:
            return 0
        if as_picas == "-":
            return self._get("ptos_as_no_jugo")
        if as_picas == "SC":
            return self._get("ptos_as_sc")
        try:
            count = int(as_picas)
            return count * self._get("ptos_as_per_pica")
        except ValueError:
            return 0
