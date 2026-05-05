from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.features.matchdays.repository import MatchdayRepository
from src.features.matchdays.schemas import (
    AdminMatchdayResponse,
    AdminMatchResponse,
    BenchPlayerEntry,
    DreamTeamPlayer,
    DreamTeamResponse,
    HighlightPlayer,
    LineupDetailResponse,
    LineupPlayerEntry,
    MatchdayDetailResponse,
    MatchdayHighlightsResponse,
    MatchdayListResponse,
    MatchdaySummary,
    MatchEntry,
    ParticipantScore,
    ScoreBreakdown,
)
from src.features.scraping.aggregation import ScoreAggregator
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

        # Fallback: if no scores yet (pre-scraping), show lineups as 0-pt entries
        if not score_rows:
            score_rows = await self.repo.get_lineups_as_scores(matchday.id)

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
                    stats_ok=m.stats_ok,
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
                    pending_players=s.pending_players,
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
            matchday_number=number,
        )

        # Get participant display name
        display_name = await self.repo.get_participant_display_name(participant_id)

        return LineupDetailResponse(
            participant_id=participant_id,
            display_name=display_name,
            matchday_number=matchday.number,
            formation=lineup.formation,
            total_points=lineup.total_points or 0,
            players=[
                LineupPlayerEntry(
                    display_order=p.display_order,
                    position_slot=p.position_slot,
                    player_id=p.player_id,
                    player_name=p.player_name,
                    photo_path=p.photo_path,
                    team_name=p.team_name,
                    points=p.points or 0,
                    score_breakdown=ScoreBreakdown(
                        pts_play=p.pts_play,
                        pts_starter=p.pts_starter,
                        pts_result=p.pts_result,
                        pts_clean_sheet=p.pts_clean_sheet,
                        pts_goals=p.pts_goals,
                        pts_penalty_goals=p.pts_penalty_goals,
                        pts_assists=p.pts_assists,
                        pts_penalties_saved=p.pts_penalties_saved,
                        pts_woodwork=p.pts_woodwork,
                        pts_penalties_won=p.pts_penalties_won,
                        pts_penalties_missed=p.pts_penalties_missed,
                        pts_own_goals=p.pts_own_goals,
                        pts_yellow=p.pts_yellow,
                        pts_red=p.pts_red,
                        pts_pen_committed=p.pts_pen_committed,
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
                    matchday_points=b.matchday_points or 0,
                    score_breakdown=ScoreBreakdown(
                        pts_play=b.pts_play,
                        pts_starter=b.pts_starter,
                        pts_result=b.pts_result,
                        pts_clean_sheet=b.pts_clean_sheet,
                        pts_goals=b.pts_goals,
                        pts_penalty_goals=b.pts_penalty_goals,
                        pts_assists=b.pts_assists,
                        pts_penalties_saved=b.pts_penalties_saved,
                        pts_woodwork=b.pts_woodwork,
                        pts_penalties_won=b.pts_penalties_won,
                        pts_penalties_missed=b.pts_penalties_missed,
                        pts_own_goals=b.pts_own_goals,
                        pts_yellow=b.pts_yellow,
                        pts_red=b.pts_red,
                        pts_pen_committed=b.pts_pen_committed,
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

        if "counts" in kwargs:
            aggregator = ScoreAggregator(self.repo.session)
            await aggregator.aggregate_matchday(matchday.id)
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

        if "counts" in kwargs:
            aggregator = ScoreAggregator(self.repo.session)
            await aggregator.aggregate_matchday(match.matchday_id)
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
                    stats_ok=m.stats_ok,
                    played_at=m.played_at,
                )
        raise NotFoundError("Match", match_id)

    async def get_matchday_highlights(
        self,
        season_id: int,
        matchday_number: int,
    ) -> MatchdayHighlightsResponse:
        matchday = await self.repo.get_matchday(season_id, matchday_number)
        if matchday is None:
            raise NotFoundError("Matchday", matchday_number)

        rows = await self.repo.get_matchday_highlights(matchday.id)
        if not rows:
            return MatchdayHighlightsResponse(matchday_number=matchday_number)

        def to_highlight(r: dict) -> HighlightPlayer:
            return HighlightPlayer(
                player_id=r["player_id"],
                player_name=r["player_name"],
                photo_path=r["photo_path"],
                position=r["position_slot"],
                team_name=r["team_name"],
                points=r["points"] or 0,
                owner_name=r["owner_name"],
                goals=r["goals"] or 0,
                assists=r["assists"] or 0,
            )

        played = [r for r in rows if (r["points"] or 0) != 0]
        mvp = to_highlight(played[0]) if played else None
        flop = to_highlight(played[-1]) if played and len(played) > 1 else None

        with_goals = [r for r in rows if (r["goals"] or 0) > 0]
        with_goals.sort(key=lambda r: r["goals"] or 0, reverse=True)
        top_scorer = to_highlight(with_goals[0]) if with_goals else None

        with_assists = [r for r in rows if (r["assists"] or 0) > 0]
        with_assists.sort(key=lambda r: r["assists"] or 0, reverse=True)
        top_assister = to_highlight(with_assists[0]) if with_assists else None

        # Dream team / Nightmare team
        all_stats = await self.repo.get_all_player_stats_for_matchday(matchday.id)
        formations = await self.repo.get_valid_formations()
        dream_team = self._build_best_xi(all_stats, formations, best=True)
        nightmare_team = self._build_best_xi(all_stats, formations, best=False)

        return MatchdayHighlightsResponse(
            matchday_number=matchday_number,
            mvp=mvp,
            flop=flop,
            top_scorer=top_scorer,
            top_assister=top_assister,
            dream_team=dream_team,
            nightmare_team=nightmare_team,
        )

    @staticmethod
    def _build_best_xi(
        stats: list[dict],
        formations: list[tuple[int, int, int]],
        *,
        best: bool,
    ) -> DreamTeamResponse | None:
        if not stats or not formations:
            return None

        by_pos: dict[str, list[dict]] = {"POR": [], "DEF": [], "MED": [], "DEL": []}
        for s in stats:
            pos = s["position"]
            if pos in by_pos:
                by_pos[pos].append(s)

        reverse = best  # best=True → sort descending
        for pos in by_pos:
            by_pos[pos].sort(key=lambda r: r["pts_total"], reverse=reverse)

        best_team: DreamTeamResponse | None = None

        for defs, mids, fwds in formations:
            needed = {"POR": 1, "DEF": defs, "MED": mids, "DEL": fwds}
            if any(len(by_pos[p]) < needed[p] for p in needed):
                continue

            picked: list[dict] = []
            for pos, count in needed.items():
                picked.extend(by_pos[pos][:count])

            total = sum(p["pts_total"] for p in picked)
            formation_str = f"1-{defs}-{mids}-{fwds}"

            if (
                best_team is None
                or (best and total > best_team.total_points)
                or (not best and total < best_team.total_points)
            ):
                best_team = DreamTeamResponse(
                    formation=formation_str,
                    total_points=total,
                    players=[
                        DreamTeamPlayer(
                            player_id=p["player_id"],
                            player_name=p["player_name"],
                            photo_path=p["photo_path"],
                            position=p["position"],
                            team_name=p["team_name"],
                            points=p["pts_total"],
                        )
                        for p in picked
                    ],
                )

        return best_team
