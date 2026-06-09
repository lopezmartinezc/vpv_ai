"""Retrospective draft analytics.

Powers four admin-only endpoints that look *backwards*:

  1. Draft-by-draft post-mortem (which picks were steals/busts).
  2. Scatter of every historical pick (pick_number vs season points).
  3. Backtest of the scorecard: would today's signals have worked
     in seasons 5..8?
  4. Per-participant "draft IQ" leaderboard.

All four share the same notion of a *slot baseline* — the median total
points scored by players drafted at a given `pick_number` across the
historical seasons. Picks above the baseline are steals; below, busts.

The module is split into:
- pure helpers (`compute_slot_curve`, `tag_pick`, `spearman_*`,
  `aggregate_buckets`) so the logic is unit-testable without a DB;
- a `DraftRetroService` class that runs the SQL and stitches it all
  together.

We keep the SQL deliberately wide (joins matchdays, players, teams,
season_participants) instead of doing N+1 queries — every endpoint
ends up needing the same enrichment.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.stats import scorecard
from src.features.stats.schemas_draft_retro import (
    BacktestPoint,
    BacktestResponse,
    BestPickHighlight,
    DraftRetrospectiveResponse,
    DraftScatterResponse,
    ParticipantIQ,
    ParticipantIQResponse,
    PickPoint,
    RetroPick,
    SignalBucket,
)
from src.features.stats.service_draft import VALID_SEASON_IDS, DraftValueService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without DB)
# ---------------------------------------------------------------------------


def compute_slot_curve(
    picks_with_totals: Sequence[tuple[int, float]],
) -> dict[int, float]:
    """For each pick_number, the median total_points of players drafted there.

    Input: iterable of (pick_number, season_total_points).
    Output: {pick_number: median_total_points}.

    The median is more robust than the mean for the late rounds where
    a handful of jackpot picks distort the average.
    """
    grouped: dict[int, list[float]] = defaultdict(list)
    for pick_number, total in picks_with_totals:
        grouped[pick_number].append(total)
    return {pn: statistics.median(values) for pn, values in grouped.items()}


def tag_pick(delta: float, all_deltas: Sequence[float]) -> str:
    """Tag a pick as steal/bust/normal based on its delta's rank.

    Top quartile of deltas in the same draft → "steal".
    Bottom quartile → "bust". Middle two → "normal".

    Quartiles are computed on the full population to avoid the all-
    deltas-tied edge case where statistics.quantiles raises.
    """
    if not all_deltas:
        return "normal"
    sorted_deltas = sorted(all_deltas)
    if len(sorted_deltas) < 4:
        # Too few picks to bother with quartiles — use median split.
        median = statistics.median(sorted_deltas)
        if delta > median:
            return "steal"
        if delta < median:
            return "bust"
        return "normal"
    q1, _, q3 = statistics.quantiles(sorted_deltas, n=4, method="inclusive")
    if delta >= q3:
        return "steal"
    if delta <= q1:
        return "bust"
    return "normal"


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Return ranks (1..N) with tie-averaging — matches scipy.stats.rankdata.

    Implemented manually so the module stays scipy-free (production
    backend doesn't ship scipy).
    """
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 2) / 2.0  # 1-based average of positions i..j
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def compute_spearman(
    predicted: Sequence[float],
    actual: Sequence[float],
) -> float:
    """Spearman rank correlation = Pearson correlation of ranks.

    Returns 0.0 if there's not enough data or either series is constant.
    """
    if len(predicted) < 3 or len(predicted) != len(actual):
        return 0.0
    rp = _average_ranks(predicted)
    ra = _average_ranks(actual)
    n = len(rp)
    mp = sum(rp) / n
    ma = sum(ra) / n
    num = sum((rp[i] - mp) * (ra[i] - ma) for i in range(n))
    den_p = sum((rp[i] - mp) ** 2 for i in range(n))
    den_a = sum((ra[i] - ma) ** 2 for i in range(n))
    if den_p == 0 or den_a == 0:
        return 0.0  # constant series — correlation undefined
    return num / (den_p * den_a) ** 0.5


def aggregate_buckets(
    points: Sequence[BacktestPoint],
    key: str,  # "predicted_signal" | "predicted_tier"
) -> dict[str, SignalBucket]:
    """Aggregate actual points by signal/tier bucket."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for p in points:
        grouped[getattr(p, key)].append(p.actual_total_points)
    return {
        bucket: SignalBucket(
            n=len(values),
            mean_actual=round(statistics.mean(values), 2),
            median_actual=round(statistics.median(values), 2),
        )
        for bucket, values in grouped.items()
    }


# ---------------------------------------------------------------------------
# Internal dataclasses to ferry SQL rows around
# ---------------------------------------------------------------------------


@dataclass
class _PickRow:
    pick_number: int
    round_number: int
    participant_id: int
    participant_display_name: str
    player_id: int
    player_name: str
    position: str
    team_name: str
    photo_path: str | None
    season_id: int
    season_name: str
    phase: str
    draft_id: int
    season_total_points: float
    season_avg_pts: float
    matchdays_played: int


@dataclass
class _ActualSeason:
    player_id: int
    slug: str
    position: str
    total_points: float
    avg_pts: float
    matchdays_played: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DraftRetroService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ----- Endpoint 1: retrospective -------------------------------------

    async def retrospective(self, draft_id: int) -> DraftRetrospectiveResponse:
        info = await self._get_draft_info(draft_id)

        # All picks in THIS draft, with the player's actual season totals.
        rows = await self._load_picks(draft_ids=[draft_id])
        if not rows:
            return DraftRetrospectiveResponse(
                draft_id=draft_id,
                season_id=info["season_id"],
                season_name=info["season_name"],
                phase=info["phase"],
                n_picks=0,
                picks=[],
            )

        # Slot baseline comes from ALL historical seasons (same phase).
        baseline_rows = await self._load_picks(
            season_ids=VALID_SEASON_IDS,
            phases=[info["phase"]],
        )
        slot_curve = compute_slot_curve(
            [(r.pick_number, r.season_total_points) for r in baseline_rows]
        )

        # Per-pick deltas, then tag relative to this draft only.
        deltas: list[float] = []
        for r in rows:
            base = slot_curve.get(r.pick_number)
            if base is None:
                deltas.append(0.0)
            else:
                deltas.append(r.season_total_points - base)

        picks: list[RetroPick] = []
        for r, delta in zip(rows, deltas, strict=True):
            base = slot_curve.get(r.pick_number)
            picks.append(
                RetroPick(
                    pick_number=r.pick_number,
                    round_number=r.round_number,
                    participant_id=r.participant_id,
                    participant_display_name=r.participant_display_name,
                    player_id=r.player_id,
                    player_name=r.player_name,
                    position=r.position,
                    team_name=r.team_name,
                    photo_path=r.photo_path,
                    season_total_points=round(r.season_total_points, 1),
                    season_avg_pts=round(r.season_avg_pts, 2),
                    matchdays_played=r.matchdays_played,
                    slot_median_total_points=(round(base, 1) if base is not None else None),
                    delta_vs_slot=(round(delta, 1) if base is not None else None),
                    tag=tag_pick(delta, deltas) if base is not None else "normal",
                )
            )

        picks.sort(key=lambda p: p.pick_number)
        return DraftRetrospectiveResponse(
            draft_id=draft_id,
            season_id=info["season_id"],
            season_name=info["season_name"],
            phase=info["phase"],
            n_picks=len(picks),
            picks=picks,
        )

    # ----- Endpoint 2: scatter -------------------------------------------

    async def scatter(
        self,
        season_ids: list[int] | None,
        phases: list[str] | None,
    ) -> DraftScatterResponse:
        sids = season_ids if season_ids else list(VALID_SEASON_IDS)
        phs = phases if phases else ["preseason"]
        rows = await self._load_picks(season_ids=sids, phases=phs)

        points = [
            PickPoint(
                pick_number=r.pick_number,
                round_number=r.round_number,
                total_points=round(r.season_total_points, 1),
                avg_points=round(r.season_avg_pts, 2),
                matchdays_played=r.matchdays_played,
                position=r.position,
                player_id=r.player_id,
                player_name=r.player_name,
                team_name=r.team_name,
                season_id=r.season_id,
                season_name=r.season_name,
                phase=r.phase,
                participant_display_name=r.participant_display_name,
            )
            for r in rows
        ]
        slot_curve = compute_slot_curve([(r.pick_number, r.season_total_points) for r in rows])
        return DraftScatterResponse(
            season_ids=sids,
            phases=phs,
            n_points=len(points),
            points=points,
            slot_curve={k: round(v, 1) for k, v in slot_curve.items()},
        )

    # ----- Endpoint 3: backtest of the scorecard -------------------------

    async def backtest(self, season_id: int) -> BacktestResponse:
        """Replay the scorecard against a completed season.

        For each player who played in `season_id` and had at least one
        prior season of history, project what the scorecard would have
        said BEFORE the season started, then compare with what actually
        happened.
        """
        season_name = await self._get_season_name(season_id)

        # History up to but not including the target season.
        past_sids = [s for s in VALID_SEASON_IDS if s < season_id]
        if not past_sids:
            raise NotFoundError(
                "BacktestData",
                f"No hay temporadas anteriores para backtest de season_id={season_id}",
            )

        # Reuse DraftValueService._load_seasons — it gives us slug-keyed
        # historical aggregates with the penalty fields we need.
        dv = DraftValueService(self.session)
        # We call with current_season_id=highest_past so _load_seasons
        # returns history-only data (no season_id pollution).
        historical = await dv._load_seasons(
            current_season_id=max(past_sids),
            min_games=1,
        )
        history_by_slug: dict[str, list] = defaultdict(list)
        for ps in historical:
            history_by_slug[ps.slug].append(ps)
        for lst in history_by_slug.values():
            lst.sort(key=lambda s: s.season_id)

        actuals = await self._load_actuals(season_id)

        points: list[BacktestPoint] = []
        for actual in actuals:
            hist = history_by_slug.get(actual.slug, [])
            if not hist:
                continue  # rookie — no prediction possible
            last = hist[-1]
            career_avg = statistics.mean(s.avg_pts for s in hist) if hist else last.avg_pts

            # Simplified "ensemble" for backtest: mean(last_season, career).
            # This is intentionally simpler than the production ensemble
            # because we want to isolate the SCORECARD signal, not chase
            # the ensemble model. The scorecard is what's new.
            ensemble = (last.avg_pts + career_avg) / 2

            enrichment = scorecard.enrich(
                position=last.position,
                ensemble_score=ensemble,
                avg_pts=last.avg_pts,
                career_avg_pts=career_avg,
                current_team=last.team_name,  # we lack the real S-season team here
                last_team=last.team_name,
                penalty_goals=last.penalty_goals,
                penalties_missed=last.penalties_missed,
            )

            # Reuse the same signal logic as production.
            availability = last.games_45min / max(last.games, 1)
            consistency = max(
                0.0, 1.0 - (last.std_pts / last.avg_pts if last.avg_pts > 0 else 1.0)
            )
            signal, _ = dv._compute_signal(
                ensemble_score=ensemble,
                career_trend_pct=None,
                availability=availability,
                consistency=consistency,
                seasons_played=len(hist),
                simple_avg=last.avg_pts,
            )

            points.append(
                BacktestPoint(
                    player_id=actual.player_id,
                    player_name=last.display_name,
                    position=last.position,
                    seasons_history=len(hist),
                    predicted_effective_score=enrichment.effective_score,
                    predicted_signal=signal,
                    predicted_tier=enrichment.position_tier,
                    actual_total_points=round(actual.total_points, 1),
                    actual_avg_points=round(actual.avg_pts, 2),
                    actual_matchdays_played=actual.matchdays_played,
                )
            )

        rho = compute_spearman(
            [p.predicted_effective_score for p in points],
            [p.actual_total_points for p in points],
        )

        return BacktestResponse(
            season_id=season_id,
            season_name=season_name,
            n_players=len(points),
            spearman_rank_correlation=round(rho, 3),
            by_signal=aggregate_buckets(points, "predicted_signal"),
            by_tier=aggregate_buckets(points, "predicted_tier"),
            points=sorted(points, key=lambda p: -p.predicted_effective_score),
        )

    # ----- Endpoint 4: per-participant draft IQ --------------------------

    async def participant_iq(
        self,
        phase: str,
        min_seasons: int,
    ) -> ParticipantIQResponse:
        rows = await self._load_picks(
            season_ids=VALID_SEASON_IDS,
            phases=[phase],
        )
        slot_curve = compute_slot_curve([(r.pick_number, r.season_total_points) for r in rows])

        # Group by participant_id. We also key by display_name to identify
        # the same person across seasons (participant_id changes per
        # season but display_name is stable for the same user).
        by_user: dict[str, list[_PickRow]] = defaultdict(list)
        for r in rows:
            by_user[r.participant_display_name].append(r)

        participants: list[ParticipantIQ] = []
        for display_name, user_rows in by_user.items():
            # n_drafts = distinct (season_id, phase) for this user.
            drafts = {(r.season_id, r.phase) for r in user_rows}
            if len(drafts) < min_seasons:
                continue

            deltas: list[tuple[_PickRow, float]] = []
            by_round_acc: dict[int, list[float]] = defaultdict(list)
            for r in user_rows:
                base = slot_curve.get(r.pick_number)
                if base is None:
                    continue
                delta = r.season_total_points - base
                deltas.append((r, delta))
                by_round_acc[r.round_number].append(delta)

            if not deltas:
                continue

            sum_delta = sum(d for _, d in deltas)
            mean_delta = sum_delta / len(deltas)
            best_row, best_delta = max(deltas, key=lambda x: x[1])
            worst_row, worst_delta = min(deltas, key=lambda x: x[1])

            participants.append(
                ParticipantIQ(
                    participant_id=user_rows[0].participant_id,
                    display_name=display_name,
                    n_drafts=len(drafts),
                    total_picks=len(deltas),
                    sum_delta_vs_slot=round(sum_delta, 1),
                    mean_delta_per_pick=round(mean_delta, 2),
                    best_pick=BestPickHighlight(
                        player_name=best_row.player_name,
                        season_name=best_row.season_name,
                        pick_number=best_row.pick_number,
                        round_number=best_row.round_number,
                        delta_vs_slot=round(best_delta, 1),
                    ),
                    worst_pick=BestPickHighlight(
                        player_name=worst_row.player_name,
                        season_name=worst_row.season_name,
                        pick_number=worst_row.pick_number,
                        round_number=worst_row.round_number,
                        delta_vs_slot=round(worst_delta, 1),
                    ),
                    by_round={
                        k: round(statistics.mean(v), 2) for k, v in sorted(by_round_acc.items())
                    },
                )
            )

        participants.sort(key=lambda p: -p.mean_delta_per_pick)
        return ParticipantIQResponse(
            phase=phase,
            min_seasons=min_seasons,
            participants=participants,
        )

    # ------------------------------------------------------------------
    # SQL helpers
    # ------------------------------------------------------------------

    async def _get_draft_info(self, draft_id: int) -> dict:
        result = await self.session.execute(
            text(
                """
                SELECT d.season_id, d.phase, s.name AS season_name
                  FROM drafts d
                  JOIN seasons s ON d.season_id = s.id
                 WHERE d.id = :id
                """
            ),
            {"id": draft_id},
        )
        row = result.first()
        if row is None:
            raise NotFoundError("Draft", draft_id)
        return {
            "season_id": row.season_id,
            "phase": row.phase,
            "season_name": row.season_name,
        }

    async def _get_season_name(self, season_id: int) -> str:
        result = await self.session.execute(
            text("SELECT name FROM seasons WHERE id = :id"),
            {"id": season_id},
        )
        row = result.first()
        if row is None:
            raise NotFoundError("Season", season_id)
        return row.name

    async def _load_picks(
        self,
        *,
        draft_ids: list[int] | None = None,
        season_ids: list[int] | None = None,
        phases: list[str] | None = None,
    ) -> list[_PickRow]:
        """Load draft_picks joined with player+team+actual season totals.

        Filters compose: pass `draft_ids` to scope to one draft, or
        `season_ids`+`phases` for cross-draft analytics.
        """
        clauses: list[str] = []
        params: dict[str, object] = {}
        if draft_ids:
            clauses.append("d.id = ANY(:draft_ids)")
            params["draft_ids"] = draft_ids
        if season_ids:
            clauses.append("d.season_id = ANY(:season_ids)")
            params["season_ids"] = season_ids
        if phases:
            clauses.append("d.phase = ANY(:phases)")
            params["phases"] = phases
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        # season_total_points uses the player's stats for the season the
        # DRAFT belongs to. We aggregate in a subquery to avoid a row
        # explosion when joining matchdays.
        sql = f"""
            WITH season_totals AS (
                SELECT ps.player_id, md.season_id,
                       COALESCE(SUM(ps.pts_total), 0) AS total_pts,
                       COALESCE(AVG(ps.pts_total), 0) AS avg_pts,
                       COUNT(*) AS matchdays_played
                  FROM player_stats ps
                  JOIN matchdays md ON ps.matchday_id = md.id AND md.counts = TRUE
                 GROUP BY ps.player_id, md.season_id
            )
            SELECT dp.pick_number, dp.round_number,
                   dp.participant_id, sp.display_name AS participant_display_name,
                   p.id AS player_id, p.display_name AS player_name,
                   p.photo_path,
                   COALESCE(ps_pos.position, 'MED') AS position,
                   COALESCE(t.name, '') AS team_name,
                   d.season_id, s.name AS season_name, d.phase, d.id AS draft_id,
                   COALESCE(st.total_pts, 0) AS season_total_points,
                   COALESCE(st.avg_pts, 0) AS season_avg_pts,
                   COALESCE(st.matchdays_played, 0) AS matchdays_played
              FROM draft_picks dp
              JOIN drafts d ON dp.draft_id = d.id
              JOIN seasons s ON d.season_id = s.id
              JOIN season_participants sp ON dp.participant_id = sp.id
              JOIN players p ON dp.player_id = p.id
              LEFT JOIN teams t ON p.team_id = t.id
              LEFT JOIN season_totals st ON st.player_id = dp.player_id AND st.season_id = d.season_id
              LEFT JOIN LATERAL (
                  SELECT ps.position
                    FROM player_stats ps
                    JOIN matchdays md ON ps.matchday_id = md.id
                   WHERE ps.player_id = dp.player_id AND md.season_id = d.season_id
                   ORDER BY md.number DESC
                   LIMIT 1
              ) ps_pos ON TRUE
            {where}
             ORDER BY d.season_id, dp.pick_number
        """
        result = await self.session.execute(text(sql), params)
        return [
            _PickRow(
                pick_number=r.pick_number,
                round_number=r.round_number,
                participant_id=r.participant_id,
                participant_display_name=r.participant_display_name,
                player_id=r.player_id,
                player_name=r.player_name,
                position=r.position,
                team_name=r.team_name,
                photo_path=r.photo_path,
                season_id=r.season_id,
                season_name=r.season_name,
                phase=r.phase,
                draft_id=r.draft_id,
                season_total_points=float(r.season_total_points or 0),
                season_avg_pts=float(r.season_avg_pts or 0),
                matchdays_played=int(r.matchdays_played or 0),
            )
            for r in result.all()
        ]

    async def _load_actuals(self, season_id: int) -> list[_ActualSeason]:
        """Total/avg points and matchdays played per player for a season."""
        result = await self.session.execute(
            text(
                """
                SELECT p.id AS player_id, p.slug,
                       COALESCE(ps.position, 'MED') AS position,
                       COALESCE(SUM(ps.pts_total), 0) AS total_pts,
                       COALESCE(AVG(ps.pts_total), 0) AS avg_pts,
                       COUNT(*) AS matchdays_played
                  FROM player_stats ps
                  JOIN players p ON ps.player_id = p.id
                  JOIN matchdays md ON ps.matchday_id = md.id AND md.counts = TRUE
                 WHERE md.season_id = :sid
                 GROUP BY p.id, p.slug, ps.position
                """
            ),
            {"sid": season_id},
        )
        return [
            _ActualSeason(
                player_id=r.player_id,
                slug=r.slug,
                position=r.position,
                total_points=float(r.total_pts or 0),
                avg_pts=float(r.avg_pts or 0),
                matchdays_played=int(r.matchdays_played or 0),
            )
            for r in result.all()
        ]
