"""Admin statistics router — three endpoints for advanced season analytics.

Endpoints (all admin-only):
  GET /stats/{season_id}/players       — Per-player aggregated stats
  GET /stats/{season_id}/participants  — Participant breakdowns, extremes, evolution
  GET /stats/{season_id}/league        — Formation usage, records, matchday averages

Helper functions compute derived data (extremes, cumulative evolution, records)
from the raw matchday score rows returned by the repository.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.stats.repository import MatchdayScoreRow, StatsRepository
from src.features.stats.schemas import (
    EvolutionEntry,
    FormationUsage,
    LeagueStatsResponse,
    MatchdayAverage,
    MostLinedUpPlayer,
    ParticipantBreakdown,
    ParticipantExtremes,
    ParticipantStatsResponse,
    PlayerStatRow,
    PlayerStatsResponse,
    RecordEntry,
)
from src.shared.dependencies import get_current_admin, get_db

router = APIRouter(prefix="/stats", tags=["stats"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_extremes(
    md_scores: list[MatchdayScoreRow],
) -> list[ParticipantExtremes]:
    """Derive best/worst/avg per participant from raw matchday score rows."""
    groups: dict[int, list[MatchdayScoreRow]] = defaultdict(list)
    for row in md_scores:
        groups[row.participant_id].append(row)

    extremes: list[ParticipantExtremes] = []
    for participant_id, rows in groups.items():
        best_row = max(rows, key=lambda r: r.total_points)
        worst_row = min(rows, key=lambda r: r.total_points)
        avg_pts = sum(r.total_points for r in rows) / len(rows)
        extremes.append(
            ParticipantExtremes(
                participant_id=participant_id,
                display_name=rows[0].display_name,
                best_points=best_row.total_points,
                best_matchday=best_row.matchday_number,
                worst_points=worst_row.total_points,
                worst_matchday=worst_row.matchday_number,
                avg_points=round(avg_pts, 2),
            )
        )
    # Sort by average descending for consistent ordering
    extremes.sort(key=lambda e: e.avg_points, reverse=True)
    return extremes


def _compute_evolution(
    md_scores: list[MatchdayScoreRow],
) -> list[EvolutionEntry]:
    """Build cumulative evolution entries ordered by matchday then participant."""
    cumulative: dict[int, int] = defaultdict(int)
    evolution: list[EvolutionEntry] = []

    # md_scores is already ordered by matchday_number ASC, participant_id ASC
    matchdays_seen: list[int] = []
    for row in md_scores:
        if not matchdays_seen or matchdays_seen[-1] != row.matchday_number:
            matchdays_seen.append(row.matchday_number)

    # Group by matchday to iterate in order
    by_matchday: dict[int, list[MatchdayScoreRow]] = defaultdict(list)
    for row in md_scores:
        by_matchday[row.matchday_number].append(row)

    for md_number in sorted(by_matchday.keys()):
        for row in sorted(by_matchday[md_number], key=lambda r: r.participant_id):
            cumulative[row.participant_id] += row.total_points
            evolution.append(
                EvolutionEntry(
                    matchday_number=md_number,
                    participant_id=row.participant_id,
                    display_name=row.display_name,
                    points=row.total_points,
                    cumulative=cumulative[row.participant_id],
                )
            )
    return evolution


def _compute_records(
    md_scores: list[MatchdayScoreRow],
    md_avgs: list,
) -> list[RecordEntry]:
    """Build high-level record entries from matchday data."""
    records: list[RecordEntry] = []

    if not md_scores:
        return records

    # Best individual score in a single matchday
    best_individual = max(md_scores, key=lambda r: r.total_points)
    records.append(
        RecordEntry(
            label="Mejor puntuacion individual",
            value=str(best_individual.total_points),
            detail=f"{best_individual.display_name} — Jornada {best_individual.matchday_number}",
        )
    )

    # Worst individual score
    worst_individual = min(md_scores, key=lambda r: r.total_points)
    records.append(
        RecordEntry(
            label="Peor puntuacion individual",
            value=str(worst_individual.total_points),
            detail=f"{worst_individual.display_name} — Jornada {worst_individual.matchday_number}",
        )
    )

    if md_avgs:
        # Matchday with highest average points
        best_avg = max(md_avgs, key=lambda a: a.avg_points)
        records.append(
            RecordEntry(
                label="Jornada con mayor media",
                value=f"{best_avg.avg_points:.1f}",
                detail=f"Jornada {best_avg.matchday_number}",
            )
        )

        # Matchday with lowest average points
        worst_avg = min(md_avgs, key=lambda a: a.avg_points)
        records.append(
            RecordEntry(
                label="Jornada con menor media",
                value=f"{worst_avg.avg_points:.1f}",
                detail=f"Jornada {worst_avg.matchday_number}",
            )
        )

        # Overall highest single-matchday total (max_points column)
        highest_matchday = max(md_avgs, key=lambda a: a.max_points)
        records.append(
            RecordEntry(
                label="Mayor puntuacion en una jornada",
                value=str(highest_matchday.max_points),
                detail=f"Jornada {highest_matchday.matchday_number}",
            )
        )

    return records


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{season_id}/players", response_model=PlayerStatsResponse)
async def get_player_stats(
    season_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PlayerStatsResponse:
    repo = StatsRepository(db)
    rows = await repo.get_player_stats(season_id)
    return PlayerStatsResponse(
        season_id=season_id,
        players=[
            PlayerStatRow(
                player_id=row.player_id,
                display_name=row.display_name,
                photo_path=row.photo_path,
                position=row.position,
                team_name=row.team_name,
                goals=row.goals,
                penalty_goals=row.penalty_goals,
                own_goals=row.own_goals,
                assists=row.assists,
                penalties_saved=row.penalties_saved,
                yellow_cards=row.yellow_cards,
                red_cards=row.red_cards,
                avg_marca=row.avg_marca,
                avg_as=row.avg_as,
                minutes_played=row.minutes_played,
                matchdays_played=row.matchdays_played,
                started_count=row.started_count,
                avg_points=row.avg_points,
                total_points=row.total_points,
            )
            for row in rows
        ],
    )


@router.get("/{season_id}/participants", response_model=ParticipantStatsResponse)
async def get_participant_stats(
    season_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ParticipantStatsResponse:
    repo = StatsRepository(db)
    breakdown_rows = await repo.get_participant_breakdowns(season_id)
    md_scores = await repo.get_participant_matchday_scores(season_id)

    breakdowns = [
        ParticipantBreakdown(
            participant_id=row.participant_id,
            display_name=row.display_name,
            pts_play=row.pts_play,
            pts_result=row.pts_result,
            pts_clean_sheet=row.pts_clean_sheet,
            pts_goals=row.pts_goals,
            pts_assists=row.pts_assists,
            pts_yellow=row.pts_yellow,
            pts_red=row.pts_red,
            pts_marca_as=row.pts_marca_as,
            pts_total=row.pts_total,
        )
        for row in breakdown_rows
    ]

    extremes = _compute_extremes(md_scores)
    evolution = _compute_evolution(md_scores)

    return ParticipantStatsResponse(
        season_id=season_id,
        breakdowns=breakdowns,
        extremes=extremes,
        evolution=evolution,
    )


@router.get("/{season_id}/league", response_model=LeagueStatsResponse)
async def get_league_stats(
    season_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> LeagueStatsResponse:
    repo = StatsRepository(db)
    formation_rows = await repo.get_formation_usage(season_id)
    most_lined_rows = await repo.get_most_lined_up(season_id)
    md_avg_rows = await repo.get_matchday_averages(season_id)
    md_scores = await repo.get_participant_matchday_scores(season_id)

    formations = [
        FormationUsage(formation=row.formation, usage_count=row.usage_count)
        for row in formation_rows
    ]

    most_lined_up = [
        MostLinedUpPlayer(
            player_id=row.player_id,
            display_name=row.display_name,
            position=row.position,
            team_name=row.team_name,
            photo_path=row.photo_path,
            times_lined_up=row.times_lined_up,
        )
        for row in most_lined_rows
    ]

    matchday_averages = [
        MatchdayAverage(
            matchday_number=row.matchday_number,
            avg_points=round(row.avg_points, 2),
            max_points=row.max_points,
            min_points=row.min_points,
        )
        for row in md_avg_rows
    ]

    records = _compute_records(md_scores, md_avg_rows)

    return LeagueStatsResponse(
        season_id=season_id,
        formations=formations,
        most_lined_up=most_lined_up,
        matchday_averages=matchday_averages,
        records=records,
    )
