from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.tournaments.schemas import (
    BracketMatch,
    BracketResponse,
    BracketRound,
    GroupResponse,
    GroupsResponse,
    PlayerOption,
    PredictionRequest,
    PredictionResponse,
    PredictionsListResponse,
    TeamGroupStanding,
    TeamOption,
)
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.tournament_prediction import TournamentPrediction
from src.shared.models.user import User

logger = logging.getLogger(__name__)


class TournamentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    async def _get_tournament_season(self, season_id: int) -> Season:
        """Load a season and verify it's a tournament."""
        season = await self.session.get(Season, season_id)
        if season is None:
            raise NotFoundError("Season", season_id)
        if season.kind != "tournament":
            raise BusinessRuleError(
                f"La temporada {season_id} no es un torneo (kind={season.kind})"
            )
        return season

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    async def get_groups(self, season_id: int) -> GroupsResponse:
        """Build the group-stage standings for a tournament."""
        season = await self._get_tournament_season(season_id)
        config = season.tournament_config or {}
        groups_cfg: dict[str, Any] = config.get("groups", {}) if isinstance(config, dict) else {}
        group_matchdays: list[int] = groups_cfg.get("matchdays", [1, 2, 3])

        # Get all teams in the season grouped by tournament_group
        teams_stmt = (
            select(Team)
            .where(Team.season_id == season_id)
            .order_by(Team.tournament_group, Team.name)
        )
        teams_result = await self.session.execute(teams_stmt)
        teams = list(teams_result.scalars().all())

        teams_by_group: dict[str, list[Team]] = defaultdict(list)
        for t in teams:
            if t.tournament_group:
                teams_by_group[t.tournament_group].append(t)

        # Get all matches in the group-stage matchdays for this season
        matches_stmt = (
            select(Match, Matchday.number.label("md_number"))
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.number.in_(group_matchdays),
            )
        )
        matches_result = await self.session.execute(matches_stmt)
        matches = list(matches_result.all())

        # Build standings per team
        stats: dict[int, dict[str, int]] = defaultdict(
            lambda: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0}
        )

        for row in matches:
            m: Match = row[0]
            if m.home_score is None or m.away_score is None:
                continue  # not played yet
            stats[m.home_team_id]["played"] += 1
            stats[m.away_team_id]["played"] += 1
            stats[m.home_team_id]["gf"] += m.home_score
            stats[m.home_team_id]["ga"] += m.away_score
            stats[m.away_team_id]["gf"] += m.away_score
            stats[m.away_team_id]["ga"] += m.home_score
            if m.home_score > m.away_score:
                stats[m.home_team_id]["won"] += 1
                stats[m.away_team_id]["lost"] += 1
            elif m.home_score < m.away_score:
                stats[m.away_team_id]["won"] += 1
                stats[m.home_team_id]["lost"] += 1
            else:
                stats[m.home_team_id]["drawn"] += 1
                stats[m.away_team_id]["drawn"] += 1

        # Build response
        group_responses: list[GroupResponse] = []
        for group_name in sorted(teams_by_group.keys()):
            standings: list[TeamGroupStanding] = []
            for t in teams_by_group[group_name]:
                s = stats[t.id]
                pts = s["won"] * 3 + s["drawn"]
                standings.append(
                    TeamGroupStanding(
                        team_id=t.id,
                        team_name=t.name,
                        short_name=t.short_name,
                        logo_path=t.logo_path,
                        played=s["played"],
                        won=s["won"],
                        drawn=s["drawn"],
                        lost=s["lost"],
                        goals_for=s["gf"],
                        goals_against=s["ga"],
                        goal_diff=s["gf"] - s["ga"],
                        points=pts,
                    )
                )
            # Sort by points desc, then goal_diff desc, then gf desc
            standings.sort(key=lambda x: (-x.points, -x.goal_diff, -x.goals_for, x.team_name))
            group_responses.append(GroupResponse(name=group_name, teams=standings))

        return GroupsResponse(
            season_id=season_id,
            season_name=season.name,
            tournament_type=season.tournament_type,
            groups=group_responses,
        )

    # ------------------------------------------------------------------
    # Bracket
    # ------------------------------------------------------------------

    async def get_bracket(self, season_id: int) -> BracketResponse:
        """Build the knockout bracket from tournament_config + matches."""
        season = await self._get_tournament_season(season_id)
        config = season.tournament_config or {}
        knockout: dict[str, Any] = config.get("knockout", {}) if isinstance(config, dict) else {}
        rounds_cfg: list[dict[str, Any]] = knockout.get("rounds", [])

        if not rounds_cfg:
            return BracketResponse(
                season_id=season_id,
                season_name=season.name,
                rounds=[],
            )

        # Preload teams for name/logo lookup
        teams_stmt = select(Team).where(Team.season_id == season_id)
        teams_result = await self.session.execute(teams_stmt)
        teams_by_id = {t.id: t for t in teams_result.scalars().all()}

        bracket_rounds: list[BracketRound] = []
        for round_cfg in rounds_cfg:
            md_number = int(round_cfg.get("matchday", 0))
            round_name = str(round_cfg.get("name", f"Ronda J{md_number}"))

            matches_stmt = (
                select(Match)
                .join(Matchday, Match.matchday_id == Matchday.id)
                .where(
                    Matchday.season_id == season_id,
                    Matchday.number == md_number,
                )
                .order_by(Match.played_at.asc().nulls_last(), Match.id)
            )
            matches_result = await self.session.execute(matches_stmt)
            matches = list(matches_result.scalars().all())

            bm_list: list[BracketMatch] = []
            for m in matches:
                home = teams_by_id.get(m.home_team_id)
                away = teams_by_id.get(m.away_team_id)
                played = m.home_score is not None and m.away_score is not None
                bm_list.append(
                    BracketMatch(
                        match_id=m.id,
                        home_team_id=m.home_team_id,
                        home_team_name=home.name if home else None,
                        home_logo=home.logo_path if home else None,
                        home_score=m.home_score,
                        away_team_id=m.away_team_id,
                        away_team_name=away.name if away else None,
                        away_logo=away.logo_path if away else None,
                        away_score=m.away_score,
                        played=played,
                    )
                )
            bracket_rounds.append(
                BracketRound(name=round_name, matchday=md_number, matches=bm_list)
            )

        return BracketResponse(
            season_id=season_id,
            season_name=season.name,
            rounds=bracket_rounds,
        )

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    async def _decorate_prediction(
        self, pred: TournamentPrediction, include_user_name: bool = True
    ) -> PredictionResponse:
        """Build a PredictionResponse with denormalized names."""
        winner_name = None
        if pred.winner_team_id is not None:
            t = await self.session.get(Team, pred.winner_team_id)
            winner_name = t.name if t else None
        top_scorer_name = None
        if pred.top_scorer_player_id is not None:
            p = await self.session.get(Player, pred.top_scorer_player_id)
            top_scorer_name = p.display_name if p else None
        best_player_name = None
        if pred.best_player_id is not None:
            p = await self.session.get(Player, pred.best_player_id)
            best_player_name = p.display_name if p else None
        dark_horse_name = None
        if pred.dark_horse_team_id is not None:
            t = await self.session.get(Team, pred.dark_horse_team_id)
            dark_horse_name = t.name if t else None
        display_name = None
        if include_user_name:
            u = await self.session.get(User, pred.user_id)
            display_name = u.display_name if u else None

        return PredictionResponse(
            id=pred.id,
            season_id=pred.season_id,
            user_id=pred.user_id,
            display_name=display_name,
            winner_team_id=pred.winner_team_id,
            winner_team_name=winner_name,
            top_scorer_player_id=pred.top_scorer_player_id,
            top_scorer_player_name=top_scorer_name,
            best_player_id=pred.best_player_id,
            best_player_name=best_player_name,
            dark_horse_team_id=pred.dark_horse_team_id,
            dark_horse_team_name=dark_horse_name,
            notes=pred.notes,
            bonus_points=pred.bonus_points,
        )

    async def get_my_prediction(self, season_id: int, user_id: int) -> PredictionResponse | None:
        await self._get_tournament_season(season_id)
        stmt = select(TournamentPrediction).where(
            TournamentPrediction.season_id == season_id,
            TournamentPrediction.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        pred = result.scalar_one_or_none()
        if pred is None:
            return None
        return await self._decorate_prediction(pred, include_user_name=False)

    async def upsert_my_prediction(
        self, season_id: int, user_id: int, body: PredictionRequest
    ) -> PredictionResponse:
        await self._get_tournament_season(season_id)
        from datetime import UTC, datetime

        stmt = select(TournamentPrediction).where(
            TournamentPrediction.season_id == season_id,
            TournamentPrediction.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        pred = result.scalar_one_or_none()

        if pred is None:
            pred = TournamentPrediction(
                season_id=season_id,
                user_id=user_id,
                winner_team_id=body.winner_team_id,
                top_scorer_player_id=body.top_scorer_player_id,
                best_player_id=body.best_player_id,
                dark_horse_team_id=body.dark_horse_team_id,
                notes=body.notes,
            )
            self.session.add(pred)
        else:
            pred.winner_team_id = body.winner_team_id
            pred.top_scorer_player_id = body.top_scorer_player_id
            pred.best_player_id = body.best_player_id
            pred.dark_horse_team_id = body.dark_horse_team_id
            pred.notes = body.notes
            pred.updated_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(pred)
        return await self._decorate_prediction(pred, include_user_name=False)

    async def list_predictions(self, season_id: int) -> PredictionsListResponse:
        """Return all participants' predictions (visible after submission)."""
        season = await self._get_tournament_season(season_id)
        stmt = select(TournamentPrediction).where(TournamentPrediction.season_id == season_id)
        result = await self.session.execute(stmt)
        preds = list(result.scalars().all())

        decorated = [await self._decorate_prediction(p) for p in preds]
        decorated.sort(key=lambda p: (-p.bonus_points, (p.display_name or "").lower()))
        return PredictionsListResponse(
            season_id=season_id,
            season_name=season.name,
            predictions=decorated,
        )

    # ------------------------------------------------------------------
    # Helper endpoints for predictions UI
    # ------------------------------------------------------------------

    async def list_teams(self, season_id: int) -> list[TeamOption]:
        await self._get_tournament_season(season_id)
        stmt = (
            select(Team)
            .where(Team.season_id == season_id)
            .order_by(Team.tournament_group, Team.name)
        )
        result = await self.session.execute(stmt)
        return [
            TeamOption(
                id=t.id,
                name=t.name,
                short_name=t.short_name,
                logo_path=t.logo_path,
                tournament_group=t.tournament_group,
            )
            for t in result.scalars().all()
        ]

    async def list_players(self, season_id: int) -> list[PlayerOption]:
        await self._get_tournament_season(season_id)
        stmt = (
            select(
                Player.id,
                Player.display_name,
                Team.id.label("team_id"),
                Team.name.label("team_name"),
            )
            .join(Team, Player.team_id == Team.id)
            .where(Player.season_id == season_id)
            .order_by(Team.name, Player.display_name)
        )
        result = await self.session.execute(stmt)
        return [
            PlayerOption(
                id=row.id,
                name=row.display_name,
                team_id=row.team_id,
                team_name=row.team_name,
            )
            for row in result.all()
        ]
