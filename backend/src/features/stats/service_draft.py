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

logger = logging.getLogger(__name__)

VALID_SEASON_IDS = [5, 6, 7, 8]
MIN_GAMES = 10


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


class DraftValueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_draft_values(
        self,
        season_id: int,
        min_games: int = MIN_GAMES,
    ) -> DraftValueResponse:
        """Compute draft value predictions for all players."""

        # Load data
        season_info = await self._get_season_info(season_id)
        all_data = await self._load_seasons(season_id, min_games)
        current_data = [ps for ps in all_data if ps.season_id == season_id]
        history_data = [ps for ps in all_data if ps.season_id != season_id]

        # Organize
        by_slug: dict[str, list[_PlayerSeason]] = defaultdict(list)
        for ps in all_data:
            by_slug[ps.slug].append(ps)
        for slug in by_slug:
            by_slug[slug].sort(key=lambda s: s.season_id)

        history: dict[str, list[_PlayerSeason]] = defaultdict(list)
        for ps in history_data:
            history[ps.slug].append(ps)

        current_map: dict[str, _PlayerSeason] = {}
        for ps in current_data:
            current_map[ps.slug] = ps

        # Determine draft type
        md_played = season_info["matchday_current"] - season_info["matchday_start"]
        is_winter = md_played >= 10
        peso_actual = min(0.9, md_played / 40) if md_played > 0 else 0.0
        peso_hist = 1 - peso_actual

        # All players to evaluate (current season roster)
        targets = set(current_map.keys())

        # Compute each model
        results: list[DraftValuePlayer] = []

        for slug in targets:
            ps = current_map[slug]
            hist = history.get(slug, [])
            seasons_played = len(hist) + 1

            # === Model A: Simple average ===
            simple_avg = hist[-1].avg_pts if hist else ps.avg_pts

            # === Model H: Second half weighted ===
            second_half_score = None
            second_half_avg = None
            if hist and hist[-1].second_half_avg > 0:
                second_half_avg = hist[-1].second_half_avg
                second_half_score = hist[-1].second_half_avg * 0.6 + hist[-1].avg_pts * 0.4
            elif hist:
                second_half_score = hist[-1].avg_pts

            # === Model I: Productivity ===
            prod_base = hist[-1].avg_pts if hist else ps.avg_pts
            ref = hist[-1] if hist else ps
            if ref.minutes > 500:
                ga_per90 = ((ref.goals + ref.assists) / ref.minutes) * 90
                if ga_per90 > 0.5:
                    prod_base *= 1 + (ga_per90 - 0.5) * 0.3
            productivity_score = prod_base

            # === Model K: Minutes stability ===
            if hist:
                starter_rates = [s.games_45min / max(s.games, 1) for s in hist]
                avg_starter = statistics.mean(starter_rates)
                career_avg_k = statistics.mean(s.avg_pts for s in hist)
                stability_score = career_avg_k * (0.8 + avg_starter * 0.4)
            else:
                stability_score = ps.avg_pts * (0.8 + (ps.games_45min / max(ps.games, 1)) * 0.4)

            # === Model C: Career trend ===
            trend_score = None
            career_trend_pct = None
            if len(hist) >= 2 and hist[-2].avg_pts > 0:
                career_trend_pct = (hist[-1].avg_pts - hist[-2].avg_pts) / hist[-2].avg_pts
                career_avg_c = statistics.mean(s.avg_pts for s in hist)
                trend_score = career_avg_c * (1 + career_trend_pct * 0.5)
            elif hist:
                trend_score = hist[-1].avg_pts

            # === Model V: Ensemble diverso (WINNER) ===
            components = [simple_avg, stability_score]
            if trend_score is not None:
                components.append(trend_score)
            if second_half_score is not None:
                components.append(second_half_score)
            ensemble_score = statistics.mean(components)

            # Winter blend: mix career prediction with current season
            if is_winter and peso_actual > 0:
                career_pred = ensemble_score
                current_avg = ps.avg_pts
                ensemble_score = career_pred * peso_hist + current_avg * peso_actual
                simple_avg = (
                    hist[-1].avg_pts if hist else 0
                ) * peso_hist + current_avg * peso_actual

            # === Signals ===
            availability = ps.games_45min / max(ps.games, 1)
            cv = ps.std_pts / ps.avg_pts if ps.avg_pts > 0 else 1.0
            consistency = max(0, 1 - cv)

            marca = ps.marca_avg if is_winter else (hist[-1].marca_avg if hist else None)
            as_val = ps.as_avg if is_winter else (hist[-1].as_avg if hist else None)

            # === Draft signal ===
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
                    player_id=ps.player_id,
                    slug=ps.slug,
                    display_name=ps.display_name,
                    team_name=ps.team_name,
                    position=ps.position,
                    photo_path=ps.photo_path,
                    games_played=ps.games,
                    seasons_played=seasons_played,
                    avg_points=round(ps.avg_pts, 2),
                    total_points=round(ps.total_pts, 1),
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
                    goals=ps.goals,
                    assists=ps.assists,
                    signal=signal,
                    signal_reasons=reasons,
                )
            )

        # Sort by ensemble score
        results.sort(key=lambda p: p.ensemble_score, reverse=True)

        return DraftValueResponse(
            season_id=season_id,
            season_name=season_info["name"],
            matchdays_played=md_played,
            draft_type="winter" if is_winter else "preseason",
            peso_historico=round(peso_hist, 2),
            model_info={
                "ensemble_score": "Ensemble diverso (Spearman 0.718) — MEJOR ranking general",
                "simple_avg": "Media temporada anterior (Spearman 0.711) — baseline",
                "second_half_score": "Forma 2a mitad (Spearman 0.712) — momentum",
                "productivity_score": "G+A per 90 (Spearman 0.712) — productividad ofensiva",
                "stability_score": "Minutos estables (Bust 10%) — seguridad",
                "trend_score": "Tendencia interanual — mejora o empeora",
            },
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
            text("SELECT name, matchday_start, matchday_current FROM seasons WHERE id = :id"),
            {"id": season_id},
        )
        row = result.one()
        return {
            "name": row.name,
            "matchday_start": row.matchday_start,
            "matchday_current": row.matchday_current,
        }

    async def _load_seasons(self, current_season_id: int, min_games: int) -> list[_PlayerSeason]:
        # Include current + historical seasons
        season_ids = [s for s in VALID_SEASON_IDS if s <= current_season_id]

        result = await self.session.execute(
            text("""
                SELECT p.id as player_id, p.slug, p.display_name, p.photo_path,
                       ps.position, md.season_id, s.name as season_name, t.name as team_name,
                       COUNT(*) as games,
                       COUNT(CASE WHEN ps.minutes_played >= 45 THEN 1 END) as games_45min,
                       AVG(ps.pts_total) as avg_pts,
                       SUM(ps.pts_total) as total_pts,
                       COALESCE(STDDEV(ps.pts_total), 0) as std_pts,
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
                JOIN matchdays md ON ps.matchday_id = md.id AND md.counts = TRUE
                JOIN teams t ON p.team_id = t.id
                JOIN seasons s ON md.season_id = s.id
                WHERE md.season_id = ANY(:ids)
                GROUP BY p.id, p.slug, p.display_name, p.photo_path,
                         ps.position, md.season_id, s.name, t.name
                HAVING COUNT(*) >= :min
                ORDER BY p.slug, md.season_id
            """),
            {"ids": season_ids, "min": min_games},
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
