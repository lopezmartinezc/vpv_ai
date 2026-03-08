from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.standings.schemas import (
    EvolutionEntry,
    EvolutionResponse,
    StandingsResponse,
)
from src.features.standings.service import StandingsService
from src.features.stats.repository import StatsRepository
from src.shared.dependencies import get_db

router = APIRouter(prefix="/standings", tags=["standings"])


def _get_service(db: AsyncSession = Depends(get_db)) -> StandingsService:
    return StandingsService(db)


@router.get("/{season_id}", response_model=StandingsResponse)
async def get_standings(
    season_id: int,
    service: StandingsService = Depends(_get_service),
) -> StandingsResponse:
    return await service.get_standings(season_id)


@router.get("/{season_id}/evolution", response_model=EvolutionResponse)
async def get_evolution(
    season_id: int,
    db: AsyncSession = Depends(get_db),
) -> EvolutionResponse:
    repo = StatsRepository(db)
    md_scores = await repo.get_participant_matchday_scores(season_id)

    cumulative: dict[int, int] = defaultdict(int)
    entries: list[EvolutionEntry] = []

    by_matchday: dict[int, list] = defaultdict(list)
    for row in md_scores:
        by_matchday[row.matchday_number].append(row)

    for md_number in sorted(by_matchday.keys()):
        for row in sorted(by_matchday[md_number], key=lambda r: r.participant_id):
            cumulative[row.participant_id] += row.total_points
            entries.append(
                EvolutionEntry(
                    matchday_number=md_number,
                    participant_id=row.participant_id,
                    display_name=row.display_name,
                    points=row.total_points,
                    cumulative=cumulative[row.participant_id],
                )
            )

    return EvolutionResponse(season_id=season_id, entries=entries)
