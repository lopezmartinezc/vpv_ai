"""Draft value predictions using backtested models.

Models ranked by Spearman correlation (backtest across 3 seasons):

  V  Ensemble diverso  0.718  ← BEST overall (main ranking)
  R  Team quality       0.713
  W  Position specific  0.713
  H  2nd half form      0.712
  I  Productivity       0.712
  U  Ensemble top3      0.712
  A  Simple average     0.711  ← baseline
  K  Minutes stability  0.710

For winter draft (with partial season data):
  W1 Winter simple      0.926  ← BEST winter
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.stats.schemas_draft import DraftValuePlayer, DraftValueResponse
from src.features.stats.scorecard import (
    REPLACEMENT_RANK,
    is_bench_risk,
    is_likely_penalty_taker,
    is_mover,
    is_peak_year,
    tier_for,
)

logger = logging.getLogger(__name__)

# --- Early-season blend (Liga draft happens at 4-8 matchdays) -------------
# Empirical-Bayes shrinkage of the current-season average toward the
# historical prior. Weight on the current signal = n / (n + k). k=4 was
# picked by an offline backtest over 6 complete seasons (real data): it
# lifted Spearman vs rest-of-season points from ~0.76 (history-only, the
# previous behaviour) to ~0.83 at K=4..8 matchdays, beating both the
# history-only and current-only extremes. The optimum is a flat plateau
# over k in [2, 6].
DRAFT_SHRINKAGE_K = 4
# A current-season player needs at least this many games to be a candidate
# (below it the 4-8 game sample is pure noise).
CURRENT_MIN_GAMES = 2
# A prior season needs at least this many games to be used as a stable prior.
HISTORY_MIN_GAMES = 3
# How many prior league seasons to pull as history (plus the current one).
N_HISTORY_SEASONS = 4


@dataclass
class _Projection:
    ensemble_score: float
    career_ensemble: float
    weight_current: float
    simple_avg: float
    second_half_score: float | None
    productivity_score: float
    stability_score: float
    trend_score: float | None
    career_trend_pct: float | None


def project_value(
    *,
    hist: list[_PlayerSeason],
    current: _PlayerSeason | None,
    k: float = DRAFT_SHRINKAGE_K,
) -> _Projection:
    """Blend the historical ensemble prediction with the current-season
    (partial) average using empirical-Bayes shrinkage.

    ``hist`` is the player's prior seasons oldest->newest; ``current`` is
    the current partial season, or ``None`` in the preseason (no current
    stats). Returns the blended ``ensemble_score`` plus the pre-blend
    ``career_ensemble``, the shrinkage ``weight_current`` and the
    informational component scores. With no history the projection is the
    current average (weight 1.0); with no current data it is the pure
    historical ensemble (weight 0.0). The caller must not pass both empty.
    """
    # --- Component models from history (informational + career ensemble) ---
    # `base` is the reference used when there's no history (falls back to the
    # current season); the `not hist` path is only reachable with current
    # present, so base is never None.
    base = hist[-1] if hist else current
    assert base is not None, "project_value requires history or current data"

    simple_avg_career = base.avg_pts

    second_half_score: float | None = None
    if hist and hist[-1].second_half_avg > 0:
        second_half_score = hist[-1].second_half_avg * 0.6 + hist[-1].avg_pts * 0.4
    elif hist:
        second_half_score = hist[-1].avg_pts

    productivity_score = base.avg_pts
    if base.minutes > 500:
        ga_per90 = ((base.goals + base.assists) / base.minutes) * 90
        if ga_per90 > 0.5:
            productivity_score = base.avg_pts * (1 + (ga_per90 - 0.5) * 0.3)

    if hist:
        starter_rates = [s.games_45min / max(s.games, 1) for s in hist]
        career_avg = statistics.mean(s.avg_pts for s in hist)
        stability_score = career_avg * (0.8 + statistics.mean(starter_rates) * 0.4)
    else:
        stability_score = base.avg_pts * (0.8 + (base.games_45min / max(base.games, 1)) * 0.4)

    trend_score: float | None = None
    career_trend_pct: float | None = None
    if len(hist) >= 2 and hist[-2].avg_pts > 0:
        career_trend_pct = (hist[-1].avg_pts - hist[-2].avg_pts) / hist[-2].avg_pts
        trend_score = statistics.mean(s.avg_pts for s in hist) * (1 + career_trend_pct * 0.5)
    elif hist:
        trend_score = hist[-1].avg_pts

    components = [simple_avg_career, stability_score]
    if trend_score is not None:
        components.append(trend_score)
    if second_half_score is not None:
        components.append(second_half_score)
    career_ensemble = statistics.mean(components)

    # --- Shrinkage blend with the current partial season ---
    if current is None:
        # Preseason / no current data → pure historical projection.
        weight_current = 0.0
        ensemble_score = career_ensemble
        blended_simple = simple_avg_career
    elif not hist:
        weight_current = 1.0
        ensemble_score = current.avg_pts
        blended_simple = current.avg_pts
    else:
        n_cur = current.games
        weight_current = n_cur / (n_cur + k) if (n_cur + k) > 0 else 0.0
        ensemble_score = career_ensemble * (1 - weight_current) + current.avg_pts * weight_current
        blended_simple = (
            simple_avg_career * (1 - weight_current) + current.avg_pts * weight_current
        )

    return _Projection(
        ensemble_score=ensemble_score,
        career_ensemble=career_ensemble,
        weight_current=weight_current,
        simple_avg=blended_simple,
        second_half_score=second_half_score,
        productivity_score=productivity_score,
        stability_score=stability_score,
        trend_score=trend_score,
        career_trend_pct=career_trend_pct,
    )


@dataclass
class _PlayerSeason:
    slug: str
    display_name: str
    position: str
    season_id: int
    season_name: str
    games: int
    games_45min: int
    avg_pts: float
    total_pts: float
    std_pts: float
    media_pts: float  # points from Marca/AS ratings (pts_marca_as sum)
    marca_avg: float | None
    as_avg: float | None
    goals: int  # open-play + penalty
    assists: int
    minutes: int
    second_half_avg: float
    team_name: str
    photo_path: str | None
    player_id: int
    # Penalty signals — needed by the scorecard heuristic for DEL
    # (≥2 attempts last season → likely penalty taker next season).
    penalty_goals: int
    penalties_missed: int


@dataclass
class _RosterPlayer:
    """A draftable player of the target season (from the ``players`` table).

    Seeds the draft board so it works PRESEASON: identity, current team and
    position come from here (not from historical stats), which is what lets
    the new/team-change/position-change flags work before any matchday.
    """

    player_id: int
    slug: str
    display_name: str
    position: str
    photo_path: str | None
    team_name: str


class DraftValueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_draft_values(
        self,
        season_id: int,
        min_games: int = CURRENT_MIN_GAMES,
    ) -> DraftValueResponse:
        """Compute the draft board for every draftable player of the season.

        Seeded from the SEASON ROSTER (``players`` table), so it works in the
        PRESEASON too (0 matchdays): players with prior-season history get a
        cold-start projection, brand-new players appear flagged with no value,
        and once the season starts the current-season stats blend in.

        ``min_games`` gates the BLEND, not appearance: a current sample below
        it is treated as too thin to trust (projection falls back to history),
        but the player still shows. Admin manual overrides replace the
        projection where set.
        """

        # Load data (SQL load floor kept at 1 so the current partial season
        # is included; candidate/history filtering happens below).
        season_info = await self._get_season_info(season_id)
        roster = await self._load_roster(season_id)
        overrides = await self._load_overrides(season_id)
        all_data = await self._load_seasons(season_id, min_games=1)
        current_data = [ps for ps in all_data if ps.season_id == season_id]
        history_data = [ps for ps in all_data if ps.season_id != season_id]

        # Organize. all_data is ordered by (slug, season_id) from the query,
        # so history[slug] stays ascending and hist[-1] is the most recent.
        history: dict[str, list[_PlayerSeason]] = defaultdict(list)
        for ps in history_data:
            history[ps.slug].append(ps)

        current_map: dict[str, _PlayerSeason] = {}
        for ps in current_data:
            current_map[ps.slug] = ps

        # "Matchdays played" = how much current-season signal we actually have.
        # Pre-draft (matchday_current < matchday_start) the league formula goes
        # negative, so fall back to the count of current-season matchdays that
        # have scraped stats (which includes the pre-draft ones we now blend).
        league_md = season_info["matchday_current"] - season_info["matchday_start"]
        md_played = max(league_md, int(season_info.get("scraped_matchdays") or 0))
        is_winter = md_played >= 19  # informational label only; blend always applies

        # Matchdays left in the season — for durability-adjusted projections.
        md_end = season_info.get("matchday_end")
        remaining_md = max(0, int(md_end) - int(season_info["matchday_current"])) if md_end else 0

        results: list[DraftValuePlayer] = []

        # Iterate the ROSTER (every draftable player), not just those with
        # current-season stats — that's what makes the board work preseason.
        for rp in roster:
            slug = rp.slug
            current = current_map.get(slug)
            # Thin current sample → don't trust the blend, but keep the player.
            if current is not None and current.games < min_games:
                current = None
            # Only reasonably-sampled prior seasons make a stable prior.
            hist = [h for h in history.get(slug, []) if h.games >= HISTORY_MIN_GAMES]
            seasons_played = len(hist) + (1 if current is not None else 0)

            proj = (
                project_value(hist=hist, current=current, k=DRAFT_SHRINKAGE_K)
                if (current is not None or hist)
                else None
            )
            # Reference for display stats: current preferred, else last season.
            ref = current if current is not None else (hist[-1] if hist else None)

            auto_projection = round(proj.ensemble_score, 2) if proj is not None else None
            ensemble_score = proj.ensemble_score if proj is not None else 0.0
            simple_avg = proj.simple_avg if proj is not None else 0.0
            second_half_score = proj.second_half_score if proj is not None else None
            productivity_score = proj.productivity_score if proj is not None else 0.0
            stability_score = proj.stability_score if proj is not None else 0.0
            trend_score = proj.trend_score if proj is not None else None
            career_trend_pct = proj.career_trend_pct if proj is not None else None
            weight_current = proj.weight_current if proj is not None else 0.0

            second_half_avg = (
                hist[-1].second_half_avg if (hist and hist[-1].second_half_avg > 0) else None
            )

            availability = ref.games_45min / max(ref.games, 1) if ref else 0.0

            # F2: points reliability (event vs media) over all available seasons.
            seasons_for_share = ([current] if current is not None else []) + hist
            career_total = sum(s.total_pts for s in seasons_for_share)
            career_media = sum(s.media_pts for s in seasons_for_share)
            event_share = (
                max(0.0, min(1.0, (career_total - career_media) / career_total))
                if career_total > 0
                else None
            )

            cv = ref.std_pts / ref.avg_pts if (ref and ref.avg_pts > 0) else 1.0
            consistency = max(0, 1 - cv)

            # === Manual override → effective value (what VORP ranks on) ===
            manual_value, note = overrides.get(rp.player_id, (None, None))
            effective_value = manual_value if manual_value is not None else auto_projection

            # F2: durability — expected games + rest-of-season points.
            exp_games_remaining = round(remaining_md * availability, 1)
            proj_rest_points = (
                round(effective_value * exp_games_remaining, 1)
                if effective_value is not None
                else None
            )

            marca = (
                current.marca_avg
                if (current is not None and current.marca_avg is not None)
                else (hist[-1].marca_avg if hist else None)
            )
            as_val = (
                current.as_avg
                if (current is not None and current.as_avg is not None)
                else (hist[-1].as_avg if hist else None)
            )

            # === Role-change flags (roster vs most-recent prior season) ===
            is_new = not hist
            team_changed = bool(hist) and is_mover(rp.team_name, hist[-1].team_name)
            position_changed = bool(hist) and rp.position != hist[-1].position

            # === Risk flags (scorecard, from history) ===
            career_avg = statistics.mean(h.avg_pts for h in hist) if hist else None
            peak_year = bool(hist) and is_peak_year(hist[-1].avg_pts, career_avg)
            penalty_taker = bool(hist) and is_likely_penalty_taker(
                rp.position, hist[-1].penalty_goals, hist[-1].penalties_missed
            )
            # Bench risk is a durability/role trait, so judge it from the last
            # COMPLETE season (history) — not the partial current one, whose
            # 1-8 game counts are all below the 22-game threshold and would flag
            # every starter (e.g. an established keeper after matchday 1).
            # No history → can't assess durability (the player is already
            # flagged NUEVO), so don't flag.
            if hist:
                h = hist[-1]
                hist_availability = h.games_45min / max(h.games, 1)
                bench_risk = is_bench_risk(hist_availability, h.games)
            else:
                bench_risk = False

            signal, reasons = self._compute_signal(
                ensemble_score=ensemble_score,
                career_trend_pct=career_trend_pct,
                availability=availability,
                consistency=consistency,
                seasons_played=seasons_played,
                simple_avg=simple_avg,
            )

            results.append(
                DraftValuePlayer(
                    player_id=rp.player_id,
                    slug=rp.slug,
                    display_name=rp.display_name,
                    team_name=rp.team_name,
                    position=rp.position,
                    photo_path=rp.photo_path,
                    games_played=ref.games if ref else 0,
                    seasons_played=seasons_played,
                    avg_points=round(ref.avg_pts, 2) if ref else 0.0,
                    total_points=round(ref.total_pts, 1) if ref else 0.0,
                    ensemble_score=round(ensemble_score, 2),
                    simple_avg=round(simple_avg, 2),
                    second_half_score=round(second_half_score, 2) if second_half_score else None,
                    productivity_score=round(productivity_score, 2),
                    stability_score=round(stability_score, 2),
                    trend_score=round(trend_score, 2) if trend_score else None,
                    career_trend_pct=round(career_trend_pct, 3) if career_trend_pct else None,
                    marca_avg=round(marca, 2) if marca else None,
                    as_avg=round(as_val, 2) if as_val else None,
                    availability=round(availability, 2),
                    consistency=round(consistency, 2),
                    second_half_avg=round(second_half_avg, 2) if second_half_avg else None,
                    goals=ref.goals if ref else 0,
                    assists=ref.assists if ref else 0,
                    signal=signal,
                    signal_reasons=reasons,
                    weight_current=round(weight_current, 2),
                    event_share=round(event_share, 2) if event_share is not None else None,
                    exp_games_remaining=exp_games_remaining,
                    proj_rest_points=proj_rest_points,
                    auto_projection=auto_projection,
                    manual_value=round(manual_value, 2) if manual_value is not None else None,
                    note=note,
                    effective_value=round(effective_value, 2)
                    if effective_value is not None
                    else None,
                    is_new=is_new,
                    team_changed=team_changed,
                    position_changed=position_changed,
                    is_peak_year=peak_year,
                    is_penalty_taker=penalty_taker,
                    is_bench_risk=bench_risk,
                    position_tier=(tier_for(rp.position, simple_avg) if hist else None),
                )
            )

        # === Draft board: VORP (value over positional replacement) ===
        # Compare positions on one axis: subtract each position's replacement
        # level (the effective value of the Nth-best player at that position)
        # from the player's EFFECTIVE value (manual override, else projection).
        # Players with no effective value (brand-new, no manual value) don't
        # rank and keep vorp=None.
        by_pos: dict[str, list[DraftValuePlayer]] = defaultdict(list)
        for r in results:
            by_pos[r.position].append(r)
        for pos, plist in by_pos.items():
            ranked = sorted(
                (p for p in plist if p.effective_value is not None),
                key=lambda p: p.effective_value or 0.0,
                reverse=True,
            )
            if not ranked:
                continue
            repl_rank = REPLACEMENT_RANK.get(pos, len(ranked))
            idx = min(repl_rank, len(ranked) - 1)
            replacement = ranked[idx].effective_value or 0.0
            for rank, p in enumerate(ranked, start=1):
                p.replacement_level = round(replacement, 2)
                p.vorp = round((p.effective_value or 0.0) - replacement, 2)
                p.position_rank = rank

        # Sort by VORP (cross-position); no-value players sort last.
        results.sort(
            key=lambda p: (p.vorp if p.vorp is not None else -1e9, p.ensemble_score),
            reverse=True,
        )

        # Global draft order (ADP): 1-based rank across all positions for
        # players that actually have a VORP. Feeds the estimated round.
        overall = 0
        for p in results:
            if p.vorp is not None:
                overall += 1
                p.overall_rank = overall

        # Season-level summary of how much the current partial season weighs
        # for a typical full-window candidate (n = md_played).
        typical_w = md_played / (md_played + DRAFT_SHRINKAGE_K) if md_played > 0 else 0.0

        return DraftValueResponse(
            season_id=season_id,
            season_name=season_info["name"],
            matchdays_played=md_played,
            draft_type="winter" if is_winter else "preseason",
            peso_historico=round(1 - typical_w, 2),
            model_info={
                "ensemble_score": (
                    f"Ensemble + blend actual (shrinkage k={DRAFT_SHRINKAGE_K}, "
                    "Spearman ~0.83 a 4-8 jornadas) — MEJOR ranking"
                ),
                "simple_avg": "Media (histórico ⊕ actual, ponderada por muestra)",
                "second_half_score": "Forma 2a mitad (momentum)",
                "productivity_score": "G+A per 90 — productividad ofensiva",
                "stability_score": "Minutos estables — seguridad",
                "trend_score": "Tendencia interanual — mejora o empeora",
            },
            participant_count=int(season_info.get("participant_count") or 0),
            players=results,
        )

    def _compute_signal(
        self,
        *,
        ensemble_score: float,
        career_trend_pct: float | None,
        availability: float,
        consistency: float,
        seasons_played: int,
        simple_avg: float,
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []

        # Positive signals
        if simple_avg > 0 and ensemble_score > simple_avg * 1.05:
            reasons.append(f"Ensemble +{(ensemble_score / simple_avg - 1) * 100:.0f}% vs media")
        if career_trend_pct and career_trend_pct > 0.1:
            reasons.append(f"Tendencia +{career_trend_pct * 100:.0f}%")
        if availability > 0.85:
            reasons.append("Alta disponibilidad")
        if consistency > 0.6:
            reasons.append("Consistente")
        if seasons_played >= 3:
            reasons.append(f"{seasons_played} temporadas (fiable)")

        # Negative signals
        if career_trend_pct and career_trend_pct < -0.15:
            reasons.append(f"En declive {career_trend_pct * 100:.0f}%")
        if availability < 0.6:
            reasons.append("Poca disponibilidad")
        if consistency < 0.3:
            reasons.append("Muy volatil")
        if seasons_played == 1:
            reasons.append("Sin historial (riesgo)")

        # Determine signal
        positives = sum(
            1 for r in reasons if not r.startswith(("En declive", "Poca", "Muy", "Sin"))
        )
        negatives = sum(1 for r in reasons if r.startswith(("En declive", "Poca", "Muy", "Sin")))

        if positives >= 3 and negatives == 0:
            return "strong_buy", reasons
        if positives >= 2 and negatives <= 1:
            return "buy", reasons
        if negatives >= 2:
            return "avoid", reasons
        return "hold", reasons

    async def _get_season_info(self, season_id: int) -> dict:
        result = await self.session.execute(
            text(
                "SELECT s.name, s.matchday_start, s.matchday_current, s.matchday_end, "
                "       (SELECT COUNT(*) FROM season_participants sp "
                "        WHERE sp.season_id = s.id) AS participant_count, "
                "       (SELECT COUNT(DISTINCT ps.matchday_id) "
                "        FROM player_stats ps JOIN matchdays md ON ps.matchday_id = md.id "
                "        WHERE md.season_id = s.id) AS scraped_matchdays "
                "FROM seasons s WHERE s.id = :id"
            ),
            {"id": season_id},
        )
        row = result.one()
        return {
            "name": row.name,
            "matchday_start": row.matchday_start,
            "matchday_current": row.matchday_current,
            "matchday_end": row.matchday_end,
            "participant_count": row.participant_count,
            "scraped_matchdays": row.scraped_matchdays,
        }

    async def _load_roster(self, season_id: int) -> list[_RosterPlayer]:
        """All DRAFTABLE players of the season (from ``players``). Available
        preseason — this is what seeds the board before any matchday.

        Only ``is_available`` players: sync-rosters soft-deactivates anyone
        gone from every squad (left the league), and a departed player must
        not appear on the draft board.
        """
        result = await self.session.execute(
            text(
                "SELECT p.id, p.slug, p.display_name, p.position, p.photo_path, "
                "       t.name AS team_name "
                "FROM players p JOIN teams t ON p.team_id = t.id "
                "WHERE p.season_id = :sid AND p.is_available = TRUE "
                "ORDER BY p.slug"
            ),
            {"sid": season_id},
        )
        return [
            _RosterPlayer(
                player_id=r.id,
                slug=r.slug,
                display_name=r.display_name,
                position=r.position,
                photo_path=r.photo_path,
                team_name=r.team_name or "",
            )
            for r in result.all()
        ]

    async def _load_overrides(self, season_id: int) -> dict[int, tuple[float | None, str | None]]:
        """player_id → (manual_value, note) admin overrides for the season."""
        result = await self.session.execute(
            text(
                "SELECT player_id, manual_value, note "
                "FROM draft_value_overrides WHERE season_id = :sid"
            ),
            {"sid": season_id},
        )
        return {
            r.player_id: (
                float(r.manual_value) if r.manual_value is not None else None,
                r.note,
            )
            for r in result.all()
        }

    async def upsert_override(
        self, season_id: int, player_id: int, manual_value: float | None, note: str | None
    ) -> None:
        """Set/clear the admin manual value + note for a player. A NULL
        ``manual_value`` keeps the row (as a note holder) but falls back to
        the automatic projection."""
        await self.session.execute(
            text(
                "INSERT INTO draft_value_overrides "
                "  (season_id, player_id, manual_value, note, updated_at) "
                "VALUES (:sid, :pid, :val, :note, now()) "
                "ON CONFLICT ON CONSTRAINT uq_draft_value_override DO UPDATE SET "
                "  manual_value = EXCLUDED.manual_value, "
                "  note = EXCLUDED.note, "
                "  updated_at = now()"
            ),
            {"sid": season_id, "pid": player_id, "val": manual_value, "note": note},
        )
        await self.session.commit()

    async def _resolve_season_ids(self, current_season_id: int, n_history: int) -> list[int]:
        """The current season + up to ``n_history`` prior LEAGUE seasons.

        Tournament seasons (Mundial, Eurocopa) are excluded — the draft-value
        model is league-only. Replaces the old hardcoded ``[5, 6, 7, 8]``."""
        result = await self.session.execute(
            text(
                "SELECT id FROM seasons "
                "WHERE kind = 'league' AND id <= :cur "
                "ORDER BY id DESC LIMIT :lim"
            ),
            {"cur": current_season_id, "lim": n_history + 1},
        )
        return [row.id for row in result.all()]

    async def _load_seasons(self, current_season_id: int, min_games: int) -> list[_PlayerSeason]:
        # Current + prior league seasons. ``min_games`` is the LOAD floor
        # (kept low so the current partial season's 4-8 games are included);
        # candidate/history thresholds are applied later in Python.
        season_ids = await self._resolve_season_ids(current_season_id, N_HISTORY_SEASONS)

        result = await self.session.execute(
            text("""
                SELECT p.id as player_id, p.slug, p.display_name, p.photo_path,
                       ps.position, md.season_id, s.name as season_name, t.name as team_name,
                       COUNT(*) as games,
                       COUNT(CASE WHEN ps.minutes_played >= 45 THEN 1 END) as games_45min,
                       AVG(ps.pts_total) as avg_pts,
                       SUM(ps.pts_total) as total_pts,
                       COALESCE(STDDEV(ps.pts_total), 0) as std_pts,
                       COALESCE(SUM(ps.pts_marca_as), 0) as media_pts,
                       AVG(CASE WHEN ps.marca_rating ~ '^[1-4]$'
                           THEN CAST(ps.marca_rating AS INTEGER) END) as marca_avg,
                       AVG(CASE WHEN ps.as_picas ~ '^[0-9]+$'
                           THEN CAST(ps.as_picas AS INTEGER) END) as as_avg,
                       COALESCE(SUM(ps.goals + ps.penalty_goals), 0) as goals,
                       COALESCE(SUM(ps.penalty_goals), 0) as penalty_goals,
                       COALESCE(SUM(ps.penalties_missed), 0) as penalties_missed,
                       COALESCE(SUM(ps.assists), 0) as assists,
                       COALESCE(SUM(ps.minutes_played), 0) as minutes,
                       AVG(CASE WHEN md.number > 19 THEN ps.pts_total END) as second_half_avg
                FROM player_stats ps
                JOIN players p ON ps.player_id = p.id
                -- History uses only counting matchdays; the CURRENT season also
                -- includes pre-draft matchdays (counts=false before
                -- matchday_start) so the board has early-season signal to blend.
                JOIN matchdays md ON ps.matchday_id = md.id
                     AND (md.counts = TRUE OR md.season_id = :current)
                JOIN teams t ON p.team_id = t.id
                JOIN seasons s ON md.season_id = s.id
                -- Only games the player actually featured in. Non-played rows
                -- (played=false, 0 min, 0/NULL pts) would otherwise inflate the
                -- game count, deflate avg_pts, and wreck availability
                -- (g45/all-rows instead of g45/games-played), falsely flagging
                -- established starters as bench risk.
                WHERE md.season_id = ANY(:ids) AND ps.played IS TRUE
                GROUP BY p.id, p.slug, p.display_name, p.photo_path,
                         ps.position, md.season_id, s.name, t.name
                HAVING COUNT(*) >= :min
                ORDER BY p.slug, md.season_id
            """),
            {"ids": season_ids, "min": min_games, "current": current_season_id},
        )

        return [
            _PlayerSeason(
                player_id=r.player_id,
                slug=r.slug,
                display_name=r.display_name,
                photo_path=r.photo_path,
                position=r.position,
                season_id=r.season_id,
                season_name=r.season_name,
                team_name=r.team_name or "",
                games=r.games,
                games_45min=r.games_45min,
                avg_pts=float(r.avg_pts or 0),
                total_pts=float(r.total_pts or 0),
                std_pts=float(r.std_pts or 0),
                media_pts=float(r.media_pts or 0),
                marca_avg=float(r.marca_avg) if r.marca_avg is not None else None,
                as_avg=float(r.as_avg) if r.as_avg is not None else None,
                goals=int(r.goals or 0),
                assists=int(r.assists or 0),
                minutes=int(r.minutes or 0),
                second_half_avg=float(r.second_half_avg or 0),
                penalty_goals=int(r.penalty_goals or 0),
                penalties_missed=int(r.penalties_missed or 0),
            )
            for r in result.all()
        ]
