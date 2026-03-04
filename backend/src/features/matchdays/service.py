from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.matchdays.repository import MatchdayRepository
from src.features.matchdays.schemas import (
    AdminMatchdayResponse,
    AdminMatchResponse,
    BenchPlayerEntry,
    LineupDetailResponse,
    LineupPlayerEntry,
    MatchdayDetailResponse,
    MatchdayListResponse,
    MatchdaySummary,
    MatchEntry,
    ParticipantScore,
    ScoreBreakdown,
)
from src.features.seasons.repository import SeasonRepository


class MatchdayService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = MatchdayRepository(session)
        self.season_repo = SeasonRepository(session)

    async def list_matchdays(
        self,
        season_id: int,
        *,
        stats_ok_only: bool = True,
    ) -> MatchdayListResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        rows = await self.repo.list_for_season(
            season_id,
            stats_ok_only=stats_ok_only,
        )
        return MatchdayListResponse(
            season_id=season_id,
            matchdays=[
                MatchdaySummary(
                    number=r.number,
                    status=r.status,
                    counts=r.counts,
                    stats_ok=r.stats_ok,
                    first_match_at=r.first_match_at,
                )
                for r in rows
            ],
        )

    async def get_matchday_detail(
        self,
        season_id: int,
        number: int,
    ) -> MatchdayDetailResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        matchday = await self.repo.get_matchday(season_id, number)
        if matchday is None:
            raise NotFoundError("Matchday", f"{season_id}/{number}")

        match_rows = await self.repo.get_matches(matchday.id)
        score_rows = await self.repo.get_scores(matchday.id)

        return MatchdayDetailResponse(
            season_id=season_id,
            number=matchday.number,
            status=matchday.status,
            counts=matchday.counts,
            stats_ok=matchday.stats_ok,
            first_match_at=matchday.first_match_at,
            matches=[
                MatchEntry(
                    id=m.id,
                    home_team=m.home_team_name,
                    away_team=m.away_team_name,
                    home_score=m.home_score,
                    away_score=m.away_score,
                    counts=m.counts,
                    played_at=m.played_at,
                )
                for m in match_rows
            ],
            scores=[
                ParticipantScore(
                    rank=s.rank,
                    participant_id=s.participant_id,
                    display_name=s.display_name,
                    total_points=s.total_points,
                    formation=s.formation,
                )
                for s in score_rows
            ],
        )

    async def get_lineup_detail(
        self,
        season_id: int,
        number: int,
        participant_id: int,
    ) -> LineupDetailResponse:
        season = await self.season_repo.get_by_id(season_id)
        if season is None:
            raise NotFoundError("Season", season_id)

        matchday = await self.repo.get_matchday(season_id, number)
        if matchday is None:
            raise NotFoundError("Matchday", f"{season_id}/{number}")

        lineup = await self.repo.get_lineup(matchday.id, participant_id)
        if lineup is None:
            raise NotFoundError(
                "Lineup",
                f"participant={participant_id}/matchday={matchday.id}",
            )

        player_rows = await self.repo.get_lineup_players(
            lineup.id,
            matchday.id,
        )

        # Get bench players (squad minus lineup)
        lineup_player_ids = {p.player_id for p in player_rows}
        bench_rows = await self.repo.get_bench_players(
            matchday.id,
            participant_id,
            season_id,
            lineup_player_ids,
        )

        # Get participant display name
        score_rows = await self.repo.get_scores(matchday.id)
        display_name = ""
        for s in score_rows:
            if s.participant_id == participant_id:
                display_name = s.display_name
                break

        return LineupDetailResponse(
            participant_id=participant_id,
            display_name=display_name,
            matchday_number=matchday.number,
            formation=lineup.formation,
            total_points=lineup.total_points,
            players=[
                LineupPlayerEntry(
                    display_order=p.display_order,
                    position_slot=p.position_slot,
                    player_id=p.player_id,
                    player_name=p.player_name,
                    photo_path=p.photo_path,
                    team_name=p.team_name,
                    points=p.points,
                    score_breakdown=ScoreBreakdown(
                        pts_play=p.pts_play,
                        pts_starter=p.pts_starter,
                        pts_result=p.pts_result,
                        pts_clean_sheet=p.pts_clean_sheet,
                        pts_goals=p.pts_goals,
                        pts_assists=p.pts_assists,
                        pts_yellow=p.pts_yellow,
                        pts_red=p.pts_red,
                        pts_marca=p.pts_marca,
                        pts_as=p.pts_as,
                        pts_total=p.pts_total,
                    )
                    if p.pts_total is not None
                    else None,
                )
                for p in player_rows
            ],
            bench=[
                BenchPlayerEntry(
                    player_id=b.player_id,
                    player_name=b.player_name,
                    photo_path=b.photo_path,
                    position=b.position,
                    team_name=b.team_name,
                    matchday_points=b.matchday_points,
                    score_breakdown=ScoreBreakdown(
                        pts_play=b.pts_play,
                        pts_starter=b.pts_starter,
                        pts_result=b.pts_result,
                        pts_clean_sheet=b.pts_clean_sheet,
                        pts_goals=b.pts_goals,
                        pts_assists=b.pts_assists,
                        pts_yellow=b.pts_yellow,
                        pts_red=b.pts_red,
                        pts_marca=b.pts_marca,
                        pts_as=b.pts_as,
                        pts_total=b.pts_total,
                    )
                    if b.pts_total is not None
                    else None,
                )
                for b in bench_rows
            ],
        )

    # --- Admin methods ---

    async def update_matchday(
        self,
        season_id: int,
        number: int,
        **kwargs: object,
    ) -> AdminMatchdayResponse:
        matchday = await self.repo.update_matchday(season_id, number, **kwargs)
        if matchday is None:
            raise NotFoundError("Matchday", f"{season_id}/{number}")
        await self.repo.session.commit()
        return AdminMatchdayResponse(
            season_id=matchday.season_id,
            number=matchday.number,
            status=matchday.status,
            counts=matchday.counts,
            stats_ok=matchday.stats_ok,
            first_match_at=matchday.first_match_at,
        )

    async def update_match(
        self,
        match_id: int,
        **kwargs: object,
    ) -> AdminMatchResponse:
        match = await self.repo.update_match(match_id, **kwargs)
        if match is None:
            raise NotFoundError("Match", match_id)
        # Need team names for response
        await self.repo.session.commit()
        # Re-fetch match with teams
        match_rows = await self.repo.get_matches(match.matchday_id)
        for m in match_rows:
            if m.id == match_id:
                return AdminMatchResponse(
                    id=m.id,
                    home_team=m.home_team_name,
                    away_team=m.away_team_name,
                    home_score=m.home_score,
                    away_score=m.away_score,
                    counts=m.counts,
                    played_at=m.played_at,
                )
        raise NotFoundError("Match", match_id)
